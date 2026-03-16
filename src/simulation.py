"""
Simulation runner: creates agents, runs circles, injects random events.
Orchestrates the full experiment comparing traditional vs DYORX circles.
"""

import json
import random
from pathlib import Path
from openai import OpenAI

from .agent import Agent
from .circle import Circle


def load_config(config_dir: str = "config") -> tuple[dict, dict]:
    """load agent and scenario configs"""
    with open(Path(config_dir) / "agents.json") as f:
        agents_config = json.load(f)
    with open(Path(config_dir) / "scenarios.json") as f:
        scenarios_config = json.load(f)
    return agents_config, scenarios_config


def create_agents(
    agents_config: dict,
    num_agents: int,
    llm_client: OpenAI,
    model: str
) -> list[Agent]:
    """spawn agents with weighted personality distribution"""
    personalities = agents_config["personalities"]
    names = list(agents_config["name_pool"])
    random.shuffle(names)

    agents = []
    for i in range(num_agents):
        # weighted random personality
        weights = [p["weight"] for p in personalities]
        personality = random.choices(personalities, weights=weights, k=1)[0]
        name = names[i % len(names)]
        agent = Agent(name=name, personality=personality, llm_client=llm_client, model=model)
        agents.append(agent)

    return agents


def run_scenario(
    scenario_config: dict,
    agents_config: dict,
    llm_client: OpenAI,
    model: str,
    sim_config: dict,
    run_index: int = 1,
    on_round_complete=None
) -> dict:
    """run a single scenario (traditional or dyorx)"""
    num_agents = scenario_config["num_agents"]
    num_rounds = scenario_config["num_rounds"]

    # create fresh agents for this run
    agents = create_agents(agents_config, num_agents, llm_client, model)

    # create circle
    circle = Circle(scenario_config)
    circle.setup_payout_order([a.name for a in agents])

    random_events = sim_config.get("random_events", True)
    event_prob = sim_config.get("random_event_probability", 0.15)
    events_pool = sim_config.get("random_events_pool", [])

    # run rounds
    for round_num in range(1, num_rounds + 1):
        # inject random life events
        if random_events:
            for agent in agents:
                if agent.active and random.random() < event_prob:
                    event = random.choice(events_pool)
                    agent.set_random_event(event)

        round_data = circle.process_round(agents, round_num)

        if on_round_complete:
            on_round_complete(scenario_config["name"], run_index, round_data)

    # compile results
    return {
        "scenario": scenario_config["name"],
        "run_index": run_index,
        "apy": scenario_config.get("apy", 0),
        "num_agents": num_agents,
        "num_rounds": num_rounds,
        "agents": [a.summary() for a in agents],
        "circle": circle.summary(),
        "metrics": compute_metrics(agents, circle)
    }


def compute_metrics(agents: list[Agent], circle: Circle) -> dict:
    """compute key metrics for comparison"""
    total = len(agents)
    completed = [a for a in agents if a.active]
    dropped = [a for a in agents if not a.active]

    total_contributed = sum(a.total_contributed for a in agents)
    total_yield = sum(a.yield_earned for a in agents)
    avg_dropout_round = (
        sum(a.dropout_round for a in dropped) / len(dropped)
        if dropped else None
    )

    return {
        "completion_rate": len(completed) / total if total > 0 else 0,
        "completed_count": len(completed),
        "dropout_count": len(dropped),
        "total_contributed": total_contributed,
        "total_yield_earned": total_yield,
        "avg_dropout_round": avg_dropout_round,
        "pool_balance_final": circle.pool_balance,
        "total_yield_generated": circle.total_yield_generated,
        "avg_months_contributed": sum(a.months_contributed for a in agents) / total if total > 0 else 0,
        "avg_months_skipped": sum(a.months_skipped for a in agents) / total if total > 0 else 0,
    }


def run_full_experiment(
    llm_client: OpenAI,
    model: str,
    config_dir: str = "config",
    on_round_complete=None
) -> dict:
    """run all scenarios with multiple runs each, return full results"""
    agents_config, scenarios_config = load_config(config_dir)
    sim_config = scenarios_config.get("simulation", {})
    runs_per = sim_config.get("runs_per_scenario", 3)

    all_results = {}

    for scenario_key, scenario_config in scenarios_config["scenarios"].items():
        scenario_runs = []
        for run_idx in range(1, runs_per + 1):
            result = run_scenario(
                scenario_config=scenario_config,
                agents_config=agents_config,
                llm_client=llm_client,
                model=model,
                sim_config=sim_config,
                run_index=run_idx,
                on_round_complete=on_round_complete
            )
            scenario_runs.append(result)

        all_results[scenario_key] = scenario_runs

    return all_results
