from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional
from datetime import datetime
import os
import uuid
from pathlib import Path

from database import get_db, User, Admin, Presenter, Mentor, Manager
from auth import verify_token
from chat_models import Chat, ChatParticipant, Message, ChatType, MessageType
from chat_schemas import (
    ChatCreate, ChatResponse, MessageCreate, MessageResponse, 
    ChatSearchRequest, UserSearchRequest, UserSearchResponse,
    GroupChatUpdate, MarkReadRequest, ChatParticipantResponse
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Create upload directory for chat files
CHAT_UPLOAD_DIR = Path("uploads/chat")
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def get_current_user_info_chat(token_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    """Get current user info from any user type"""
    username = token_data.get("sub")
    role = token_data.get("role")
    user_id = token_data.get("user_id")
    
    if role == "Admin":
        user = db.query(Admin).filter(Admin.username == username).first()
    elif role == "Presenter":
        user = db.query(Presenter).filter(Presenter.username == username).first()
    elif role == "Mentor":
        user = db.query(Mentor).filter(Mentor.username == username).first()
    elif role == "Manager":
        user = db.query(Manager).filter(Manager.username == username).first()
    elif role == "Student":
        user = db.query(User).filter(User.username == username).first()
    else:
        raise HTTPException(status_code=401, detail="Invalid user role")
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": role
    }

def get_user_by_id_and_type(user_id: int, user_type: str, db: Session):
    """Get user by ID and type"""
    if user_type == "Admin":
        return db.query(Admin).filter(Admin.id == user_id).first()
    elif user_type == "Presenter":
        return db.query(Presenter).filter(Presenter.id == user_id).first()
    elif user_type == "Mentor":
        return db.query(Mentor).filter(Mentor.id == user_id).first()
    elif user_type == "Manager":
        return db.query(Manager).filter(Manager.id == user_id).first()
    elif user_type == "Student":
        return db.query(User).filter(User.id == user_id).first()
    return None

def can_access_chat(user_info: dict, chat: Chat, db: Session) -> bool:
    """Check if user can access a specific chat"""
    # Check if user is a participant
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat.id,
        ChatParticipant.user_id == user_info["id"],
        ChatParticipant.user_type == user_info["role"],
        ChatParticipant.is_active == True
    ).first()
    
    return participant is not None

@router.post("/find-or-create-private")
async def find_or_create_private_chat(
    request: dict,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Find existing private chat or create new one - ensures consistent chat IDs"""
    try:
        participant_id = request.get("participant_id")
        if not participant_id:
            raise HTTPException(status_code=400, detail="participant_id is required")
        
        current_user_id = current_user["id"]
        
        # Ensure we're working with integers
        current_user_id = int(current_user_id)
        participant_id = int(participant_id)
        
        print(f"Finding/creating private chat between {current_user_id} and {participant_id}")
        
        # Find existing single chat between these two users
        # Use a deterministic approach by checking both directions
        existing_chat = db.query(Chat).filter(
            Chat.chat_type == ChatType.SINGLE,
            Chat.is_active == True
        ).join(ChatParticipant, Chat.id == ChatParticipant.chat_id).filter(
            ChatParticipant.is_active == True
        ).filter(
            Chat.id.in_(
                # Subquery to find chats where current user is participant
                db.query(ChatParticipant.chat_id).filter(
                    ChatParticipant.user_id == current_user_id,
                    ChatParticipant.user_type == current_user["role"],
                    ChatParticipant.is_active == True
                )
            )
        ).filter(
            Chat.id.in_(
                # Subquery to find chats where target user is participant
                db.query(ChatParticipant.chat_id).filter(
                    ChatParticipant.user_id == participant_id,
                    ChatParticipant.is_active == True
                )
            )
        ).first()
        
        if existing_chat:
            # Verify it's exactly 2 participants
            participant_count = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == existing_chat.id,
                ChatParticipant.is_active == True
            ).count()
            
            if participant_count == 2:
                print(f"Found existing private chat: {existing_chat.id}")
                chat_response = await get_chat_response(existing_chat.id, current_user, db)
                chat_response_dict = chat_response.__dict__.copy()
                chat_response_dict["isNew"] = False
                return chat_response_dict
        
        # Get target user info to determine their type
        target_user = None
        target_user_type = None
        
        # Try to find user in different tables
        for user_type, model in [("Student", User), ("Admin", Admin), ("Presenter", Presenter), ("Mentor", Mentor), ("Manager", Manager)]:
            user = db.query(model).filter(model.id == participant_id).first()
            if user:
                target_user = user
                target_user_type = user_type
                break
        
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        
        print(f"Creating new private chat between {current_user_id} ({current_user['role']}) and {participant_id} ({target_user_type})")
        
        # Create new chat
        chat = Chat(
            name=None,
            chat_type=ChatType.SINGLE,
            created_by=current_user_id if current_user["role"] == "Admin" else None
        )
        db.add(chat)
        db.flush()
        
        # Add both participants
        participants = [
            ChatParticipant(
                chat_id=chat.id,
                user_id=current_user_id,
                user_type=current_user["role"]
            ),
            ChatParticipant(
                chat_id=chat.id,
                user_id=participant_id,
                user_type=target_user_type
            )
        ]
        
        for participant in participants:
            db.add(participant)
        
        db.commit()
        db.refresh(chat)
        
        print(f"Created new private chat: {chat.id}")
        
        # Return chat response
        chat_response = await get_chat_response(chat.id, current_user, db)
        chat_response_dict = chat_response.__dict__.copy()
        chat_response_dict["isNew"] = True
        return chat_response_dict
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in find_or_create_private_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to find or create private chat: {str(e)}")

@router.post("/create")
async def create_chat(
    chat_data: ChatCreate,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Create a new chat (single or group)"""
    try:
        # For single chat, validate participants
        if chat_data.chat_type == ChatType.SINGLE:
            if len(chat_data.participant_ids) != len(chat_data.participant_types):
                raise HTTPException(status_code=400, detail="Participant IDs and types must match")
            
            if len(chat_data.participant_ids) != 1:
                raise HTTPException(status_code=400, detail="Single chat must have exactly 1 other participant")
            
            # Check if single chat already exists
            other_user_id = chat_data.participant_ids[0]
            other_user_type = chat_data.participant_types[0]
            
            existing_chat = db.query(Chat).join(ChatParticipant).filter(
                Chat.chat_type == ChatType.SINGLE,
                Chat.is_active == True
            ).filter(
                Chat.id.in_(
                    db.query(ChatParticipant.chat_id).filter(
                        ChatParticipant.user_id == current_user["id"],
                        ChatParticipant.user_type == current_user["role"],
                        ChatParticipant.is_active == True
                    )
                )
            ).filter(
                Chat.id.in_(
                    db.query(ChatParticipant.chat_id).filter(
                        ChatParticipant.user_id == other_user_id,
                        ChatParticipant.user_type == other_user_type,
                        ChatParticipant.is_active == True
                    )
                )
            ).first()
            
            if existing_chat:
                return await get_chat_response(existing_chat.id, current_user, db)
        
        # For group chats, check if cohort group chat already exists
        elif chat_data.chat_type == ChatType.GROUP and chat_data.name and "Group Chat" in chat_data.name:
            # Extract cohort name from chat name
            cohort_name = chat_data.name.replace(" Group Chat", "")
            existing_group_chat = db.query(Chat).filter(
                Chat.chat_type == ChatType.GROUP,
                Chat.name.like(f"%{cohort_name}%Group Chat%"),
                Chat.is_active == True
            ).first()
            
            if existing_group_chat:
                # Check if current user is already a participant
                existing_participant = db.query(ChatParticipant).filter(
                    ChatParticipant.chat_id == existing_group_chat.id,
                    ChatParticipant.user_id == current_user["id"],
                    ChatParticipant.user_type == current_user["role"],
                    ChatParticipant.is_active == True
                ).first()
                
                if not existing_participant:
                    # Add current user as participant
                    new_participant = ChatParticipant(
                        chat_id=existing_group_chat.id,
                        user_id=current_user["id"],
                        user_type=current_user["role"]
                    )
                    db.add(new_participant)
                    db.commit()
                
                return await get_chat_response(existing_group_chat.id, current_user, db)
        
        # Create new chat
        chat = Chat(
            name=chat_data.name,
            chat_type=chat_data.chat_type,
            created_by=current_user["id"] if current_user["role"] == "Admin" else None
        )
        db.add(chat)
        db.flush()
        
        # Add current user as participant
        current_participant = ChatParticipant(
            chat_id=chat.id,
            user_id=current_user["id"],
            user_type=current_user["role"]
        )
        db.add(current_participant)
        
        # Add other participants (if any)
        if chat_data.participant_ids and chat_data.participant_types:
            for user_id, user_type in zip(chat_data.participant_ids, chat_data.participant_types):
                # Verify user exists
                user = get_user_by_id_and_type(user_id, user_type, db)
                if not user:
                    raise HTTPException(status_code=404, detail=f"User {user_id} of type {user_type} not found")
                
                participant = ChatParticipant(
                    chat_id=chat.id,
                    user_id=user_id,
                    user_type=user_type
                )
                db.add(participant)
        
        db.commit()
        db.refresh(chat)
        
        # Return chat response
        return await get_chat_response(chat.id, current_user, db)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create chat: {str(e)}")

@router.get("/list")
async def get_user_chats(
    search: Optional[str] = None,
    chat_type: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get user's chats with search and filtering"""
    try:
        # Base query for user's chats
        query = db.query(Chat).join(ChatParticipant).filter(
            ChatParticipant.user_id == current_user["id"],
            ChatParticipant.user_type == current_user["role"],
            ChatParticipant.is_active == True,
            Chat.is_active == True
        )
        
        # Apply filters
        if chat_type:
            query = query.filter(Chat.chat_type == chat_type)
        
        if search:
            query = query.filter(
                or_(
                    Chat.name.contains(search),
                    Chat.id.in_(
                        db.query(Message.chat_id).filter(
                            Message.content.contains(search)
                        )
                    )
                )
            )
        
        # Get all chats first
        chats = query.all()
        
        # Sort chats by updated_at (most recent first) to show new messages at top
        chats.sort(key=lambda chat: chat.updated_at, reverse=True)
        
        # Apply pagination after sorting
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_chats = chats[start_idx:end_idx]
        
        # Build response
        chat_responses = []
        for chat in paginated_chats:
            chat_response = await get_chat_response(chat.id, current_user, db)
            chat_responses.append(chat_response)
        
        return chat_responses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chats: {str(e)}")

@router.get("/unread-notifications")
async def get_unread_notifications(
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get all unread messages for the current user across all chats"""
    try:
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Find all active chat participants for the user
        participants = db.query(ChatParticipant).filter(
            ChatParticipant.user_id == user_id,
            ChatParticipant.user_type == user_role,
            ChatParticipant.is_active == True
        ).all()
        
        unread_notifications = []
        total_unread_count = 0
        
        for p in participants:
            # Get chat info to check type
            chat = db.query(Chat).filter(Chat.id == p.chat_id).first()
            if not chat or not chat.is_active:
                continue
            
            # Count both SINGLE and GROUP unread messages
            if chat.chat_type not in [ChatType.SINGLE, ChatType.GROUP]:
                continue

            # For each chat, find unread messages
            unread_query = db.query(Message).filter(
                Message.chat_id == p.chat_id,
                Message.sender_id != user_id  # Don't count own messages
            )
            
            if p.last_read_at:
                unread_query = unread_query.filter(Message.created_at > p.last_read_at)
            
            unread_messages = unread_query.order_by(desc(Message.created_at)).all()
            
            if unread_messages:
                # Add unread messages to notifications list
                for msg in unread_messages:
                    sender = get_user_by_id_and_type(msg.sender_id, msg.sender_type, db)
                    sender_name = sender.username if sender else "Unknown"
                    
                    # Determine chat name
                    chat = db.query(Chat).filter(Chat.id == p.chat_id).first()
                    chat_name = chat.name
                    if chat.chat_type == ChatType.SINGLE and not chat_name:
                        # Find the other participant's name
                        other_p = db.query(ChatParticipant).filter(
                            ChatParticipant.chat_id == p.chat_id,
                            ChatParticipant.user_id != user_id
                        ).first()
                        if other_p:
                            other_user = get_user_by_id_and_type(other_p.user_id, other_p.user_type, db)
                            chat_name = other_user.username if other_user else "Private Chat"
                        else:
                            chat_name = "Private Chat"
                    
                    # Find cohort_id for navigation
                    cohort_id = None
                    if chat.chat_type == ChatType.GROUP:
                        # Try to find cohort by name match
                        from database import Cohort
                        all_cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
                        for c in all_cohorts:
                            if c.name in chat.name:
                                cohort_id = c.id
                                break
                    
                    if not cohort_id:
                        # Fallback: Find a student participant and their cohort
                        from database import UserCohort
                        student_participant = db.query(ChatParticipant).filter(
                            ChatParticipant.chat_id == chat.id,
                            ChatParticipant.user_type == "Student"
                        ).first()
                        if student_participant:
                            uc = db.query(UserCohort).filter(UserCohort.user_id == student_participant.user_id).first()
                            if uc:
                                cohort_id = uc.cohort_id
                    
                    # If user is a student and we still don't have a cohort_id, use their own
                    if not cohort_id and user_role == "Student":
                        from database import User
                        u = db.query(User).filter(User.id == user_id).first()
                        if u and u.cohort_id:
                            cohort_id = u.cohort_id
                        else:
                            from database import UserCohort
                            uc = db.query(UserCohort).filter(UserCohort.user_id == user_id).first()
                            if uc:
                                cohort_id = uc.cohort_id

                    unread_notifications.append({
                        "id": msg.id,
                        "chat_id": msg.chat_id,
                        "cohort_id": cohort_id,
                        "chat_name": chat_name,
                        "sender_id": msg.sender_id,
                        "sender_name": sender_name,
                        "content": msg.content[:100],
                        "created_at": msg.created_at.isoformat(),
                        "chat_type": chat.chat_type.value
                    })
                    total_unread_count += 1
        
        # Sort notifications by time
        unread_notifications.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "notifications": unread_notifications[:20],  # Return latest 20 unread
            "total_count": total_unread_count
        }
        
    except Exception as e:
        print(f"Error getting unread notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_chat_response(chat_id: int, current_user: dict, db: Session) -> ChatResponse:
    """Build chat response with participants and unread count"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Get participants
    participants_data = []
    participants = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.is_active == True
    ).all()
    
    for participant in participants:
        user = get_user_by_id_and_type(participant.user_id, participant.user_type, db)
        if user:
            participants_data.append(ChatParticipantResponse(
                id=participant.id,
                user_id=participant.user_id,
                user_type=participant.user_type,
                username=user.username,
                email=user.email,
                joined_at=participant.joined_at,
                last_read_at=participant.last_read_at,
                is_active=participant.is_active
            ))
    
    # Get unread count
    current_participant = db.query(ChatParticipant).filter(
        ChatParticipant.chat_id == chat_id,
        ChatParticipant.user_id == current_user["id"],
        ChatParticipant.user_type == current_user["role"]
    ).first()
    
    unread_count = 0
    if current_participant:
        unread_query = db.query(Message).filter(Message.chat_id == chat_id)
        if current_participant.last_read_at:
            unread_query = unread_query.filter(Message.created_at > current_participant.last_read_at)
        unread_count = unread_query.count()
    
    # Get last message
    last_message = db.query(Message).filter(Message.chat_id == chat_id).order_by(desc(Message.created_at)).first()
    
    # Generate chat name for single chats
    display_name = chat.name
    if chat.chat_type == ChatType.SINGLE and not display_name:
        other_participant = next((p for p in participants_data if p.user_id != current_user["id"]), None)
        if other_participant:
            display_name = other_participant.username
    
    return ChatResponse(
        id=chat.id,
        name=display_name,
        chat_type=chat.chat_type.value,
        created_by=chat.created_by,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        is_active=chat.is_active,
        participants=participants_data,
        unread_count=unread_count,
        last_message=last_message.content[:100] if last_message else None,
        last_message_time=last_message.created_at if last_message else None
    )

@router.get("/{chat_id}/messages")
async def get_chat_messages(
    chat_id: int,
    page: int = 1,
    limit: int = 50,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get messages for a specific chat"""
    try:
        # Check access
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages
        messages = db.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.asc()).offset((page - 1) * limit).limit(limit).all()
        
        # Build response
        message_responses = []
        for message in messages:
            sender = get_user_by_id_and_type(message.sender_id, message.sender_type, db)
            sender_name = sender.username if sender else "Unknown User"
            
            message_responses.append(MessageResponse(
                id=message.id,
                chat_id=message.chat_id,
                sender_id=message.sender_id,
                sender_type=message.sender_type,
                sender_name=sender_name,
                message_type=message.message_type.value,
                content=message.content,
                file_path=message.file_path,
                file_name=message.file_name,
                file_size=message.file_size,
                created_at=message.created_at,
                is_edited=message.is_edited,
                edited_at=message.edited_at
            ))
        
        print(f"Retrieved {len(message_responses)} messages for chat {chat_id}")
        return message_responses
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")

@router.post("/send-message")
async def send_message(
    message_data: MessageCreate,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Send a message to a chat"""
    try:
        # Check access
        chat = db.query(Chat).filter(Chat.id == message_data.chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Create message
        message = Message(
            chat_id=message_data.chat_id,
            sender_id=current_user["id"],
            sender_type=current_user["role"],
            message_type=message_data.message_type,
            content=message_data.content,
            file_name=message_data.file_name
        )
        db.add(message)
        
        # Update chat timestamp
        chat.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        # Log the message save
        print(f"Message saved to database: ID={message.id}, Chat={message.chat_id}, Sender={current_user['username']}, Content={message.content[:50]}...")
        
        return MessageResponse(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            sender_type=message.sender_type,
            sender_name=current_user["username"],
            message_type=message.message_type.value,
            content=message.content,
            file_path=message.file_path,
            file_name=message.file_name,
            file_size=message.file_size,
            created_at=message.created_at,
            is_edited=message.is_edited,
            edited_at=message.edited_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error saving message to database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@router.post("/upload-file")
async def upload_chat_file(
    file: UploadFile = File(...),
    chat_id: int = Form(...),
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Upload a file to chat"""
    try:
        # Check access
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Save file
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = CHAT_UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create message
        message = Message(
            chat_id=chat_id,
            sender_id=current_user["id"],
            sender_type=current_user["role"],
            message_type=MessageType.FILE,
            content=f"Shared a file: {file.filename}",
            file_path=str(file_path),
            file_name=file.filename,
            file_size=len(content)
        )
        db.add(message)
        
        # Update chat timestamp
        chat.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        return {
            "message": "File uploaded successfully",
            "message_id": message.id,
            "file_name": file.filename,
            "file_size": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@router.get("/download-file/{message_id}")
async def download_chat_file(
    message_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Download a chat file"""
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check access
        chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not message.file_path or not os.path.exists(message.file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            message.file_path,
            filename=message.file_name,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@router.post("/mark-read")
async def mark_chat_as_read(
    request: MarkReadRequest,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Mark chat as read for current user"""
    try:
        participant = db.query(ChatParticipant).filter(
            ChatParticipant.chat_id == request.chat_id,
            ChatParticipant.user_id == current_user["id"],
            ChatParticipant.user_type == current_user["role"]
        ).first()
        
        if not participant:
            raise HTTPException(status_code=404, detail="Chat participant not found")
        
        participant.last_read_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Chat marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark chat as read: {str(e)}")

@router.get("/search-users")
async def search_users(
    search: Optional[str] = None,
    user_type: Optional[str] = None,
    exclude_chat_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Search users for creating chats"""
    try:
        users = []
        
        # Search in different user tables based on user_type filter
        if not user_type or user_type == "Student":
            student_query = db.query(User).filter(User.role == "Student")
            if search:
                student_query = student_query.filter(
                    or_(
                        User.username.contains(search),
                        User.email.contains(search)
                    )
                )
            students = student_query.limit(limit).all()
            for student in students:
                users.append(UserSearchResponse(
                    id=student.id,
                    username=student.username,
                    email=student.email,
                    user_type="Student",
                    college=student.college,
                    department=student.department
                ))
        
        if not user_type or user_type == "Admin":
            admin_query = db.query(Admin)
            if search:
                admin_query = admin_query.filter(
                    or_(
                        Admin.username.contains(search),
                        Admin.email.contains(search)
                    )
                )
            admins = admin_query.limit(limit).all()
            for admin in admins:
                if admin.id != current_user["id"]:  # Exclude current user
                    users.append(UserSearchResponse(
                        id=admin.id,
                        username=admin.username,
                        email=admin.email,
                        user_type="Admin"
                    ))
        
        if not user_type or user_type == "Presenter":
            presenter_query = db.query(Presenter)
            if search:
                presenter_query = presenter_query.filter(
                    or_(
                        Presenter.username.contains(search),
                        Presenter.email.contains(search)
                    )
                )
            presenters = presenter_query.limit(limit).all()
            for presenter in presenters:
                if presenter.id != current_user["id"]:  # Exclude current user
                    users.append(UserSearchResponse(
                        id=presenter.id,
                        username=presenter.username,
                        email=presenter.email,
                        user_type="Presenter"
                    ))
        
        if not user_type or user_type == "Mentor":
            mentor_query = db.query(Mentor)
            if search:
                mentor_query = mentor_query.filter(
                    or_(
                        Mentor.username.contains(search),
                        Mentor.email.contains(search)
                    )
                )
            mentors = mentor_query.limit(limit).all()
            for mentor in mentors:
                if mentor.id != current_user["id"]:  # Exclude current user
                    users.append(UserSearchResponse(
                        id=mentor.id,
                        username=mentor.username,
                        email=mentor.email,
                        user_type="Mentor"
                    ))
        
        if not user_type or user_type == "Manager":
            manager_query = db.query(Manager)
            if search:
                manager_query = manager_query.filter(
                    or_(
                        Manager.username.contains(search),
                        Manager.email.contains(search)
                    )
                )
            managers = manager_query.limit(limit).all()
            for manager in managers:
                if manager.id != current_user["id"] or current_user["role"] != "Manager":
                    users.append(UserSearchResponse(
                        id=manager.id,
                        username=manager.username,
                        email=manager.email,
                        user_type="Manager"
                    ))
        
        # Filter out users already in the chat if exclude_chat_id is provided
        if exclude_chat_id:
            existing_participants = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == exclude_chat_id,
                ChatParticipant.is_active == True
            ).all()
            
            existing_user_ids = {(p.user_id, p.user_type) for p in existing_participants}
            users = [u for u in users if (u.id, u.user_type) not in existing_user_ids]
        
        return users[:limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search users: {str(e)}")

@router.put("/{chat_id}/update")
async def update_group_chat(
    chat_id: int,
    update_data: GroupChatUpdate,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Update group chat (add/remove participants, change name)"""
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        if chat.chat_type != ChatType.GROUP:
            raise HTTPException(status_code=400, detail="Can only update group chats")
        
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update name
        if update_data.name:
            chat.name = update_data.name
        
        # Add participants
        if update_data.add_participants:
            for participant_data in update_data.add_participants:
                user_id = participant_data["user_id"]
                user_type = participant_data["user_type"]
                
                # Check if already exists
                existing = db.query(ChatParticipant).filter(
                    ChatParticipant.chat_id == chat_id,
                    ChatParticipant.user_id == user_id,
                    ChatParticipant.user_type == user_type
                ).first()
                
                if not existing:
                    new_participant = ChatParticipant(
                        chat_id=chat_id,
                        user_id=user_id,
                        user_type=user_type
                    )
                    db.add(new_participant)
                elif not existing.is_active:
                    existing.is_active = True
                    existing.joined_at = datetime.utcnow()
        
        # Remove participants
        if update_data.remove_participants:
            for participant_id in update_data.remove_participants:
                participant = db.query(ChatParticipant).filter(
                    ChatParticipant.id == participant_id,
                    ChatParticipant.chat_id == chat_id
                ).first()
                if participant:
                    participant.is_active = False
        
        chat.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Group chat updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update group chat: {str(e)}")

@router.get("/cohorts")
async def get_user_cohorts(
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get cohorts accessible to the current user based on their role"""
    try:
        cohorts = []
        user_role = current_user["role"]
        user_id = current_user["id"]
        
        # Try to import cohort models, with fallback
        try:
            from database import Cohort, UserCohort, PresenterCohort
            cohort_tables_exist = True
        except ImportError:
            cohort_tables_exist = False
        
        if not cohort_tables_exist:
            # Fallback: Check if tables exist in database
            try:
                # Check if cohorts table exists
                db.execute("SELECT 1 FROM cohorts LIMIT 1")
                
                # Get cohorts based on role
                if user_role == "Admin":
                    # Admin can see all cohorts
                    result = db.execute("SELECT id, name, description FROM cohorts WHERE is_active = 1")
                elif user_role == "Presenter":
                    # Presenter can see assigned cohorts
                    result = db.execute("""
                        SELECT c.id, c.name, c.description 
                        FROM cohorts c 
                        JOIN presenter_cohorts pc ON c.id = pc.cohort_id 
                        WHERE pc.presenter_id = %s AND c.is_active = 1
                    """, (user_id,))
                elif user_role == "Student":
                    # Student can see their cohort
                    result = db.execute("""
                        SELECT c.id, c.name, c.description 
                        FROM cohorts c 
                        JOIN user_cohorts uc ON c.id = uc.cohort_id 
                        WHERE uc.user_id = %s AND c.is_active = 1
                    """, (user_id,))
                elif user_role == "Mentor":
                    # Mentor can see all cohorts (or implement specific logic)
                    result = db.execute("SELECT id, name, description FROM cohorts WHERE is_active = 1")
                else:
                    result = []
                
                cohorts_data = result.fetchall() if hasattr(result, 'fetchall') else []
                
                for cohort_row in cohorts_data:
                    # Count users in cohort
                    try:
                        user_count_result = db.execute(
                            "SELECT COUNT(*) FROM user_cohorts WHERE cohort_id = %s", 
                            (cohort_row[0],)
                        )
                        user_count = user_count_result.fetchone()[0]
                    except:
                        user_count = 0
                    
                    cohorts.append({
                        "id": cohort_row[0],
                        "name": cohort_row[1],
                        "description": cohort_row[2] or "",
                        "user_count": user_count
                    })
                
                return {"cohorts": cohorts}
                
            except Exception as db_error:
                print(f"Database query failed: {db_error}")
                return {"cohorts": []}
        
        # Original logic if models exist
        if user_role == "Admin":
            # Admin can see all cohorts
            all_cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
            for cohort in all_cohorts:
                try:
                    user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
                except:
                    user_count = 0
                cohorts.append({
                    "id": cohort.id,
                    "name": cohort.name,
                    "description": cohort.description or "",
                    "user_count": user_count
                })
        
        elif user_role == "Presenter":
            # Presenter can see assigned cohorts
            try:
                presenter_cohorts = db.query(PresenterCohort).filter(
                    PresenterCohort.presenter_id == user_id
                ).all()
                
                for pc in presenter_cohorts:
                    cohort = pc.cohort
                    try:
                        user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
                    except:
                        user_count = 0
                    cohorts.append({
                        "id": cohort.id,
                        "name": cohort.name,
                        "description": cohort.description or "",
                        "user_count": user_count
                    })
            except:
                # Fallback: show all cohorts for presenters if relationship doesn't exist
                all_cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
                for cohort in all_cohorts:
                    cohorts.append({
                        "id": cohort.id,
                        "name": cohort.name,
                        "description": cohort.description or "",
                        "user_count": 0
                    })
        
        elif user_role in ["Mentor", "Manager"]:
            # Mentor and Manager can see all cohorts
            all_cohorts = db.query(Cohort).filter(Cohort.is_active == True).all()
            for cohort in all_cohorts:
                try:
                    user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
                except:
                    user_count = 0
                cohorts.append({
                    "id": cohort.id,
                    "name": cohort.name,
                    "description": cohort.description or "",
                    "user_count": user_count
                })
        
        elif user_role == "Student":
            # Student can see their own cohort
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # Try to get cohort from user_cohorts table
                try:
                    user_cohort = db.query(UserCohort).filter(UserCohort.user_id == user.id).first()
                    if user_cohort:
                        cohort = user_cohort.cohort
                        user_count = db.query(UserCohort).filter(UserCohort.cohort_id == cohort.id).count()
                        cohorts.append({
                            "id": cohort.id,
                            "name": cohort.name,
                            "description": cohort.description or "",
                            "user_count": user_count
                        })
                except:
                    # Fallback: check if user has cohort_id field
                    if hasattr(user, 'cohort_id') and user.cohort_id:
                        cohort = db.query(Cohort).filter(Cohort.id == user.cohort_id).first()
                        if cohort:
                            cohorts.append({
                                "id": cohort.id,
                                "name": cohort.name,
                                "description": cohort.description or "",
                                "user_count": 1
                            })
        
        return {"cohorts": cohorts}
        
    except Exception as e:
        print(f"Error in get_user_cohorts: {str(e)}")
        # Return empty cohorts instead of error to prevent frontend crash
        return {"cohorts": []}

# Add a new endpoint to get cohort chat by cohort ID
@router.get("/cohort/{cohort_id}")
async def get_cohort_chat(
    cohort_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get or create cohort group chat"""
    try:
        from database import Cohort
        
        # Get cohort info
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Look for existing group chat for this cohort
        existing_chat = db.query(Chat).filter(
            Chat.chat_type == ChatType.GROUP,
            Chat.name.like(f"%{cohort.name}%Group Chat%"),
            Chat.is_active == True
        ).first()
        
        if existing_chat:
            # Check if current user is a participant
            participant = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == existing_chat.id,
                ChatParticipant.user_id == current_user["id"],
                ChatParticipant.user_type == current_user["role"],
                ChatParticipant.is_active == True
            ).first()
            
            if not participant:
                # Add user as participant
                new_participant = ChatParticipant(
                    chat_id=existing_chat.id,
                    user_id=current_user["id"],
                    user_type=current_user["role"]
                )
                db.add(new_participant)
                db.commit()
            
            return await get_chat_response(existing_chat.id, current_user, db)
        
        # Create new group chat for cohort
        from chat_schemas import ChatCreate
        chat_data = ChatCreate(
            name=f"{cohort.name} Group Chat",
            chat_type=ChatType.GROUP,
            participant_ids=[],
            participant_types=[]
        )
        
        return await create_chat(chat_data, current_user, db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cohort chat: {str(e)}")

@router.get("/cohorts/{cohort_id}/users")
async def get_cohort_users(
    cohort_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get users in a specific cohort"""
    try:
        from database import Cohort, UserCohort
        
        # Check if user has access to this cohort
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Get users in the cohort
        user_cohorts = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        
        users = []
        for uc in user_cohorts:
            user = uc.user
            users.append({
                "id": user.id,
                "name": user.username,
                "email": user.email,
                "role": "Student",
                "user_type": "Student"
            })
        
        # Also include presenters and mentors if applicable
        if current_user["role"] in ["Admin", "Presenter", "Mentor"]:
            # Add presenters assigned to this cohort
            from database import PresenterCohort
            presenter_cohorts = db.query(PresenterCohort).filter(
                PresenterCohort.cohort_id == cohort_id
            ).all()
            
            for pc in presenter_cohorts:
                presenter = pc.presenter
                users.append({
                    "id": presenter.id,
                    "name": presenter.username,
                    "email": presenter.email,
                    "role": "Presenter",
                    "user_type": "Presenter"
                })
        
        return {"users": users}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cohort users: {str(e)}")

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Delete/leave a chat"""
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        if not can_access_chat(current_user, chat, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # For single chats or if user is admin, deactivate the chat
        if chat.chat_type == ChatType.SINGLE or current_user["role"] == "Admin":
            chat.is_active = False
        else:
            # For group chats, just remove the user
            participant = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == chat_id,
                ChatParticipant.user_id == current_user["id"],
                ChatParticipant.user_type == current_user["role"]
            ).first()
            if participant:
                participant.is_active = False
        
        db.commit()
        return {"message": "Chat deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")