"""
api/main.py

FastAPI application — Intelligent University Course Finder.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.recommend_route import router as recommend_router

app = FastAPI(
    title="Intelligent University Course Finder",
    description="AI-powered multimodal course discovery and recommendation system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
def health():
    """Liveness check."""
    return {"status": "ok", "service": "University Course Finder API"}

# Register routes
app.include_router(recommend_router)
