"""
Telegram bot interface for the Multi-Agent World.
Shows live agent conversations, health, and world state.
"""

import asyncio
import html
import logging
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import config
from agents.autonomous_agent import AutonomousAgent
from core.conversation import ConversationSession, Turn
from core.memory import WorldDB
from core.peer_eval import run_peer_evaluations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_NAMES = ["Ara", "Kael", "Sova", "Nyx", "Zhen"]
MAX_MSG = 4000


def _chunk(text: str, size: int = MAX_MSG) -> list[str]:
    return [text[i:i+size] for i in range(0, len(text), size)]


def _health_bar(h: float) -> str:
    filled = int(h / 10)
    bar = "█" * filled + "░" * (10 - filled)
    emoji = "🟢" if h > 60 else ("🟡" if h > 30 else "🔴")
    return f"{emoji} {bar} {h:.0f}/100"


def _ensure_agents(db: WorldDB) -> list[AutonomousAgent]:
    alive = db.all_alive()
    if not alive:
        agents = []
        for name in DEFAULT_NAMES:
            a = AutonomousAgent.create_new(name, db)
            agents.append(a)
        return agents
    return [a for row in alive if (a := AutonomousAgent.load(row["id"], db))]


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    db: WorldDB = ctx.bot_data["db"]
    agents = _ensure_agents(db)
    lines = ["<b>🌍 Multi-Agent World</b>\n"]
    for a in agents:
        row = db.get_agent(a.id)
        h = row["health"] if row else 0
        lines.append(f"• <b>{html.escape(a.name)}</b> — {_health_bar(h)}")
    lines.append("\n<i>Commands:</i>")
    lines.append("/talk [topic] — run a conversation session")
    lines.append("/agents — agent status table")
    lines.append("/reset — restart the world with fresh agents")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_agents(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    db: WorldDB = ctx.bot_data["db"]
    rows = db.all_alive()
    if not rows:
        await update.message.reply_text("🌑 The world is empty. Use /start to begin.")
        return

    lines = ["<b>Agent Status</b>\n"]
    for row in rows:
        skills = db.get_skills(row["id"])
        top = ", ".join(f"{k}({v:.2f})" for k, v in list(skills.items())[:3]) or "none"
        lines.append(
            f"<b>{html.escape(row['name'])}</b> (gen {row['generation']})\n"
            f"  {_health_bar(row['health'])}\n"
            f"  Age: {row['age']} | Skills: {html.escape(top)}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    db: WorldDB = ctx.bot_data["db"]
    with db._cx() as c:
        c.execute("UPDATE agents SET alive=0")
    agents = _ensure_agents(db)
    names = ", ".join(a.name for a in agents)
    await update.message.reply_text(
        f"🌱 <b>World reset.</b> New agents: {html.escape(names)}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_talk(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    db: WorldDB = ctx.bot_data["db"]
    topic = " ".join(ctx.args) if ctx.args else ""

    agents = _ensure_agents(db)
    if not agents:
        await update.message.reply_text("🌑 No agents alive. Use /reset.")
        return

    header = f"💬 <b>Session starting</b> {'— Topic: ' + html.escape(topic) if topic else ''}\n"
    header += f"Agents: {', '.join(html.escape(a.name) for a in agents)}\n"
    header += "─" * 30
    await update.message.reply_text(header, parse_mode=ParseMode.HTML)

    buffer: list[str] = []
    msg_obj = None

    async def flush_buffer():
        nonlocal msg_obj, buffer
        if not buffer:
            return
        text = "\n".join(buffer)
        for chunk in _chunk(text):
            msg_obj = await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        buffer = []

    AGENT_COLORS = {}
    color_pool = ["cyan", "magenta", "blue", "green", "yellow"]
    color_idx = 0

    def on_turn(turn: Turn) -> None:
        nonlocal color_idx
        if turn.speaker_id == "world":
            buffer.append(f"<i>{html.escape(turn.content)}</i>")
            return
        if turn.speaker_id not in AGENT_COLORS:
            AGENT_COLORS[turn.speaker_id] = color_pool[color_idx % len(color_pool)]
            color_idx += 1
        buffer.append(f"<b>{html.escape(turn.speaker_name)}:</b> {html.escape(turn.content)}")

    # Run conversation in thread pool (Claude calls are blocking)
    loop = asyncio.get_event_loop()
    session = ConversationSession(agents, db, topic=topic, max_turns=10, on_turn=on_turn)

    history = await loop.run_in_executor(None, session.run)

    await flush_buffer()

    # Learning phase
    await update.message.reply_text("📚 <b>Learning phase...</b>", parse_mode=ParseMode.HTML)
    health_map = await loop.run_in_executor(None, session.apply_all_learning)

    health_lines = ["<b>Health after learning:</b>"]
    for name, h in health_map.items():
        if h <= 0:
            health_lines.append(f"• {html.escape(name)}: 💀 <b>DIED</b>")
        else:
            health_lines.append(f"• {html.escape(name)}: {_health_bar(h)}")
    await update.message.reply_text("\n".join(health_lines), parse_mode=ParseMode.HTML)

    # Peer evaluation
    alive_agents = [a for a in agents if a.is_alive()]
    agent_names = {a.id: a.name for a in agents}
    history_dicts = [
        {"speaker_id": t.speaker_id, "speaker_name": t.speaker_name, "content": t.content}
        for t in history
    ]
    trust_map = await loop.run_in_executor(
        None,
        lambda: run_peer_evaluations(history_dicts, [a.id for a in alive_agents], agent_names, db)
    )

    trust_lines = ["<b>Peer trust updates:</b>"]
    for aid, delta in trust_map.items():
        name = agent_names.get(aid, aid)
        sign = "+" if delta >= 0 else ""
        trust_lines.append(f"• {html.escape(name)}: {sign}{delta:.3f}")
    await update.message.reply_text("\n".join(trust_lines), parse_mode=ParseMode.HTML)

    # Reproduction
    children = await loop.run_in_executor(None, session.check_reproduction)
    if children:
        born_names = ", ".join(html.escape(c.name) for c in children)
        await update.message.reply_text(f"🌱 <b>New agents born:</b> {born_names}", parse_mode=ParseMode.HTML)

    # Final status
    await cmd_agents(update, ctx)


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if text:
        ctx.args = text.split()
        await cmd_talk(update, ctx)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN missing in .env")

    db = WorldDB()
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("talk", cmd_talk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
