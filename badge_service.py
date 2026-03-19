import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from badge_models import BadgeConfiguration, AwardedBadge, BadgeAuditLog
from database import User, Attendance, Session as SessionModel, StudentSessionStatus, Enrollment, Module
from assignment_quiz_models import Assignment, AssignmentSubmission, AssignmentGrade
from cohort_specific_models import CohortCourseSession, CohortCourseModule, CohortAttendance, CohortSpecificCourse
from email_service import send_notification_email, email_service

logger = logging.getLogger(__name__)

class BadgeService:
    @staticmethod
    def get_student_performance(db: Session, student_id: int, config: BadgeConfiguration) -> Dict[str, Any]:
        """
        Gathers performance metrics for a student within a specific session range and course.
        """
        # 1. Find sessions within the course and range
        session_ids = []
        is_cohort = False
        
        if config.cohort_specific_course_id:
            is_cohort = True
            sessions = db.query(CohortCourseSession).join(CohortCourseSession.module).filter(
                CohortCourseModule.course_id == config.cohort_specific_course_id,
                CohortCourseModule.week_number >= config.week_start,
                CohortCourseModule.week_number <= config.week_end
            ).all()
            session_ids = [s.id for s in sessions]
        elif config.course_id:
            sessions = db.query(SessionModel).join(SessionModel.module).filter(
                Module.course_id == config.course_id,
                Module.week_number >= config.week_start,
                Module.week_number <= config.week_end
            ).all()
            session_ids = [s.id for s in sessions]
           
        if not session_ids:
            return None
            
        total_sessions = len(session_ids)
        
        # 2. Attendance Metrics
        if is_cohort:
            attended_count = db.query(CohortAttendance).filter(
                CohortAttendance.student_id == student_id,
                CohortAttendance.session_id.in_(session_ids),
                CohortAttendance.attended == True
            ).count()
        else:
            attended_count = db.query(Attendance).filter(
                Attendance.student_id == student_id,
                Attendance.session_id.in_(session_ids),
                Attendance.attended == True
            ).count()
        
        attendance_percentage = (attended_count / total_sessions * 100) if total_sessions > 0 else 0
        
        # 3. Assignment Metrics
        session_type = "cohort" if is_cohort else "global"
        assignments = db.query(Assignment).filter(
            Assignment.session_id.in_(session_ids),
            Assignment.session_type == session_type
        ).all()
        
        total_assignments = len(assignments)
        assignment_ids = [a.id for a in assignments]
        
        submitted_count = 0
        avg_score = 0
        
        if total_assignments > 0:
            submissions = db.query(AssignmentSubmission).filter(
                AssignmentSubmission.student_id == student_id,
                AssignmentSubmission.assignment_id.in_(assignment_ids)
            ).all()
            submitted_count = len(submissions)
            
            grades = db.query(AssignmentGrade).filter(
                AssignmentGrade.student_id == student_id,
                AssignmentGrade.assignment_id.in_(assignment_ids)
            ).all()
            
            if grades:
                avg_score = sum([g.percentage for g in grades if g.percentage]) / len(grades)
        
        submission_status = submitted_count == total_assignments if total_assignments > 0 else True
        
        # 4. Session Progress
        completed_sessions = db.query(StudentSessionStatus).filter(
            StudentSessionStatus.student_id == student_id,
            StudentSessionStatus.session_id.in_(session_ids),
            StudentSessionStatus.session_type == session_type,
            StudentSessionStatus.status == "Completed"
        ).count()
        
        progress_percentage = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        return {
            "attendance": round(attendance_percentage, 2),
            "avg_score": round(avg_score, 2),
            "assignment_submission_status": submission_status,
            "progress": round(progress_percentage, 2),
            "total_sessions": total_sessions,
            "attended_count": attended_count,
            "submitted_count": submitted_count,
            "total_assignments": total_assignments
        }

    @staticmethod
    def evaluate_eligibility(performance: Dict[str, Any], config: BadgeConfiguration) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates a student's performance against a badge configuration.
        """
        criteria = config.criteria
        mandatory = config.mandatory_checks
        results = {}
        is_eligible = True
        
        # Map criteria keys to performance keys
        mapping = {
            "min_attendance": ("attendance", performance.get("attendance", 0)),
            "min_assignments_completed": ("submitted_count", performance.get("submitted_count", 0)),
            "min_progress": ("progress", performance.get("progress", 0))
        }
        
        # Phase 1: Evaluate all individual rules
        for rule, threshold in criteria.items():
            if rule in mapping:
                perf_key, actual_val = mapping[rule]
                
                if isinstance(threshold, bool):
                     passed = actual_val == threshold
                else:
                     passed = actual_val >= threshold
                
                results[rule] = {
                    "required": threshold,
                    "actual": actual_val,
                    "pass": passed
                }
        
        # Phase 2: Determine overall eligibility
        is_eligible = True
        
        # 1. Assignments are STRICTLY mandatory
        if not results.get("min_assignments_completed", {}).get("pass", True):
            is_eligible = False
            
        # 2. Flexible Attendance OR Progress logic
        # If both are marked mandatory, satisfying EITHER one is enough
        att_is_mandatory = "min_attendance" in mandatory
        prog_is_mandatory = "min_progress" in mandatory
        
        if att_is_mandatory and prog_is_mandatory:
            att_pass = results.get("min_attendance", {}).get("pass", False)
            prog_pass = results.get("min_progress", {}).get("pass", False)
            if not (att_pass or prog_pass):
                is_eligible = False
        elif att_is_mandatory:
            if not results.get("min_attendance", {}).get("pass", False):
                is_eligible = False
        elif prog_is_mandatory:
            if not results.get("min_progress", {}).get("pass", False):
                is_eligible = False
                    
        return is_eligible, results

    @staticmethod
    def process_badge_evaluation(db: Session, config_id: int) -> Dict[str, Any]:
        """
        Evaluates students for a badge configuration with filtering support.
        """
        config = db.query(BadgeConfiguration).filter(BadgeConfiguration.id == config_id).first()
        if not config:
            return {"error": "Configuration not found"}
            
        # Determine student pool
        query = db.query(User).filter(User.role == "Student")
        
        if config.cohort_id:
            query = query.filter(User.cohort_id == config.cohort_id)
        elif config.cohort_specific_course_id:
            # If for some reason cohort_id is null but specific_course_id is set
            course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == config.cohort_specific_course_id).first()
            if course:
                query = query.filter(User.cohort_id == course.cohort_id)
        elif config.course_id:
            # If no cohort but global course is specified, find students enrolled in the course
            query = query.join(User.enrollments).filter(Enrollment.course_id == config.course_id)
           
        students = query.all()
        
        # Get already issued badges for this config
        issued_user_ids = {
            b.user_id for b in db.query(AwardedBadge.user_id).filter(
                AwardedBadge.badge_config_id == config.id
            ).all()
        }
        
        summary = {
            "badge_config_id": config.id,
            "total_evaluated": 0,
            "eligible_now": [],
            "already_issued": [],
            "rejected": []
        }
        
        for student in students:
            performance = BadgeService.get_student_performance(db, student.id, config)
            if not performance:
                continue
                
            is_eligible, details = BadgeService.evaluate_eligibility(performance, config)
            
            # Categorize the student
            student_data = {
                "userId": student.id,
                "name": f"{student.first_name} {student.last_name}" if hasattr(student, 'first_name') else student.username,
                "username": student.username,
                "email": student.email,
                "attendance_percentage": performance.get("attendance", 0),
                "submitted_count": performance.get("submitted_count", 0),
                "total_assignments": performance.get("total_assignments", 0),
                "is_eligible": is_eligible,
                "details": details
            }
            
            if student.id in issued_user_ids:
                summary["already_issued"].append(student_data)
            elif is_eligible:
                summary["eligible_now"].append(student_data)
            else:
                summary["rejected"].append(student_data)
                
            summary["total_evaluated"] += 1

            # Log/Update audit
            existing_audit = db.query(BadgeAuditLog).filter(
                BadgeAuditLog.user_id == student.id,
                BadgeAuditLog.badge_config_id == config.id
            ).first()
            
            if existing_audit:
                existing_audit.status = "ELIGIBLE" if is_eligible else "REJECTED"
                existing_audit.details = {"criteria_results": details, "performance": performance}
                existing_audit.evaluated_at = datetime.utcnow()
            else:
                audit = BadgeAuditLog(
                    user_id=student.id,
                    badge_config_id=config.id,
                    status="ELIGIBLE" if is_eligible else "REJECTED",
                    details={"criteria_results": details, "performance": performance},
                    remarks="Automated evaluation"
                )
                db.add(audit)
        
        db.commit()
        return summary

    @staticmethod
    def issue_badges(db: Session, config_id: int, user_ids: List[int]) -> Dict[str, Any]:
        """
        Strictly issues badges to confirmed users and sends emails.
        """
        config = db.query(BadgeConfiguration).filter(BadgeConfiguration.id == config_id).first()
        if not config:
            return {"error": "Configuration not found"}
            
        issued_count = 0
        for user_id in user_ids:
            # Check if already awarded
            exists = db.query(AwardedBadge).filter(
                AwardedBadge.user_id == user_id,
                AwardedBadge.badge_config_id == config_id
            ).first()
            
            if exists:
                continue
                
            # Get performance for snapshot
            performance = BadgeService.get_student_performance(db, user_id, config)
            
            # Award Badge with performance snapshot
            award = AwardedBadge(
                user_id=user_id,
                badge_config_id=config_id,
                criteria_snapshot={
                    "metrics": performance,
                    "rules": config.criteria
                }
            )
            db.add(award)
            
            # Send Email
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                from database import EmailTemplate
                # Try to get the template from database first (for UI-edited content)
                template = db.query(EmailTemplate).filter(
                    EmailTemplate.name == "Badge Achievement",
                    EmailTemplate.is_active == True
                ).first()
                
                subject = f"Congratulations! You've earned the '{config.title}' Badge"
                if template:
                    # Use template from database
                    subject = template.subject.replace("{badge_title}", config.title).replace("{username}", user.username)
                    body_content = template.body.replace("{badge_title}", config.title).replace("{username}", user.username)
                    
                    # Wrap in base layout and send
                    from email_styling import wrap_in_base_layout
                    html_message = wrap_in_base_layout(body_content, subject)
                    
                    # Import send_email or use email_service.send_email
                    from email_service import send_notification_email
                    send_notification_email([user.email], subject, html_message, "badge_award")
                else:
                    # Fallback to hardcoded template in EmailService
                    email_service.send_template_email(
                        to_emails=[user.email],
                        template_name='badge_achievement',
                        template_data={
                            'username': user.username,
                            'badge_title': config.title,
                            'icon_url': config.icon_url or 'https://cdn-icons-png.flaticon.com/512/190/190411.png'
                        },
                        subject=subject
                    )
            
            issued_count += 1
            
        db.commit()
        return {"issued_count": issued_count}
    @staticmethod
    def get_available_badges_for_student(db: Session, student_id: int) -> List[Dict[str, Any]]:
        """
        Returns a list of badges available to the student that they haven't earned yet,
        along with their current progress/eligibility status.
        """
        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            return []
            
        # 1. Identify potential badge configurations
        # - Global badges
        # - Badges for their cohort
        # - Badges for courses they are enrolled in
        configs = db.query(BadgeConfiguration).filter(BadgeConfiguration.is_active == True)
        
        # Filter configurations relevant to this student
        relevant_configs = []
        all_active_configs = configs.all()
        
        # Get student's enrolled course IDs
        enrolled_course_ids = [e.course_id for e in student.enrollments]
        
        for config in all_active_configs:
            is_relevant = False
            
            # Global (no cohort, no course) - everyone
            if not config.cohort_id and not config.course_id and not config.cohort_specific_course_id:
                is_relevant = True
            # Cohort specific
            elif config.cohort_id == student.cohort_id:
                is_relevant = True
            # Course specific (Global Course)
            elif config.course_id in enrolled_course_ids:
                is_relevant = True
            # Cohort Specific Course
            elif config.cohort_specific_course_id:
                csc = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == config.cohort_specific_course_id).first()
                if csc and csc.cohort_id == student.cohort_id:
                    is_relevant = True
                    
            if is_relevant:
                relevant_configs.append(config)
                
        # 2. Filter out already earned badges
        earned_badge_ids = [b.badge_config_id for b in db.query(AwardedBadge).filter(AwardedBadge.user_id == student_id).all()]
        unearned_configs = [c for c in relevant_configs if c.id not in earned_badge_ids]
        
        # 3. Evaluate progress for each unearned badge
        results = []
        for config in unearned_configs:
            performance = BadgeService.get_student_performance(db, student_id, config)
            if not performance:
                continue
                
            is_eligible, details = BadgeService.evaluate_eligibility(performance, config)
            
            # Enrich config info
            course_title = None
            if config.cohort_specific_course_id:
                course = db.query(CohortSpecificCourse).filter(CohortSpecificCourse.id == config.cohort_specific_course_id).first()
                course_title = course.title if course else None
            elif config.course_id:
                course = db.query(Course).filter(Course.id == config.course_id).first()
                course_title = course.title if course else None
                
            results.append({
                "id": config.id,
                "title": config.title,
                "description": config.description,
                "icon_url": config.icon_url,
                "week_start": config.week_start,
                "week_end": config.week_end,
                "course_title": course_title,
                "is_eligible": is_eligible,
                "performance": performance,
                "criteria_results": details,
                "requirements": config.criteria
            })
            
        return results
