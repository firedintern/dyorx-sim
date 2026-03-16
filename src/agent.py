"""
Agent class: Each agent is a savings circle member with a personality.
Uses Qwen LLM to make monthly decisions: contribute, skip, or drop out.
"""

import json
import random
from openai import OpenAI


class Agent:
    def __init__(self, name: str, personality: dict, llm_client: OpenAI, model: str):
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
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            raw = response.choices[0].message.content.strip()
            decision = self._parse_decision(raw)
        except Exception as e:
            # fallback to personality-based decision if LLM fails
            decision = self._fallback_decision(circle_state)
            decision["reasoning"] = f"LLM error ({e}), used fallback logic"

        self._apply_decision(decision, circle_state)
        return decision

    def _system_prompt(self) -> str:
        return f"""You are {self.name}, a member of a savings circle (consorcio/ROSCA).

Your personality:
→ Type: {self.personality['type']}
→ Description: {self.personality['description']}
→ Reliability: {self.personality['reliability']:.0%}
→ Risk tolerance: {self.personality['risk_tolerance']:.0%}
→ Income stability: {self.personality['income_stability']:.0%}
→ Sensitivity to yields/earnings: {self.personality['yield_sensitivity']:.0%}
→ Social pressure sensitivity: {self.personality['social_pressure_sensitivity']:.0%}

You must respond ONLY with valid JSON in this exact format:
{{"action": "contribute" or "skip" or "dropout", "reasoning": "one sentence why"}}

Nothing else. No markdown, no explanation outside the JSON."""

    def _build_prompt(self, state: dict) -> str:
        lines = [
            f"Round {state['current_round']} of {state['total_rounds']}.",
            f"Monthly contribution: ${state['contribution_amount']}",
            f"Members still active: {state['active_members']} of {state['total_members']}",
            f"Pool balance: ${state['pool_balance']:.2f}",
            f"Your total contributed so far: ${self.total_contributed:.2f}",
            f"You have contributed {self.months_contributed} months, skipped {self.months_skipped}",
            f"Have you received your payout yet: {'yes' if self.payout_received else 'no'}",
        ]

        if state.get("apy", 0) > 0:
            lines.append(f"Circle APY: {state['apy']:.1%} (from DeFi yields on Solana)")
            lines.append(f"Your yield earned so far: ${self.yield_earned:.2f}")

        if state.get("dropout_count", 0) > 0:
            lines.append(f"Members who dropped out: {state['dropout_count']}")

        if self.current_event:
            lines.append(f"LIFE EVENT THIS MONTH: {self.current_event}")

        lines.append("\nWhat do you do this round? Respond with JSON only.")
        return "\n".join(lines)

    def _parse_decision(self, raw: str) -> dict:
        """try to parse LLM response as JSON"""
        # strip markdown fences if present
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
            # if LLM returned garbage, check for keywords
            lower = raw.lower()
            if "dropout" in lower or "drop out" in lower or "quit" in lower:
                return {"action": "dropout", "reasoning": raw[:100]}
            elif "skip" in lower:
                return {"action": "skip", "reasoning": raw[:100]}
            return {"action": "contribute", "reasoning": raw[:100]}

    def _fallback_decision(self, state: dict) -> dict:
        """personality-based fallback when LLM is unavailable"""
        roll = random.random()

        # adjust threshold based on personality
        contribute_threshold = self.personality["reliability"]

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
