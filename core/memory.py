"""
Persistent memory layer for all agents.
Stores analyses, dialogue turns, feedback, and evolved prompts in SQLite.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional

import config


class AgentMemory:
    def __init__(self, db_path: str = config.MEMORY_DB) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id    TEXT PRIMARY KEY,
                    role        TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    generation  INTEGER DEFAULT 0,
                    parent_id   TEXT,
                    fitness     REAL DEFAULT 0.5,
                    total_runs  INTEGER DEFAULT 0,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id    TEXT NOT NULL,
                    topic       TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    round       INTEGER DEFAULT 1,
                    session_id  TEXT NOT NULL,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id  TEXT PRIMARY KEY,
                    topic       TEXT NOT NULL,
                    final_report TEXT,
                    user_rating REAL,
                    created_at  REAL DEFAULT (unixepoch())
                );

                CREATE TABLE IF NOT EXISTS learnings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id    TEXT NOT NULL,
                    topic       TEXT NOT NULL,
                    insight     TEXT NOT NULL,
                    source      TEXT,
                    created_at  REAL DEFAULT (unixepoch())
                );
            """)

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def upsert_agent(
        self,
        agent_id: str,
        role: str,
        system_prompt: str,
        generation: int = 0,
        parent_id: Optional[str] = None,
        fitness: float = 0.5,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agents (agent_id, role, system_prompt, generation, parent_id, fitness)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    system_prompt = excluded.system_prompt,
                    fitness = excluded.fitness
                """,
                (agent_id, role, system_prompt, generation, parent_id, fitness),
            )

    def get_agent(self, agent_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_fitness(self, agent_id: str, rating: float) -> None:
        """Exponential moving average update: new_fitness = 0.7 * old + 0.3 * rating"""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agents
                SET fitness = 0.7 * fitness + 0.3 * ?,
                    total_runs = total_runs + 1
                WHERE agent_id = ?
                """,
                (rating / 100.0, agent_id),
            )

    # ------------------------------------------------------------------
    # Sessions & Analyses
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, topic: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, topic) VALUES (?, ?)",
                (session_id, topic),
            )

    def save_analysis(
        self, agent_id: str, topic: str, content: str, round_num: int, session_id: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO analyses (agent_id, topic, content, round, session_id) VALUES (?,?,?,?,?)",
                (agent_id, topic, content, round_num, session_id),
            )

    def save_final_report(self, session_id: str, report: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET final_report = ? WHERE session_id = ?",
                (report, session_id),
            )

    def save_user_rating(self, session_id: str, rating: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET user_rating = ? WHERE session_id = ?",
                (rating, session_id),
            )

    def get_past_analyses(self, agent_id: str, limit: int = 5) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.topic, a.content, s.user_rating
                FROM analyses a
                JOIN sessions s ON a.session_id = s.session_id
                WHERE a.agent_id = ? AND s.user_rating IS NOT NULL
                ORDER BY a.created_at DESC
                LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Learnings (cross-session knowledge)
    # ------------------------------------------------------------------

    def save_learning(
        self, agent_id: str, topic: str, insight: str, source: str = ""
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO learnings (agent_id, topic, insight, source) VALUES (?,?,?,?)",
                (agent_id, topic, insight, source),
            )

    def get_relevant_learnings(self, agent_id: str, limit: int = 3) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT insight FROM learnings WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
            return [r["insight"] for r in rows]
