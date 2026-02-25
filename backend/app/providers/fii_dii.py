"""
Pluggable FII/DII data provider.
Currently returns mock data. Replace get_fii_dii_data() with
real NSE / Trendlyne API call when ready.
"""
from datetime import date
from typing import Optional
import httpx
from loguru import logger


async def get_fii_dii_data(for_date: Optional[date] = None) -> dict:
    """
    Returns FII / DII cash market activity.
    Mock data currently — replace with real API call.
    """
    # TODO: Replace with real NSE / Trendlyne API
    # Example real endpoint:
    # https://www.nseindia.com/api/fiidiiTradeReact?date=19-02-2026
    try:
        return {
            "date": str(for_date or date.today()),
            "fii": {
                "buy": 18543.25,
                "sell": 16821.10,
                "net": 1722.15,
                "label": "FII Buyers",
            },
            "dii": {
                "buy": 12840.50,
                "sell": 14311.80,
                "net": -1471.30,
                "label": "DII Sellers",
            },
            "net_institutional": 250.85,
            "bias": "BULLISH",           # net FII positive
            "source": "mock",
        }
    except Exception as e:
        logger.warning(f"FII/DII provider error: {e}")
        return {"source": "mock", "bias": "NEUTRAL", "fii": {}, "dii": {}}
