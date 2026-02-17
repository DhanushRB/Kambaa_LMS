from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import asyncio
import logging
from datetime import datetime
from database import get_db, Notification, NotificationPreference, User, Admin, Presenter, Mentor, Manager
from auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()

class NotificationManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.user_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        
        self.user_connections[user_id].append(websocket)
        self.active_connections[id(websocket)] = websocket
        
        logger.info(f"User {user_id} connected to notifications WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if id(websocket) in self.active_connections:
            del self.active_connections[id(websocket)]
        
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"User {user_id} disconnected from notifications WebSocket")

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.user_connections:
            disconnected_connections = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected_connections.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected_connections:
                self.disconnect(conn, user_id)

    async def broadcast_message(self, message: dict):
        disconnected_connections = []
        for connection in self.active_connections.values():
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected_connections:
            if id(conn) in self.active_connections:
                del self.active_connections[id(conn)]

notification_manager = NotificationManager()

async def get_current_user_from_token(token: str, db: Session):
    """Get current user from WebSocket token"""
    try:
        payload = verify_token(token)
        username = payload.get("sub")
        role = payload.get("role")
        user_id = payload.get("user_id")
        
        if not username or not role or not user_id:
            return None
        
        # Check different user tables based on role
        if role == "Student":
            user = db.query(User).filter(User.username == username, User.id == user_id).first()
        elif role == "Admin":
            user = db.query(Admin).filter(Admin.username == username, Admin.id == user_id).first()
        elif role == "Presenter":
            user = db.query(Presenter).filter(Presenter.username == username, Presenter.id == user_id).first()
        elif role == "Mentor":
            user = db.query(Mentor).filter(Mentor.username == username, Mentor.id == user_id).first()
        elif role == "Manager":
            user = db.query(Manager).filter(Manager.username == username, Manager.id == user_id).first()
        else:
            return None
        
        return user
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        return None

@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time notifications"""
    user = await get_current_user_from_token(token, db)
    
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication")
        return
    
    user_id = user.id
    
    try:
        await notification_manager.connect(websocket, user_id)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "Connected to notification service",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }))
        
        # Send any pending notifications
        await send_pending_notifications(user_id, db)
        
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                message_type = message.get("type")
                
                if message_type == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                
                elif message_type == "mark_read":
                    notification_id = message.get("notificationId")
                    if notification_id:
                        await mark_notification_as_read(notification_id, user_id, db)
                
                elif message_type == "get_history":
                    limit = message.get("limit", 50)
                    history = await get_notification_history(user_id, limit, db)
                    await websocket.send_text(json.dumps({
                        "type": "notification_history",
                        "notifications": history,
                        "timestamp": datetime.now().isoformat()
                    }))
                
                elif message_type == "send_notification" and hasattr(user, 'username'):
                    # Only allow admins/presenters to send notifications
                    admin_check = db.query(Admin).filter(Admin.id == user_id).first()
                    presenter_check = db.query(Presenter).filter(Presenter.id == user_id).first()
                    
                    if admin_check or presenter_check:
                        notification_data = message.get("data", {})
                        await create_and_send_notification(notification_data, user_id, db)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"WebSocket message handling error: {str(e)}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Message processing failed",
                    "timestamp": datetime.now().isoformat()
                }))
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        notification_manager.disconnect(websocket, user_id)

async def send_pending_notifications(user_id: int, db: Session):
    """Send any unread notifications to the user"""
    try:
        notifications = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        for notification in notifications:
            await notification_manager.send_personal_message({
                "type": "notification",
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "notification_type": notification.notification_type,
                "priority": getattr(notification, 'priority', 'medium'),
                "timestamp": notification.created_at.isoformat(),
                "read": notification.is_read
            }, user_id)
    
    except Exception as e:
        logger.error(f"Error sending pending notifications: {str(e)}")

async def mark_notification_as_read(notification_id: int, user_id: int, db: Session):
    """Mark a notification as read"""
    try:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            db.commit()
            
            await notification_manager.send_personal_message({
                "type": "notification_marked_read",
                "notification_id": notification_id,
                "timestamp": datetime.now().isoformat()
            }, user_id)
    
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")

async def get_notification_history(user_id: int, limit: int, db: Session):
    """Get notification history for a user"""
    try:
        notifications = db.query(Notification).filter(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc()).limit(limit).all()
        
        return [{
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "notification_type": n.notification_type,
            "priority": getattr(n, 'priority', 'medium'),
            "timestamp": n.created_at.isoformat(),
            "read": n.is_read
        } for n in notifications]
    
    except Exception as e:
        logger.error(f"Error getting notification history: {str(e)}")
        return []

async def create_and_send_notification(notification_data: dict, sender_id: int, db: Session):
    """Create and send a new notification"""
    try:
        # Create notification in database
        notification = Notification(
            user_id=notification_data.get("user_id"),
            title=notification_data.get("title", "New Notification"),
            message=notification_data.get("message", ""),
            notification_type=notification_data.get("type", "INFO"),
            is_global=notification_data.get("is_global", False)
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Send to specific user or broadcast
        message = {
            "type": "notification",
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type,
            "priority": notification_data.get("priority", "medium"),
            "timestamp": notification.created_at.isoformat(),
            "read": False
        }
        
        if notification.is_global:
            await notification_manager.broadcast_message(message)
        elif notification.user_id:
            await notification_manager.send_personal_message(message, notification.user_id)
    
    except Exception as e:
        logger.error(f"Error creating and sending notification: {str(e)}")

# Function to send notification from other parts of the application
async def send_notification_to_user(user_id: int, title: str, message: str, notification_type: str = "INFO", priority: str = "medium"):
    """Send a notification to a specific user (can be called from other modules)"""
    try:
        await notification_manager.send_personal_message({
            "type": "notification",
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }, user_id)
    except Exception as e:
        logger.error(f"Error sending notification to user {user_id}: {str(e)}")

# Function to broadcast notification to all connected users
async def broadcast_notification(title: str, message: str, notification_type: str = "INFO", priority: str = "medium"):
    """Broadcast a notification to all connected users"""
    try:
        await notification_manager.broadcast_message({
            "type": "notification",
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "read": False
        })
    except Exception as e:
        logger.error(f"Error broadcasting notification: {str(e)}")