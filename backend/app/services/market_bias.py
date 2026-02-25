"""
Market Bias Engine
Determines Bullish / Bearish / Sideways bias from:
  - FII/DII net activity
  - News sentiment score
  - Heavyweight stock contributions
  - NIFTY % change
"""
from typing import Dict, Any
from loguru import logger
from app.providers.fii_dii import get_fii_dii_data
from app.providers.news_sentiment import get_news_sentiment


async def compute_market_bias(
    nifty_change_pct: float,
    heavyweights: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute overall market bias and return structured summary.
    """
    fii_dii = await get_fii_dii_data()
    news = await get_news_sentiment()

    # ---- Scoring (each component gives -1, 0, or +1) ----
    score = 0
    reasons = []

    # 1. NIFTY trend
    if nifty_change_pct > 0.3:
        score += 1
        reasons.append(f"NIFTY up {nifty_change_pct:.2f}% — bullish momentum")
    elif nifty_change_pct < -0.3:
        score -= 1
        reasons.append(f"NIFTY down {nifty_change_pct:.2f}% — bearish pressure")
    else:
        reasons.append("NIFTY range-bound — sideways market")

    # 2. FII/DII net
    fii_net = fii_dii.get("fii", {}).get("net", 0)
    dii_net = fii_dii.get("dii", {}).get("net", 0)
    if fii_net > 500:
        score += 1
        reasons.append(f"FII net buyers ₹{fii_net:.0f} Cr — institutional support")
    elif fii_net < -500:
        score -= 1
        reasons.append(f"FII net sellers ₹{abs(fii_net):.0f} Cr — institutional selling")

    # 3. News sentiment
    news_score = news.get("score", 0)
    if news_score > 0.3:
        score += 1
        reasons.append("News sentiment POSITIVE — market-friendly headlines")
    elif news_score < -0.3:
        score -= 1
        reasons.append("News sentiment NEGATIVE — cautious market")
    else:
        reasons.append("News sentiment NEUTRAL")

    # 4. Heavyweight contribution
    positive_hws = sum(1 for h in heavyweights.values() if h.get("change_pct", 0) > 0)
    if positive_hws >= 4:
        score += 1
        reasons.append(f"{positive_hws}/5 heavyweights in green — broad-based rally")
    elif positive_hws <= 1:
        score -= 1
        reasons.append(f"Only {positive_hws}/5 heavyweights in green — broad selling")

    # ---- Determine bias ----
    if score >= 2:
        bias = "BULLISH"
        bias_color = "#00ff88"
    elif score <= -2:
        bias = "BEARISH"
        bias_color = "#ff4757"
    else:
        bias = "SIDEWAYS"
        bias_color = "#ffa502"

    return {
        "bias": bias,
        "bias_color": bias_color,
        "score": score,
        "reasons": reasons,
        "nifty_change_pct": nifty_change_pct,
        "fii_dii": fii_dii,
        "news_sentiment": news,
        "heavyweights_green": positive_hws,
    }
