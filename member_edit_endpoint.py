@app.put("/admin/members/{role}/{member_id}")
async def update_member(
    role: str,
    member_id: int,
    member_data: dict,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    try:
        if role.lower() == "admin":
            member = db.query(Admin).filter(Admin.id == member_id).first()
            if not member:
                raise HTTPException(status_code=404, detail="Admin not found")
            
            # Check for duplicate username/email
            if member_data.get('username'):
                existing = db.query(Admin).filter(
                    Admin.username == member_data['username'],
                    Admin.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Username already exists")
                member.username = member_data['username']
            
            if member_data.get('email'):
                existing = db.query(Admin).filter(
                    Admin.email == member_data['email'],
                    Admin.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Email already exists")
                member.email = member_data['email']
            
            if member_data.get('password'):
                member.password_hash = get_password_hash(member_data['password'])
            
        elif role.lower() == "presenter":
            member = db.query(Presenter).filter(Presenter.id == member_id).first()
            if not member:
                raise HTTPException(status_code=404, detail="Presenter not found")
            
            # Check for duplicate username/email
            if member_data.get('username'):
                existing = db.query(Presenter).filter(
                    Presenter.username == member_data['username'],
                    Presenter.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Username already exists")
                member.username = member_data['username']
            
            if member_data.get('email'):
                existing = db.query(Presenter).filter(
                    Presenter.email == member_data['email'],
                    Presenter.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Email already exists")
                member.email = member_data['email']
            
            if member_data.get('password'):
                member.password_hash = get_password_hash(member_data['password'])
                
        elif role.lower() == "mentor":
            member = db.query(Mentor).filter(Mentor.id == member_id).first()
            if not member:
                raise HTTPException(status_code=404, detail="Mentor not found")
            
            # Check for duplicate username/email
            if member_data.get('username'):
                existing = db.query(Mentor).filter(
                    Mentor.username == member_data['username'],
                    Mentor.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Username already exists")
                member.username = member_data['username']
            
            if member_data.get('email'):
                existing = db.query(Mentor).filter(
                    Mentor.email == member_data['email'],
                    Mentor.id != member_id
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Email already exists")
                member.email = member_data['email']
            
            if member_data.get('password'):
                member.password_hash = get_password_hash(member_data['password'])
            
            if member_data.get('full_name') is not None:
                member.full_name = member_data['full_name']
        else:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        db.commit()
        return {"message": f"{role} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update member error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update member")