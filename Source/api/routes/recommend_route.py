"""
api/routes/recommend_route.py

FastAPI router for recommendation endpoints.
"""

from fastapi import APIRouter
from api.schemas import RecommendRequest, RecommendResponse
from api.core.recommend_logic import generate_recommendations

router = APIRouter(tags=["Recommendations"])

@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    """
    Full AI-powered course recommendation pipeline.
    """
    return await generate_recommendations(req)
