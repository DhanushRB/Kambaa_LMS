from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, Manager
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_manager(token_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    manager = db.query(Manager).filter(Manager.username == token_data.get("sub")).first()
    if manager is None:
        raise HTTPException(status_code=401, detail="Manager not found")
    return manager

def get_current_admin_or_manager(token_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    """Get current admin or manager - both have management permissions"""
    username = token_data.get("sub")
    role = token_data.get("role")
    
    if role == "Admin":
        from database import Admin
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin
    elif role == "Manager":
        manager = db.query(Manager).filter(Manager.username == username).first()
        if not manager:
            raise HTTPException(status_code=401, detail="Manager not found")
        return manager
    else:
        raise HTTPException(status_code=403, detail="Access denied. Admin or Manager role required.")