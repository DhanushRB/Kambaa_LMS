from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ChatTypeEnum(str, Enum):
    SINGLE = "SINGLE"
    GROUP = "GROUP"

class MessageTypeEnum(str, Enum):
    TEXT = "TEXT"
    FILE = "FILE"
    LINK = "LINK"

class UserTypeEnum(str, Enum):
    ADMIN = "Admin"
    PRESENTER = "Presenter"
    MENTOR = "Mentor"
    STUDENT = "Student"

# Chat Schemas
class ChatCreate(BaseModel):
    name: Optional[str] = None
    chat_type: ChatTypeEnum
    participant_ids: List[int]
    participant_types: List[UserTypeEnum]

class ChatParticipantResponse(BaseModel):
    id: int
    user_id: int
    user_type: str
    username: str
    email: str
    joined_at: datetime
    last_read_at: Optional[datetime]
    is_active: bool

class ChatResponse(BaseModel):
    id: int
    name: Optional[str]
    chat_type: str
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    participants: List[ChatParticipantResponse]
    unread_count: int = 0
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None

# Message Schemas
class MessageCreate(BaseModel):
    chat_id: int
    content: str
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    file_name: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    sender_type: str
    sender_name: str
    message_type: str
    content: str
    file_path: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    created_at: datetime
    is_edited: bool
    edited_at: Optional[datetime]

# Search and Filter Schemas
class ChatSearchRequest(BaseModel):
    search: Optional[str] = None
    chat_type: Optional[ChatTypeEnum] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

class UserSearchRequest(BaseModel):
    search: Optional[str] = None
    user_type: Optional[UserTypeEnum] = None
    exclude_chat_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

class UserSearchResponse(BaseModel):
    id: int
    username: str
    email: str
    user_type: str
    college: Optional[str] = None
    department: Optional[str] = None

# Group Chat Management
class GroupChatUpdate(BaseModel):
    name: Optional[str] = None
    add_participants: Optional[List[dict]] = None  # [{"user_id": 1, "user_type": "Student"}]
    remove_participants: Optional[List[int]] = None  # participant_ids

class MarkReadRequest(BaseModel):
    chat_id: int