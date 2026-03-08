import pandas as pd
from datetime import datetime

# Sample 1-minute data for a couple of days, including overnight times
dates = pd.date_range(start="2023-01-01 09:15:00", periods=60*24*2, freq='1min', tz='Asia/Kolkata')
df = pd.DataFrame({"close": range(len(dates))}, index=dates)

# What does '1D' resampling do by default here?
resampled = df.resample('1D', label='right', closed='right').agg({'close': 'last'})
print(resampled.head())
