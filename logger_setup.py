import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

import colorlog


LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


def setup_logger(name: str = "instagram_bot", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Console handler with colors
    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s | %(message)s",
        datefmt="%H:%M:%S",
        log_colors=LOG_COLORS,
    )
    console_handler.setFormatter(console_formatter)

    # Rotating file handler — keeps last 5 files of 10MB each
    log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
