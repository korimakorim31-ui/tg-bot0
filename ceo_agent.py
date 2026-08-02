"""
Quantum Alpha AI — CEO Agent
============================

The CEO agent never generates signals. It only receives structured reports
from the 10 specialist agents and decides APPROVE / REJECT based on a fixed,
mechanical rule set. Nothing here is "soft" — every rule in CEO_APPROVAL_RULES
maps to a hard check, and any failed check rejects the trade with a stated
reason.

This module is exchange- and model-agnostic: it doesn't call Bitget or an
LLM API itself. It expects the 10 agents to have already produced their
reports (however they got there) and hands back a Decision object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# Enums / constants
# --------------------------------------------------------------------------

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


AGENT_NAMES = [
    "Market Structure Expert",
    "Smart Money Concepts",
    "Technical Analysis",
    "Volume Expert",
    "Order Flow Expert",
    "Derivatives Expert",
    "On-chain AI",
    "News AI",
    "Social Sentiment AI",
    "Quant AI",
]

# Relative weight of each agent in the CEO's confidence calculation.
# These are configurable — tune based on backtest results, not guesses.
DEFAULT_AGENT_WEIGHTS = {
    "Market Structure Expert": 1.3,
    "Smart Money Concepts": 1.2,
    "Technical Analysis": 1.0,
    "Volume Expert": 1.0,
    "Order Flow Expert": 1.1,
    "Derivatives Expert": 1.0,
    "On-chain AI": 0.8,
    "News AI": 0.7,
    "Social Sentiment AI": 0.6,
    "Quant AI": 1.3,
}


# --------------------------------------------------------------------------
# Agent report — the contract every one of the 10 agents must output
# --------------------------------------------------------------------------

@dataclass
class AgentReport:
    agent_name: str
    bullish_score: float          # 0-100
    bearish_score: float          # 0-100
    confidence: float             # 0-100, agent's own confidence in its read
    reason: str                   # short explanation, becomes part of signal output
    risk: RiskLevel = RiskLevel.MEDIUM
    timeframe: Optional[str] = None  # e.g. "1H" if this report is TF-specific

    def bias(self) -> Direction:
        if self.bullish_score - self.bearish_score >= 10:
            return Direction.LONG
        if self.bearish_score - self.bullish_score >= 10:
            return Direction.SHORT
        return Direction.NEUTRAL

    def __post_init__(self):
        for name, val in [("bullish_score", self.bullish_score),
                           ("bearish_score", self.bearish_score),
                           ("confidence", self.confidence)]:
            if not (0 <= val <= 100):
                raise ValueError(f"{name} must be 0-100, got {val}")
        if self.agent_name not in AGENT_NAMES:
            raise ValueError(f"Unknown agent_name: {self.agent_name}")


# --------------------------------------------------------------------------
# Trade context — everything the CEO needs beyond the 10 reports
# --------------------------------------------------------------------------

@dataclass
class TradeSetup:
    coin: str
    exchange: str
    entry_low: float
    entry_high: float
    stop_loss: float
    take_profits: list[float]     # ordered TP1..TP4
    leverage: float
    risk_pct: float                # % of capital risked
    near_major_resistance: bool = False
    near_major_support: bool = False
    high_volatility_event: bool = False
    manipulation_detected: bool = False
    funding_healthy: bool = True
    spread_acceptable: bool = True
    timeframes_checked: list[str] = field(default_factory=list)
    timeframe_directions: dict = field(default_factory=dict)  # {tf: Direction}


# --------------------------------------------------------------------------
# CEO approval rules (mirrors the spec's CEO_APPROVAL_RULES section exactly)
# --------------------------------------------------------------------------

@dataclass
class ApprovalRules:
    min_confidence: float = 95.0
    min_agent_agreement: int = 8          # out of 10
    min_risk_reward: float = 3.0          # 1:3
    require_trend_alignment: bool = True
    require_low_news_risk: bool = True
    require_healthy_funding: bool = True
    require_acceptable_spread: bool = True
    reject_near_resistance_support: bool = True
    reject_high_volatility_event: bool = True
    reject_on_manipulation: bool = True
    reject_on_conflicting_timeframes: bool = True


# --------------------------------------------------------------------------
# Decision result
# --------------------------------------------------------------------------

@dataclass
class Decision:
    approved: bool
    direction: Optional[Direction]
    confidence: float
    agent_agreement: int
    failed_checks: list[str]
    weighted_bullish: float
    weighted_bearish: float
    reasons: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --------------------------------------------------------------------------
# CEO Agent
# --------------------------------------------------------------------------

class CEOAgent:
    def __init__(self, rules: ApprovalRules = None, weights: dict = None):
        self.rules = rules or ApprovalRules()
        self.weights = weights or DEFAULT_AGENT_WEIGHTS

    # ---- individual checks -----------------------------------------------

    def _weighted_scores(self, reports: list[AgentReport]) -> tuple[float, float]:
        """Weighted average bullish/bearish score across all agents that reported."""
        total_weight = sum(self.weights.get(r.agent_name, 1.0) for r in reports)
        if total_weight == 0:
            return 0.0, 0.0
        wb = sum(r.bullish_score * self.weights.get(r.agent_name, 1.0) for r in reports) / total_weight
        ws = sum(r.bearish_score * self.weights.get(r.agent_name, 1.0) for r in reports) / total_weight
        return round(wb, 2), round(ws, 2)

    def _agreement_count(self, reports: list[AgentReport], direction: Direction) -> int:
        return sum(1 for r in reports if r.bias() == direction)

    def _weighted_confidence(self, reports: list[AgentReport], direction: Direction) -> float:
        """
        Confidence isn't just averaged — it's discounted by disagreement.
        An agent voting the opposite direction actively drags confidence down,
        rather than just being ignored.
        """
        total_weight = sum(self.weights.get(r.agent_name, 1.0) for r in reports)
        if total_weight == 0:
            return 0.0
        score = 0.0
        for r in reports:
            w = self.weights.get(r.agent_name, 1.0)
            if r.bias() == direction:
                score += r.confidence * w
            elif r.bias() == Direction.NEUTRAL:
                score += (r.confidence * 0.5) * w
            else:
                score -= (r.confidence * 0.5) * w  # opposing vote penalizes
        return round(max(0.0, min(100.0, score / total_weight)), 2)

    def _risk_reward(self, setup: TradeSetup) -> float:
        entry = (setup.entry_low + setup.entry_high) / 2
        risk = abs(entry - setup.stop_loss)
        if risk == 0 or not setup.take_profits:
            return 0.0
        reward = abs(setup.take_profits[0] - entry)  # conservative: use TP1
        return round(reward / risk, 2)

    def _timeframes_conflict(self, setup: TradeSetup, direction: Direction) -> bool:
        if not setup.timeframe_directions:
            return False
        for tf, d in setup.timeframe_directions.items():
            if d not in (direction, Direction.NEUTRAL):
                return True
        return False

    # ---- main entry point --------------------------------------------------

    def evaluate(
        self,
        reports: list[AgentReport],
        setup: TradeSetup,
        news_risk: RiskLevel = RiskLevel.LOW,
    ) -> Decision:
        failed: list[str] = []

        if len(reports) != 10:
            failed.append(f"Expected 10 agent reports, got {len(reports)}")

        weighted_bull, weighted_bear = self._weighted_scores(reports)
        direction = Direction.LONG if weighted_bull > weighted_bear else Direction.SHORT

        agreement = self._agreement_count(reports, direction)
        confidence = self._weighted_confidence(reports, direction)
        rr = self._risk_reward(setup)

        rules = self.rules

        if confidence < rules.min_confidence:
            failed.append(f"Confidence {confidence}% below required {rules.min_confidence}%")

        if agreement < rules.min_agent_agreement:
            failed.append(f"Agent agreement {agreement}/10 below required {rules.min_agent_agreement}/10")

        if rr < rules.min_risk_reward:
            failed.append(f"Risk/Reward 1:{rr} below required 1:{rules.min_risk_reward}")

        if rules.require_trend_alignment and self._timeframes_conflict(setup, direction):
            failed.append("Conflicting timeframe alignment")

        if rules.require_low_news_risk and news_risk != RiskLevel.LOW:
            failed.append(f"News risk is {news_risk.value}, requires Low")

        if rules.require_healthy_funding and not setup.funding_healthy:
            failed.append("Funding rate not healthy")

        if rules.require_acceptable_spread and not setup.spread_acceptable:
            failed.append("Spread not acceptable")

        if rules.reject_near_resistance_support and (setup.near_major_resistance or setup.near_major_support):
            failed.append("Price near major support/resistance level")

        if rules.reject_high_volatility_event and setup.high_volatility_event:
            failed.append("High volatility event nearby")

        if rules.reject_on_manipulation and setup.manipulation_detected:
            failed.append("Manipulation pattern detected")

        approved = len(failed) == 0
        reasons = [r.reason for r in reports if r.bias() == direction]

        return Decision(
            approved=approved,
            direction=direction if approved else None,
            confidence=confidence,
            agent_agreement=agreement,
            failed_checks=failed,
            weighted_bullish=weighted_bull,
            weighted_bearish=weighted_bear,
            reasons=reasons,
            )
