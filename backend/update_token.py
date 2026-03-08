import sys
import os
import asyncio
from dotenv import load_dotenv

# We load settings directly, but first load .env to ensure we have the latest
load_dotenv(override=True)

# Important: Append the backend folder to sys.path so we can import app modules properly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config.settings import settings
from kiteconnect import KiteConnect

async def main():
    if len(sys.argv) < 2:
        print("Usage: python update_token.py <request_token>")
        sys.exit(1)

    request_token = sys.argv[1]
    
    kite = KiteConnect(api_key=settings.kite_api_key)
    
    try:
        print("Generating session...")
        data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
        access_token = data["access_token"]
        
        # Save to .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        
        with open(env_path, "r") as f:
            lines = f.readlines()
            
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("KITE_ACCESS_TOKEN="):
                    f.write(f"KITE_ACCESS_TOKEN={access_token}\n")
                else:
                    f.write(line)
                    
        print(f"Successfully updated KITE_ACCESS_TOKEN in {env_path}")
        sys.exit(0)
                        
    except Exception as e:
        print(f"Error exchanging token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
