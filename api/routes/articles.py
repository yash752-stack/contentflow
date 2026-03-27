"""
api/routes/articles.py
Full CRUD for articles with versioning, publishing workflow, and pagination.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import re

from db.database import get_db, Article, ArticleVersion, Tag, User, article_tags

router = APIRouter()


# ── SCHEMAS ────────────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    title:    str = Field(..., min_length=3, max_length=300)
    content:  str = Field(..., min_length=10)
    excerpt:  Optional[str] = None
    author_id: int
    tag_ids:  List[int] = []

class ArticleUpdate(BaseModel):
    title:    Optional[str] = None
    content:  Optional[str] = None
    excerpt:  Optional[str] = None
    tag_ids:  Optional[List[int]] = None

class ArticleResponse(BaseModel):
    id:          int
    title:       str
    slug:        str
    excerpt:     Optional[str]
    status:      str
    author_id:   int
    view_count:  int
    created_at:  datetime
    updated_at:  datetime
    published_at: Optional[datetime]
    tags:        List[str] = []

    class Config:
        from_attributes = True


# ── HELPERS ────────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:300]

def make_unique_slug(db: Session, title: str) -> str:
    base = slugify(title)
    slug = base
    counter = 1
    while db.query(Article).filter(Article.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug

def save_version(db: Session, article: Article, saved_by: int):
    last_version = db.query(func.max(ArticleVersion.version))\
                     .filter(ArticleVersion.article_id == article.id).scalar() or 0
    version = ArticleVersion(
        article_id=article.id,
        version=last_version + 1,
        title=article.title,
        content=article.content,
        saved_by=saved_by,
    )
    db.add(version)


# ── ROUTES ────────────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_articles(
    page:    int = Query(1, ge=1),
    limit:   int = Query(20, ge=1, le=100),
    status:  Optional[str] = Query(None, regex="^(draft|published|archived)$"),
    tag:     Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List articles with pagination, status filter, and tag filter."""
    q = db.query(Article)

    if status:
        q = q.filter(Article.status == status)
    if tag:
        q = q.join(article_tags).join(Tag).filter(Tag.slug == tag)

    total = q.count()
    articles = q.order_by(Article.created_at.desc())\
                .offset((page - 1) * limit)\
                .limit(limit)\
                .all()

    return {
        "total":    total,
        "page":     page,
        "limit":    limit,
        "pages":    (total + limit - 1) // limit,
        "articles": [
            {
                "id":           a.id,
                "title":        a.title,
                "slug":         a.slug,
                "status":       a.status,
                "author_id":    a.author_id,
                "view_count":   a.view_count,
                "created_at":   a.created_at.isoformat(),
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "tags":         [t.name for t in a.tags],
            }
            for a in articles
        ],
    }


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_article(payload: ArticleCreate, db: Session = Depends(get_db)):
    """Create a new article in draft status."""
    author = db.query(User).filter(User.id == payload.author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    slug = make_unique_slug(db, payload.title)

    article = Article(
        title=payload.title,
        slug=slug,
        content=payload.content,
        excerpt=payload.excerpt or payload.content[:200],
        author_id=payload.author_id,
        status="draft",
    )

    # Attach tags
    if payload.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()
        article.tags = tags

    db.add(article)
    db.commit()
    db.refresh(article)

    save_version(db, article, saved_by=payload.author_id)
    db.commit()

    return {"id": article.id, "slug": article.slug, "status": article.status}


@router.get("/{slug}", response_model=dict)
def get_article(slug: str, db: Session = Depends(get_db)):
    """Fetch a single article by slug. Increments view count."""
    article = db.query(Article).filter(Article.slug == slug).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.view_count += 1
    db.commit()

    return {
        "id":           article.id,
        "title":        article.title,
        "slug":         article.slug,
        "content":      article.content,
        "excerpt":      article.excerpt,
        "status":       article.status,
        "author":       {"id": article.author.id, "name": article.author.full_name},
        "view_count":   article.view_count,
        "tags":         [{"id": t.id, "name": t.name, "slug": t.slug} for t in article.tags],
        "created_at":   article.created_at.isoformat(),
        "updated_at":   article.updated_at.isoformat(),
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "version_count": len(article.versions),
    }


@router.put("/{article_id}", response_model=dict)
def update_article(
    article_id: int,
    payload: ArticleUpdate,
    editor_id: int = Query(..., description="ID of the user making the edit"),
    db: Session = Depends(get_db),
):
    """Update an article and save a new version."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if payload.title:
        article.title = payload.title
        article.slug = make_unique_slug(db, payload.title)
    if payload.content:
        article.content = payload.content
    if payload.excerpt:
        article.excerpt = payload.excerpt
    if payload.tag_ids is not None:
        article.tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()

    article.updated_at = datetime.utcnow()
    save_version(db, article, saved_by=editor_id)
    db.commit()

    return {"id": article.id, "slug": article.slug, "message": "Article updated"}


@router.post("/{article_id}/publish", response_model=dict)
def publish_article(article_id: int, db: Session = Depends(get_db)):
    """Publish a draft article. Can only publish from 'draft' status."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.status == "published":
        raise HTTPException(status_code=400, detail="Article is already published")

    article.status = "published"
    article.published_at = datetime.utcnow()
    db.commit()

    return {"id": article.id, "status": "published", "published_at": article.published_at.isoformat()}


@router.post("/{article_id}/unpublish", response_model=dict)
def unpublish_article(article_id: int, db: Session = Depends(get_db)):
    """Move a published article back to draft."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    article.status = "draft"
    article.published_at = None
    db.commit()

    return {"id": article.id, "status": "draft"}


@router.get("/{article_id}/versions", response_model=dict)
def get_versions(article_id: int, db: Session = Depends(get_db)):
    """List all saved versions of an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    versions = sorted(article.versions, key=lambda v: v.version, reverse=True)
    return {
        "article_id": article_id,
        "current_title": article.title,
        "versions": [
            {
                "version":  v.version,
                "title":    v.title,
                "saved_by": v.saved_by,
                "saved_at": v.saved_at.isoformat(),
                "preview":  (v.content or "")[:150] + "...",
            }
            for v in versions
        ],
    }


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Soft-delete by setting status to 'archived'."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.status = "archived"
    db.commit()
