"""
Circle class: handles the savings circle mechanics.
Tracks pool balance, payouts, yield accrual, and member state.

Payout model (aligned with DYORX product docs):
- Each round, all active members contribute their monthly amount into the pool.
- The pool earns yield on its balance (APY / 12 per month).
- DYORX takes a 15% spread on gross yield; members receive the remaining 85%.
- Yield is attributed pro-rata based on each member's total amount contributed.
- The designated member for that round receives the FULL pool (contributions +
  accumulated yield), which resets the pool back to near zero each round.
- This mirrors the traditional ROSCA model: Member A gets $1,000 in month 1
  (all 10 × $100 contributions), Member B gets $1,000 in month 2, etc.
"""

# DYORX takes 15% of gross yield as platform revenue; members keep 85%
DYORX_YIELD_SPREAD = 0.15


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
        self.total_dyorx_revenue = 0.0
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

        # accrue yield on pool balance (monthly rate = APY / 12)
        # DYORX takes a 15% spread; members receive 85% of gross yield
        monthly_yield_gross = 0.0
        monthly_yield_net = 0.0
        dyorx_revenue_this_round = 0.0

        if self.apy > 0 and self.pool_balance > 0:
            monthly_yield_gross = self.pool_balance * (self.apy / 12)
            dyorx_revenue_this_round = monthly_yield_gross * DYORX_YIELD_SPREAD
            monthly_yield_net = monthly_yield_gross - dyorx_revenue_this_round

            self.total_yield_generated += monthly_yield_gross
            self.total_dyorx_revenue += dyorx_revenue_this_round
            # only net yield enters the pool (platform revenue is extracted)
            self.pool_balance += monthly_yield_net

            # attribute yield pro-rata by each member's total contributed amount
            # (matches DYORX docs: "pro-rata attribution based on deposit timing")
            active_contributors = [a for a in agents if a.active and a.total_contributed > 0]
            total_principal = sum(a.total_contributed for a in active_contributors)
            if active_contributors and total_principal > 0:
                for agent in active_contributors:
                    agent.yield_earned += monthly_yield_net * (agent.total_contributed / total_principal)

        # process payout for this round
        # payout = FULL pool balance (contributions this round + accumulated yield)
        # this matches ROSCA mechanics: the pot is awarded whole to the designated member
        payout_agent_name = self.payout_order[round_num - 1] if round_num <= len(self.payout_order) else None
        payout_amount = 0.0
        payout_contributions = 0.0
        payout_yield = 0.0

        if payout_agent_name:
            payout_agent = next((a for a in agents if a.name == payout_agent_name), None)
            if payout_agent and payout_agent.active:
                # the full pool goes to this round's recipient
                payout_amount = self.pool_balance
                payout_contributions = contributions_this_round * self.monthly_contribution
                payout_yield = payout_amount - payout_contributions
                payout_agent.payout_received = True
                payout_agent.payout_amount = payout_amount
                # pool resets to zero after payout (clean slate for next round)
                self.pool_balance = 0.0

        round_data = {
            "round": round_num,
            "contributions": contributions_this_round,
            "skips": skips,
            "dropouts": dropouts,
            "pool_balance": self.pool_balance,
            "monthly_yield_gross": monthly_yield_gross,
            "monthly_yield_net": monthly_yield_net,
            "dyorx_revenue": dyorx_revenue_this_round,
            "payout_to": payout_agent_name,
            "payout_amount": payout_amount,
            "payout_contributions": payout_contributions,
            "payout_yield_component": payout_yield,
            "decisions": decisions,
            "active_count": len([a for a in agents if a.active])
        }
        self.round_log.append(round_data)
        return round_data

    def get_state(self, agents: list) -> dict:
        """current circle state for agent decision-making"""
        active = [a for a in agents if a.active]
        dropped = [a for a in agents if not a.active]
        total_pool_contributions = sum(a.total_contributed for a in agents)
        return {
            "current_round": self.current_round,
            "total_rounds": self.num_rounds,
            "contribution_amount": self.monthly_contribution,
            "pool_balance": self.pool_balance,
            "active_members": len(active),
            "total_members": len(agents),
            "dropout_count": len(dropped),
            "apy": self.apy,
            "total_yield_generated": self.total_yield_generated,
            "dyorx_yield_spread": DYORX_YIELD_SPREAD,
            "total_pool_contributions": total_pool_contributions
        }

    def summary(self) -> dict:
        return {
            "name": self.name,
            "apy": self.apy,
            "total_rounds": self.num_rounds,
            "pool_balance_final": self.pool_balance,
            "total_yield_generated": self.total_yield_generated,
            "total_dyorx_revenue": self.total_dyorx_revenue,
            "round_log": self.round_log
        }
