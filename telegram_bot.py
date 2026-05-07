"""
Telegram Bot — Multi-Agent Intelligence System
===============================================
Commands:
  /start          — Welcome message
  /analyze <topic> — Run full 5-expert analysis
  /fitness        — Show agent fitness table
  /help           — Help message

Usage:
    python telegram_bot.py
"""

import asyncio
import sys
import textwrap
import threading
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import config
from core.memory import AgentMemory
from core.evolution import EvolutionEngine
from agents.historical_analyst import HistoricalAnalyst
from agents.behavioral_analyst import BehavioralAnalyst
from agents.strategic_forecaster import StrategicForecaster
from agents.devils_advocate import DevilsAdvocate
from agents.coordinator import Coordinator

# ── Shared memory (all users share the same agent pool) ───────────────
memory = AgentMemory()

# Lock so only one analysis runs at a time (avoids SQLite conflicts)
_analysis_lock = threading.Lock()

# Track ongoing sessions: user_id → session_id (for rating callback)
_pending_ratings: dict[int, str] = {}

# ── Agent labels for progress messages ────────────────────────────────
AGENT_STEPS = [
    ("📜", "Historical Analyst",   "analyzing historical patterns..."),
    ("🧠", "Behavioral Analyst",   "decoding crowd psychology..."),
    ("🌍", "Strategic Forecaster", "mapping macro scenarios..."),
    ("😈", "Devil's Advocate",     "stress-testing all arguments..."),
]

RATING_BUTTONS = [
    [
        InlineKeyboardButton("💀 0",   callback_data="rate_0"),
        InlineKeyboardButton("😞 25",  callback_data="rate_25"),
        InlineKeyboardButton("😐 50",  callback_data="rate_50"),
    ],
    [
        InlineKeyboardButton("👍 75",  callback_data="rate_75"),
        InlineKeyboardButton("🔥 90",  callback_data="rate_90"),
        InlineKeyboardButton("🏆 100", callback_data="rate_100"),
    ],
]

MAX_TG_LEN = 4000  # Telegram message character limit (safe margin)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _split_message(text: str, limit: int = MAX_TG_LEN) -> list[str]:
    """Split a long text into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


def _build_agents():
    experts = [
        HistoricalAnalyst(memory),
        BehavioralAnalyst(memory),
        StrategicForecaster(memory),
        DevilsAdvocate(memory),
    ]
    coordinator = Coordinator(memory)
    return experts, coordinator


def _fitness_text() -> str:
    experts, _ = _build_agents()
    lines = ["*🧬 Agent Fitness Scores*\n"]
    for agent in experts:
        stored = memory.get_agent(agent.agent_id)
        fitness = stored["fitness"] if stored else 0.5
        gen = stored["generation"] if stored else 0
        bar_filled = int(fitness * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        status = "✅" if fitness >= config.MIN_FITNESS_THRESHOLD else "⚠️"
        lines.append(
            f"{status} `{agent.ROLE}`\n"
            f"   Gen {gen} | Fitness `{fitness:.2f}` `{bar}`\n"
        )
    return "\n".join(lines)


def _run_analysis_sync(topic: str) -> tuple[str, str, list]:
    """Blocking analysis — runs in a thread executor."""
    experts, coordinator = _build_agents()

    import uuid
    session_id = uuid.uuid4().hex
    for agent in [*experts, coordinator]:
        agent.memory.create_session(session_id, topic)

    all_rounds: list[dict[str, str]] = []

    # Round 1 — independent
    round_1: dict[str, str] = {}
    for expert in experts:
        analysis = expert.analyze(topic, session_id, round_num=1)
        round_1[expert.ROLE] = analysis
    all_rounds.append(round_1)

    # Debate rounds
    for round_num in range(2, config.DIALOGUE_ROUNDS + 2):
        current: dict[str, str] = {}
        for expert in experts:
            peers = {
                role: content
                for role, content in all_rounds[-1].items()
                if role != expert.ROLE
            }
            response = expert.respond_to_peers(topic, peers, session_id, round_num)
            current[expert.ROLE] = response
        all_rounds.append(current)

    # Final synthesis
    final_report = coordinator.synthesize(topic, all_rounds, session_id)
    coordinator.extract_learnings(
        topic, all_rounds, {e.ROLE: e for e in experts}
    )
    return session_id, final_report, all_rounds


# ─────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🧠 *Multi\\-Agent Intelligence System*\n\n"
        "5 AI experts debate your topic, challenge each other, "
        "and produce a final intelligence report\\.\n\n"
        "📜 Historical Analyst\n"
        "🧠 Behavioral Analyst\n"
        "🌍 Strategic Forecaster\n"
        "😈 Devil's Advocate\n"
        "⚖️ Coordinator \\(final report\\)\n\n"
        "Agents *learn and evolve* from your feedback\\.\n\n"
        "▶️ Send any topic or use:\n"
        "`/analyze Saudi Aramco 2025`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Commands:*\n\n"
        "`/analyze <topic>` — Run full analysis\n"
        "`/fitness` — Show agent fitness scores\n"
        "`/start` — Welcome message\n\n"
        "*Or just send any text message* to analyze it directly\\."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_fitness(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_fitness_text(), parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await update.message.reply_text(
            "Please provide a topic:\n`/analyze Saudi Aramco outlook 2025`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    await _run_topic(update, context, topic)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any plain message is treated as a topic to analyze."""
    topic = update.message.text.strip()
    if topic:
        await _run_topic(update, context, topic)


# ─────────────────────────────────────────────────────────────────────
# Core analysis flow
# ─────────────────────────────────────────────────────────────────────

async def _run_topic(
    update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str
) -> None:
    user_id = update.effective_user.id

    if not _analysis_lock.acquire(blocking=False):
        await update.message.reply_text(
            "⏳ An analysis is already running. Please wait a moment and try again."
        )
        return

    try:
        # Progress message that we edit as each step completes
        progress_msg = await update.message.reply_text(
            f"🔍 *Analyzing:* `{topic}`\n\n"
            "⏳ Starting expert panel...",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        async def update_progress(step: int, done: bool = False) -> None:
            lines = [f"🔍 *Analyzing:* `{topic}`\n"]
            for i, (icon, name, action) in enumerate(AGENT_STEPS):
                if i < step:
                    lines.append(f"✅ {icon} {name}")
                elif i == step and not done:
                    lines.append(f"⚙️ {icon} {name} — _{action}_")
                else:
                    lines.append(f"⬜ {icon} {name}")
            if done:
                lines.append("\n⚖️ Coordinator synthesizing final report...")
            try:
                await progress_msg.edit_text(
                    "\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception:
                pass

        # Run blocking analysis in thread (keeps event loop free)
        loop = asyncio.get_event_loop()

        # Update progress before each expert (approximate — actual call is sync)
        for step_idx in range(len(AGENT_STEPS)):
            await update_progress(step_idx)
            await asyncio.sleep(0.1)

        session_id, final_report, all_rounds = await loop.run_in_executor(
            None, _run_analysis_sync, topic
        )

        await update_progress(len(AGENT_STEPS), done=True)
        _pending_ratings[user_id] = session_id

        # Delete progress message
        try:
            await progress_msg.delete()
        except Exception:
            pass

        # Send header
        await update.message.reply_text(
            f"⚖️ *INTELLIGENCE REPORT*\n📌 Topic: `{topic}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        # Send final report (split if too long)
        for chunk in _split_message(final_report):
            await update.message.reply_text(chunk)

        # Rating buttons
        await update.message.reply_text(
            "📊 *Rate this analysis* to help agents evolve:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(RATING_BUTTONS),
        )

    except Exception as exc:
        await update.message.reply_text(
            f"❌ Analysis failed: `{str(exc)[:200]}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    finally:
        _analysis_lock.release()


# ─────────────────────────────────────────────────────────────────────
# Rating callback
# ─────────────────────────────────────────────────────────────────────

async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # e.g. "rate_75"

    if not data.startswith("rate_"):
        return

    rating = float(data.split("_")[1])
    session_id = _pending_ratings.pop(user_id, None)

    if session_id:
        # Apply feedback and evolve
        experts, _ = _build_agents()
        evolution = EvolutionEngine(experts)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, evolution.apply_feedback, session_id, rating
        )

        await query.edit_message_text(
            f"✅ Feedback saved: *{int(rating)}/100*\n\n"
            f"Agents will evolve based on your rating\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        # Send updated fitness table
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=_fitness_text(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        await query.edit_message_text("⚠️ Session not found. Rating not applied.")


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("fitness", cmd_fitness))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern=r"^rate_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Telegram bot started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
