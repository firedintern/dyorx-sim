"""
Simulation runner: creates agents, runs circles, injects random events.
Orchestrates the full experiment comparing traditional vs DYORX circles.
"""

import json
import random
from pathlib import Path
from anthropic import Anthropic

from .agent import Agent
from .circle import Circle


def load_config(config_dir: str = "config") -> tuple[dict, dict]:
    """load agent and scenario configs"""
    with open(Path(config_dir) / "agents.json") as f:
        agents_config = json.load(f)
    with open(Path(config_dir) / "scenarios.json") as f:
        scenarios_config = json.load(f)
    return agents_config, scenarios_config


def _get_personality_by_type(personalities: list, ptype: str) -> dict:
    """look up a personality dict by type name"""
    for p in personalities:
        if p["type"] == ptype:
            return p
    raise ValueError(f"Unknown personality type: '{ptype}'. Check agents.json.")


def create_agents_from_composition(
    agents_config: dict,
    composition: list | str,
    llm_client: Anthropic,
    model: str
) -> list[Agent]:
    """
    Build agents from a explicit composition list or random weighted draw.
    composition is either:
      - "random"  → weighted random draw (control group)
      - list of {"type": str, "count": int}
    """
    personalities = agents_config["personalities"]
    names = list(agents_config["name_pool"])
    random.shuffle(names)

    agents = []

    if composition == "random":
        weights = [p["weight"] for p in personalities]
        # determine num_agents from total in scenarios (caller passes total via len check)
        # we generate 10 agents for the random group
        for i in range(10):
            personality = random.choices(personalities, weights=weights, k=1)[0]
            name = names[i % len(names)]
            agents.append(Agent(name=name, personality=personality,
                                llm_client=llm_client, model=model))
    else:
        i = 0
        for slot in composition:
            ptype = slot["type"]
            count = slot["count"]
            personality = _get_personality_by_type(personalities, ptype)
            for _ in range(count):
                name = names[i % len(names)]
                agents.append(Agent(name=name, personality=personality,
                                    llm_client=llm_client, model=model))
                i += 1

    return agents


def run_scenario(
    scenario_config: dict,
    agents_config: dict,
    llm_client: Anthropic,
    model: str,
    sim_config: dict,
    run_index: int = 1,
    composition_meta: dict = None,
    on_round_complete=None
) -> dict:
    """run a single scenario (traditional or dyorx) with a given circle composition"""
    num_rounds = scenario_config["num_rounds"]

    # build agents from the composition for this run
    composition = composition_meta["composition"] if composition_meta else "random"
    agents = create_agents_from_composition(agents_config, composition, llm_client, model)
    num_agents = len(agents)

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
            label = composition_meta["label"] if composition_meta else f"run {run_index}"
            on_round_complete(scenario_config["name"], run_index, label, round_data)

    # compile results
    return {
        "scenario": scenario_config["name"],
        "run_index": run_index,
        "composition_label": composition_meta["label"] if composition_meta else "random",
        "apy": scenario_config.get("apy", 0),
        "num_agents": num_agents,
        "num_rounds": num_rounds,
        "agents": [a.summary() for a in agents],
        "agents_swarm": [a.swarm_summary() for a in agents],
        "circle": circle.summary(),
        "metrics": compute_metrics(agents, circle)
    }


def compute_metrics(agents: list[Agent], circle: Circle) -> dict:
    """compute key metrics for comparison"""
    total = len(agents)
    completed = [a for a in agents if a.active]
    dropped = [a for a in agents if not a.active]

    total_contributed = sum(a.total_contributed for a in agents)
    total_yield_net = sum(a.yield_earned for a in agents)
    avg_dropout_round = (
        sum(a.dropout_round for a in dropped) / len(dropped)
        if dropped else None
    )

    paid_out = [a for a in agents if a.payout_received]
    avg_payout_received = (
        sum(a.payout_amount for a in paid_out) / len(paid_out)
        if paid_out else 0.0
    )

    return {
        "completion_rate": len(completed) / total if total > 0 else 0,
        "completed_count": len(completed),
        "dropout_count": len(dropped),
        "total_contributed": total_contributed,
        "total_yield_earned_by_members": total_yield_net,
        "total_yield_generated_gross": circle.total_yield_generated,
        "total_dyorx_revenue": circle.total_dyorx_revenue,
        "avg_dropout_round": avg_dropout_round,
        "pool_balance_final": circle.pool_balance,
        "payout_recipients": len(paid_out),
        "avg_payout_received": avg_payout_received,
        "avg_months_contributed": sum(a.months_contributed for a in agents) / total if total > 0 else 0,
        "avg_months_skipped": sum(a.months_skipped for a in agents) / total if total > 0 else 0,
    }


def run_full_experiment(
    llm_client: Anthropic,
    model: str,
    config_dir: str = "config",
    on_round_complete=None
) -> dict:
    """run all scenarios with one run per circle composition, return full results"""
    agents_config, scenarios_config = load_config(config_dir)
    sim_config = scenarios_config.get("simulation", {})
    compositions = sim_config.get("circle_compositions", [])

    all_results = {}

    for scenario_key, scenario_config in scenarios_config["scenarios"].items():
        scenario_runs = []
        for comp_meta in compositions:
            run_idx = comp_meta["circle_index"]
            result = run_scenario(
                scenario_config=scenario_config,
                agents_config=agents_config,
                llm_client=llm_client,
                model=model,
                sim_config=sim_config,
                run_index=run_idx,
                composition_meta=comp_meta,
                on_round_complete=on_round_complete
            )
            scenario_runs.append(result)

        all_results[scenario_key] = scenario_runs

    return all_results
