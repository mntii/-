import os
import re
import time
import random
from pathlib import Path
from typing import Optional

from instagrapi import Client
from instagrapi.types import Media
from instagrapi.exceptions import MediaNotFound, LoginRequired

from config import config
from logger_setup import setup_logger

logger = setup_logger("downloader", config.log_level)

# Regex to extract a shortcode from any Instagram URL
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|p|tv|stories/[^/]+)/([A-Za-z0-9_-]+)")


class MediaDownloader:
    """Downloads Instagram media (video, photo, carousel) to disk."""

    def __init__(self, client: Client) -> None:
        self.cl = client
        self.folder = Path(config.download_folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_shortcode(self, text: str) -> Optional[str]:
        """Pull the media shortcode from a raw Instagram URL."""
        match = _SHORTCODE_RE.search(text)
        return match.group(1) if match else None

    def download(self, url: str) -> list[Path]:
        """
        Download all media from the given Instagram URL.
        Returns a list of local file paths (may be multiple for carousels).
        """
        shortcode = self.extract_shortcode(url)
        if not shortcode:
            logger.warning("No valid Instagram shortcode found in: %s", url)
            return []

        try:
            media_pk = self.cl.media_pk_from_code(shortcode)
            media: Media = self.cl.media_info(media_pk)
        except MediaNotFound:
            logger.error("Media not found for shortcode '%s' (may be private/deleted).", shortcode)
            return []
        except LoginRequired:
            raise  # Let the caller handle re-auth
        except Exception as exc:
            logger.error("Failed to fetch media info for '%s': %s", shortcode, exc)
            return []

        logger.info("Downloading media [type=%s, pk=%s]...", media.media_type, media_pk)

        paths = self._dispatch_download(media)
        if paths:
            logger.info("Downloaded %d file(s): %s", len(paths), [str(p) for p in paths])
        return paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch_download(self, media: Media) -> list[Path]:
        """Route to the correct download method based on media type."""
        # media_type: 1=Photo, 2=Video, 8=Carousel
        if media.media_type == 1:
            return self._download_photo(media)
        elif media.media_type == 2:
            return self._download_video(media)
        elif media.media_type == 8:
            return self._download_carousel(media)
        else:
            logger.warning("Unsupported media type: %s", media.media_type)
            return []

    def _download_photo(self, media: Media) -> list[Path]:
        try:
            path = self.cl.photo_download(media.pk, folder=self.folder)
            return [Path(path)]
        except Exception as exc:
            logger.error("Photo download failed: %s", exc)
            return []

    def _download_video(self, media: Media) -> list[Path]:
        try:
            path = self.cl.video_download(media.pk, folder=self.folder)
            return [Path(path)]
        except Exception as exc:
            logger.error("Video download failed: %s", exc)
            return []

    def _download_carousel(self, media: Media) -> list[Path]:
        """Download all items in a carousel (album) post."""
        paths: list[Path] = []
        for resource in media.resources:
            try:
                if resource.media_type == 1:
                    p = self.cl.photo_download(resource.pk, folder=self.folder)
                else:
                    p = self.cl.video_download(resource.pk, folder=self.folder)
                paths.append(Path(p))
                # Small delay between carousel items to avoid rate limiting
                time.sleep(random.uniform(1, 3))
            except Exception as exc:
                logger.error("Carousel item download failed (pk=%s): %s", resource.pk, exc)
        return paths
