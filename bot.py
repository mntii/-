"""
Instagram DM Media Bot — Main Entry Point
=========================================
Monitors DMs, downloads Instagram media links (Reels, Posts, IGTV, Stories),
and sends the files back to the sender automatically.

Usage:
    cp .env.example .env        # Fill in your credentials
    pip install -r requirements.txt
    python bot.py
"""

import sys
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from config import config
from session_manager import SessionManager
from downloader import MediaDownloader
from dm_handler import DMHandler
from utils import GracefulShutdown, cleanup_downloads, system_health_check, print_banner
from logger_setup import setup_logger

logger = setup_logger("bot", config.log_level)

# How often (cycles) to run cleanup and health checks
_CLEANUP_EVERY = 120   # ~every hour at 30s intervals
_HEALTH_EVERY  = 20    # ~every 10 minutes


def build_client() -> Client:
    cl = Client()
    cl.delay_range = [config.min_action_delay, config.max_action_delay]

    if config.proxy_url:
        cl.set_proxy(config.proxy_url)
        logger.info("Proxy configured: %s", config.proxy_url)

    # Randomise device fingerprint to reduce detection risk
    cl.set_locale("en_US")
    cl.set_timezone_offset(0)
    return cl


@retry(
    retry=retry_if_exception_type(LoginRequired),
    stop=stop_after_attempt(config.max_retries),
    wait=wait_exponential(multiplier=2, min=10, max=120),
    reraise=True,
)
def run_cycle(dm_handler: DMHandler, session_manager: SessionManager) -> None:
    """One full check cycle with automatic retry on auth errors."""
    dm_handler.check_inbox()
    session_manager.refresh_session()


def main() -> None:
    print_banner()

    try:
        config.validate()
    except ValueError as exc:
        logger.critical(str(exc))
        sys.exit(1)

    cl = build_client()
    session_manager = SessionManager(cl)
    downloader = MediaDownloader(cl)
    dm_handler = DMHandler(cl, downloader, relogin_callback=session_manager.relogin)
    shutdown = GracefulShutdown()

    # Login
    if not session_manager.login():
        logger.critical("Could not log in. Exiting.")
        sys.exit(1)

    logger.info("Bot is running. Checking DMs every %d seconds.", config.check_interval)

    cycle = 0
    while not shutdown.stop:
        cycle += 1

        try:
            run_cycle(dm_handler, session_manager)
        except LoginRequired:
            logger.error("All re-auth attempts failed. Will retry next cycle.")
        except Exception as exc:
            logger.error("Unexpected error in cycle %d: %s", cycle, exc, exc_info=True)

        # Periodic maintenance
        if cycle % _HEALTH_EVERY == 0:
            system_health_check()

        if cycle % _CLEANUP_EVERY == 0:
            cleanup_downloads()

        # Wait for next cycle (interruptible by shutdown signal)
        for _ in range(config.check_interval):
            if shutdown.stop:
                break
            time.sleep(1)

    logger.info("Bot stopped gracefully. Goodbye.")


if __name__ == "__main__":
    main()
