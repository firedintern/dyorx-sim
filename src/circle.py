"""
Circle class: handles the savings circle mechanics.
Tracks pool balance, payouts, yield accrual, and member state.
"""


class Circle:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.apy = config.get("apy", 0.0)
        self.monthly_contribution = config["monthly_contribution_usd"]
        self.num_rounds = config["num_rounds"]
        self.payout_method = config.get("payout_method", "round_robin")
        self.yield_source = config.get("yield_source", None)

        self.pool_balance = 0.0
        self.total_yield_generated = 0.0
        self.current_round = 0
        self.payout_order = []
        self.round_log = []

    def setup_payout_order(self, agent_names: list[str]):
        """set round-robin payout order (shuffle for fairness)"""
        import random
        self.payout_order = list(agent_names)
        random.shuffle(self.payout_order)

    def process_round(self, agents: list, round_num: int) -> dict:
        """run one round of the circle"""
        self.current_round = round_num

        active_agents = [a for a in agents if a.active]
        contributions_this_round = 0
        skips = 0
        dropouts = 0
        decisions = {}

        # get state for agents to see
        state = self.get_state(agents)

        # each agent decides
        for agent in agents:
            decision = agent.decide(state)
            decisions[agent.name] = decision

            if decision["action"] == "contribute":
                self.pool_balance += self.monthly_contribution
                contributions_this_round += 1
            elif decision["action"] == "skip":
                skips += 1
            elif decision["action"] == "dropout":
                dropouts += 1

        # accrue yield on pool balance (monthly = APY / 12)
        monthly_yield = 0.0
        if self.apy > 0 and self.pool_balance > 0:
            monthly_yield = self.pool_balance * (self.apy / 12)
            self.total_yield_generated += monthly_yield
            self.pool_balance += monthly_yield

            # distribute yield proportionally to active contributing agents
            active_contributors = [a for a in agents if a.active and a.months_contributed > 0]
            if active_contributors:
                yield_per_agent = monthly_yield / len(active_contributors)
                for agent in active_contributors:
                    agent.yield_earned += yield_per_agent

        # process payout for this round
        payout_agent_name = self.payout_order[round_num - 1] if round_num <= len(self.payout_order) else None
        payout_amount = 0.0

        if payout_agent_name:
            payout_agent = next((a for a in agents if a.name == payout_agent_name), None)
            if payout_agent and payout_agent.active:
                # payout = contributions from active members this round
                payout_amount = contributions_this_round * self.monthly_contribution
                payout_agent.payout_received = True
                payout_agent.payout_amount = payout_amount
                self.pool_balance -= payout_amount

        round_data = {
            "round": round_num,
            "contributions": contributions_this_round,
            "skips": skips,
            "dropouts": dropouts,
            "pool_balance": self.pool_balance,
            "monthly_yield": monthly_yield,
            "payout_to": payout_agent_name,
            "payout_amount": payout_amount,
            "decisions": decisions,
            "active_count": len([a for a in agents if a.active])
        }
        self.round_log.append(round_data)
        return round_data

    def get_state(self, agents: list) -> dict:
        """current circle state for agent decision-making"""
        active = [a for a in agents if a.active]
        dropped = [a for a in agents if not a.active]
        return {
            "current_round": self.current_round,
            "total_rounds": self.num_rounds,
            "contribution_amount": self.monthly_contribution,
            "pool_balance": self.pool_balance,
            "active_members": len(active),
            "total_members": len(agents),
            "dropout_count": len(dropped),
            "apy": self.apy,
            "total_yield_generated": self.total_yield_generated
        }

    def summary(self) -> dict:
        return {
            "name": self.name,
            "apy": self.apy,
            "total_rounds": self.num_rounds,
            "pool_balance_final": self.pool_balance,
            "total_yield_generated": self.total_yield_generated,
            "round_log": self.round_log
        }
