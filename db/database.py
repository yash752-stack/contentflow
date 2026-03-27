"""
db/database.py — SQLAlchemy setup with PostgreSQL (falls back to SQLite for dev)
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./contentflow.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,      # connection health check before use
    pool_size=10,            # connection pool size
    max_overflow=20,         # extra connections beyond pool_size
) if "sqlite" not in DATABASE_URL else create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ASSOCIATION TABLE (many-to-many: articles ↔ tags) ─────────────────────
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id"), primary_key=True),
    Column("tag_id",     Integer, ForeignKey("tags.id"),     primary_key=True),
)


# ── MODELS ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String(50), unique=True, index=True, nullable=False)
    email      = Column(String(120), unique=True, index=True, nullable=False)
    full_name  = Column(String(100), nullable=False)
    role       = Column(String(20), default="editor")   # editor | admin | viewer
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles   = relationship("Article", back_populates="author")


class Article(Base):
    __tablename__ = "articles"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(300), nullable=False, index=True)
    slug         = Column(String(320), unique=True, index=True, nullable=False)
    content      = Column(Text, nullable=False)
    excerpt      = Column(Text)
    status       = Column(String(20), default="draft")  # draft | published | archived
    author_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    view_count   = Column(Integer, default=0)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    author       = relationship("User", back_populates="articles")
    tags         = relationship("Tag", secondary=article_tags, back_populates="articles")
    versions     = relationship("ArticleVersion", back_populates="article")
    comments     = relationship("Comment", back_populates="article")


class ArticleVersion(Base):
    """Version history — every save creates a new version row."""
    __tablename__ = "article_versions"

    id         = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    version    = Column(Integer, nullable=False)
    title      = Column(String(300))
    content    = Column(Text)
    saved_by   = Column(Integer, ForeignKey("users.id"))
    saved_at   = Column(DateTime, default=datetime.utcnow)

    article    = relationship("Article", back_populates="versions")


class Tag(Base):
    __tablename__ = "tags"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(50), unique=True, index=True, nullable=False)
    slug       = Column(String(60), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles   = relationship("Article", secondary=article_tags, back_populates="tags")


class Comment(Base):
    __tablename__ = "comments"

    id         = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    parent_id  = Column(Integer, ForeignKey("comments.id"), nullable=True)  # threaded comments
    author     = Column(String(100), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    article    = relationship("Article", back_populates="comments")
    replies    = relationship("Comment", backref="parent", remote_side="Comment.id")


# ── DB DEPENDENCY ──────────────────────────────────────────────────────────

def get_db():
    """FastAPI dependency — yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
