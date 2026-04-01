# ContentFlow — AI-Powered Headless CMS API

> Built specifically to demonstrate the skills required for Publive's Software Developer Intern role.

A production-style headless CMS backend with an AI content assistant — the exact type of system Publive builds for 150+ digital media clients

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI (Python) |
| Database | PostgreSQL (SQLite for dev) |
| ORM | SQLAlchemy |
| Containerisation | Docker + Docker Compose |
| Reverse Proxy | Nginx |
| Testing | Pytest + FastAPI TestClient |
| Deployment | AWS-ready (ECS / EC2) |

## Architecture

```
Client (React.js)
      │
      ▼
   Nginx (reverse proxy, port 80)
      │
      ▼
  FastAPI (port 8000, 2 workers)
      │
  ┌───┴────────────────────┐
  │                        │
SQLite/PostgreSQL     In-memory cache
(articles, users,    (rate limiter)
 tags, versions)
```

## Features

### Core CMS
- Full CRUD for articles with **automatic slug generation**
- **Publishing workflow**: draft → published → archived
- **Version history** — every save creates a new version row
- Threaded comments with `parent_id` for nested replies
- Many-to-many article ↔ tag relationships
- Pagination on all list endpoints

### AI Content Assistant (`/api/v1/ai/`)
- **Content analyser** — SEO score (A/B/C/D grade), readability (Flesch score), keyword density, auto-excerpt
- **Tag suggester** — keyword extraction to recommend relevant tags
- **Headline variants** — generate 5 A/B-testable titles in 4 styles (news, listicle, how-to, question)
- **Readability tips** — editorial guidelines for content teams

### Engineering Patterns
- Middleware for request timing headers
- CORS configured for React frontend
- Health check endpoint (`/health`) for Docker + load balancer
- Connection pooling (SQLAlchemy pool_size=10)
- Soft deletes (archived status) instead of hard deletes
- Rate limiter service (token bucket, Redis-ready)

## Quick Start

```bash
# Clone and run locally (SQLite, no Docker needed)
git clone https://github.com/yash752-stack/contentflow.git
cd contentflow
pip install -r requirements.txt
uvicorn api.main:app --reload

# API docs at:
open http://localhost:8000/docs
```

## Docker (full stack with PostgreSQL + Nginx)

```bash
docker-compose up --build
# API: http://localhost:80/api/v1/
# Docs: http://localhost:80/docs
```

## Run Tests

```bash
pytest tests/ -v
```

## API Endpoints

### Articles
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/articles/` | List articles (paginated, filterable) |
| POST | `/api/v1/articles/` | Create article (draft) |
| GET | `/api/v1/articles/{slug}` | Get article + increment view count |
| PUT | `/api/v1/articles/{id}` | Update + save version |
| POST | `/api/v1/articles/{id}/publish` | Publish draft |
| POST | `/api/v1/articles/{id}/unpublish` | Move back to draft |
| GET | `/api/v1/articles/{id}/versions` | Version history |
| DELETE | `/api/v1/articles/{id}` | Soft delete (archive) |

### AI Assistant
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/ai/analyse` | Full content + SEO analysis |
| POST | `/api/v1/ai/suggest-tags` | Keyword-based tag suggestions |
| POST | `/api/v1/ai/headline-variants` | Generate 5 headline variants |
| GET | `/api/v1/ai/readability-tips` | Editorial guidelines |

### Search
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/search/?q=keyword` | Full-text search with relevance ranking |
| GET | `/api/v1/search/trending` | Most-viewed published articles |

## What This Demonstrates

Directly maps to Publive's requirements:

- **Python** — FastAPI, SQLAlchemy, Pydantic, pytest
- **SQL databases** — Relational schema, foreign keys, many-to-many, indexing
- **System design** — Microservice-ready API, separation of concerns, middleware
- **Docker / Nginx** — Full containerised stack with reverse proxy
- **AWS-ready** — Health checks, environment variables, connection pooling
- **REST API design** — Proper HTTP verbs, status codes, pagination
- **AI integration** — Content intelligence layer relevant to Publive's DXP

---

**Author:** Yash Chaudhary | [github.com/yash752-stack](https://github.com/yash752-stack)
