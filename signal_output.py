"""
Quantum Alpha AI — Signal Formatting & Risk Math
=================================================

Takes a CEO Decision + TradeSetup and produces:
  1. Risk-management numbers (position size, Kelly fraction, EV, liq price)
  2. The exact human-readable signal / rejection format from the spec
"""

from __future__ import annotations

from dataclasses import dataclass
from ceo_agent import CEOAgent, AgentReport, TradeSetup, Decision, Direction, RiskLevel


# --------------------------------------------------------------------------
# Risk management
# --------------------------------------------------------------------------

@dataclass
class RiskPlan:
    position_size_units: float
    position_size_usd: float
    max_loss_usd: float
    liquidation_price: float
    kelly_fraction: float
    expected_value_r: float          # EV expressed in R-multiples
    breakeven_price: float


def calculate_risk_plan(
    setup: TradeSetup,
    direction: Direction,
    account_equity_usd: float,
    win_probability: float,           # 0-1, from Quant AI agent
) -> RiskPlan:
    entry = (setup.entry_low + setup.entry_high) / 2
    stop_distance = abs(entry - setup.stop_loss)
    if stop_distance == 0:
        raise ValueError("Stop loss cannot equal entry price")

    # Risk-per-trade sizing: risk_pct of equity, sized to the stop distance
    risk_usd = account_equity_usd * (setup.risk_pct / 100)
    position_size_units = risk_usd / stop_distance
    position_size_usd = position_size_units * entry

    # Reward from TP1 (conservative), used for R-multiple / Kelly
    if not setup.take_profits:
        raise ValueError("At least one take-profit level required")
    reward_distance = abs(setup.take_profits[0] - entry)
    r_multiple = reward_distance / stop_distance

    # Kelly fraction: f* = p - (1-p)/R   (R = reward:risk ratio)
    p = win_probability
    kelly = p - (1 - p) / r_multiple
    kelly = max(0.0, kelly)  # never suggest negative sizing

    # Simple EV in R-multiples: p*R - (1-p)*1
    ev_r = p * r_multiple - (1 - p)

    # Liquidation price (isolated margin, simplified — ignores fees/funding drag)
    if direction == Direction.LONG:
        liq_price = entry * (1 - 1 / setup.leverage)
    else:
        liq_price = entry * (1 + 1 / setup.leverage)

    breakeven = entry  # after fees this would need a small offset; kept simple here

    return RiskPlan(
        position_size_units=round(position_size_units, 6),
        position_size_usd=round(position_size_usd, 2),
        max_loss_usd=round(risk_usd, 2),
        liquidation_price=round(liq_price, 2),
        kelly_fraction=round(kelly, 4),
        expected_value_r=round(ev_r, 3),
        breakeven_price=round(breakeven, 2),
    )


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def format_signal(
    decision: Decision,
    setup: TradeSetup,
    risk_plan: RiskPlan = None,
    probability_pct: float = None,
) -> str:
    if not decision.approved:
        lines = [
            "❌ CEO DECISION: NO TRADE",
            "",
            f"Coin: {setup.coin}",
            f"Exchange: {setup.exchange}",
            "",
            "Reason:",
        ]
        for reason in decision.failed_checks:
            lines.append(f"  - {reason}")
        lines.append("")
        lines.append(f"Confidence: {decision.confidence}% (required: 95%)")
        lines.append(f"Agent Agreement: {decision.agent_agreement}/10 (required: 8/10)")
        return "\n".join(lines)

    tps = setup.take_profits + [None] * (4 - len(setup.take_profits))
    prob = probability_pct if probability_pct is not None else decision.confidence

    lines = [
        "🚨 ELITE AI SIGNAL 🚨",
        "",
        f"Coin: {setup.coin}",
        f"Exchange: {setup.exchange}",
        f"Direction: {decision.direction.value}",
        f"Confidence: {decision.confidence}%",
        f"Probability: {prob}%",
        "",
        f"Entry Zone: {setup.entry_low} - {setup.entry_high}",
        f"Stop Loss: {setup.stop_loss}",
        f"Take Profit 1: {tps[0]}",
        f"Take Profit 2: {tps[1]}",
        f"Take Profit 3: {tps[2]}",
        f"Take Profit 4: {tps[3]}",
        f"Risk Reward: 1:{decision.confidence and round((abs(tps[0]-((setup.entry_low+setup.entry_high)/2))/abs(((setup.entry_low+setup.entry_high)/2)-setup.stop_loss)),2)}",
        f"Leverage: {setup.leverage}x",
        f"Suggested Capital Allocation: {setup.risk_pct}% Risk",
    ]

    if risk_plan:
        lines += [
            "",
            "-- Risk Plan --",
            f"Position Size: {risk_plan.position_size_units} units (${risk_plan.position_size_usd})",
            f"Max Loss: ${risk_plan.max_loss_usd}",
            f"Liquidation Price: {risk_plan.liquidation_price}",
            f"Kelly Fraction: {risk_plan.kelly_fraction}",
            f"Expected Value: {risk_plan.expected_value_r} R",
        ]

    lines += [
        "",
        "Reason:",
    ]
    for r in decision.reasons:
        lines.append(f"  - {r}")

    lines += [
        "",
        "CEO Final Decision: APPROVED ✅",
    ]
    return "\n".join(lines)
