"""
Free-form multi-agent conversation engine.
Agents speak naturally, learn from each other, and survive or perish.
"""

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.autonomous_agent import AutonomousAgent
from core.memory import WorldDB


@dataclass
class Turn:
    session_id: str
    speaker_id: str
    speaker_name: str
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationSession:
    """Runs a single multi-agent conversation session."""

    def __init__(
        self,
        agents: list[AutonomousAgent],
        db: WorldDB,
        topic: str = "",
        max_turns: int = 12,
        on_turn: Optional[Callable[[Turn], None]] = None,
    ) -> None:
        self.agents = [a for a in agents if a.is_alive()]
        self.db = db
        self.topic = topic
        self.session_id = str(uuid.uuid4())[:12]
        self.max_turns = max_turns
        self.on_turn = on_turn
        self.history: list[Turn] = []

    def _history_for(self, agent: AutonomousAgent) -> list[dict]:
        """Format history as conversation from agent's perspective."""
        return [
            {
                "session_id": self.session_id,
                "speaker_id": t.speaker_id,
                "speaker_name": t.speaker_name,
                "content": t.content,
            }
            for t in self.history
        ]

    def _pick_speaker(self, last_speaker_id: Optional[str] = None) -> Optional[AutonomousAgent]:
        """Choose next speaker, avoid repeating same agent twice."""
        alive = [a for a in self.agents if a.is_alive()]
        if not alive:
            return None
        if len(alive) == 1:
            return alive[0]
        candidates = [a for a in alive if a.id != last_speaker_id]
        weights = []
        for a in candidates:
            h = a.health()
            trust_sum = sum(
                self.db.get_trust(a.id, other.id)
                for other in alive if other.id != a.id
            )
            weights.append(max(0.1, h / 100 + trust_sum * 0.1))
        total = sum(weights)
        weights = [w / total for w in weights]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _inject_topic(self) -> None:
        """Seed conversation with topic if provided."""
        if not self.topic:
            return
        narrator_turn = Turn(
            session_id=self.session_id,
            speaker_id="world",
            speaker_name="World",
            content=f"[New conversation topic: {self.topic}]",
        )
        self.history.append(narrator_turn)
        if self.on_turn:
            self.on_turn(narrator_turn)

    def _teach_moment(self, speaker: AutonomousAgent) -> Optional[Turn]:
        """Occasionally trigger a teaching moment if speaker has skills others lack."""
        alive = [a for a in self.agents if a.is_alive() and a.id != speaker.id]
        if not alive:
            return None

        speaker_skills = self.db.get_skills(speaker.id)
        if not speaker_skills:
            return None

        student = random.choice(alive)
        student_skills = self.db.get_skills(student.id)

        teachable = [
            (t, v) for t, v in speaker_skills.items()
            if v > 0.3 and student_skills.get(t, 0) < v - 0.15
        ]
        if not teachable:
            return None

        topic, _ = max(teachable, key=lambda x: x[1])
        teaching = speaker.teach(topic, student.name)

        self.db.learn(student.id, topic, 0.07, source=f"taught:{speaker.id}")
        self.db.update_health(speaker.id, AutonomousAgent.HEALTH_TEACH)
        self.db.update_trust(speaker.id, student.id, 0.05)
        self.db.update_trust(student.id, speaker.id, 0.08)
        self.db.remember(student.id, f"{speaker.name} taught me about {topic}.", importance=0.8)

        return Turn(
            session_id=self.session_id,
            speaker_id=speaker.id,
            speaker_name=speaker.name,
            content=f"[Teaching {student.name} about {topic}]\n{teaching}",
        )

    def run(self) -> list[Turn]:
        """Execute the full conversation. Returns all turns."""
        self._inject_topic()

        last_speaker_id = None
        teach_interval = max(3, self.max_turns // 4)

        for turn_num in range(self.max_turns):
            alive = [a for a in self.agents if a.is_alive()]
            if len(alive) < 1:
                break

            speaker = self._pick_speaker(last_speaker_id)
            if not speaker:
                break

            # Teaching moment every few turns
            if turn_num > 0 and turn_num % teach_interval == 0:
                teach_turn = self._teach_moment(speaker)
                if teach_turn:
                    self.history.append(teach_turn)
                    self.db.log_turn(self.session_id, teach_turn.speaker_id, teach_turn.content)
                    if self.on_turn:
                        self.on_turn(teach_turn)

            reply = speaker.speak(self._history_for(speaker))
            turn = Turn(
                session_id=self.session_id,
                speaker_id=speaker.id,
                speaker_name=speaker.name,
                content=reply,
            )
            self.history.append(turn)
            if self.on_turn:
                self.on_turn(turn)

            last_speaker_id = speaker.id

            # Update trust between speaker and others
            for other in alive:
                if other.id != speaker.id:
                    self.db.update_trust(speaker.id, other.id, 0.02)

        return self.history

    def apply_all_learning(self) -> dict[str, float]:
        """After conversation, extract and apply learning for every agent. Returns {name: new_health}."""
        results = {}
        for agent in self.agents:
            if not agent.is_alive():
                results[agent.name] = 0.0
                continue
            learned = agent.extract_learning(
                [{"speaker_id": t.speaker_id, "speaker_name": t.speaker_name, "content": t.content}
                 for t in self.history if t.speaker_id != "world"]
            )
            new_health = agent.apply_learning(learned)
            results[agent.name] = new_health

            if new_health <= 0:
                results[agent.name] = 0.0  # dead

        self.db.age_agents()
        return results

    def check_reproduction(self) -> list[AutonomousAgent]:
        """Reproduce eligible agents. Returns list of new children."""
        children = []
        for agent in self.agents:
            if agent.is_alive() and agent.can_reproduce():
                child = agent.reproduce(self.db)
                if child:
                    children.append(child)
        return children
