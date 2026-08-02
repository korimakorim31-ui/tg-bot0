"""
Example: run the CEO gate against two mock scenarios.

  1. A strong setup -> should APPROVE
  2. A weak/conflicting setup -> should REJECT

In production, `reports` would be built by actually calling your 10
specialist agents (each hitting Bitget data + your LLM of choice), not
hardcoded like this. This script only exercises the CEO's decision logic.
"""

from ceo_agent import CEOAgent, AgentReport, TradeSetup, RiskLevel, AGENT_NAMES
from signal_output import calculate_risk_plan, format_signal


def strong_bullish_reports() -> list[AgentReport]:
    # 9/10 agents bullish with high confidence, 1 neutral -> should clear
    # both the 8/10 agreement bar and the 95% confidence bar.
    data = [
        ("Market Structure Expert", 92, 5, 98, "Bullish BOS on 4H, HH/HL intact"),
        ("Smart Money Concepts", 90, 6, 97, "Bullish order block retested with FVG fill"),
        ("Technical Analysis", 88, 8, 96, "EMA stack bullish, RSI 58, MACD cross up"),
        ("Volume Expert", 87, 8, 95, "Rising CVD, volume spike on breakout candle"),
        ("Order Flow Expert", 85, 10, 95, "Bid-heavy order book, absorption at support"),
        ("Derivatives Expert", 84, 10, 96, "Positive but not overheated funding, OI rising"),
        ("On-chain AI", 80, 12, 94, "Exchange outflows increasing, whale accumulation"),
        ("News AI", 78, 8, 93, "Mildly positive news flow, no negative catalysts"),
        ("Social Sentiment AI", 75, 15, 90, "Improving sentiment, Fear & Greed neutral-bullish"),
        ("Quant AI", 93, 4, 98, "Historical pattern similarity 89%, Monte Carlo favors upside"),
    ]
    return [AgentReport(agent_name=n, bullish_score=b, bearish_score=s, confidence=c, reason=r)
            for n, b, s, c, r in data]


def weak_conflicting_reports() -> list[AgentReport]:
    # Split roughly 5/5, moderate confidence -> should fail agreement + confidence.
    data = [
        ("Market Structure Expert", 60, 55, 62, "Choppy structure, no clear BOS"),
        ("Smart Money Concepts", 45, 50, 58, "No clean order block, mitigation unclear"),
        ("Technical Analysis", 55, 52, 60, "Indicators mixed, ADX low (weak trend)"),
        ("Volume Expert", 50, 48, 55, "Volume declining, no clear delta bias"),
        ("Order Flow Expert", 52, 50, 57, "Balanced book, no absorption signal"),
        ("Derivatives Expert", 40, 60, 65, "Funding slightly negative, OI flat"),
        ("On-chain AI", 48, 52, 50, "No notable whale activity"),
        ("News AI", 50, 50, 40, "No significant news catalysts"),
        ("Social Sentiment AI", 55, 45, 45, "Sentiment neutral, low engagement"),
        ("Quant AI", 50, 50, 48, "Low historical pattern match, high uncertainty"),
    ]
    return [AgentReport(agent_name=n, bullish_score=b, bearish_score=s, confidence=c, reason=r)
            for n, b, s, c, r in data]


def main():
    ceo = CEOAgent()

    print("=" * 60)
    print("SCENARIO 1: Strong bullish confluence")
    print("=" * 60)

    setup_strong = TradeSetup(
        coin="BTCUSDT",
        exchange="Bitget",
        entry_low=64200,
        entry_high=64400,
        stop_loss=63500,
        take_profits=[66900, 68000, 69200, 70500],
        leverage=5,
        risk_pct=2,
        timeframe_directions={"1H": None, "4H": None},  # None = not conflicting in this mock
    )
    # remove the None placeholders so the conflict check is skipped cleanly
    setup_strong.timeframe_directions = {}

    reports = strong_bullish_reports()
    decision = ceo.evaluate(reports, setup_strong, news_risk=RiskLevel.LOW)
    risk_plan = None
    if decision.approved:
        risk_plan = calculate_risk_plan(
            setup_strong, decision.direction,
            account_equity_usd=10_000, win_probability=0.90,
        )
    print(format_signal(decision, setup_strong, risk_plan, probability_pct=96.0))

    print()
    print("=" * 60)
    print("SCENARIO 2: Weak / conflicting setup")
    print("=" * 60)

    setup_weak = TradeSetup(
        coin="ETHUSDT",
        exchange="Bitget",
        entry_low=3400,
        entry_high=3420,
        stop_loss=3350,
        take_profits=[3480],
        leverage=10,
        risk_pct=2,
    )
    reports_weak = weak_conflicting_reports()
    decision_weak = ceo.evaluate(reports_weak, setup_weak, news_risk=RiskLevel.MEDIUM)
    print(format_signal(decision_weak, setup_weak))


if __name__ == "__main__":
    main()
