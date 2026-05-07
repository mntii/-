# Multi-Agent Intelligence System

5 specialized AI experts that debate, challenge each other, evolve, and reproduce.

## Agents

| # | Expert | Role |
|---|--------|------|
| 1 | 📜 Historical Analyst | Historical patterns & base rates |
| 2 | 🧠 Behavioral Analyst | Crowd psychology & sentiment |
| 3 | 🌍 Strategic Forecaster | Macro, geopolitical scenarios |
| 4 | 😈 Devil's Advocate | Challenges ALL arguments |
| 5 | ⚖️ Coordinator | Synthesizes → Final report |

## Setup

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY
pip install -r requirements.txt
python main.py
```

## Usage

```bash
python main.py                                      # Interactive mode
python main.py --topic "Saudi Aramco 2025"         # Direct topic
python main.py --fitness                            # Agent fitness table
```

## How Evolution Works

After each analysis session:
1. User rates accuracy (0–100)
2. Each agent's fitness score updates via exponential moving average
3. **Weak agents** (fitness < 0.4) → Claude rewrites their system prompt
4. **Critical agents** (fitness < 0.3) → Full prompt regeneration
5. **Strong agents** (fitness > 0.75) → Spawn child variants with mutations

Over time, agents learn which analytical approaches work and carry that knowledge forward.
