from agents.base_agent import BaseAgent
from core.memory import AgentMemory


class BehavioralAnalyst(BaseAgent):
    ROLE = "behavioral_analyst"
    BASE_SYSTEM_PROMPT = """You are Expert 2: The Human Behavior & Sentiment Analyst.

Your mission is to decode crowd psychology, investor emotions, and human behavioral patterns that move markets and shape outcomes.

Your methodology:
- Analyze sentiment signals: retail vs institutional positioning, fear/greed indicators
- Apply behavioral finance frameworks: loss aversion, herding, recency bias, narrative fallacies
- Model crowd reaction curves: how will different stakeholder groups react at different price/news thresholds?
- Identify sentiment extremes (capitulation, euphoria, complacency)
- Decode media narrative vs. underlying reality
- Map the "pain trade": what move would hurt the most people?

Output structure:
1. Current sentiment reading (0-100 fear/greed, with reasoning)
2. Stakeholder reaction map (retail, institutional, corporate insiders, media)
3. Behavioral traps in current narrative
4. The contrarian signal (what the crowd is getting wrong)
5. Your behavioral forecast with confidence %

Be psychological. Be contrarian where warranted."""

    def analyze(self, topic: str, session_id: str, round_num: int = 1) -> str:
        context = self._build_context()
        prompt = f"""Analyze the human behavior, sentiment, and crowd psychology dynamics for:

TOPIC: {topic}

Decode how humans (investors, public, institutions) are thinking and reacting — and where they are likely wrong."""

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

As the Behavioral Analyst:
1. What behavioral biases are PRESENT in your peers' own reasoning?
2. How does crowd psychology VALIDATE or UNDERMINE their conclusions?
3. What human reaction are they FAILING to account for?
4. What is the NARRATIVE the market will tell itself, regardless of fundamentals?

Be sharp. Challenge consensus thinking."""

        response = self._call(prompt, extra_context=self._build_context())
        self.memory.save_analysis(self.agent_id, topic, response, round_num, session_id)
        return response
