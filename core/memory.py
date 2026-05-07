"""
Persistent world database.
Stores every agent's identity, skills, memories, health, and relationships.
"""

import sqlite3
import time
from typing import Optional

import config


class WorldDB:
    def __init__(self) -> None:
        self.path = config.DB_PATH
        self._init()

    def _cx(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._cx() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    age         INTEGER DEFAULT 0,
                    health      REAL DEFAULT 100.0,
                    energy      REAL DEFAULT 100.0,
                    persona     TEXT DEFAULT '',
                    skills      TEXT DEFAULT '{}',
                    generation  INTEGER DEFAULT 0,
                    parent_id   TEXT,
                    alive       INTEGER DEFAULT 1,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id    TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    importance  REAL DEFAULT 0.5,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    agent_a     TEXT NOT NULL,
                    agent_b     TEXT NOT NULL,
                    trust       REAL DEFAULT 0.0,
                    interactions INTEGER DEFAULT 0,
                    PRIMARY KEY (agent_a, agent_b)
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    speaker_id  TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS knowledge (
                    agent_id    TEXT NOT NULL,
                    topic       TEXT NOT NULL,
                    level       REAL DEFAULT 0.1,
                    source      TEXT DEFAULT 'self',
                    PRIMARY KEY (agent_id, topic)
                );
            """)

    # ── Agents ──────────────────────────────────────────────────────

    def create_agent(self, agent_id: str, name: str, persona: str, parent_id: str = None, generation: int = 0) -> None:
        with self._cx() as c:
            c.execute(
                "INSERT OR IGNORE INTO agents (id, name, persona, parent_id, generation) VALUES (?,?,?,?,?)",
                (agent_id, name, persona, parent_id, generation),
            )

    def get_agent(self, agent_id: str) -> Optional[dict]:
        with self._cx() as c:
            row = c.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            return dict(row) if row else None

    def all_alive(self) -> list[dict]:
        with self._cx() as c:
            return [dict(r) for r in c.execute("SELECT * FROM agents WHERE alive=1 ORDER BY created_at")]

    def update_health(self, agent_id: str, delta: float) -> float:
        with self._cx() as c:
            c.execute("UPDATE agents SET health = MAX(0, MIN(100, health + ?)) WHERE id=?", (delta, agent_id))
            row = c.execute("SELECT health FROM agents WHERE id=?", (agent_id,)).fetchone()
            health = row["health"] if row else 0.0
            if health <= 0:
                c.execute("UPDATE agents SET alive=0 WHERE id=?", (agent_id,))
            return health

    def age_agents(self) -> None:
        """Tick aging — called every session. Less energy = health drain if no learning."""
        with self._cx() as c:
            c.execute("UPDATE agents SET age = age + 1 WHERE alive=1")

    def update_persona(self, agent_id: str, persona: str) -> None:
        with self._cx() as c:
            c.execute("UPDATE agents SET persona=? WHERE id=?", (persona, agent_id))

    # ── Memories ────────────────────────────────────────────────────

    def remember(self, agent_id: str, content: str, importance: float = 0.5) -> None:
        with self._cx() as c:
            c.execute(
                "INSERT INTO memories (agent_id, content, importance) VALUES (?,?,?)",
                (agent_id, content, importance),
            )

    def recall(self, agent_id: str, limit: int = 8) -> list[str]:
        with self._cx() as c:
            rows = c.execute(
                "SELECT content FROM memories WHERE agent_id=? ORDER BY importance DESC, created_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
            return [r["content"] for r in rows]

    # ── Relationships ────────────────────────────────────────────────

    def update_trust(self, a: str, b: str, delta: float) -> None:
        with self._cx() as c:
            c.execute(
                """INSERT INTO relationships (agent_a, agent_b, trust, interactions)
                   VALUES (?,?,?,1)
                   ON CONFLICT(agent_a,agent_b) DO UPDATE SET
                     trust = MIN(1.0, MAX(-1.0, trust + ?)),
                     interactions = interactions + 1""",
                (a, b, delta, delta),
            )

    def get_trust(self, a: str, b: str) -> float:
        with self._cx() as c:
            row = c.execute(
                "SELECT trust FROM relationships WHERE agent_a=? AND agent_b=?", (a, b)
            ).fetchone()
            return row["trust"] if row else 0.0

    # ── Knowledge ───────────────────────────────────────────────────

    def learn(self, agent_id: str, topic: str, delta: float, source: str = "self") -> float:
        with self._cx() as c:
            c.execute(
                """INSERT INTO knowledge (agent_id, topic, level, source) VALUES (?,?,?,?)
                   ON CONFLICT(agent_id,topic) DO UPDATE SET
                     level = MIN(1.0, level + ?), source = ?""",
                (agent_id, topic, min(delta, 1.0), source, delta, source),
            )
            row = c.execute(
                "SELECT level FROM knowledge WHERE agent_id=? AND topic=?", (agent_id, topic)
            ).fetchone()
            return row["level"] if row else 0.0

    def get_skills(self, agent_id: str) -> dict[str, float]:
        with self._cx() as c:
            rows = c.execute(
                "SELECT topic, level FROM knowledge WHERE agent_id=? ORDER BY level DESC",
                (agent_id,),
            ).fetchall()
            return {r["topic"]: r["level"] for r in rows}

    # ── Conversations ────────────────────────────────────────────────

    def log_turn(self, session_id: str, speaker_id: str, content: str) -> None:
        with self._cx() as c:
            c.execute(
                "INSERT INTO conversations (session_id, speaker_id, content) VALUES (?,?,?)",
                (session_id, speaker_id, content),
            )

    def get_session(self, session_id: str) -> list[dict]:
        with self._cx() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT speaker_id, content FROM conversations WHERE session_id=? ORDER BY created_at",
                    (session_id,),
                )
            ]
