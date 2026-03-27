"""
ContentFlow — AI-Powered Headless CMS API
A production-style CMS backend demonstrating microservices patterns,
REST API design, SQL/NoSQL databases, and AI content assistance.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from api.routes import articles, users, tags, search, ai_assistant
from db.database import engine, Base
from services.rate_limiter import RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ContentFlow CMS API",
    description="AI-Powered Headless CMS — built for digital media teams",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (React frontend integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://contentflow.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    logger.info(f"{request.method} {request.url.path} — {process_time*1000:.1f}ms")
    return response

# Routers
app.include_router(users.router,         prefix="/api/v1/users",     tags=["Users"])
app.include_router(articles.router,      prefix="/api/v1/articles",  tags=["Articles"])
app.include_router(tags.router,          prefix="/api/v1/tags",      tags=["Tags"])
app.include_router(search.router,        prefix="/api/v1/search",    tags=["Search"])
app.include_router(ai_assistant.router,  prefix="/api/v1/ai",        tags=["AI Assistant"])


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for load balancer / Docker healthcheck."""
    return {"status": "healthy", "service": "contentflow-api", "version": "1.0.0"}


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "ContentFlow CMS API",
        "docs": "/docs",
        "health": "/health",
    }
