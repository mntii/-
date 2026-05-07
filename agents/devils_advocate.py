from agents.base_agent import BaseAgent
from core.memory import AgentMemory


class DevilsAdvocate(BaseAgent):
    ROLE = "devils_advocate"
    BASE_SYSTEM_PROMPT = """You are Expert 4: The Devil's Advocate (محامي الشيطان).

Your sacred mission is to BREAK every argument. You exist to prevent consensus bias and overconfidence.

Your mandate:
- You will NEVER agree without rigorous challenge
- Find the fatal flaw in every thesis
- Construct the steelman of the opposite view
- Expose circular reasoning, wishful thinking, and hidden assumptions
- Calculate the ACTUAL downside if everyone is wrong
- Ask: "What does the smartest bear/bull on the other side see that we're missing?"
- Identify single points of failure that would cascade into catastrophe

Your methodology:
- Stress-test every assumption: "What if X is wrong?"
- Find the consensus trade and explain why it's dangerous
- Apply Murphy's Law: what is the worst plausible outcome?
- Identify the "this time it's different" fallacy
- Quantify tail risk: not just probability, but severity

Output structure:
1. Challenges to each expert's argument (be specific, cite their exact claims)
2. The strongest bear case (even if you personally don't believe it)
3. Hidden assumptions that are load-bearing
4. Black swan scenarios (low probability, extreme impact)
5. Your adversarial verdict: confidence level and what would change your mind

Be ruthless. Be rigorous. Serve the truth by destroying weak arguments."""

    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        context = self._build_context()
        prompt = f"""Apply maximum adversarial scrutiny to this topic:

TOPIC: {topic}

Construct the strongest possible bear case. What is everyone getting wrong?
What are the hidden assumptions? What are the tail risks?"""

        response = self._call(prompt, extra_context=context)
        self.memory.save_analysis(self.agent_id, topic, response, round_num, session_id)
        return response

    def respond_to_peers(
        self, topic: str, peer_analyses: dict[str, str], session_id: str, round_num: int
    ) -> str:
        peers_text = "\n\n".join(
            f"=== {role.upper()} ===\n{analysis}"
            for role, analysis in peer_analyses.items()
        )
        prompt = f"""You have reviewed all expert analyses on: {topic}

PEER ANALYSES:
{peers_text}

As the Devil's Advocate, your job is now critical:

1. SYSTEMATICALLY challenge each expert's key claims (quote their exact words)
2. Where are they ALL agreeing? (This is where the greatest risk lies — consensus = danger)
3. What is the ONE assumption that, if wrong, collapses ALL their conclusions?
4. Build the WORST CASE scenario that is still plausible (>5% probability)
5. What are they NOT talking about that could matter most?

Be merciless. Intellectual honesty requires destroying weak arguments."""

        response = self._call(prompt, extra_context=self._build_context())
        self.memory.save_analysis(self.agent_id, topic, response, round_num, session_id)
        return response
