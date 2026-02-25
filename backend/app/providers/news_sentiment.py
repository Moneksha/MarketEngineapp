"""
Pluggable News Sentiment provider.
Currently returns mock data. Replace with real NLP / news API.
"""
from typing import Optional
from loguru import logger


async def get_news_sentiment() -> dict:
    """
    Returns market news sentiment.
    Mock data — replace with Benzinga, NewsAPI + VADER, or Gemini NLP.
    """
    # TODO: Integrate real news API + sentiment analysis
    # e.g., NewsAPI + VADER, or Gemini Flash for real-time sentiment
    try:
        return {
            "overall": "POSITIVE",
            "score": 0.62,            # -1.0 to 1.0
            "headlines": [
                {
                    "title": "NIFTY surges on strong FII buying in IT stocks",
                    "sentiment": "POSITIVE",
                    "impact": "HIGH",
                    "source": "Economic Times",
                },
                {
                    "title": "RBI keeps repo rate unchanged at 6.5%",
                    "sentiment": "NEUTRAL",
                    "impact": "MEDIUM",
                    "source": "Business Standard",
                },
                {
                    "title": "Global cues muted; US markets closed flat",
                    "sentiment": "NEUTRAL",
                    "impact": "LOW",
                    "source": "LiveMint",
                },
            ],
            "source": "mock",
        }
    except Exception as e:
        logger.warning(f"News sentiment provider error: {e}")
        return {"overall": "NEUTRAL", "score": 0.0, "headlines": [], "source": "mock"}
