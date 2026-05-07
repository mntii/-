import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
MODEL: str = os.getenv("MODEL", "claude-opus-4-7")
DB_PATH: str = os.getenv("DB_PATH", "world.db")

if not ANTHROPIC_API_KEY:
    raise EnvironmentError("ANTHROPIC_API_KEY missing — copy .env.example to .env")
