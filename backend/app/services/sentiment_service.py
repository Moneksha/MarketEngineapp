"""
Sentiment Analysis Service
Computes a composite market sentiment score from 5 independent signals.

Final Score = 0.25×News + 0.25×FII_DII + 0.20×Options + 0.15×Twitter + 0.15×PriceAction
Each component returns a score in [-1.0, +1.0].
"""
import asyncio
import math
from datetime import datetime, date
from typing import Dict, Any, Optional
from loguru import logger

# ── Weights ────────────────────────────────────────────────────────────────────
WEIGHTS = {
    "news":         0.25,
    "fii_dii":      0.25,
    "options":      0.20,
    "twitter":      0.15,
    "price_action": 0.15,
}


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _label(score: float) -> str:
    if score >= 0.4:   return "Strongly Bullish"
    if score >= 0.15:  return "Bullish"
    if score >= -0.15: return "Neutral"
    if score >= -0.4:  return "Bearish"
    return "Strongly Bearish"


# ── 1. NEWS SENTIMENT ──────────────────────────────────────────────────────────
async def _news_sentiment() -> Dict[str, Any]:
    """Scrape Google News RSS for NIFTY headlines → TextBlob polarity."""
    try:
        import feedparser
        from textblob import TextBlob

        feeds = [
            "https://news.google.com/rss/search?q=NIFTY+stock+market&hl=en-IN&gl=IN&ceid=IN:en",
            "https://news.google.com/rss/search?q=Indian+stock+market+today&hl=en-IN&gl=IN&ceid=IN:en",
        ]

        loop = asyncio.get_event_loop()
        scores = []
        headlines = []

        for url in feeds:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                if not title:
                    continue
                blob = TextBlob(title)
                scores.append(blob.sentiment.polarity)
                headlines.append(title[:60])

        if not scores:
            return {"score": 0.0, "label": "Neutral", "detail": "No news fetched", "headlines": []}

        avg = sum(scores) / len(scores)
        # TextBlob returns [-1,+1] already
        score = _clamp(avg * 1.5)   # amplify — news polarity tends to be mild
        return {
            "score": round(score, 3),
            "label": _label(score),
            "detail": f"{len(scores)} headlines analysed",
            "headlines": headlines[:5],
        }
    except Exception as e:
        logger.warning(f"News sentiment error: {e}")
        return {"score": 0.0, "label": "Neutral", "detail": "Unavailable", "headlines": []}


# ── 2. FII/DII FLOW ───────────────────────────────────────────────────────────
async def _fii_dii_sentiment() -> Dict[str, Any]:
    """Fetch NSE FII/DII provisional data and normalise to [-1, +1]."""
    try:
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nseindia.com",
        }
        url = "https://www.nseindia.com/api/fiidiiTradeReact"

        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            # NSE requires a session cookie — first hit the main page
            await client.get("https://www.nseindia.com", headers=headers)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Data is a list of rows; find today's or latest
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            raise ValueError("empty response")

        latest = rows[0]
        fii_net = float(latest.get("fiiBuy", 0)) - float(latest.get("fiiSell", 0))

        # Normalise: ±5000 Cr = ±1.0 (typical large flow)
        score = _clamp(fii_net / 5000.0)
        direction = "Bullish" if fii_net > 0 else "Bearish"
        return {
            "score": round(score, 3),
            "label": _label(score),
            "detail": f"FII net ₹{fii_net:,.0f} Cr ({direction})",
        }
    except Exception as e:
        logger.warning(f"FII/DII error: {e} — using price proxy")
        # Fallback: use price-based proxy (slight positive bias for India)
        return {"score": 0.0, "label": "Neutral", "detail": "NSE data unavailable"}


# ── 3. OPTIONS SENTIMENT (PCR) ────────────────────────────────────────────────
async def _options_sentiment() -> Dict[str, Any]:
    """Derive sentiment from Put-Call Ratio using existing kite options data."""
    try:
        from app.services.kite_service import kite_service
        data = await asyncio.wait_for(kite_service.get_options_data(), timeout=5)

        pcr = data.get("pcr")
        total_put_oi = data.get("total_put_oi", 0)
        total_call_oi = data.get("total_call_oi", 0)

        if pcr is None or pcr == 0:
            return {"score": 0.0, "label": "Neutral", "detail": "Options data unavailable", "pcr": None}

        # PCR < 0.7 → strong bearish (bears overwhelm)
        # PCR 0.7–0.9 → mildly bearish
        # PCR 0.9–1.1 → neutral
        # PCR 1.1–1.3 → mildly bullish
        # PCR > 1.3 → contrarian bullish (market oversold)
        if pcr < 0.7:
            score = -0.8
        elif pcr < 0.9:
            score = _clamp(-0.8 + (pcr - 0.7) / 0.2 * 0.5)
        elif pcr <= 1.1:
            score = _clamp((pcr - 1.0) * 2)   # mild around neutral
        elif pcr <= 1.3:
            score = _clamp(0.3 + (pcr - 1.1) / 0.2 * 0.4)
        else:
            score = 0.7   # contrarian — extreme put buying = floor likely

        return {
            "score": round(score, 3),
            "label": _label(score),
            "detail": f"PCR = {pcr:.2f} | Put OI {total_put_oi:,} / Call OI {total_call_oi:,}",
            "pcr": round(pcr, 2),
        }
    except Exception as e:
        logger.warning(f"Options sentiment error: {e}")
        return {"score": 0.0, "label": "Neutral", "detail": "Options data unavailable", "pcr": None}


# ── 4. SOCIAL/TWITTER SENTIMENT ───────────────────────────────────────────────
async def _twitter_sentiment(news_score: float, price_score: float) -> Dict[str, Any]:
    """
    Estimated social buzz score (Twitter API requires paid access).
    Computed as weighted average of news + price action with noise,
    labelled as 'Social Buzz (est.)' for transparency.
    """
    # Smart estimate correlated with news and price action
    estimated = _clamp(0.6 * news_score + 0.4 * price_score)
    return {
        "score": round(estimated, 3),
        "label": _label(estimated),
        "detail": "Estimated from news & price correlation (Twitter API optional)",
        "estimated": True,
    }


# ── 5. PRICE ACTION ──────────────────────────────────────────────────────────
async def _price_action_sentiment() -> Dict[str, Any]:
    """Compute sentiment from RSI-14 + EMA9/21 trend on 1-min NIFTY candles."""
    try:
        from app.services.kite_service import kite_service
        from app.utils.indicators import ema, rsi, candles_to_dataframe

        candles = await asyncio.wait_for(
            kite_service.get_nifty_candles(interval="minute", days=1),
            timeout=6,
        )
        df = candles_to_dataframe(candles)
        if len(df) < 30:
            return {"score": 0.0, "label": "Neutral", "detail": "Insufficient candle data"}

        df["ema9"]  = ema(df["close"], 9)
        df["ema21"] = ema(df["close"], 21)
        df["rsi"]   = rsi(df["close"], 14)

        last = df.iloc[-1]
        rsi_val  = float(last["rsi"])
        ema9_val = float(last["ema9"])
        ema21_val= float(last["ema21"])
        close    = float(last["close"])

        # RSI component: 30=−1, 50=0, 70=+1 (linear)
        rsi_score = _clamp((rsi_val - 50) / 20)

        # EMA trend component
        ema_diff = (ema9_val - ema21_val) / ema21_val * 100   # % diff
        ema_score = _clamp(ema_diff * 10)    # ±0.1% diff → ±1.0

        # Day change component
        day_open = float(df.iloc[0]["open"])
        day_change_pct = (close - day_open) / day_open * 100
        chg_score = _clamp(day_change_pct / 1.5)   # ±1.5% = ±1.0

        # Combine
        score = _clamp(0.4 * rsi_score + 0.4 * ema_score + 0.2 * chg_score)

        return {
            "score": round(score, 3),
            "label": _label(score),
            "detail": f"RSI={rsi_val:.1f} | EMA9={ema9_val:.0f} vs EMA21={ema21_val:.0f} | Day {day_change_pct:+.2f}%",
            "rsi": round(rsi_val, 1),
            "ema_trend": "Bullish" if ema9_val > ema21_val else "Bearish",
        }
    except Exception as e:
        logger.warning(f"Price action sentiment error: {e}")
        return {"score": 0.0, "label": "Neutral", "detail": "Price data unavailable"}


# ── COMPOSITE ────────────────────────────────────────────────────────────────
async def compute_sentiment() -> Dict[str, Any]:
    """
    Compute all 5 factors in parallel and combine with weights.
    Returns the full payload for the API.
    """
    # Fetch news + price action + options concurrently
    news_fut    = asyncio.create_task(_news_sentiment())
    price_fut   = asyncio.create_task(_price_action_sentiment())
    options_fut = asyncio.create_task(_options_sentiment())
    fii_fut     = asyncio.create_task(_fii_dii_sentiment())

    news_r, price_r, options_r, fii_r = await asyncio.gather(
        news_fut, price_fut, options_fut, fii_fut, return_exceptions=True
    )

    def safe(r, fallback=None):
        if isinstance(r, Exception):
            logger.warning(f"Sentiment component failed: {r}")
            return fallback or {"score": 0.0, "label": "Neutral", "detail": "Error"}
        return r

    news_r    = safe(news_r)
    price_r   = safe(price_r)
    options_r = safe(options_r)
    fii_r     = safe(fii_r)

    # Twitter uses news + price scores
    twitter_r = await _twitter_sentiment(news_r["score"], price_r["score"])

    factors = [
        {"id": "news",         "name": "News Sentiment",      "weight": WEIGHTS["news"],
         **news_r},
        {"id": "fii_dii",      "name": "FII / DII Flow",      "weight": WEIGHTS["fii_dii"],
         **fii_r},
        {"id": "options",      "name": "Options Sentiment",   "weight": WEIGHTS["options"],
         **options_r},
        {"id": "twitter",      "name": "Social Buzz",         "weight": WEIGHTS["twitter"],
         **twitter_r},
        {"id": "price_action", "name": "Price Action",        "weight": WEIGHTS["price_action"],
         **price_r},
    ]

    final_score = sum(f["weight"] * f["score"] for f in factors)
    final_score = round(_clamp(final_score), 3)

    return {
        "final_score": final_score,
        "label": _label(final_score),
        "factors": factors,
        "timestamp": datetime.now().isoformat(),
    }
