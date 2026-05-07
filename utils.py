import os
import time
import signal
import psutil
from pathlib import Path
from datetime import datetime

from logger_setup import setup_logger
from config import config

logger = setup_logger("utils", config.log_level)


class GracefulShutdown:
    """Intercept SIGINT / SIGTERM so the bot exits cleanly."""

    def __init__(self) -> None:
        self.stop = False
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, *_) -> None:
        logger.info("Shutdown signal received. Finishing current cycle then stopping...")
        self.stop = True


def cleanup_downloads(folder: str = config.download_folder, max_age_hours: int = 24) -> None:
    """Delete downloaded files older than max_age_hours to free disk space."""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for f in Path(folder).iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except Exception as exc:
                logger.warning("Could not remove '%s': %s", f, exc)
    if removed:
        logger.info("Cleanup: removed %d old file(s) from '%s'.", removed, folder)


def system_health_check() -> None:
    """Log CPU and memory usage for monitoring purposes."""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(".")
    logger.debug(
        "System | CPU: %.1f%% | RAM: %.1f%% (%.0f MB free) | Disk: %.1f%% free",
        cpu,
        mem.percent,
        mem.available / 1024 / 1024,
        100 - disk.percent,
    )


def print_banner() -> None:
    banner = r"""
  ___           _          ____        _
 |_ _|_ __  ___| |_ __ _  | __ )  ___ | |_
  | || '_ \/ __| __/ _` | |  _ \ / _ \| __|
  | || | | \__ \ || (_| | | |_) | (_) | |_
 |___|_| |_|___/\__\__,_| |____/ \___/ \__|
  DM Media Downloader — Professional Edition
    """
    print(banner)
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Account   : {config.username}")
    print(f"  Interval  : every {config.check_interval}s")
    print(f"  Downloads : {config.download_folder}/")
    print()
