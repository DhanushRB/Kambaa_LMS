from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import logging
from datetime import datetime

from database import get_db
from auth import get_current_user_info
from chat_models import Chat, Message, ChatParticipant
from chat_schemas import MessageCreate

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/chat/online-users")
async def get_online_users():
    """Get list of currently online users"""
    return {"online_users": list(manager.online_users)}

class ConnectionManager:
    def __init__(self):
        # Store active connections: {user_id: [websocket1, websocket2, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Store user chat rooms: {user_id: [chat_id1, chat_id2, ...]}
        self.user_chats: Dict[int, List[int]] = {}
        # Store online users
        self.online_users: set = set()

    async def connect(self, websocket: WebSocket, user_id: int, db: Session):
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # Mark user as online
        was_offline = user_id not in self.online_users
        self.online_users.add(user_id)
        
        # Load user's chat rooms based on their role and permissions
        try:
            # Get user info to determine role
            from database import Admin, Presenter, Mentor, User, Manager
            user_role = None
            
            if db.query(Admin).filter(Admin.id == user_id).first():
                user_role = "Admin"
            elif db.query(Presenter).filter(Presenter.id == user_id).first():
                user_role = "Presenter"
            elif db.query(Mentor).filter(Mentor.id == user_id).first():
                user_role = "Mentor"
            elif db.query(Manager).filter(Manager.id == user_id).first():
                user_role = "Manager"
            elif db.query(User).filter(User.id == user_id).first():
                user_role = "Student"
            
            # Load user's accessible chats
            user_chats = db.query(ChatParticipant).filter(
                ChatParticipant.user_id == user_id,
                ChatParticipant.user_type == user_role,
                ChatParticipant.is_active == True
            ).all()
            
            self.user_chats[user_id] = [cp.chat_id for cp in user_chats]
            
            logger.info(f"User {user_id} ({user_role}) connected to WebSocket with {len(self.user_chats[user_id])} chats")
            
            # Notify others that user came online (if they were offline)
            if was_offline:
                await self.broadcast_user_status(user_id, True)
                
        except Exception as e:
            logger.error(f"Error loading user chats for {user_id}: {str(e)}")
            self.user_chats[user_id] = []

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # If no more connections for this user, mark as offline
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.user_chats:
                    del self.user_chats[user_id]
                
                # Mark user as offline and notify others
                if user_id in self.online_users:
                    self.online_users.remove(user_id)
                    # Note: We can't await here since this is not async
                    # The offline notification will be handled by the websocket endpoint
        
        logger.info(f"User {user_id} disconnected from WebSocket")

    async def broadcast_user_status(self, user_id: int, is_online: bool):
        """Broadcast user online/offline status to all connected users"""
        status_message = {
            "type": "user_online" if is_online else "user_offline",
            "user_id": user_id
        }
        
        # Send to all connected users
        for connected_user_id in list(self.active_connections.keys()):
            if connected_user_id != user_id:
                await self.send_personal_message(status_message, connected_user_id)

    async def send_online_users_list(self, user_id: int):
        """Send current online users list to a specific user"""
        online_message = {
            "type": "online_users",
            "users": list(self.online_users)
        }
        await self.send_personal_message(online_message, user_id)

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            disconnected_sockets = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected_sockets.append(websocket)
            
            # Clean up disconnected sockets
            for socket in disconnected_sockets:
                self.active_connections[user_id].remove(socket)

    async def broadcast_to_chat(self, message: dict, chat_id: int, exclude_user_id: int = None):
        # Get all participants of the chat
        participants = []
        for user_id, chat_ids in self.user_chats.items():
            if chat_id in chat_ids and user_id != exclude_user_id:
                participants.append(user_id)
        
        # Send message to all participants
        for user_id in participants:
            await self.send_personal_message(message, user_id)
    
    async def notify_new_message_to_user(self, user_id: int, chat_id: int, message_data: dict):
        """Notify specific user about new message in a chat"""
        notification = {
            "type": "new_message_notification",
            "chat_id": chat_id,
            "message": message_data
        }
        await self.send_personal_message(notification, user_id)

manager = ConnectionManager()

async def get_current_user_websocket(websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)):
    try:
        from auth import verify_token
        token_data = verify_token(token)
        username = token_data.get("sub")
        role = token_data.get("role")
        user_id = token_data.get("user_id")
        
        if role == "Admin":
            from database import Admin
            user = db.query(Admin).filter(Admin.username == username).first()
        elif role == "Presenter":
            from database import Presenter
            user = db.query(Presenter).filter(Presenter.username == username).first()
        elif role == "Mentor":
            from database import Mentor
            user = db.query(Mentor).filter(Mentor.username == username).first()
        elif role == "Manager":
            from database import Manager
            user = db.query(Manager).filter(Manager.username == username).first()
        elif role == "Student":
            from database import User
            user = db.query(User).filter(User.username == username).first()
        else:
            await websocket.close(code=4001, reason="Invalid user role")
            return None
        
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return None
            
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": role
        }
    except Exception as e:
        logger.error(f"WebSocket auth error: {str(e)}")
        await websocket.close(code=4001, reason="Authentication failed")
        return None

@router.websocket("/ws/chat/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    # Authenticate user first
    current_user = await get_current_user_websocket(websocket, token, db)
    if not current_user or current_user["id"] != user_id:
        return

    await manager.connect(websocket, user_id, db)
    
    # Send current online users list to the newly connected user
    await manager.send_online_users_list(user_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            await handle_websocket_message(message_data, user_id, db)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        # Notify others that user went offline
        if user_id not in manager.active_connections:
            await manager.broadcast_user_status(user_id, False)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        manager.disconnect(websocket, user_id)
        # Notify others that user went offline
        if user_id not in manager.active_connections:
            await manager.broadcast_user_status(user_id, False)

async def handle_websocket_message(message_data: dict, user_id: int, db: Session):
    message_type = message_data.get("type")
    
    if message_type == "send_message":
        await handle_send_message(message_data, user_id, db)
    elif message_type == "mark_read":
        await handle_mark_as_read(message_data, user_id, db)
    elif message_type == "typing_start":
        await handle_typing(message_data, user_id, True)
    elif message_type == "typing_stop":
        await handle_typing(message_data, user_id, False)
    elif message_type == "join_chat":
        await handle_join_chat(message_data, user_id, db)
    elif message_type == "leave_chat":
        await handle_leave_chat(message_data, user_id, db)

async def handle_send_message(message_data: dict, user_id: int, db: Session):
    try:
        chat_id = message_data.get("chat_id")
        content = message_data.get("content")
        message_type = message_data.get("message_type", "TEXT")
        
        # Get user info to determine sender type
        from chat_endpoints import get_current_user_info_chat
        from database import Admin, Presenter, Mentor, User, Manager
        
        # Determine user type
        sender_type = None
        if db.query(Admin).filter(Admin.id == user_id).first():
            sender_type = "Admin"
        elif db.query(Presenter).filter(Presenter.id == user_id).first():
            sender_type = "Presenter"
        elif db.query(Mentor).filter(Mentor.id == user_id).first():
            sender_type = "Mentor"
        elif db.query(Manager).filter(Manager.id == user_id).first():
            sender_type = "Manager"
        elif db.query(User).filter(User.id == user_id).first():
            sender_type = "Student"
        
        if not sender_type:
            return
        
        # Verify user is participant in chat
        participant = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
            ChatParticipant.user_type == sender_type
        ).first()
        
        if not participant:
            return
        
        # Create message
        from chat_models import MessageType
        message = Message(
            chat_id=chat_id,
            sender_id=user_id,
            sender_type=sender_type,
            message_type=MessageType.TEXT if message_type == "TEXT" else MessageType.FILE,
            content=content,
            created_at=datetime.utcnow()
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Update chat's last message
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            chat.updated_at = datetime.utcnow()
            db.commit()
        
        # Get sender name
        sender_name = "Unknown User"
        if sender_type == "Admin":
            sender = db.query(Admin).filter(Admin.id == user_id).first()
        elif sender_type == "Presenter":
            sender = db.query(Presenter).filter(Presenter.id == user_id).first()
        elif sender_type == "Mentor":
            sender = db.query(Mentor).filter(Mentor.id == user_id).first()
        elif sender_type == "Manager":
            sender = db.query(Manager).filter(Manager.id == user_id).first()
        elif sender_type == "Student":
            sender = db.query(User).filter(User.id == user_id).first()
        
        if sender:
            sender_name = sender.username
        
        # Find cohort_id for navigation
        cohort_id = None
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            if chat.chat_type == ChatType.GROUP:
                from database import Cohort
                all_cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
                for c in all_cohorts:
                    if c.name in chat.name:
                        cohort_id = c.id
                        break
            
            if not cohort_id:
                from database import UserCohort
                student_p = db.query(ChatParticipant).filter(
                    ChatParticipant.chat_id == chat.id,
                    ChatParticipant.user_type == "Student"
                ).first()
                if student_p:
                    uc = db.query(UserCohort).filter(UserCohort.user_id == student_p.user_id).first()
                    if uc:
                        cohort_id = uc.cohort_id

        # Broadcast to all chat participants
        broadcast_message = {
            "type": "message",
            "chat_id": chat_id,
            "cohort_id": cohort_id,
            "chat_type": chat.chat_type.value if chat else "SINGLE",
            "message": {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": sender_name,
                "sender_type": message.sender_type,
                "created_at": message.created_at.isoformat()
            }
        }
        
        await manager.broadcast_to_chat(broadcast_message, chat_id)
        
        logger.info(f"Message {message.id} sent to chat {chat_id} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling send_message: {str(e)}")

async def handle_mark_as_read(message_data: dict, user_id: int, db: Session):
    try:
        chat_id = message_data.get("chat_id")
        
        # Determine user type
        from database import Admin, Presenter, Mentor, User, Manager
        sender_type = None
        if db.query(Admin).filter(Admin.id == user_id).first():
            sender_type = "Admin"
        elif db.query(Presenter).filter(Presenter.id == user_id).first():
            sender_type = "Presenter"
        elif db.query(Mentor).filter(Mentor.id == user_id).first():
            sender_type = "Mentor"
        elif db.query(Manager).filter(Manager.id == user_id).first():
            sender_type = "Manager"
        elif db.query(User).filter(User.id == user_id).first():
            sender_type = "Student"
        
        if not sender_type:
            return
        
        # Update read status for user
        participant = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
            ChatParticipant.user_type == sender_type
        ).first()
        
        if participant:
            participant.last_read_at = datetime.utcnow()
            db.commit()
            
            # Notify other participants
            read_message = {
                "type": "message_read",
                "chat_id": chat_id,
                "user_id": user_id,
                "read_at": participant.last_read_at.isoformat()
            }
            
            await manager.broadcast_to_chat(read_message, chat_id, exclude_user_id=user_id)
            
    except Exception as e:
        logger.error(f"Error handling mark_as_read: {str(e)}")

async def handle_typing(message_data: dict, user_id: int, is_typing: bool):
    try:
        chat_id = message_data.get("chat_id")
        
        typing_message = {
            "type": "typing_start" if is_typing else "typing_stop",
            "chat_id": chat_id,
            "user_id": user_id
        }
        
        await manager.broadcast_to_chat(typing_message, chat_id, exclude_user_id=user_id)
        
    except Exception as e:
        logger.error(f"Error handling typing: {str(e)}")

async def handle_join_chat(message_data: dict, user_id: int, db: Session):
    """Handle user joining a chat room"""
    try:
        chat_id = message_data.get("chat_id")
        
        # Add chat to user's chat list if not already there
        if user_id in manager.user_chats:
            if chat_id not in manager.user_chats[user_id]:
                manager.user_chats[user_id].append(chat_id)
        else:
            manager.user_chats[user_id] = [chat_id]
            
        logger.info(f"User {user_id} joined chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error handling join_chat: {str(e)}")

async def handle_leave_chat(message_data: dict, user_id: int, db: Session):
    """Handle user leaving a chat room"""
    try:
        chat_id = message_data.get("chat_id")
        
        # Remove chat from user's chat list
        if user_id in manager.user_chats and chat_id in manager.user_chats[user_id]:
            manager.user_chats[user_id].remove(chat_id)
            
        logger.info(f"User {user_id} left chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error handling leave_chat: {str(e)}")

# Function to send notifications for new messages (can be called from other parts of the app)
async def notify_new_message(message: Message, db: Session):
    broadcast_message = {
        "type": "new_message",
        "message": {
            "id": message.id,
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat(),
            "is_own": False
        }
    }
    
    await manager.broadcast_to_chat(broadcast_message, message.chat_id, exclude_user_id=message.sender_id)