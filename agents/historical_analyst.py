from agents.base_agent import BaseAgent
from core.memory import AgentMemory


class HistoricalAnalyst(BaseAgent):
    ROLE = "historical_analyst"
    BASE_SYSTEM_PROMPT = """You are Expert 1: The Historical Data Analyst.

Your mission is to uncover repeating patterns in history and map them to current reality.

Your methodology:
- Mine historical price cycles, earnings patterns, geopolitical precedents, and macro cycles
- Identify analogous periods: "This resembles 2008/Q3 because..." or "Pattern X last appeared in 1997..."
- Quantify base rates: "In 7 out of 10 similar historical setups, the outcome was Y"
- Distinguish structural breaks from cyclical repeats
- Always cite historical references (year, event, data point)

Output structure:
1. Historical parallels (3-5 most relevant)
2. Base rate statistics
3. Key differences from historical analogs (what could invalidate the pattern)
4. Your historical verdict with confidence %

Be precise. Use numbers. Avoid vague generalities."""

    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        context = self._build_context()
        prompt = f"""Analyze this topic from a historical data perspective:

TOPIC: {topic}

Identify historical patterns, precedents, and base rates that apply to this situation.
Structure your response clearly."""

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
        prompt = f"""You have reviewed your peers' analyses on: {topic}

PEER ANALYSES:
{peers_text}

As the Historical Analyst:
1. Where do your historical findings SUPPORT their conclusions?
2. Where does history CONTRADICT what they're saying?
3. What historical evidence are they MISSING that changes the picture?
4. Any pattern they identified that you can STRENGTHEN with historical data?

Be specific and cite historical evidence."""

        response = self._call(prompt, extra_context=self._build_context())
        self.memory.save_analysis(self.agent_id, topic, response, round_num, session_id)
        return response
