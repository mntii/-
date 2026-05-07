"""
Multi-Agent World — CLI entry point.
Agents start as strangers, learn to survive, teach each other, reproduce.
"""

import argparse
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from agents.autonomous_agent import AutonomousAgent
from core.conversation import ConversationSession
from core.memory import WorldDB
from core.peer_eval import run_peer_evaluations

console = Console()

DEFAULT_NAMES = ["Ara", "Kael", "Sova", "Nyx", "Zhen"]


def _status_table(db: WorldDB) -> Table:
    agents = db.all_alive()
    t = Table(title="Agent World", show_lines=True)
    t.add_column("Name", style="cyan")
    t.add_column("Health", justify="right")
    t.add_column("Age", justify="right")
    t.add_column("Gen", justify="right")
    t.add_column("Top Skills")
    for row in agents:
        skills = db.get_skills(row["id"])
        top = ", ".join(f"{k}({v:.2f})" for k, v in list(skills.items())[:3]) or "—"
        h = row["health"]
        color = "green" if h > 60 else ("yellow" if h > 30 else "red")
        t.add_row(
            row["name"],
            f"[{color}]{h:.1f}[/{color}]",
            str(row["age"]),
            str(row["generation"]),
            top,
        )
    return t


def _ensure_world(db: WorldDB) -> list[AutonomousAgent]:
    alive = db.all_alive()
    agents = []
    if not alive:
        console.print("[yellow]No agents found — creating founding generation...[/yellow]")
        for name in DEFAULT_NAMES:
            a = AutonomousAgent.create_new(name, db)
            agents.append(a)
            console.print(f"  Born: [cyan]{name}[/cyan] ({a.id})")
    else:
        for row in alive:
            a = AutonomousAgent.load(row["id"], db)
            if a:
                agents.append(a)
    return agents


def run_session(db: WorldDB, topic: str = "", turns: int = 12) -> None:
    agents = _ensure_world(db)
    if not agents:
        console.print("[red]All agents are dead. World is empty.[/red]")
        return

    console.print(Panel(f"[bold]Session starting[/bold] | Topic: {topic or '(open)'} | Agents: {len(agents)} | Turns: {turns}"))

    def on_turn(turn):
        if turn.speaker_id == "world":
            console.print(f"\n[dim italic]{turn.content}[/dim italic]")
        else:
            color = "cyan" if turn.speaker_id == agents[0].id else "magenta"
            console.print(f"\n[bold {color}]{turn.speaker_name}:[/bold {color}] {turn.content}")

    session = ConversationSession(agents, db, topic=topic, max_turns=turns, on_turn=on_turn)
    history = session.run()

    console.print("\n[bold]─── Learning Phase ───[/bold]")
    health_map = session.apply_all_learning()
    for name, h in health_map.items():
        status = "[red]DIED[/red]" if h <= 0 else f"[green]{h:.1f}[/green]"
        console.print(f"  {name}: health → {status}")

    console.print("\n[bold]─── Peer Evaluations ───[/bold]")
    alive_agents = [a for a in agents if a.is_alive()]
    agent_names = {a.id: a.name for a in agents}
    history_dicts = [
        {"speaker_id": t.speaker_id, "speaker_name": t.speaker_name, "content": t.content}
        for t in history
    ]
    trust_map = run_peer_evaluations(history_dicts, [a.id for a in alive_agents], agent_names, db)
    for aid, delta in trust_map.items():
        name = agent_names.get(aid, aid)
        sign = "+" if delta >= 0 else ""
        console.print(f"  {name}: trust received {sign}{delta:.3f}")

    console.print("\n[bold]─── Reproduction ───[/bold]")
    children = session.check_reproduction()
    if children:
        for child in children:
            console.print(f"  [green]Born:[/green] {child.name} (child of {child._row().get('parent_id', '?')})")
    else:
        console.print("  No reproduction this session.")

    console.print()
    console.print(_status_table(db))


def cmd_status(db: WorldDB) -> None:
    console.print(_status_table(db))


def cmd_kill_all(db: WorldDB) -> None:
    with db._cx() as c:
        c.execute("UPDATE agents SET alive=0")
    console.print("[red]All agents killed. Run without --reset to start fresh.[/red]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent World")
    parser.add_argument("--topic", "-t", default="", help="Conversation topic")
    parser.add_argument("--turns", "-n", type=int, default=12, help="Max conversation turns")
    parser.add_argument("--status", action="store_true", help="Show agent status table")
    parser.add_argument("--reset", action="store_true", help="Kill all agents and start fresh")
    args = parser.parse_args()

    db = WorldDB()

    if args.status:
        cmd_status(db)
        return

    if args.reset:
        cmd_kill_all(db)
        db = WorldDB()

    try:
        run_session(db, topic=args.topic, turns=args.turns)
    except KeyboardInterrupt:
        console.print("\n[yellow]Session interrupted.[/yellow]")


if __name__ == "__main__":
    main()
