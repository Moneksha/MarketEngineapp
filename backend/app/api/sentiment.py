"""
Sentiment API — GET /api/sentiment
Returns composite market sentiment score + per-factor breakdown.
"""
from fastapi import APIRouter
from loguru import logger
from app.services.sentiment_service import compute_sentiment

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


@router.get("")
async def get_sentiment():
    """Compute and return the composite sentiment score."""
    try:
        result = await compute_sentiment()
        return result
    except Exception as e:
        logger.error(f"Sentiment API error: {e}")
        return {
            "final_score": 0.0,
            "label": "Neutral",
            "factors": [],
            "error": str(e),
        }
