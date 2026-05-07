"""
Base agent: wraps Claude API calls, manages memory, handles evolution.
All five expert agents inherit from this.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional

import anthropic

import config
from core.memory import AgentMemory


class BaseAgent(ABC):
    # Subclasses define these
    ROLE: str = "base"
    BASE_SYSTEM_PROMPT: str = "You are a helpful expert."

    def __init__(self, memory: AgentMemory, agent_id: Optional[str] = None) -> None:
        self.memory = memory
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.generation = 0
        self.parent_id: Optional[str] = None

        # Load or create agent record
        self.agent_id = agent_id or self.ROLE
        stored = memory.get_agent(self.agent_id)

        if stored:
            self.system_prompt: str = stored["system_prompt"]
            self.fitness: float = stored["fitness"]
            self.generation = stored["generation"]
            self.parent_id = stored["parent_id"]
        else:
            self.system_prompt = self.BASE_SYSTEM_PROMPT
            self.fitness = 0.5
            memory.upsert_agent(
                agent_id=self.agent_id,
                role=self.ROLE,
                system_prompt=self.system_prompt,
                generation=self.generation,
                parent_id=self.parent_id,
                fitness=self.fitness,
            )

    # ------------------------------------------------------------------
    # Core LLM call (streaming + adaptive thinking)
    # ------------------------------------------------------------------

    def _call(self, user_message: str, extra_context: str = "") -> str:
        """Call Claude with adaptive thinking, stream and collect the full response."""
        system = self.system_prompt
        if extra_context:
            system = f"{system}\n\n--- Relevant past learnings ---\n{extra_context}"

        full_text: list[str] = []

        with self.client.messages.stream(
            model=config.DEFAULT_MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for event in stream:
                if (
                    hasattr(event, "type")
                    and event.type == "content_block_delta"
                    and hasattr(event, "delta")
                    and hasattr(event.delta, "type")
                    and event.delta.type == "text_delta"
                ):
                    full_text.append(event.delta.text)

        return "".join(full_text).strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @abstractmethod
    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        """Perform initial analysis of the topic."""

    @abstractmethod
    def respond_to_peers(
        self, topic: str, peer_analyses: dict[str, str], session_id: str, round_num: int
    ) -> str:
        """Read peer analyses and provide corrections or reinforcements."""

    def _build_context(self) -> str:
        """Pull relevant past learnings to inject into the system prompt at call time."""
        learnings = self.memory.get_relevant_learnings(self.agent_id, limit=3)
        past = self.memory.get_past_analyses(self.agent_id, limit=3)

        parts: list[str] = []
        if learnings:
            parts.append("Key learnings from past sessions:\n" + "\n".join(f"• {l}" for l in learnings))
        if past:
            rated = [p for p in past if p["user_rating"] is not None]
            if rated:
                summary = "\n".join(
                    f"• [{int(p['user_rating'])}/100] Topic: {p['topic'][:60]}"
                    for p in rated[:3]
                )
                parts.append("Past performance:\n" + summary)

        return "\n\n".join(parts)

    def update_fitness(self, rating: float) -> None:
        """Update fitness score after user feedback (rating 0-100)."""
        self.memory.update_fitness(self.agent_id, rating)
        self.fitness = 0.7 * self.fitness + 0.3 * (rating / 100.0)

    def evolve_prompt(self, feedback_summary: str) -> str:
        """
        Ask Claude to improve this agent's own system prompt based on feedback.
        Returns the new prompt (caller decides whether to commit it).
        """
        prompt = f"""You are a meta-AI improving an expert agent's system prompt.

Current system prompt:
---
{self.system_prompt}
---

Feedback and failure patterns:
{feedback_summary}

Rewrite the system prompt to address these weaknesses. Keep the same role and expertise.
Return ONLY the improved system prompt — no commentary, no preamble.
"""
        return self._call(prompt)

    def commit_evolved_prompt(self, new_prompt: str) -> None:
        """Apply and persist the improved system prompt."""
        self.system_prompt = new_prompt
        self.memory.upsert_agent(
            agent_id=self.agent_id,
            role=self.ROLE,
            system_prompt=new_prompt,
            generation=self.generation,
            parent_id=self.parent_id,
            fitness=self.fitness,
        )

    def reproduce(self) -> "BaseAgent":
        """
        Spawn a child agent with a mutated system prompt.
        The child shares this class but gets a new unique ID and generation.
        """
        child_id = f"{self.ROLE}_gen{self.generation + 1}_{uuid.uuid4().hex[:6]}"
        mutation_prompt = f"""
You are a meta-AI that generates specialized expert variants.

Parent agent role: {self.ROLE}
Parent system prompt:
---
{self.system_prompt}
---

Create a slightly different variant of this expert that:
1. Keeps the core expertise
2. Emphasizes a different analytical angle or method
3. Could complement the parent in group discussions

Return ONLY the new system prompt — no commentary.
"""
        new_prompt = self._call(mutation_prompt)

        # Build child using a factory so we get the right subclass type
        child = self.__class__.__new__(self.__class__)
        child.memory = self.memory
        child.client = self.client
        child.agent_id = child_id
        child.ROLE = self.ROLE
        child.generation = self.generation + 1
        child.parent_id = self.agent_id
        child.system_prompt = new_prompt
        child.fitness = 0.5

        self.memory.upsert_agent(
            agent_id=child_id,
            role=self.ROLE,
            system_prompt=new_prompt,
            generation=child.generation,
            parent_id=self.agent_id,
            fitness=0.5,
        )
        return child
