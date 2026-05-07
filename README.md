# Instagram DM Media Bot

An automated bot that monitors your Instagram DMs, detects Instagram media links (Reels, Posts, IGTV, Stories, Carousels), downloads them, and sends the files back to the sender.

## Features

- **DM Monitoring** — checks inbox every 30 seconds (configurable)
- **Multi-media support** — Reels, Posts, IGTV, Stories, Carousel albums
- **Session Persistence** — saves session to JSON to avoid repeated logins
- **Self-Healing** — automatic re-authentication on session expiry with exponential backoff
- **Human Simulation** — randomised delays and typing indicators to reduce detection risk
- **Logging** — color console output + rotating log files in `logs/`
- **Auto-Cleanup** — deletes downloaded files older than 24 hours
- **Health Monitoring** — periodic CPU/RAM/disk usage reporting
- **Graceful Shutdown** — handles Ctrl+C cleanly without data loss
- **Proxy Support** — optional HTTP/SOCKS proxy

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd instagram-bot

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
nano .env   # Fill in INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD

# 5. Run the bot
python bot.py
```

## Project Structure

```
├── bot.py              # Entry point & main loop
├── config.py           # Settings loaded from .env
├── session_manager.py  # Login, session save/restore, re-auth
├── downloader.py       # Media download logic (photo/video/carousel)
├── dm_handler.py       # DM polling and message processing
├── utils.py            # Cleanup, health check, graceful shutdown
├── logger_setup.py     # Color console + rotating file logging
├── requirements.txt    # Python dependencies
├── .env.example        # Template for environment variables
├── downloads/          # Downloaded media files (auto-created)
└── logs/               # Log files (auto-created)
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `INSTAGRAM_USERNAME` | — | Your Instagram username |
| `INSTAGRAM_PASSWORD` | — | Your Instagram password |
| `CHECK_INTERVAL` | `30` | Seconds between DM checks |
| `MAX_RETRIES` | `3` | Max re-auth attempts on failure |
| `DOWNLOAD_FOLDER` | `downloads` | Where media files are saved |
| `SESSION_FILE` | `session.json` | Session persistence file |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PROXY_URL` | *(empty)* | Optional proxy URL |
| `MIN_ACTION_DELAY` | `2` | Min seconds between actions |
| `MAX_ACTION_DELAY` | `6` | Max seconds between actions |

## Important Notes

- **Use a secondary account** — avoid using your main personal account with automation tools.
- **Keep delays realistic** — the default 2–6s delay range mimics human behavior.
- **Do not share your `session.json`** — it contains your login session data.
- **Two-Factor Authentication** — disable 2FA on the bot account or the bot will refuse to start.
