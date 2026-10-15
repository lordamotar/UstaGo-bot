import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.engine import URL

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # Database Configuration
    _db_url = os.getenv("DATABASE_URL")
    if _db_url:
        DATABASE_URL = _db_url
    else:
        # We build the URL programmatically so that special characters in passwords (like % and @) are auto-escaped.
        DATABASE_URL = URL.create(
            drivername="postgresql+asyncpg",
            username=os.getenv("DB_USER", "UstaGo"),
            password=os.getenv("DB_PASS", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "UstaGo_db")
        ).render_as_string(hide_password=False)
    
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Administration: list of telegram IDs allowed to use admin commands
    ADMIN_IDS = [int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()]
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    # Secret for signing admin JWT tokens (min 32 chars). REQUIRED for admin_api.
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
    # Comma-separated list of allowed origins for the admin panel, e.g. https://admin.example.com
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    # Set to 1 when the API is behind nginx/Cloudflare: take the client IP from X-Forwarded-For
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"
    # Business rules
    MAX_BIDS_PER_ORDER = int(os.getenv("MAX_BIDS_PER_ORDER", 5))
    ORDER_TTL_HOURS = int(os.getenv("ORDER_TTL_HOURS", 72))  # 0 disables auto-closing of stale orders
    TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", 5))  # local time for "do not disturb" (Kazakhstan: UTC+5)

config = Config()
