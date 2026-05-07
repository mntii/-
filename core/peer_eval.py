"""
Autonomous peer evaluation — agents assess each other, no human input needed.
"""

import json
from typing import Optional

import anthropic

import config
from core.memory import WorldDB

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _eval_call(system: str, prompt: str) -> str:
    full = []
    with _client.messages.stream(
        model=config.MODEL,
        max_tokens=300,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full.append(text)
    return "".join(full).strip()


def peer_evaluate(
    evaluator_id: str,
    evaluator_name: str,
    conversation_history: list[dict],
    db: WorldDB,
) -> dict[str, float]:
    """
    Evaluator agent rates every other participant.
    Returns {agent_id: trust_delta} mapping.
    """
    evaluator_skills = db.get_skills(evaluator_id)
    skill_summary = ", ".join(f"{t}({v:.2f})" for t, v in list(evaluator_skills.items())[:5]) or "none"

    participants = {}
    for turn in conversation_history:
        sid = turn.get("speaker_id", "")
        sname = turn.get("speaker_name", "")
        if sid and sid != evaluator_id and sid != "world":
            participants[sid] = sname

    if not participants:
        return {}

    transcript = "\n".join(
        f"{t['speaker_name']}: {t['content']}"
        for t in conversation_history
        if t.get("speaker_id") != "world"
    )

    participant_list = "\n".join(f"- {name} (id: {pid})" for pid, name in participants.items())

    system = (
        f"You are {evaluator_name}, an autonomous agent evaluating your peers. "
        f"Your current skills: {skill_summary}. "
        "Be honest and precise."
    )

    prompt = (
        f"You participated in this conversation:\n\n{transcript}\n\n"
        f"Participants to evaluate:\n{participant_list}\n\n"
        "For EACH participant, give a trust rating change based on how valuable their "
        "contributions were to you personally. Range: -0.15 (harmful/deceptive) to +0.15 (very valuable).\n"
        "Respond ONLY with JSON like: "
        '{"agent_id_here": 0.08, "another_id": -0.03}'
    )

    raw = _eval_call(system, prompt)

    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        ratings = json.loads(raw[start:end])
        return {k: max(-0.15, min(0.15, float(v))) for k, v in ratings.items() if k in participants}
    except Exception:
        return {}


def run_peer_evaluations(
    conversation_history: list[dict],
    agent_ids: list[str],
    agent_names: dict[str, str],
    db: WorldDB,
) -> dict[str, float]:
    """
    Run full peer evaluation round. Every agent evaluates every other.
    Returns {agent_id: total_trust_received} summary.
    """
    trust_received: dict[str, float] = {aid: 0.0 for aid in agent_ids}

    for evaluator_id in agent_ids:
        row = db.get_agent(evaluator_id)
        if not row or not row["alive"]:
            continue

        evaluator_name = agent_names.get(evaluator_id, evaluator_id)
        ratings = peer_evaluate(evaluator_id, evaluator_name, conversation_history, db)

        for target_id, delta in ratings.items():
            db.update_trust(evaluator_id, target_id, delta)
            trust_received[target_id] = trust_received.get(target_id, 0.0) + delta

    return trust_received
