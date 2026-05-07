import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "claude-opus-4-7")
DIALOGUE_ROUNDS: int = int(os.getenv("DIALOGUE_ROUNDS", 2))
MIN_FITNESS_THRESHOLD: float = float(os.getenv("MIN_FITNESS_THRESHOLD", 0.4))
MEMORY_DB: str = os.getenv("MEMORY_DB", "agent_memory.db")

if not ANTHROPIC_API_KEY:
    raise EnvironmentError("ANTHROPIC_API_KEY is not set. Copy .env.example → .env and fill it in.")
