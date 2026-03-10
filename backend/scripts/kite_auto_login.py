import os
import sys
import pyotp
import asyncio
import urllib.parse
import httpx
from loguru import logger
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

USER_ID = os.getenv("KITE_USER_ID", "")
PASSWORD = os.getenv("KITE_PASSWORD", "")
TOTP_SECRET = os.getenv("KITE_TOTP_SECRET", "")
API_KEY = os.getenv("KITE_API_KEY", "")

BACKEND_URL = os.getenv("BACKEND_CALLBACK_URL", "https://marketengine.in/api/market/auth/zerodha/callback")


async def auto_login():
    """Automates the Kite Connect login process to fetch the daily request token."""
    logger.add("logs/kite_auto_login.log", rotation="5 MB", retention="10 days")
    logger.info("Starting automated Kite login process...")

    if not all([USER_ID, PASSWORD, TOTP_SECRET, API_KEY]):
        logger.error("Missing credentials. Please ensure KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET, and KITE_API_KEY are set in the .env file.")
        sys.exit(1)

    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={API_KEY}"
    
    async with async_playwright() as p:
        # Launch headless browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            logger.info("Opening Kite login page...")
            await page.goto(login_url)

            # 1. Enter User ID and Password
            logger.info("Entering User ID and Password...")
            await page.fill('input[type="text"][id="userid"]', USER_ID)
            await page.fill('input[type="password"][id="password"]', PASSWORD)
            await page.click('button[type="submit"]')

            # 2. Wait for TOTP field (usually an input for app code)
            logger.info("Waiting for TOTP/App Code field...")
            # Zerodha's TOTP input often has id="userid" replaced by the TOTP input or specific class
            totp_input = page.locator('input[type="text"][maxlength="6"], input[type="password"][maxlength="6"], input[minlength="6"]')
            await totp_input.wait_for(state="visible", timeout=15000)
            
            # Generate the current 6-digit TOTP code
            totp = pyotp.TOTP(TOTP_SECRET)
            current_otp = totp.now()
            logger.info(f"Generated TOTP code: {current_otp}")
            
            # 3. Enter the TOTP code
            await totp_input.fill(current_otp)
            
            # Sometimes Kite auto-submits on 6th digit, sometimes you need to click continue
            submit_btn = page.locator('button[type="submit"]')
            if await submit_btn.is_visible():
                await submit_btn.click()

            # 4. Wait for redirect back to our Market Engine app
            logger.info("Waiting for redirection to Market Engine callback...")
            
            async with page.expect_navigation(url=lambda u: "request_token" in u, timeout=15000):
                pass 

            final_url = page.url
            logger.info(f"Redirected successfully. URL: {final_url.split('?')[0]}?...")
            
            parsed = urllib.parse.urlparse(final_url)
            params = urllib.parse.parse_qs(parsed.query)
            
            if "request_token" in params:
                request_token = params["request_token"][0]
                logger.info(f"✅ Success! Captured Request Token: {request_token}")
                
                # Send the token directly to our running backend
                logger.info("Sending token to backend...")
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    resp = await client.get(f"{BACKEND_URL}?request_token={request_token}")
                    if resp.status_code in (200, 302):
                        logger.info("✅ Backend updated successfully! Live data should now flow.")
                    else:
                        logger.error(f"Failed to update backend. Status: {resp.status_code}, Response: {resp.text}")
            else:
                logger.error("Failed to find 'request_token' in redirect URL.")
                
        except Exception as e:
            logger.error(f"Login automation failed: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(auto_login())
