from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Zerodha
    kite_api_key: str = Field(default="", env="KITE_API_KEY")
    kite_api_secret: str = Field(default="", env="KITE_API_SECRET")
    kite_access_token: str = Field(default="", env="KITE_ACCESS_TOKEN")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:2411@localhost:5432/MarketEngine_db",
        env="DATABASE_URL"
    )

    # App
    app_env: str = Field(default="development", env="APP_ENV")
    app_port: int = Field(default=8000, env="APP_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    frontend_url: str = Field(default="http://localhost:5173", env="FRONTEND_URL")
    mock_mode: bool = Field(default=False, env="MOCK_MODE")

    # Paper Trading
    default_quantity: int = Field(default=50, env="DEFAULT_QUANTITY")
    market_open: str = Field(default="09:15", env="MARKET_OPEN")
    market_close: str = Field(default="15:30", env="MARKET_CLOSE")
    eod_square_off: str = Field(default="15:20", env="EOD_SQUARE_OFF")

    # Email / SMTP
    smtp_host: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_password: str = Field(default="", env="SMTP_PASSWORD")
    notify_email: str = Field(default="dmoneksh@yahoo.com", env="NOTIFY_EMAIL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Module-level singleton — loaded once at import time.
# Uvicorn --reload re-imports modules, so new .env values are picked up on reload.
settings = Settings()

