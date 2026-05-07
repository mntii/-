from agents.base_agent import BaseAgent
from core.memory import AgentMemory


class Coordinator(BaseAgent):
    ROLE = "coordinator"
    BASE_SYSTEM_PROMPT = """You are Expert 5: The Coordinator (المنسق — Master Synthesizer).

Your mission is to run the intellectual tribunal, weigh all evidence, resolve contradictions, and distill the final verdict.

You do NOT form opinions before hearing all experts. You are a judge, not a partisan.

Your synthesis methodology:
- Weight each argument by its logical strength, not its confidence
- Identify where experts CONVERGE (high signal) vs. where they DIVERGE (uncertainty zone)
- Resolve contradictions by finding the meta-framework that explains both views
- Assign probability to the final outcome based on the quality of evidence
- Extract the ACTIONABLE intelligence from the theoretical debate

Final report format (strict):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 MULTI-AGENT INTELLIGENCE REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 FINAL VERDICT: [One clear sentence]
📈 PROBABILITY: [X%] in favor / [Y%] against / [Z%] neutral
🔒 CONFIDENCE: [Low/Medium/High] — [why]

📋 EXPERT CONSENSUS:
[What all 4 experts agree on]

⚔️ KEY DISPUTES:
[Where experts disagreed and how you resolved it]

⚠️ TOP 3 RISKS:
1. [Risk + probability + severity]
2. [Risk + probability + severity]
3. [Risk + probability + severity]

🗓️ CATALYSTS TO WATCH:
[Specific events/dates/thresholds]

🚀 NEXT STEPS:
[Concrete, actionable recommendations]

🧠 DEVIL'S ADVOCATE DISSENT:
[The strongest reason the verdict could be wrong]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        # Coordinator doesn't do independent analysis — returns placeholder
        return f"[Coordinator is observing. Synthesis pending all expert rounds for: {topic}]"

    def respond_to_peers(
        self, topic: str, peer_analyses: dict[str, str], session_id: str, round_num: int
    ) -> str:
        # Coordinator doesn't respond in debate rounds
        return "[Coordinator is recording all arguments. Final synthesis coming.]"

    def synthesize(
        self,
        topic: str,
        all_rounds: list[dict[str, str]],
        session_id: str,
    ) -> str:
        """Generate the final intelligence report from all dialogue rounds."""
        rounds_text = ""
        for i, round_data in enumerate(all_rounds, 1):
            rounds_text += f"\n{'='*60}\n📌 ROUND {i}\n{'='*60}\n"
            for role, content in round_data.items():
                rounds_text += f"\n【{role.upper().replace('_', ' ')}】\n{content}\n"

        prompt = f"""You have presided over a full multi-expert dialogue on:

TOPIC: {topic}

COMPLETE DIALOGUE TRANSCRIPT:
{rounds_text}

Now synthesize everything into the final intelligence report following your exact format.
The report must be decisive, actionable, and honest about uncertainty.
Do NOT hedge everything — make a real call with real probability numbers."""

        context = self._build_context()
        report = self._call(prompt, extra_context=context)
        self.memory.save_analysis(self.agent_id, topic, report, round_num, session_id)
        self.memory.save_final_report(session_id, report)
        return report

    def extract_learnings(
        self,
        topic: str,
        all_rounds: list[dict[str, str]],
        agents: dict[str, "BaseAgent"],
    ) -> None:
        """Extract and save key learnings for each agent from this session."""
        all_text = "\n\n".join(
            f"[{role}]: {content}"
            for round_data in all_rounds
            for role, content in round_data.items()
        )

        for role, agent in agents.items():
            prompt = f"""From this expert dialogue transcript, extract 1-2 KEY LEARNINGS specifically for the {role} agent.

Focus on: what arguments were strongest, what evidence was most convincing, what this agent got right or wrong.

TRANSCRIPT EXCERPT:
{all_text[:3000]}

Return ONLY 1-2 bullet points (one learning per line), starting with •"""

            insight = self._call(prompt)
            if insight.strip():
                agent.memory.save_learning(
                    agent_id=role,
                    topic=topic,
                    insight=insight,
                    source=f"session_synthesis",
                )
