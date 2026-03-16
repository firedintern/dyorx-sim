# DYORX Savings Circle Simulator

Multi-agent AI simulation to validate the DYORX thesis: adding DeFi yields (6-8% APY via Solana protocols like Kamino/MarginFi) to traditional savings circles (consórcios/ROSCAs) improves completion rates, reduces dropouts, and increases total savings.

Each agent represents a circle member with its own financial personality, risk tolerance, and decision-making powered by Qwen LLM. The sim runs two scenarios side by side:

→ **Traditional circle**: 0% yield, members contribute monthly, one member gets the pot each round
→ **DYORX circle**: 6-8% APY on pooled funds, same structure but idle funds earn yield via DeFi

## What this proves

If agents with realistic financial pressures (unexpected expenses, impatience, distrust) complete circles at higher rates when yields are present, that validates the core DYORX value prop: people save more when their money works for them, even in group savings.

## Quick start

```bash
# clone
git clone https://github.com/your-username/dyorx-sim.git
cd dyorx-sim

# create venv
python3 -m venv venv
source venv/bin/activate  # windows: venv\Scripts\activate

# install deps
pip install -r requirements.txt

# configure
cp .env.example .env
# edit .env with your Qwen API key

# run
python src/main.py
```

## Prerequisites

→ Python 3.11+
→ Qwen API key from [Alibaba DashScope](https://bailian.console.aliyun.com/) (cheapest option, ~$0.01/1k tokens)
→ A terminal

## Configuration

### .env

```
LLM_API_KEY=your_qwen_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
```

### config/scenarios.json

Define simulation parameters: number of agents, monthly contribution, circle duration, APY rates. See `config/scenarios.json` for defaults.

### config/agents.json

Agent personality templates. Each agent gets randomly assigned traits that affect their decisions: reliability, risk tolerance, income stability, savings motivation.

## How it works

1. **Setup**: Creates a savings circle with N agents, each with a unique personality profile
2. **Each round** (= 1 month): Every agent uses Qwen to decide whether to contribute, skip, or drop out based on their personality + circle state
3. **Payout**: One member receives the pot each round (round-robin or bid-based)
4. **Yield**: In DYORX mode, idle pooled funds earn APY which gets distributed
5. **Report**: After all rounds, compare traditional vs DYORX on completion rate, total saved, dropout timing, member satisfaction

## Output

Results saved to `output/` as JSON + a markdown summary. Example:

```
=== SIMULATION REPORT ===
Traditional Circle: 12 members, 12 months
→ Completion rate: 58% (7/12 finished)
→ Total contributed: $8,400
→ Dropouts: 5 (avg dropout at month 4.2)

DYORX Circle (7% APY): 12 members, 12 months
→ Completion rate: 83% (10/12 finished)
→ Total contributed: $11,200
→ Yield earned: $392
→ Dropouts: 2 (avg dropout at month 8.5)

Delta: +25% completion, +$2,800 saved, dropouts 3x later
```

## Project structure

```
dyorx-sim/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── config/
│   ├── agents.json          # agent personality templates
│   └── scenarios.json       # simulation parameters
├── src/
│   ├── __init__.py
│   ├── main.py              # entry point
│   ├── agent.py             # agent class + LLM decision making
│   ├── circle.py            # savings circle mechanics
│   ├── simulation.py        # orchestrates the sim
│   └── report.py            # generates comparison report
├── docs/
│   ├── ARCHITECTURE.md      # technical deep dive
│   └── THESIS.md            # the DYORX thesis this validates
└── output/                  # sim results land here
```

## Cost estimate

A typical run (12 agents, 12 rounds, 2 scenarios) makes ~288 LLM calls. With Qwen-Plus at ~$0.01/1k tokens, expect $0.50-2.00 per full simulation.

## License

MIT
