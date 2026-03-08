from app.services.backtest_engine import run_backtest
import json

if __name__ == "__main__":
    print("Running backtest for RELIANCE...")
    result = run_backtest(
        symbol="RELIANCE",
        ema_period=9,
        from_date="2020-01-01",
        to_date="2024-01-01",
        timeframe="15m"
    )
    
    # Remove the exhaustive lists for an easier read
    if "equity_curve" in result:
        result["equity_curve"] = f"[{len(result['equity_curve'])} data points]"
    if "trades" in result:
        result["trades"] = f"[{len(result['trades'])} trades]"
        
    print(json.dumps(result, indent=2))
