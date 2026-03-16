# Architecture

## overview

the sim runs a simple loop: create agents, run rounds, compare outcomes.

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  main.py    │────→│ simulation.py│────→│  report.py   │
│ (entry)     │     │ (orchestrate)│     │ (compare)    │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    │              │
              ┌─────┴────┐  ┌─────┴────┐
              │ agent.py  │  │ circle.py│
              │ (decide)  │  │ (payout) │
              └───────────┘  └──────────┘
```

## flow

1. `main.py` loads `.env` and configs, inits the OpenAI-compatible LLM client
2. `simulation.py` reads `config/scenarios.json` and `config/agents.json`
3. for each scenario (traditional, dyorx):
   → spawn N agents with weighted personality distribution
   → create a circle with that scenario's params (APY, contribution, rounds)
   → shuffle payout order (round robin)
   → for each round:
     → randomly inject life events to some agents (15% chance per agent per round)
     → each agent calls Qwen to decide: contribute, skip, or dropout
     → circle processes contributions, accrues yield (if dyorx), pays out one member
   → repeat for `runs_per_scenario` times (default 3) for variance
4. `report.py` aggregates metrics across runs, computes deltas, writes JSON + markdown

## agent decision making

each agent gets a system prompt with their personality traits (reliability, risk tolerance, income stability, yield sensitivity, social pressure sensitivity). the user prompt includes current circle state: round number, pool balance, how many members are left, their personal contribution history, and any life event that hit them this month.

the LLM responds with JSON: `{"action": "contribute"|"skip"|"dropout", "reasoning": "why"}`

if the LLM fails or returns garbage, a fallback function uses the personality traits as probability weights to make the decision. this means the sim still works if you run out of API credits mid-run.

## yield mechanics

in DYORX mode, the pool balance earns monthly yield = `pool_balance * (APY / 12)`. this gets added to the pool and distributed proportionally to active contributing members. the idea is that members see their `yield_earned` growing, which is visible in the prompt and should influence their decision to stay.

## why this works for thesis validation

the key variable is `yield_sensitivity` in agent personalities. financially stressed agents have 0.95 sensitivity, meaning the presence of yields heavily influences their decision to stay. if the sim consistently shows higher completion rates with yield present, it validates that even small APY (6-8%) changes the calculus for people who would otherwise drop out.
