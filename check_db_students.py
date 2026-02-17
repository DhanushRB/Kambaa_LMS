from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Assuming SQLite for now based on 'lms.db' appearing in list_dir
engine = create_engine('sqlite:///lms.db')
Session = sessionmaker(bind=engine)
session = Session()

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    email = Column(String)
    role = Column(String)

print("--- STUDENTS IN DATABASE (Sample 10) ---")
students = session.query(User).filter(User.role == 'student').limit(10).all()
for s in students:
    print(f"ID: {s.id}, Name: {s.full_name}, Username: {s.username}, Email: {s.email}")

session.close()
