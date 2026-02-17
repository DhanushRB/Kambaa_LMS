from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime

from database import get_db, User, Admin, Presenter, Mentor, Manager, Cohort, UserCohort, PresenterCohort
from auth import verify_token
from chat_models import Chat, ChatParticipant, ChatType
from chat_endpoints import get_current_user_info_chat

router = APIRouter(prefix="/api/cohort-chat", tags=["Cohort Chat"])

@router.post("/create-cohort-group-chat/{cohort_id}")
async def create_cohort_group_chat(
    cohort_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Create or get existing group chat for a cohort"""
    try:
        # Verify cohort exists
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        # Check if user has access to this cohort
        has_access = False
        user_role = current_user["role"]
        user_id = current_user["id"]
        
        if user_role in ["Admin", "Manager"]:
            has_access = True
        elif user_role == "Presenter":
            presenter_cohort = db.query(PresenterCohort).filter(
                PresenterCohort.presenter_id == user_id,
                PresenterCohort.cohort_id == cohort_id
            ).first()
            has_access = presenter_cohort is not None
        elif user_role == "Student":
            user = db.query(User).filter(User.id == user_id).first()
            has_access = user and user.cohort_id == cohort_id
        elif user_role == "Mentor":
            # For now, mentors can access all cohorts
            has_access = True
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this cohort")
        
        # Check if group chat already exists for this cohort
        existing_chat = db.query(Chat).filter(
            Chat.chat_type == ChatType.GROUP,
            Chat.name == f"{cohort.name} - Group Chat",
            Chat.is_active == True
        ).first()
        
        if existing_chat:
            # Check if current user is already a participant
            participant = db.query(ChatParticipant).filter(
                ChatParticipant.chat_id == existing_chat.id,
                ChatParticipant.user_id == user_id,
                ChatParticipant.user_type == user_role,
                ChatParticipant.is_active == True
            ).first()
            
            if not participant:
                # Add current user as participant
                new_participant = ChatParticipant(
                    chat_id=existing_chat.id,
                    user_id=user_id,
                    user_type=user_role
                )
                db.add(new_participant)
                db.commit()
            
            return {"chat_id": existing_chat.id, "message": "Joined existing group chat"}
        
        # Create new group chat
        group_chat = Chat(
            name=f"{cohort.name} - Group Chat",
            chat_type=ChatType.GROUP,
            created_by=user_id if user_role in ["Admin", "Manager"] else None
        )
        db.add(group_chat)
        db.flush()
        
        # Add current user as participant
        current_participant = ChatParticipant(
            chat_id=group_chat.id,
            user_id=user_id,
            user_type=user_role
        )
        db.add(current_participant)
        
        # Auto-add all cohort members as participants
        cohort_users = db.query(UserCohort).filter(UserCohort.cohort_id == cohort_id).all()
        for uc in cohort_users:
            if not (uc.user_id == user_id and user_role == "Student"):
                participant = ChatParticipant(
                    chat_id=group_chat.id,
                    user_id=uc.user_id,
                    user_type="Student"
                )
                db.add(participant)
        
        # Add presenters assigned to this cohort
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        for pc in presenter_cohorts:
            if not (pc.presenter_id == user_id and user_role == "Presenter"):
                participant = ChatParticipant(
                    chat_id=group_chat.id,
                    user_id=pc.presenter_id,
                    user_type="Presenter"
                )
                db.add(participant)
        
        db.commit()
        db.refresh(group_chat)
        
        return {
            "chat_id": group_chat.id,
            "message": "Group chat created successfully",
            "chat_name": group_chat.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create cohort group chat: {str(e)}")

@router.get("/cohort-members/{cohort_id}")
async def get_cohort_members_for_chat(
    cohort_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Get all members in a cohort for chat purposes"""
    try:
        # Import MentorCohort
        from database import MentorCohort
        
        # Verify cohort exists and user has access
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        members = []
        user_role = current_user["role"]
        
        # For students: Only show assigned presenters, assigned mentors, and all admins/managers
        # For other roles: Show all users based on their role-specific logic
        
        # Get students in cohort (only for non-students or admins/managers)
        if user_role in ["Admin", "Manager", "Presenter", "Mentor"]:
            cohort_users = db.query(UserCohort).filter(
                UserCohort.cohort_id == cohort_id,
                UserCohort.is_active == True
            ).all()
            if cohort_users:
                for uc in cohort_users:
                    user = db.query(User).filter(User.id == uc.user_id).first()
                    if user and (user.id != current_user["id"] or current_user["role"] != "Student"):
                        members.append({
                            "id": user.id,
                            "name": user.username,
                            "email": user.email,
                            "role": "Student",
                            "user_type": "Student"
                        })
        
        # Get presenters assigned to this specific cohort
        presenter_cohorts = db.query(PresenterCohort).filter(
            PresenterCohort.cohort_id == cohort_id
        ).all()
        if presenter_cohorts:
            for pc in presenter_cohorts:
                presenter = db.query(Presenter).filter(Presenter.id == pc.presenter_id).first()
                if presenter and (presenter.id != current_user["id"] or current_user["role"] != "Presenter"):
                    members.append({
                        "id": presenter.id,
                        "name": presenter.username,
                        "email": presenter.email,
                        "role": "Presenter",
                        "user_type": "Presenter"
                    })
        
        # Get mentors assigned to this specific cohort
        mentor_cohorts = db.query(MentorCohort).filter(
            MentorCohort.cohort_id == cohort_id
        ).all()
        if mentor_cohorts:
            for mc in mentor_cohorts:
                mentor = db.query(Mentor).filter(Mentor.id == mc.mentor_id).first()
                if mentor and (mentor.id != current_user["id"] or current_user["role"] != "Mentor"):
                    members.append({
                        "id": mentor.id,
                        "name": mentor.username,
                        "email": mentor.email,
                        "role": "Mentor",
                        "user_type": "Mentor"
                    })
        
        # Add all admins (always visible to everyone)
        admins = db.query(Admin).all()
        for admin in admins:
            if admin.id != current_user["id"] or current_user["role"] != "Admin":
                members.append({
                    "id": admin.id,
                    "name": admin.username,
                    "email": admin.email,
                    "role": "Admin",
                    "user_type": "Admin"
                })
        
        # Add all managers (always visible to everyone)
        managers = db.query(Manager).all()
        for manager in managers:
            if manager.id != current_user["id"] or current_user["role"] != "Manager":
                members.append({
                    "id": manager.id,
                    "name": manager.username,
                    "email": manager.email,
                    "role": "Manager",
                    "user_type": "Manager"
                })
        
        return {"members": members}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cohort members: {str(e)}")

@router.post("/ensure-cohort-access/{cohort_id}")
async def ensure_user_cohort_access(
    cohort_id: int,
    current_user = Depends(get_current_user_info_chat),
    db: Session = Depends(get_db)
):
    """Ensure user has proper access to cohort chats"""
    try:
        cohort = db.query(Cohort).filter(Cohort.id == cohort_id).first()
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        
        user_role = current_user["role"]
        user_id = current_user["id"]
        
        # Check access based on role
        if user_role == "Admin":
            return {"access": True, "role": "Admin"}
        elif user_role == "Manager":
            return {"access": True, "role": "Manager"}
        elif user_role == "Presenter":
            presenter_cohort = db.query(PresenterCohort).filter(
                PresenterCohort.presenter_id == user_id,
                PresenterCohort.cohort_id == cohort_id
            ).first()
            return {"access": presenter_cohort is not None, "role": "Presenter"}
        elif user_role == "Student":
            user = db.query(User).filter(User.id == user_id).first()
            has_access = user and user.cohort_id == cohort_id
            return {"access": has_access, "role": "Student"}
        elif user_role == "Mentor":
            return {"access": True, "role": "Mentor"}
        else:
            return {"access": False, "role": user_role}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check cohort access: {str(e)}")