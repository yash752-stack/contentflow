"""
api/routes/search.py
Full-text search across articles using SQL LIKE with relevance scoring.
In production: replace with Elasticsearch or PostgreSQL full-text search.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from db.database import get_db, Article, Tag, article_tags
from typing import Optional

router = APIRouter()


def relevance_score(article, query: str) -> int:
    """Simple relevance: title match = 10pts, content match = 1pt."""
    q = query.lower()
    score = 0
    if q in article.title.lower():
        score += 10
    score += article.content.lower().count(q)
    return score


@router.get("/")
def search_articles(
    q:      str = Query(..., min_length=2, description="Search query"),
    status: Optional[str] = Query("published"),
    limit:  int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Full-text search across article titles and content.
    Results are ranked by relevance (title matches weighted higher).
    """
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    query_filter = or_(
        Article.title.ilike(f"%{q}%"),
        Article.content.ilike(f"%{q}%"),
        Article.excerpt.ilike(f"%{q}%"),
    )

    base_q = db.query(Article).filter(query_filter)
    if status:
        base_q = base_q.filter(Article.status == status)

    results = base_q.limit(limit * 2).all()  # fetch extra, then re-rank

    ranked = sorted(results, key=lambda a: relevance_score(a, q), reverse=True)
    ranked = ranked[:limit]

    return {
        "query":        q,
        "total_found":  len(ranked),
        "results": [
            {
                "id":          a.id,
                "title":       a.title,
                "slug":        a.slug,
                "excerpt":     a.excerpt,
                "status":      a.status,
                "tags":        [t.name for t in a.tags],
                "relevance":   relevance_score(a, q),
                "view_count":  a.view_count,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
            for a in ranked
        ],
    }


@router.get("/trending")
def trending_articles(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return most-viewed published articles."""
    articles = db.query(Article)\
                 .filter(Article.status == "published")\
                 .order_by(Article.view_count.desc())\
                 .limit(limit)\
                 .all()
    return [
        {"id": a.id, "title": a.title, "slug": a.slug,
         "view_count": a.view_count, "tags": [t.name for t in a.tags]}
        for a in articles
    ]
