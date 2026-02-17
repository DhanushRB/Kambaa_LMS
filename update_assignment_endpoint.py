@router.put("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: int,
    session_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    instructions: str = Form(None),
    submission_type: str = Form("FILE"),
    due_date: str = Form(...),
    total_marks: int = Form(100),
    evaluation_criteria: str = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Update an existing assignment"""
    try:
        # Get existing assignment
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Handle file upload if provided
        if file:
            file_extension = os.path.splitext(file.filename)[1]
            if file_extension.lower() not in ['.pdf', '.doc', '.docx', '.zip', '.rar']:
                raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, DOC, DOCX, ZIP, RAR allowed")
            
            # Delete old file if exists
            if assignment.file_path and os.path.exists(assignment.file_path):
                try:
                    os.remove(assignment.file_path)
                except:
                    pass  # Ignore if file doesn't exist
            
            filename = f"assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = ASSIGNMENT_UPLOAD_DIR / filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            assignment.file_path = str(file_path)

        # Parse due_date
        try:
            due_date_parsed = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except:
            due_date_parsed = datetime.strptime(due_date, "%Y-%m-%d")

        # Update assignment fields
        assignment.title = title
        assignment.description = description
        assignment.instructions = instructions
        assignment.submission_type = SubmissionType[submission_type]
        assignment.due_date = due_date_parsed
        assignment.total_marks = total_marks
        assignment.evaluation_criteria = evaluation_criteria

        db.commit()
        db.refresh(assignment)

        return {
            "message": "Assignment updated successfully",
            "assignment_id": assignment.id,
            "assignment": {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "due_date": assignment.due_date,
                "total_marks": assignment.total_marks,
                "submission_type": assignment.submission_type.value,
                "has_file": assignment.file_path is not None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update assignment: {str(e)}")

