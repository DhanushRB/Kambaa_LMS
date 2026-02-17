# Student Meeting Endpoints

# Add these endpoints to main.py for student meeting functionality

@app.get("/student/meetings")
async def get_student_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all meetings for the current student"""
    try:
        logger.info(f"Get student meetings request from user: {current_user.username}")
        
        # Get all enrolled courses for the student
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).all()
        
        all_meetings = []
        
        for enrollment in enrollments:
            # Get all modules for the course
            modules = db.query(Module).filter(Module.course_id == enrollment.course_id).all()
            
            for module in modules:
                # Get all sessions for the module
                sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                
                for session in sessions:
                    # Get session content with meeting links
                    session_contents = db.query(SessionContent).filter(
                        SessionContent.session_id == session.id,
                        SessionContent.content_type == 'MEETING_LINK',
                        SessionContent.meeting_url.isnot(None)
                    ).all()
                    
                    for content in session_contents:
                        meeting = {
                            "id": f"meeting_{content.id}",
                            "title": content.title or session.title,
                            "description": content.description or session.description,
                            "meeting_url": format_meeting_url(content.meeting_url),
                            "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
                            "session_id": session.id,
                            "session_title": session.title,
                            "module_id": module.id,
                            "module_title": module.title,
                            "course_id": enrollment.course_id,
                            "course_title": enrollment.course.title,
                            "duration_minutes": session.duration_minutes or 60
                        }
                        all_meetings.append(meeting)
        
        # Sort meetings by scheduled time
        all_meetings.sort(key=lambda x: x['scheduled_time'] if x['scheduled_time'] else '9999-12-31')
        
        # Log student meeting access
        log_student_action(
            student_id=current_user.id,
            student_username=current_user.username,
            action_type="VIEW",
            resource_type="MEETINGS",
            details=f"Retrieved {len(all_meetings)} scheduled meetings"
        )
        
        return {
            "meetings": all_meetings,
            "total": len(all_meetings)
        }
    except Exception as e:
        logger.error(f"Get student meetings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch meetings")

@app.post("/student/meetings/{meeting_id}/join")
async def join_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log when a student joins a meeting"""
    try:
        logger.info(f"Join meeting request: meeting_id={meeting_id}")
        
        # Extract content ID from various meeting_id formats
        content_id = None
        
        if meeting_id.startswith("meeting_"):
            # Format: meeting_123
            content_id = int(meeting_id.replace("meeting_", ""))
        elif "content_" in meeting_id:
            # Format: session-201-content_15 or content_15
            content_part = meeting_id.split("content_")[-1]
            content_id = int(content_part)
        else:
            # Direct ID
            content_id = int(meeting_id)
        
        logger.info(f"Extracted content_id: {content_id}")
        
        # Get the meeting content
        content = db.query(SessionContent).filter(
            SessionContent.id == content_id
        ).first()
        
        logger.info(f"Found content: {content is not None}")
        if content:
            logger.info(f"Content type: {content.content_type}, has meeting_url: {content.meeting_url is not None}")
        
        # Check if it's a meeting link type
        if not content or content.content_type != 'MEETING_LINK':
            # Try to find any session content with this ID
            all_content = db.query(SessionContent).filter(SessionContent.id == content_id).first()
            if all_content:
                logger.info(f"Found content but wrong type: {all_content.content_type}")
            raise HTTPException(status_code=404, detail=f"Meeting not found for ID {content_id}")
        
        # Log meeting join
        log_student_action(
            student_id=current_user.id,
            student_username=current_user.username,
            action_type="JOIN",
            resource_type="MEETING",
            resource_id=content.session_id,
            details=f"Joined meeting: {content.title} (URL: {content.meeting_url})"
        )
        
        return {
            "message": "Meeting join logged successfully",
            "meeting_url": format_meeting_url(content.meeting_url),
            "title": content.title
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Join meeting error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to log meeting join")

@app.get("/student/meetings/upcoming")
async def get_upcoming_meetings(
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get meetings scheduled within the next specified hours"""
    try:
        now = datetime.now()
        future_time = now + timedelta(hours=hours)
        
        # Get all enrolled courses for the student
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).all()
        
        upcoming_meetings = []
        
        for enrollment in enrollments:
            # Get all modules for the course
            modules = db.query(Module).filter(Module.course_id == enrollment.course_id).all()
            
            for module in modules:
                # Get all sessions for the module
                sessions = db.query(SessionModel).filter(SessionModel.module_id == module.id).all()
                
                for session in sessions:
                    # Get session content with meeting links scheduled within the time range
                    session_contents = db.query(SessionContent).filter(
                        SessionContent.session_id == session.id,
                        SessionContent.content_type == 'MEETING_LINK',
                        SessionContent.meeting_url.isnot(None),
                        SessionContent.scheduled_time.isnot(None),
                        SessionContent.scheduled_time >= now,
                        SessionContent.scheduled_time <= future_time
                    ).all()
                    
                    for content in session_contents:
                        meeting = {
                            "id": f"meeting_{content.id}",
                            "title": content.title or session.title,
                            "description": content.description or session.description,
                            "meeting_url": format_meeting_url(content.meeting_url),
                            "scheduled_time": content.scheduled_time.isoformat(),
                            "session_id": session.id,
                            "session_title": session.title,
                            "module_id": module.id,
                            "module_title": module.title,
                            "course_id": enrollment.course_id,
                            "course_title": enrollment.course.title,
                            "duration_minutes": session.duration_minutes or 60,
                            "time_until_meeting": (content.scheduled_time - now).total_seconds()
                        }
                        upcoming_meetings.append(meeting)
        
        # Sort by scheduled time
        upcoming_meetings.sort(key=lambda x: x['scheduled_time'])
        
        return {
            "meetings": upcoming_meetings,
            "total": len(upcoming_meetings),
            "time_range_hours": hours
        }
    except Exception as e:
        logger.error(f"Get upcoming meetings error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch upcoming meetings")

@app.get("/debug/session-content")
async def debug_session_content(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check session content"""
    try:
        # Get all session content
        all_content = db.query(SessionContent).all()
        
        content_info = []
        for content in all_content:
            content_info.append({
                "id": content.id,
                "session_id": content.session_id,
                "content_type": content.content_type,
                "title": content.title,
                "meeting_url": content.meeting_url,
                "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None
            })
        
        return {
            "total_content": len(content_info),
            "content": content_info
        }
    except Exception as e:
        logger.error(f"Debug session content error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch debug info")