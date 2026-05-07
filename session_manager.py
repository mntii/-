import json
import os
import time
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword, TwoFactorRequired

from config import config
from logger_setup import setup_logger

logger = setup_logger("session_manager", config.log_level)


class SessionManager:
    """Handles login, session persistence, and re-authentication."""

    def __init__(self, client: Client) -> None:
        self.cl = client
        self.session_file = Path(config.session_file)
        self._logged_in = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """Attempt login from saved session first, then credentials."""
        if self._try_session_login():
            return True
        return self._fresh_login()

    def relogin(self) -> bool:
        """Force a fresh login — used after session expiry."""
        logger.warning("Attempting re-authentication...")
        self._logged_in = False
        if self.session_file.exists():
            self.session_file.unlink()
        return self._fresh_login()

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_session_login(self) -> bool:
        if not self.session_file.exists():
            logger.debug("No saved session found.")
            return False

        try:
            logger.info("Loading saved session from '%s'...", self.session_file)
            session_data = json.loads(self.session_file.read_text(encoding="utf-8"))
            self.cl.set_settings(session_data)
            self.cl.login(config.username, config.password)

            # Verify the session is still alive
            self.cl.get_timeline_feed()
            logger.info("Session restored successfully.")
            self._logged_in = True
            return True

        except LoginRequired:
            logger.warning("Saved session expired — will perform fresh login.")
            return False
        except Exception as exc:
            logger.error("Session restore failed: %s", exc)
            return False

    def _fresh_login(self) -> bool:
        try:
            logger.info("Logging in as '%s'...", config.username)
            self.cl.login(config.username, config.password)
            self._save_session()
            logger.info("Login successful.")
            self._logged_in = True
            return True

        except BadPassword:
            logger.critical("Invalid password. Check your .env credentials.")
            return False
        except TwoFactorRequired:
            logger.critical(
                "Two-factor authentication is enabled. "
                "Disable 2FA on Instagram or add support for it."
            )
            return False
        except Exception as exc:
            logger.error("Login failed: %s", exc)
            return False

    def _save_session(self) -> None:
        try:
            settings = self.cl.get_settings()
            self.session_file.write_text(
                json.dumps(settings, indent=2), encoding="utf-8"
            )
            logger.debug("Session saved to '%s'.", self.session_file)
        except Exception as exc:
            logger.warning("Could not save session: %s", exc)

    def refresh_session(self) -> None:
        """Periodically refresh the saved session to keep it alive."""
        try:
            self.cl.get_timeline_feed()
            self._save_session()
            logger.debug("Session refreshed.")
        except Exception as exc:
            logger.warning("Session refresh failed: %s", exc)
