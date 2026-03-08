import asyncio
from httpx import AsyncClient
from app.main import app

async def test_api():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Mock auth for test
        from app.services.kite_service import kite_service
        kite_service.set_access_token("test_token")
        
        # We also need mock to return a lightweight historical payload if DB empty
        import app.config.settings as settings
        settings.settings.mock_mode = True 
        
        print("Fetching 5minute NIFTY 50...")
        response = await ac.get("/api/market/ohlc/NIFTY%2050", params={"interval": "5minute"})
        
        if response.status_code == 200:
            data = response.json()
            candles = data.get("candles", [])
            print(f"Success! Returned {len(candles)} candles.")
            if candles:
                c1 = candles[0]
                print(f"First candle: {c1.get('date')} | Close: {c1.get('close')} | EMA9: {c1.get('ema_9')} | EMA21: {c1.get('ema_21')}")
                
                clast = candles[-1]
                print(f"Last candle: {clast.get('date')} | Close: {clast.get('close')} | EMA9: {clast.get('ema_9')} | EMA21: {clast.get('ema_21')}")
        else:
            print(f"Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_api())
