from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse
import uuid
import os
import httpx
import random
from jose import jwt
from loguru import logger

from app.database.base import get_db
from app.database.models import User, PasswordReset
from app.api.deps import get_current_user
from app.utils.security import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from app.utils.email_sender import send_password_reset_email
from app.config.settings import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _token_response(user: User) -> dict:
    """Standard token + user payload returned on login/signup."""
    access_token = create_access_token(data={"sub": user.id})
    return {
        "access_token": access_token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone_number": user.phone_number,
        }
    }


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    phone_number: Optional[str] = None
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    """Login with email OR phone number + password."""
    identifier: str        # email or phone (+91XXXXXXXXXX)
    password: str


class GoogleLoginRequest(BaseModel):
    token: str             # Google ID token from frontend

class ForgotPasswordRequest(BaseModel):
    identifier: str

class VerifyOTPRequest(BaseModel):
    identifier: str
    otp: str

class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str
    confirm_password: str


# ─── Signup ──────────────────────────────────────────────────────────────────

def _sanitize_phone(phone: str) -> Optional[str]:
    """Helper to strip spaces/hyphens and auto-prepend +91 to 10-digit numbers."""
    if not phone:
        return None
    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.isdigit() and len(cleaned) == 10:
        return f"+91{cleaned}"
    if not cleaned.startswith("+"):
        return f"+{cleaned}"
    return cleaned

@router.post("/signup")
async def signup(user_data: SignupRequest, db: AsyncSession = Depends(get_db)):
    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check phone uniqueness (if provided)
    sanitized_phone = _sanitize_phone(user_data.phone_number)
    if sanitized_phone:
        result = await db.execute(select(User).where(User.phone_number == sanitized_phone))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Phone number already registered")

    new_user = User(
        id=str(uuid.uuid4()),
        name=user_data.name,
        email=user_data.email,
        phone_number=sanitized_phone,
        password_hash=get_password_hash(user_data.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Return JWT so the frontend can log the user in immediately after signup
    return _token_response(new_user)


# ─── Login (email OR phone) ───────────────────────────────────────────────────

@router.post("/login")
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = credentials.identifier.strip()

    # Determine lookup strategy
    if "@" in identifier:
        logger.info(f"Login lookup for email: {identifier.lower()}")
        condition = func.lower(User.email) == identifier.lower()
    else:
        # Auto-format 10 digit Indian phones to +91XXXXXXXXXX
        sanitized_phone = _sanitize_phone(identifier)
        logger.info(f"Login lookup for phone: {sanitized_phone}")
        condition = User.phone_number == sanitized_phone

    result = await db.execute(select(User).where(condition))
    user = result.scalars().first()

    if not user or not user.password_hash:
        logger.warning(f"Login failed: User not found or no password hash for '{identifier}'")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(credentials.password, user.password_hash):
        logger.warning(f"Login failed: Invalid password for '{identifier}'")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login = datetime.utcnow()
    await db.commit()

    return _token_response(user)


# ─── Google Login (Authorization Code Flow) ───────────────────────────────────

@router.get("/google/login")
async def google_login_redirect():
    google_client_id = settings.google_client_id
    google_redirect_uri = settings.google_redirect_uri
    
    if not google_client_id:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In is not configured on the server. Add GOOGLE_CLIENT_ID to .env"
        )

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={google_client_id}&"
        f"redirect_uri={google_redirect_uri}&"
        "response_type=code&"
        "scope=openid email profile&"
        "access_type=offline&"
        "prompt=consent"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None, db: AsyncSession = Depends(get_db)):
    frontend_url = settings.frontend_url
    frontend_base = frontend_url.rstrip('/')
    google_client_id = settings.google_client_id
    google_client_secret = settings.google_client_secret
    google_redirect_uri = settings.google_redirect_uri
    
    if error:
        return RedirectResponse(url=f"{frontend_base}/login?error=Google+login+failed+or+was+cancelled")

    if not code:
        return RedirectResponse(url=f"{frontend_base}/login?error=Authorization+code+missing")

    if not google_client_id or not google_client_secret:
        return RedirectResponse(url=f"{frontend_base}/login?error=Google+credentials+not+configured")

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": google_client_id,
        "client_secret": google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": google_redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=token_data)
        if response.status_code != 200:
            return RedirectResponse(url=f"{frontend_base}/login?error=Failed+to+exchange+authorization+code")
        
        token_info = response.json()
        access_token = token_info.get("access_token")

        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        user_response = await client.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
        if user_response.status_code != 200:
            return RedirectResponse(url=f"{frontend_base}/login?error=Failed+to+fetch+user+info+from+Google")
            
        user_info = user_response.json()

    google_user_id = user_info.get("sub")
    email = user_info.get("email", "")
    name = user_info.get("name", email.split("@")[0])

    # Look up by google_id first, then email
    result = await db.execute(
        select(User).where(or_(User.google_id == google_user_id, User.email == email))
    )
    user = result.scalars().first()

    if user:
        # Link google_id if signing in via Google for the first time
        if not user.google_id:
            user.google_id = google_user_id
        user.last_login = datetime.utcnow()
    else:
        # Create a new user — no password needed for Google-only accounts
        user = User(
            id=str(uuid.uuid4()),
            name=name,
            email=email,
            google_id=google_user_id,
            password_hash=None,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Generate JWT token
    jwt_token = create_access_token(data={"sub": user.id})

    # Decoded URL for redirect (so frontend URL doesn't end up double encoded)
    return RedirectResponse(url=f"{frontend_base}/dashboard?token={jwt_token}")


# ─── Password Reset Flow ────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    identifier = req.identifier.strip()
    if "@" in identifier:
        logger.info(f"Forgot password lookup for email: {identifier.lower()}")
        condition = func.lower(User.email) == identifier.lower()
    else:
        sanitized_phone = _sanitize_phone(identifier)
        logger.info(f"Forgot password lookup for phone: {sanitized_phone}")
        condition = User.phone_number == sanitized_phone

    result = await db.execute(select(User).where(condition))
    user = result.scalars().first()

    if not user:
        logger.warning(f"Forgot password failed: User not found for '{identifier}'")
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.email:
        raise HTTPException(status_code=400, detail="Cannot reset password: no email associated with this account.")

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    otp_hash = get_password_hash(otp)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    # Store OTP
    reset_record = PasswordReset(
        user_id=user.id,
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0
    )
    db.add(reset_record)
    await db.commit()

    # Send OTP
    success = await send_password_reset_email(user.email, otp)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send OTP email.")

    # Mask email for security (e.g. m***@gmail.com)
    email_parts = user.email.split("@")
    masked_email = f"{email_parts[0][0]}***@{email_parts[1]}"
    
    return {"detail": f"OTP sent to {masked_email}"}


@router.post("/verify-reset-otp")
async def verify_reset_otp(req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    identifier = req.identifier.strip()
    if "@" in identifier:
        condition = User.email == identifier
    else:
        sanitized_phone = _sanitize_phone(identifier)
        condition = User.phone_number == sanitized_phone

    result = await db.execute(select(User).where(condition))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Get the latest password reset attempt
    result = await db.execute(
        select(PasswordReset)
        .where(PasswordReset.user_id == user.id)
        .order_by(PasswordReset.created_at.desc())
    )
    reset_record = result.scalars().first()

    if not reset_record:
        raise HTTPException(status_code=400, detail="No OTP request found.")

    # Convert out of DB if it comes back naive, or just assume DB returns offset aware
    # Ensure both are offset aware to be safe
    db_expires_at = reset_record.expires_at
    if db_expires_at.tzinfo is None:
        db_expires_at = db_expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > db_expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if reset_record.attempts >= 3:
        raise HTTPException(status_code=400, detail="Too many failed attempts. Please request a new OTP.")

    if not verify_password(req.otp, reset_record.otp_hash):
        reset_record.attempts += 1
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Success — create a short-lived reset token (10 mins)
    reset_token = create_access_token(
        data={"sub": user.id, "type": "password_reset"}, 
        expires_delta=timedelta(minutes=10)
    )

    # Clean up the OTP record so it can't be reused
    await db.delete(reset_record)
    await db.commit()

    return {"reset_token": reset_token, "detail": "OTP verified safely."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    try:
        payload = jwt.decode(req.reset_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "password_reset":
            raise HTTPException(status_code=401, detail="Invalid or expired reset token.")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired reset token.")

    # Update password
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = get_password_hash(req.new_password)
    await db.commit()

    return {"detail": "Password successfully reset."}


# ─── Get Current User ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
        }
    }

