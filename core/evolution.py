"""
Evolution engine: evaluates agent fitness, improves weak agents,
and triggers reproduction of high-performing variants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

import config

console = Console()


class EvolutionEngine:
    def __init__(self, agents: list[BaseAgent]) -> None:
        self.agents = agents

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_feedback(self, session_id: str, rating: float) -> None:
        """
        After user rates a session (0-100), update all agent fitness scores
        and trigger evolution if needed.
        """
        for agent in self.agents:
            agent.memory.save_user_rating(session_id, rating)
            agent.update_fitness(rating)

        self._display_fitness_table()
        self._evolve_if_needed(rating)

    def display_fitness_table(self) -> None:
        self._display_fitness_table()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _display_fitness_table(self) -> None:
        table = Table(title="🧬 Agent Fitness Scores", show_lines=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Generation", justify="center")
        table.add_column("Fitness", justify="right")
        table.add_column("Status", justify="center")

        for agent in self.agents:
            stored = agent.memory.get_agent(agent.agent_id)
            fitness = stored["fitness"] if stored else agent.fitness
            gen = stored["generation"] if stored else 0
            bar = self._fitness_bar(fitness)
            status = "✅ Healthy" if fitness >= config.MIN_FITNESS_THRESHOLD else "⚠️  Weak"
            table.add_row(agent.ROLE, str(gen), f"{fitness:.2f}  {bar}", status)

        console.print(table)

    def _fitness_bar(self, fitness: float, width: int = 10) -> str:
        filled = int(fitness * width)
        return "█" * filled + "░" * (width - filled)

    def _evolve_if_needed(self, last_rating: float) -> None:
        """
        Three evolution strategies based on performance:
          1. LOW fitness → improve the system prompt via self-reflection
          2. HIGH fitness → spawn a child variant to explore new angles
          3. CRITICAL (<0.3) → force a full prompt regeneration
        """
        for agent in self.agents:
            stored = agent.memory.get_agent(agent.agent_id)
            fitness = stored["fitness"] if stored else agent.fitness

            if fitness < 0.3:
                # Critical — full regeneration
                console.print(
                    f"[red]🔴 {agent.ROLE} fitness critical ({fitness:.2f}) — regenerating prompt...[/red]"
                )
                self._regenerate_prompt(agent)

            elif fitness < config.MIN_FITNESS_THRESHOLD:
                # Weak — self-improvement
                console.print(
                    f"[yellow]🟡 {agent.ROLE} fitness low ({fitness:.2f}) — evolving prompt...[/yellow]"
                )
                self._improve_prompt(agent)

            elif fitness > 0.75 and last_rating > 75:
                # Strong — reproduce
                console.print(
                    f"[green]🟢 {agent.ROLE} fitness high ({fitness:.2f}) — spawning child variant...[/green]"
                )
                child = agent.reproduce()
                console.print(
                    f"[green]   Child created: {child.agent_id} (Gen {child.generation})[/green]"
                )

    def _improve_prompt(self, agent: BaseAgent) -> None:
        past = agent.memory.get_past_analyses(agent.agent_id, limit=3)
        if not past:
            return

        low_rated = [p for p in past if p.get("user_rating") is not None and p["user_rating"] < 60]
        if not low_rated:
            return

        feedback_summary = "\n".join(
            f"• Rating {int(p['user_rating'])}/100 on topic: {p['topic'][:80]}"
            for p in low_rated
        )
        new_prompt = agent.evolve_prompt(feedback_summary)
        if new_prompt and len(new_prompt) > 50:
            agent.commit_evolved_prompt(new_prompt)
            console.print(f"[yellow]   ✏️  {agent.ROLE} system prompt updated.[/yellow]")

    def _regenerate_prompt(self, agent: BaseAgent) -> None:
        feedback = (
            f"This agent has fitness {agent.fitness:.2f} and needs a complete overhaul. "
            f"Keep the same role but create a fundamentally stronger analytical framework."
        )
        new_prompt = agent.evolve_prompt(feedback)
        if new_prompt and len(new_prompt) > 50:
            agent.commit_evolved_prompt(new_prompt)
            console.print(f"[red]   🔄 {agent.ROLE} prompt fully regenerated.[/red]")
