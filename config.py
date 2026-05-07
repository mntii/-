import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    username: str = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD", ""))
    check_interval: int = field(default_factory=lambda: int(os.getenv("CHECK_INTERVAL", 30)))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", 3)))
    download_folder: str = field(default_factory=lambda: os.getenv("DOWNLOAD_FOLDER", "downloads"))
    session_file: str = field(default_factory=lambda: os.getenv("SESSION_FILE", "session.json"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    proxy_url: str = field(default_factory=lambda: os.getenv("PROXY_URL", ""))
    min_action_delay: float = field(default_factory=lambda: float(os.getenv("MIN_ACTION_DELAY", 2)))
    max_action_delay: float = field(default_factory=lambda: float(os.getenv("MAX_ACTION_DELAY", 6)))

    # Instagram link patterns
    link_patterns: tuple = (
        "instagram.com/reel/",
        "instagram.com/p/",
        "instagram.com/tv/",
        "instagram.com/stories/",
    )

    def validate(self) -> None:
        if not self.username or not self.password:
            raise ValueError(
                "INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in the .env file."
            )
        os.makedirs(self.download_folder, exist_ok=True)


# Singleton config instance
config = BotConfig()
