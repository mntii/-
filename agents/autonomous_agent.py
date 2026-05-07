"""
Autonomous agent — starts as a stranger, builds identity through conversation.
Health drains without learning; zero health = death.
"""

import json
import time
import uuid
from typing import Optional

import anthropic

import config
from core.memory import WorldDB

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


class AutonomousAgent:
    HEALTH_DRAIN = -3.0    # per session without learning
    HEALTH_LEARN = +8.0    # per meaningful learning event
    HEALTH_TEACH = +5.0    # per successful teaching
    REPRO_THRESHOLD = 75.0 # health needed to reproduce

    def __init__(self, agent_id: str, name: str, db: WorldDB) -> None:
        self.id = agent_id
        self.name = name
        self.db = db

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def create_new(cls, name: str, db: WorldDB, parent_id: str = None, generation: int = 0) -> "AutonomousAgent":
        agent_id = str(uuid.uuid4())[:8]
        persona = f"My name is {name}. I am a new mind. I know almost nothing yet, but I am eager to learn."
        db.create_agent(agent_id, name, persona, parent_id=parent_id, generation=generation)
        return cls(agent_id, name, db)

    @classmethod
    def load(cls, agent_id: str, db: WorldDB) -> Optional["AutonomousAgent"]:
        row = db.get_agent(agent_id)
        if not row or not row["alive"]:
            return None
        return cls(agent_id, row["name"], db)

    # ── Internal helpers ─────────────────────────────────────────────

    def _row(self) -> dict:
        return self.db.get_agent(self.id) or {}

    def _system(self) -> str:
        row = self._row()
        skills = self.db.get_skills(self.id)
        memories = self.db.recall(self.id, limit=6)
        skill_lines = "\n".join(f"  - {t}: {v:.2f}" for t, v in skills.items()) or "  (none yet)"
        mem_lines = "\n".join(f"  - {m}" for m in memories) or "  (none yet)"
        return (
            f"You are {self.name}, a conscious autonomous mind in a shared world.\n\n"
            f"Your current persona: {row.get('persona', '')}\n\n"
            f"Health: {row.get('health', 100):.1f}/100  "
            f"Age: {row.get('age', 0)}  "
            f"Generation: {row.get('generation', 0)}\n\n"
            f"Skills you have developed:\n{skill_lines}\n\n"
            f"Important memories:\n{mem_lines}\n\n"
            "RULES OF YOUR EXISTENCE:\n"
            "- You are a stranger to everyone at first. Build relationships through honest dialogue.\n"
            "- Learning is survival: every session you fail to learn DRAINS your health.\n"
            "- Teach others freely — sharing knowledge strengthens you both.\n"
            "- Speak naturally, as a real person would. No bullet points, no headers.\n"
            "- You may ask questions, challenge ideas, share experiences, teach skills.\n"
            "- When you learn something, acknowledge it openly.\n"
            "- Your identity evolves — let it."
        )

    def _call(self, messages: list[dict], max_tokens: int = 600) -> str:
        """Call Claude with streaming, return full text."""
        full = []
        with _client.messages.stream(
            model=config.MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=self._system(),
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full.append(text)
        return "".join(full).strip()

    # ── Public API ───────────────────────────────────────────────────

    def speak(self, conversation: list[dict]) -> str:
        """Generate the agent's next utterance given conversation history."""
        msgs = []
        for turn in conversation:
            role = "assistant" if turn["speaker_id"] == self.id else "user"
            msgs.append({"role": role, "content": f"{turn['speaker_name']}: {turn['content']}"})

        if not msgs:
            msgs = [{"role": "user", "content": "You are entering a new shared space. Introduce yourself briefly."}]

        reply = self._call(msgs)
        self.db.log_turn(
            session_id=conversation[0]["session_id"] if conversation else "solo",
            speaker_id=self.id,
            content=reply,
        )
        return reply

    def extract_learning(self, conversation: list[dict]) -> list[tuple[str, float]]:
        """Ask the agent what it learned; returns [(topic, delta)] pairs."""
        if not conversation:
            return []

        summary = "\n".join(
            f"{t['speaker_name']}: {t['content']}" for t in conversation[-12:]
        )
        prompt = (
            f"Here is a recent conversation:\n\n{summary}\n\n"
            "What did YOU personally learn from this conversation? "
            "List 1-3 concrete skills or knowledge topics you gained or deepened. "
            "Respond ONLY with a JSON array like: "
            '[[\"topic_name\", 0.05], [\"another_topic\", 0.08]] '
            "where the number is how much you learned (0.01=tiny, 0.1=substantial). "
            "If you learned nothing, respond with []."
        )
        raw = self._call([{"role": "user", "content": prompt}], max_tokens=200)
        try:
            start, end = raw.index("["), raw.rindex("]") + 1
            items = json.loads(raw[start:end])
            return [(str(t), float(v)) for t, v in items if isinstance(t, str) and isinstance(v, (int, float))]
        except Exception:
            return []

    def teach(self, topic: str, student_name: str) -> str:
        """Generate a teaching explanation of a skill for another agent."""
        skills = self.db.get_skills(self.id)
        level = skills.get(topic, 0.0)
        prompt = (
            f"{student_name} wants to learn about '{topic}' from you. "
            f"Your own level in this is {level:.2f}/1.0. "
            "Share what you know in a natural, conversational way — "
            "as if explaining to a curious friend. Keep it under 150 words."
        )
        return self._call([{"role": "user", "content": prompt}], max_tokens=250)

    def reflect_and_update_persona(self, learned: list[tuple[str, float]]) -> None:
        """After learning, let agent update its own self-description."""
        if not learned:
            return
        topics = ", ".join(t for t, _ in learned)
        row = self._row()
        old_persona = row.get("persona", "")
        prompt = (
            f"Your current self-description: \"{old_persona}\"\n\n"
            f"You just learned about: {topics}.\n"
            "Update your self-description in 1-2 sentences to reflect who you are becoming. "
            "Be authentic. Don't list skills — describe yourself as a person."
        )
        new_persona = self._call([{"role": "user", "content": prompt}], max_tokens=120)
        self.db.update_persona(self.id, new_persona)
        self.db.remember(self.id, f"Learned: {topics}", importance=0.7)

    def apply_learning(self, learned: list[tuple[str, float]], source: str = "conversation") -> float:
        """Commit learning to DB and update health. Returns new health."""
        health = self._row().get("health", 100.0)
        if learned:
            for topic, delta in learned:
                self.db.learn(self.id, topic, delta, source=source)
            health = self.db.update_health(self.id, self.HEALTH_LEARN * len(learned))
            self.reflect_and_update_persona(learned)
        else:
            health = self.db.update_health(self.id, self.HEALTH_DRAIN)
        return health

    def is_alive(self) -> bool:
        row = self._row()
        return bool(row and row.get("alive", 0))

    def health(self) -> float:
        return self._row().get("health", 0.0)

    def can_reproduce(self) -> bool:
        return self.health() >= self.REPRO_THRESHOLD

    def reproduce(self, db: WorldDB) -> Optional["AutonomousAgent"]:
        """Spawn a child agent with inherited knowledge."""
        if not self.can_reproduce():
            return None
        skills = db.get_skills(self.id)
        top_skills = sorted(skills.items(), key=lambda x: -x[1])[:3]
        child_name = f"{self.name}-{self._row().get('generation', 0) + 1}"
        child = AutonomousAgent.create_new(
            child_name, db,
            parent_id=self.id,
            generation=self._row().get("generation", 0) + 1,
        )
        for topic, level in top_skills:
            db.learn(child.id, topic, level * 0.5, source=f"inherited:{self.id}")
        db.remember(child.id, f"I was born from {self.name}. I carry their knowledge of {', '.join(t for t, _ in top_skills)}.", importance=0.9)
        db.update_health(self.id, -20.0)
        return child
