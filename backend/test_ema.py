import pandas as pd
from app.services.backtest_engine import _calc_ema

def main():
    # Create sample synthetic price series
    prices = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0])
    print("Prices:")
    print(prices)
    
    # Calculate EMA with period = 5
    # The first 4 rows should be NaN. The 5th row (index 4) should be the first valid EMA
    ema = _calc_ema(prices, 5)
    print("\nEMA (period=5):")
    print(ema)
    
if __name__ == "__main__":
    main()
