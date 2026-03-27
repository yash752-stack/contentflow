"""api/routes/users.py"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from db.database import get_db, User

router = APIRouter()

class UserCreate(BaseModel):
    username:  str = Field(..., min_length=3, max_length=50)
    email:     str
    full_name: str = Field(..., min_length=2, max_length=100)
    role:      Optional[str] = "editor"

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(**payload.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}

@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id, "username": user.username, "full_name": user.full_name,
        "email": user.email, "role": user.role, "is_active": user.is_active,
        "article_count": len(user.articles),
    }

@router.get("/")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()
    return [{"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role} for u in users]
