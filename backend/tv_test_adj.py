import pandas as pd
from app.services.backtest_engine import _fetch_ohlcv

# September 2017 Bonus issue check
df = _fetch_ohlcv("RELIANCE", "2017-09-01", "2017-09-15")
df.index = df.index.tz_localize(None).tz_localize("Asia/Kolkata")
df_ist = df.between_time("09:15", "15:29")
df_ist["trade_date"] = df_ist.index.date
resampled = df_ist.groupby("trade_date").agg({"close": "last"})
print(resampled)
