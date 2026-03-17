"""
Agent class: Each agent is a savings circle member with a personality.
Uses Claude (Anthropic) to make monthly decisions: contribute, skip, or drop out.
"""

import json
import random
from anthropic import Anthropic


class Agent:
    def __init__(self, name: str, personality: dict, llm_client: Anthropic, model: str):
        self.name = name
        self.personality = personality
        self.llm_client = llm_client
        self.model = model

        self.active = True
        self.total_contributed = 0.0
        self.months_contributed = 0
        self.months_skipped = 0
        self.payout_received = False
        self.payout_amount = 0.0
        self.yield_earned = 0.0
        self.dropout_round = None
        self.decision_history = []
        self.current_event = None

    def set_random_event(self, event: str | None):
        """inject a random life event for this round"""
        self.current_event = event

    def decide(self, circle_state: dict) -> dict:
        """
        ask the LLM to decide what this agent does this round.
        returns: {"action": "contribute"|"skip"|"dropout", "reasoning": str}
        """
        if not self.active:
            return {"action": "inactive", "reasoning": "already dropped out"}

        prompt = self._build_prompt(circle_state)

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                system=self._system_prompt(circle_state),
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                max_tokens=300
            )
            raw = response.content[0].text.strip()
            decision = self._parse_decision(raw)
        except Exception as e:
            # fallback to personality-based decision if LLM fails
            decision = self._fallback_decision(circle_state)
            decision["reasoning"] = f"LLM error ({e}), used fallback logic"

        self._apply_decision(decision, circle_state)
        return decision

    def _system_prompt(self, circle_state: dict = None) -> str:
        apy = circle_state.get("apy", 0) if circle_state else 0

        mechanics = """You are a member of a savings circle (also known as consórcio or ROSCA). Here is how it works:

- A group of members each contribute a fixed amount every month to a shared pool.
- Each month, one member receives the entire pot (all contributions for that round).
- The payout order is set at the beginning and rotates so every member gets one payout by the end.
- If you drop out, you lose your place in the rotation and may not get your payout at all.
- If others drop out, the pot each month gets smaller, so everyone's payout is worth less.
- The circle only works if everyone keeps contributing. Every dropout hurts the whole group."""

        if apy > 0:
            mechanics += """

This circle also earns 7% APY on the pooled funds through DeFi yield (Kamino USDC vaults on Solana). This means the money sitting in the pool between payouts earns interest. You earn yield proportional to what you've contributed — skip a month and your yield share shrinks. This is free money on top of the normal circle payout that would not exist in a traditional savings circle."""

        # impatient_saver: adjust effective reliability based on round
        effective_reliability = self.personality["reliability"]
        if (self.personality["type"] == "impatient_saver"
                and circle_state
                and circle_state.get("current_round", 0) > self.personality.get("reliability_decay_after_round", 5)
                and not self.payout_received):
            effective_reliability = self.personality.get("reliability_late", 0.4)

        personality_block = f"""
You are {self.name}.

Your personality:
→ Type: {self.personality['type']}
→ Description: {self.personality['description']}
→ Reliability: {effective_reliability:.0%}
→ Risk tolerance: {self.personality['risk_tolerance']:.0%}
→ Income stability: {self.personality['income_stability']:.0%}
→ Sensitivity to yields/earnings: {self.personality['yield_sensitivity']:.0%}
→ Social pressure sensitivity: {self.personality['social_pressure_sensitivity']:.0%}"""

        return f"""{mechanics}
{personality_block}

You must respond ONLY with valid JSON in this exact format:
{{"action": "contribute" or "skip" or "dropout", "reasoning": "one sentence why"}}

Nothing else. No markdown, no explanation outside the JSON."""

    def _build_prompt(self, state: dict) -> str:
        contribution = state["contribution_amount"]
        total_rounds = state["total_rounds"]
        num_agents = state["total_members"]
        apy = state.get("apy", 0)

        lines = [
            f"Round {state['current_round']} of {total_rounds}.",
            f"Monthly contribution: ${contribution}",
            f"Members still active: {state['active_members']} of {num_agents}",
            f"Pool balance this round: ${state['pool_balance']:.2f}",
            f"Your total contributed so far: ${self.total_contributed:.2f}",
            f"You have contributed {self.months_contributed} months, skipped {self.months_skipped}",
            f"Have you received your payout yet: {'YES' if self.payout_received else 'NO — you are still waiting for your turn'}",
        ]

        if apy > 0:
            # projected total yield: contribution * num_agents * apy * (total_rounds/12) / num_agents
            # simplifies to: contribution * apy * (total_rounds / 12)
            projected_total_yield = contribution * apy * (total_rounds / 12)
            lines.append(
                f"You have earned ${self.yield_earned:.2f} in passive income so far just by being in this circle. "
                f"If you drop out, you permanently lose this income stream. "
                f"Members who stay until the end are projected to earn ${projected_total_yield:.2f} total in yield on top of their payout."
            )
            # yield share visibility
            total_pool_contributions = state.get("total_pool_contributions", 0)
            if total_pool_contributions > 0 and self.total_contributed > 0:
                my_share_pct = (self.total_contributed / total_pool_contributions) * 100
                lines.append(
                    f"Your yield share: you contributed ${self.total_contributed:.0f} out of ${total_pool_contributions:.0f} total — "
                    f"your share is {my_share_pct:.1f}% of the yield pool. "
                    f"Skip a month and your share shrinks."
                )

        if state.get("dropout_count", 0) > 0:
            lines.append(
                f"WARNING: {state['dropout_count']} member(s) have already dropped out. "
                f"This means the monthly pot is now smaller — everyone's payout is worth less because of these dropouts."
            )

        lines.append("Remember: if you drop out, your payout slot is lost and the monthly pot shrinks for everyone else who stayed.")

        if self.current_event:
            lines.append(f"LIFE EVENT THIS MONTH: {self.current_event}")

        lines.append("\nWhat do you do this round? Respond with JSON only.")
        return "\n".join(lines)

    def _parse_decision(self, raw: str) -> dict:
        """try to parse LLM response as JSON"""
        clean = raw.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(clean)
            action = parsed.get("action", "").lower().strip()
            if action not in ("contribute", "skip", "dropout"):
                action = "contribute"  # safe default
            return {
                "action": action,
                "reasoning": parsed.get("reasoning", "no reason given")
            }
        except (json.JSONDecodeError, AttributeError):
            lower = raw.lower()
            if "dropout" in lower or "drop out" in lower or "quit" in lower:
                return {"action": "dropout", "reasoning": raw[:100]}
            elif "skip" in lower:
                return {"action": "skip", "reasoning": raw[:100]}
            return {"action": "contribute", "reasoning": raw[:100]}

    def _fallback_decision(self, state: dict) -> dict:
        """personality-based fallback when LLM is unavailable"""
        roll = random.random()

        # impatient_saver: decay reliability after round threshold if no payout yet
        contribute_threshold = self.personality["reliability"]
        if (self.personality["type"] == "impatient_saver"
                and state.get("current_round", 0) > self.personality.get("reliability_decay_after_round", 5)
                and not self.payout_received):
            contribute_threshold = self.personality.get("reliability_late", 0.4)

        # life events lower reliability
        if self.current_event and self.current_event in [
            "unexpected_medical_expense", "job_loss", "car_repair",
            "family_emergency", "rent_increase"
        ]:
            contribute_threshold -= 0.3

        # yield makes people more likely to stay
        if state.get("apy", 0) > 0:
            contribute_threshold += self.personality["yield_sensitivity"] * 0.15

        # social pressure: more dropouts = more likely to drop
        if state.get("dropout_count", 0) > state["total_members"] * 0.3:
            contribute_threshold -= self.personality["social_pressure_sensitivity"] * 0.2

        contribute_threshold = max(0.1, min(0.99, contribute_threshold))

        if roll < contribute_threshold:
            return {"action": "contribute", "reasoning": "fallback: within reliability threshold"}
        elif roll < contribute_threshold + 0.15:
            return {"action": "skip", "reasoning": "fallback: just above threshold, skipping"}
        else:
            return {"action": "dropout", "reasoning": "fallback: well above threshold, dropping out"}

    def _apply_decision(self, decision: dict, state: dict):
        """update agent state based on decision"""
        action = decision["action"]
        self.decision_history.append({
            "round": state["current_round"],
            "action": action,
            "reasoning": decision["reasoning"],
            "event": self.current_event
        })

        if action == "contribute":
            self.total_contributed += state["contribution_amount"]
            self.months_contributed += 1
        elif action == "skip":
            self.months_skipped += 1
        elif action == "dropout":
            self.active = False
            self.dropout_round = state["current_round"]

        self.current_event = None

    def summary(self) -> dict:
        return {
            "name": self.name,
            "personality": self.personality["type"],
            "active": self.active,
            "total_contributed": self.total_contributed,
            "months_contributed": self.months_contributed,
            "months_skipped": self.months_skipped,
            "payout_received": self.payout_received,
            "payout_amount": self.payout_amount,
            "yield_earned": self.yield_earned,
            "dropout_round": self.dropout_round
        }

    def swarm_summary(self) -> dict:
        """full agent data for swarm visualizer — includes decision history"""
        return {
            **self.summary(),
            "reliability": self.personality["reliability"],
            "yield_sensitivity": self.personality["yield_sensitivity"],
            "social_pressure_sensitivity": self.personality["social_pressure_sensitivity"],
            "income_stability": self.personality["income_stability"],
            "decision_history": self.decision_history,
        }
