import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.engine import URL

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # We build the URL programmatically so that special characters in passwords (like % and @) are auto-escaped.
    DATABASE_URL = URL.create(
        drivername="postgresql+asyncpg",
        username=os.getenv("DB_USER", "UstaGo"),
        password=os.getenv("DB_PASS", "nJ9f$Av!9SEf5Fu%9s%Xmt&Y6"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "UstaGo_db")
    ).render_as_string(hide_password=False)
    
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Administraton: list of telegram IDs allowed to use admin commands
    ADMIN_IDS = set(int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip())

config = Config()
