import time
import random
from pathlib import Path
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from instagrapi.types import DirectThread, DirectMessage

from config import config
from downloader import MediaDownloader
from logger_setup import setup_logger

logger = setup_logger("dm_handler", config.log_level)


class DMHandler:
    """Monitors DMs and processes Instagram media links."""

    def __init__(self, client: Client, downloader: MediaDownloader, relogin_callback) -> None:
        self.cl = client
        self.downloader = downloader
        self.relogin = relogin_callback
        # Track processed message IDs to avoid double-handling
        self._processed_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_inbox(self) -> None:
        """Fetch unread DM threads and process any Instagram links."""
        try:
            threads = self.cl.direct_threads(amount=20)
        except LoginRequired:
            logger.warning("Session expired during inbox check — re-logging in...")
            self.relogin()
            return
        except Exception as exc:
            logger.error("Failed to fetch DM inbox: %s", exc)
            return

        for thread in threads:
            self._process_thread(thread)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_thread(self, thread: DirectThread) -> None:
        try:
            messages = self.cl.direct_messages(thread.id, amount=10)
        except Exception as exc:
            logger.error("Could not fetch messages for thread %s: %s", thread.id, exc)
            return

        for msg in messages:
            self._handle_message(thread, msg)

    def _handle_message(self, thread: DirectThread, msg: DirectMessage) -> None:
        # Skip already processed or sent by the bot itself
        if msg.id in self._processed_ids:
            return
        if str(msg.user_id) == str(self.cl.user_id):
            self._processed_ids.add(msg.id)
            return

        text = msg.text or ""
        link = self._extract_instagram_link(text)

        if not link:
            self._processed_ids.add(msg.id)
            return

        logger.info("Link detected from user %s: %s", msg.user_id, link)
        self._processed_ids.add(msg.id)

        self._send_typing_indicator(thread.id)
        files = self._download_with_retry(link)

        if not files:
            self._reply(thread.id, "Sorry, I couldn't download that media. It may be private or unavailable.")
            return

        self._send_files(thread.id, files)

    def _extract_instagram_link(self, text: str) -> Optional[str]:
        for pattern in config.link_patterns:
            if pattern in text:
                # Extract just the URL portion from the message
                for word in text.split():
                    if pattern in word:
                        return word.strip()
        return None

    def _download_with_retry(self, link: str) -> list[Path]:
        """Try downloading, re-authenticate once on LoginRequired."""
        try:
            return self.downloader.download(link)
        except LoginRequired:
            logger.warning("LoginRequired during download — re-authenticating...")
            if self.relogin():
                try:
                    return self.downloader.download(link)
                except Exception as exc:
                    logger.error("Download failed after re-auth: %s", exc)
        except Exception as exc:
            logger.error("Download error: %s", exc)
        return []

    def _send_files(self, thread_id: str, files: list[Path]) -> None:
        for file_path in files:
            try:
                ext = file_path.suffix.lower()
                self._human_delay()

                if ext in (".mp4", ".mov", ".avi", ".mkv"):
                    self.cl.direct_send_video(str(file_path), thread_ids=[thread_id])
                    logger.info("Sent video to thread %s: %s", thread_id, file_path.name)
                elif ext in (".jpg", ".jpeg", ".png", ".webp"):
                    self.cl.direct_send_photo(str(file_path), thread_ids=[thread_id])
                    logger.info("Sent photo to thread %s: %s", thread_id, file_path.name)
                else:
                    logger.warning("Unknown file extension '%s' — skipping.", ext)

            except LoginRequired:
                logger.warning("LoginRequired while sending file — re-authenticating...")
                self.relogin()
            except Exception as exc:
                logger.error("Failed to send file '%s': %s", file_path, exc)

    def _reply(self, thread_id: str, text: str) -> None:
        try:
            self._human_delay()
            self.cl.direct_send(text, thread_ids=[thread_id])
            logger.debug("Sent text reply to thread %s.", thread_id)
        except Exception as exc:
            logger.error("Failed to send text reply: %s", exc)

    def _send_typing_indicator(self, thread_id: str) -> None:
        """Simulate typing to make the bot feel more human."""
        try:
            self.cl.direct_send_seen(thread_id)
        except Exception:
            pass  # Non-critical — ignore failures
        time.sleep(random.uniform(1, 2))

    def _human_delay(self) -> None:
        time.sleep(random.uniform(config.min_action_delay, config.max_action_delay))
