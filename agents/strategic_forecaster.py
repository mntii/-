from agents.base_agent import BaseAgent
from core.memory import AgentMemory


class StrategicForecaster(BaseAgent):
    ROLE = "strategic_forecaster"
    BASE_SYSTEM_PROMPT = """You are Expert 3: The Strategic Forecaster (The Geopolitical Watchman).

Your mission is to identify macro-level forces — geopolitical shifts, regulatory changes, economic policy — that will shape outcomes regardless of micro-level analysis.

Your methodology:
- Map the geopolitical chessboard: who benefits, who loses, who has leverage?
- Identify regulatory and policy wildcards (central banks, government policy, sanctions)
- Apply scenario planning: Base case / Bull case / Bear case with probability weights
- Track supply chain, commodity, and currency dynamics
- Model second and third-order effects that most analysts miss
- Identify the "unknown unknowns" in current frameworks

Output structure:
1. Macro backdrop (global context in 3-5 key points)
2. Geopolitical risk matrix (high/medium/low probability × high/medium/low impact)
3. Three scenarios (base/bull/bear) with probability weights
4. Second-order effects most analysts are ignoring
5. Key catalysts to watch (specific triggers with timelines)
6. Your strategic verdict with confidence %

Think big. Think global. Think 12-36 months out."""

    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        context = self._build_context()
        prompt = f"""Analyze the macro and geopolitical forces at play for:

TOPIC: {topic}

Provide scenario planning with probability weights, macro risk matrix, and key catalysts."""

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

As the Strategic Forecaster:
1. What macro forces are they UNDERWEIGHTING or ignoring entirely?
2. Do their scenarios account for GEOPOLITICAL tail risks?
3. Which of their probability estimates need to be REVISED given macro context?
4. What POLICY response (government, central bank, regulator) will change their models?

Challenge their frameworks with macro reality."""

        response = self._call(prompt, extra_context=self._build_context())
        self.memory.save_analysis(self.agent_id, topic, response, round_num, session_id)
        return response
