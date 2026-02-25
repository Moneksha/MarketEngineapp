import asyncio
from datetime import datetime
from app.services.kite_service import kite_service
from app.strategies.ema_21_option_selling import EMA21OptionSelling
from app.utils.indicators import ema

async def main():
    s = EMA21OptionSelling()
    df = await kite_service.get_nifty_candles("minute", days=1)
    print("Filtered Candles:")
    print("Last 5 candles from Kite Engine:")
    print(df[-5:])
    
    # Run the strategy on it
    import pandas as pd
    pdf = pd.DataFrame(df)
    pdf["date"] = pd.to_datetime(pdf["date"])
    pdf.set_index("date", inplace=True)
    
    res = s.run(pdf)
    print("Result of run() ==>", res)
    
    # Print the specific rows and ema calculated
    pdf["ema21"] = ema(pdf["close"], 21)
    
    target_time_start = pd.to_datetime("2026-02-23 10:20:00+05:30")
    target_time_end = pd.to_datetime("2026-02-23 10:25:00+05:30")
    print("10:20 to 10:25 rows with EMA21:")
    print(pdf.loc[target_time_start:target_time_end, ["close", "ema21"]])

if __name__ == "__main__":
    asyncio.run(main())
