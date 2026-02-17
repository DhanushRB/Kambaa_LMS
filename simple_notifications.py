from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_token

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.get("")
async def get_notifications(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get user notifications"""
    return {"notifications": []}

@router.get("/unread-count")
async def get_unread_count(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get unread notifications count"""
    return {"unread_count": 0}