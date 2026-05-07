"""
Multi-Agent Intelligence System
================================
5 specialized AI experts debate, challenge each other, learn from humans,
evolve their prompts, and reproduce high-performing variants.

Usage:
    python main.py
    python main.py --topic "Saudi Aramco stock outlook 2025"
    python main.py --fitness   # Show current fitness table
"""

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt, Confirm

from config import ANTHROPIC_API_KEY
from core.memory import AgentMemory
from core.dialogue import DialogueOrchestrator
from core.evolution import EvolutionEngine
from agents.historical_analyst import HistoricalAnalyst
from agents.behavioral_analyst import BehavioralAnalyst
from agents.strategic_forecaster import StrategicForecaster
from agents.devils_advocate import DevilsAdvocate
from agents.coordinator import Coordinator

console = Console()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║        🧠  MULTI-AGENT INTELLIGENCE SYSTEM  🧠               ║
║                                                              ║
║  Expert 1 • Historical Analyst   📜                          ║
║  Expert 2 • Behavioral Analyst   🧠                          ║
║  Expert 3 • Strategic Forecaster 🌍                          ║
║  Expert 4 • Devil's Advocate     😈                          ║
║  Expert 5 • Coordinator          ⚖️                           ║
║                                                              ║
║  Agents learn, evolve, and reproduce with every session.     ║
╚══════════════════════════════════════════════════════════════╝
"""


def build_agents(memory: AgentMemory) -> tuple[list, Coordinator]:
    experts = [
        HistoricalAnalyst(memory),
        BehavioralAnalyst(memory),
        StrategicForecaster(memory),
        DevilsAdvocate(memory),
    ]
    coordinator = Coordinator(memory)
    return experts, coordinator


def run_analysis(topic: str, memory: AgentMemory) -> None:
    experts, coordinator = build_agents(memory)
    evolution = EvolutionEngine(experts)
    orchestrator = DialogueOrchestrator(experts, coordinator)

    console.print(
        Panel(
            f"[bold white]TOPIC:[/bold white] [yellow]{topic}[/yellow]",
            title="🔍 Analysis Target",
            border_style="blue",
        )
    )

    session_id, final_report, all_rounds = orchestrator.run(topic)

    # ── Human feedback loop ────────────────────────────────────────────
    console.rule("[bold blue]📊 Human Feedback & Evolution[/bold blue]")
    console.print(
        "\n[cyan]Your feedback trains the agents to improve over time.[/cyan]\n"
    )

    if Confirm.ask("Rate this analysis? (helps agents evolve)", default=True):
        rating = FloatPrompt.ask(
            "Rate the analysis accuracy (0 = terrible, 100 = perfect)",
            default=70.0,
        )
        rating = max(0.0, min(100.0, rating))

        evolution.apply_feedback(session_id, rating)
        memory.save_user_rating(session_id, rating)

        console.print(f"\n[green]✅ Feedback saved. Rating: {rating:.0f}/100[/green]")
        console.print("[green]Agents will evolve based on this session.[/green]\n")
    else:
        console.print("[dim]Skipping feedback. Agents will not evolve this session.[/dim]\n")


def show_fitness(memory: AgentMemory) -> None:
    experts, _ = build_agents(memory)
    evolution = EvolutionEngine(experts)
    evolution.display_fitness_table()


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent Intelligence System")
    parser.add_argument("--topic", type=str, help="Topic to analyze")
    parser.add_argument("--fitness", action="store_true", help="Show agent fitness table")
    args = parser.parse_args()

    console.print(BANNER, style="bold cyan")

    memory = AgentMemory()

    if args.fitness:
        show_fitness(memory)
        return

    if args.topic:
        topic = args.topic
    else:
        console.print(
            "[cyan]Enter any topic you want analyzed:[/cyan]\n"
            "[dim]Examples: 'Saudi Aramco stock 2025', 'Bitcoin next 6 months', "
            "'Tesla valuation', 'Real estate Dubai'[/dim]\n"
        )
        topic = Prompt.ask("[bold yellow]Topic").strip()
        if not topic:
            console.print("[red]No topic provided. Exiting.[/red]")
            sys.exit(1)

    run_analysis(topic, memory)


if __name__ == "__main__":
    main()
