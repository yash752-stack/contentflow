"""api/routes/tags.py"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from db.database import get_db, Tag
import re

router = APIRouter()

class TagCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)

def slugify(name: str) -> str:
    return re.sub(r"[\s_]+", "-", name.lower().strip())

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    slug = slugify(payload.name)
    if db.query(Tag).filter(Tag.slug == slug).first():
        raise HTTPException(status_code=400, detail="Tag already exists")
    tag = Tag(name=payload.name, slug=slug)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "slug": tag.slug}

@router.get("/")
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "article_count": len(t.articles)} for t in tags]

@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
