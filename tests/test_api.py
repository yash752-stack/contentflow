"""
tests/test_api.py
Pytest test suite for ContentFlow CMS API.
Run: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.main import app
from db.database import Base, engine, SessionLocal, User, Tag

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Seed a test user and tag
    if not db.query(User).filter(User.username == "testuser").first():
        u = User(username="testuser", email="test@test.com", full_name="Test User", role="editor")
        db.add(u)
    if not db.query(Tag).filter(Tag.slug == "tech").first():
        t = Tag(name="Tech", slug="tech")
        db.add(t)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


# ── HEALTH CHECK ──────────────────────────────────────────────────────────

def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ── USERS ─────────────────────────────────────────────────────────────────

def test_create_user():
    r = client.post("/api/v1/users/", json={
        "username": "yash", "email": "yash@test.com",
        "full_name": "Yash Chaudhary", "role": "editor"
    })
    assert r.status_code == 201
    assert r.json()["username"] == "yash"

def test_duplicate_email_rejected():
    client.post("/api/v1/users/", json={
        "username": "user1", "email": "dup@test.com", "full_name": "User One"
    })
    r = client.post("/api/v1/users/", json={
        "username": "user2", "email": "dup@test.com", "full_name": "User Two"
    })
    assert r.status_code == 400

def test_get_nonexistent_user():
    r = client.get("/api/v1/users/9999")
    assert r.status_code == 404


# ── ARTICLES ──────────────────────────────────────────────────────────────

def _get_author_id():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "testuser").first()
    uid = user.id
    db.close()
    return uid

def test_create_article():
    uid = _get_author_id()
    r = client.post("/api/v1/articles/", json={
        "title": "My First Article",
        "content": "This is the content of the article. " * 10,
        "author_id": uid,
        "tag_ids": [],
    })
    assert r.status_code == 201
    assert r.json()["status"] == "draft"

def test_article_slug_generated():
    uid = _get_author_id()
    r = client.post("/api/v1/articles/", json={
        "title": "Slug Test Article",
        "content": "Some content here. " * 10,
        "author_id": uid,
    })
    assert r.status_code == 201
    assert "slug-test-article" in r.json()["slug"]

def test_get_article_by_slug():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "Fetch This Article",
        "content": "Fetchable content. " * 10,
        "author_id": uid,
    })
    slug = create_r.json()["slug"]
    r = client.get(f"/api/v1/articles/{slug}")
    assert r.status_code == 200
    assert r.json()["title"] == "Fetch This Article"

def test_view_count_increments():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "View Count Test",
        "content": "Content for view count test. " * 10,
        "author_id": uid,
    })
    slug = create_r.json()["slug"]
    client.get(f"/api/v1/articles/{slug}")
    r2 = client.get(f"/api/v1/articles/{slug}")
    assert r2.json()["view_count"] >= 1

def test_publish_article():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "Article To Publish",
        "content": "Publish me. " * 10,
        "author_id": uid,
    })
    article_id = create_r.json()["id"]
    r = client.post(f"/api/v1/articles/{article_id}/publish")
    assert r.status_code == 200
    assert r.json()["status"] == "published"
    assert r.json()["published_at"] is not None

def test_double_publish_rejected():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "Double Publish Test",
        "content": "Publish content. " * 10,
        "author_id": uid,
    })
    aid = create_r.json()["id"]
    client.post(f"/api/v1/articles/{aid}/publish")
    r = client.post(f"/api/v1/articles/{aid}/publish")
    assert r.status_code == 400

def test_version_created_on_update():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "Version Test Article",
        "content": "Original content. " * 10,
        "author_id": uid,
    })
    aid = create_r.json()["id"]
    client.put(f"/api/v1/articles/{aid}?editor_id={uid}", json={"content": "Updated content. " * 10})
    r = client.get(f"/api/v1/articles/{aid}/versions")
    assert r.status_code == 200
    assert len(r.json()["versions"]) >= 1

def test_delete_archives_article():
    uid = _get_author_id()
    create_r = client.post("/api/v1/articles/", json={
        "title": "Article To Archive",
        "content": "Archive me. " * 10,
        "author_id": uid,
    })
    slug = create_r.json()["slug"]
    aid = create_r.json()["id"]
    client.delete(f"/api/v1/articles/{aid}")
    r = client.get(f"/api/v1/articles/{slug}")
    assert r.json()["status"] == "archived"


# ── SEARCH ────────────────────────────────────────────────────────────────

def test_search_returns_results():
    uid = _get_author_id()
    client.post("/api/v1/articles/", json={
        "title": "Python Microservices Guide",
        "content": "Python is great for microservices. " * 20,
        "author_id": uid,
    })
    aid = client.post("/api/v1/articles/", json={
        "title": "Python Microservices Guide 2",
        "content": "Python is great for microservices. " * 20,
        "author_id": uid,
    }).json()["id"]
    client.post(f"/api/v1/articles/{aid}/publish")
    r = client.get("/api/v1/search/?q=Python&status=published")
    assert r.status_code == 200

def test_search_requires_min_length():
    r = client.get("/api/v1/search/?q=a")
    assert r.status_code == 422


# ── AI ASSISTANT ──────────────────────────────────────────────────────────

def test_content_analysis():
    r = client.post("/api/v1/ai/analyse", json={
        "title": "The Complete Guide to Python for Web Development",
        "content": "Python is one of the most popular languages for web development. " * 30,
        "target_keyword": "python",
    })
    assert r.status_code == 200
    data = r.json()
    assert "seo" in data
    assert "reading_ease" in data
    assert "word_count" in data
    assert data["word_count"] > 0

def test_tag_suggestions():
    r = client.post("/api/v1/ai/suggest-tags", json={
        "title": "Machine Learning in Python",
        "content": "Machine learning with Python and scikit-learn is powerful. " * 10,
        "max_tags": 5,
    })
    assert r.status_code == 200
    assert len(r.json()["suggested_tags"]) <= 5

def test_headline_variants():
    r = client.post("/api/v1/ai/headline-variants", json={
        "topic": "artificial intelligence in journalism",
        "style": "listicle",
    })
    assert r.status_code == 200
    assert len(r.json()["variants"]) == 5
