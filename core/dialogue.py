"""
Orchestrates the internal dialogue protocol between all 5 agents.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent
    from agents.coordinator import Coordinator

import config

console = Console()

AGENT_COLORS = {
    "historical_analyst": "cyan",
    "behavioral_analyst": "magenta",
    "strategic_forecaster": "yellow",
    "devils_advocate": "red",
    "coordinator": "green",
}

AGENT_LABELS = {
    "historical_analyst": "📜 HISTORICAL ANALYST",
    "behavioral_analyst": "🧠 BEHAVIORAL ANALYST",
    "strategic_forecaster": "🌍 STRATEGIC FORECASTER",
    "devils_advocate": "😈 DEVIL'S ADVOCATE",
    "coordinator": "⚖️  COORDINATOR",
}


class DialogueOrchestrator:
    def __init__(
        self,
        experts: list[BaseAgent],
        coordinator: Coordinator,
    ) -> None:
        self.experts = experts
        self.coordinator = coordinator
        self.expert_map: dict[str, BaseAgent] = {e.ROLE: e for e in experts}

    def run(self, topic: str) -> tuple[str, str, list[dict[str, str]]]:
        """
        Full dialogue protocol:
          Round 1: Independent analysis by each expert
          Round N: Peer response rounds
          Final: Coordinator synthesizes all rounds

        Returns: (session_id, final_report, all_rounds)
        """
        session_id = uuid.uuid4().hex
        for agent in [*self.experts, self.coordinator]:
            agent.memory.create_session(session_id, topic)

        all_rounds: list[dict[str, str]] = []

        # ── Round 1: Independent analyses ─────────────────────────────
        console.rule("[bold blue]🔬 ROUND 1 — Independent Analysis[/bold blue]")
        round_1: dict[str, str] = {}

        for expert in self.experts:
            label = AGENT_LABELS.get(expert.ROLE, expert.ROLE)
            color = AGENT_COLORS.get(expert.ROLE, "white")
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[{color}]{label} is analyzing...[/{color}]"),
                transient=True,
            ) as progress:
                progress.add_task("", total=None)
                analysis = expert.analyze(topic, session_id, round_num=1)

            round_1[expert.ROLE] = analysis
            console.print(
                Panel(
                    Markdown(analysis),
                    title=f"[bold {color}]{label}[/bold {color}]",
                    border_style=color,
                    expand=False,
                )
            )

        all_rounds.append(round_1)

        # ── Debate rounds: each expert responds to peers ───────────────
        for round_num in range(2, config.DIALOGUE_ROUNDS + 2):
            console.rule(f"[bold blue]⚔️  ROUND {round_num} — Peer Debate[/bold blue]")
            current_round: dict[str, str] = {}

            for expert in self.experts:
                # Each expert sees all OTHER experts from the last round
                peers = {
                    role: content
                    for role, content in all_rounds[-1].items()
                    if role != expert.ROLE
                }
                label = AGENT_LABELS.get(expert.ROLE, expert.ROLE)
                color = AGENT_COLORS.get(expert.ROLE, "white")

                with Progress(
                    SpinnerColumn(),
                    TextColumn(f"[{color}]{label} responds to peers...[/{color}]"),
                    transient=True,
                ) as progress:
                    progress.add_task("", total=None)
                    response = expert.respond_to_peers(topic, peers, session_id, round_num)

                current_round[expert.ROLE] = response
                console.print(
                    Panel(
                        Markdown(response),
                        title=f"[bold {color}]{label} — Round {round_num}[/bold {color}]",
                        border_style=color,
                        expand=False,
                    )
                )

            all_rounds.append(current_round)

        # ── Final synthesis by coordinator ─────────────────────────────
        console.rule("[bold green]⚖️  FINAL SYNTHESIS — Coordinator[/bold green]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[green]Coordinator synthesizing all rounds...[/green]"),
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            final_report = self.coordinator.synthesize(topic, all_rounds, session_id)

        console.print(
            Panel(
                Markdown(final_report),
                title="[bold green]⚖️  COORDINATOR — FINAL INTELLIGENCE REPORT[/bold green]",
                border_style="green",
                expand=True,
            )
        )

        # Extract and save learnings for each agent
        self.coordinator.extract_learnings(topic, all_rounds, self.expert_map)

        return session_id, final_report, all_rounds
