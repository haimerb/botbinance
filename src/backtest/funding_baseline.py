from dataclasses import dataclass, field
from typing import Optional

from src.strategy.funding_arbitrage import net_annual_pct, should_close
from src.strategy.funding_gate import FundingCandidate, FundingGate

MS_PER_DAY = 86_400_000


@dataclass
class FundingTrade:
    symbol: str
    entry_ts: int
    entry_rate: float
    funding_pnl: float = 0.0
    entry_cost: float = 0.0
    exit_cost: float = 0.0
    basis_cost: float = 0.0
    exit_ts: Optional[int] = None

    @property
    def net_pnl(self) -> float:
        return self.funding_pnl - self.entry_cost - self.exit_cost - self.basis_cost

    @property
    def days(self) -> float:
        if self.exit_ts is None:
            return 0.0
        return max((self.exit_ts - self.entry_ts) / MS_PER_DAY, 0.0)


def run_funding_backtest(rows, *, symbol="BTCUSDT", notional=100.0,
                         entry_fee=0.0004, exit_fee=0.0004,
                         min_hold_days=7.0, max_hold_days=30.0,
                         gate: Optional[FundingGate] = None) -> dict:
    """Simula carry spot long + perp short sobre filas de funding histórico."""
    trades = []
    open_trade = None
    history = []
    last_ts = None

    for row in rows:
        ts = int(row["funding_time"])
        last_ts = ts
        rate = float(row["funding_rate"])

        if open_trade is not None:
            open_trade.funding_pnl += rate * notional
            too_long = open_trade.days >= max_hold_days
            if should_close(rate, True) or (too_long and rate <= 0):
                open_trade.exit_ts = ts
                open_trade.exit_cost = exit_fee * notional
                trades.append(open_trade)
                open_trade = None
        else:
            net = net_annual_pct(rate, entry_fee, exit_fee, min_hold_days)
            candidate = FundingCandidate(
                symbol=symbol,
                funding_rate=rate,
                net_annual_pct=net,
                funding_time=ts,
                basis_pct=row.get("basis_pct"),
            )
            allowed = gate.evaluate(candidate, history).allowed if gate else rate > 0
            if allowed:
                basis = row.get("basis_pct") or 0.0
                open_trade = FundingTrade(
                    symbol=symbol,
                    entry_ts=ts,
                    entry_rate=rate,
                    entry_cost=entry_fee * notional,
                    basis_cost=max(basis, 0.0) / 100 * notional,
                )

        history.append(rate)

    if open_trade is not None:
        open_trade.exit_ts = last_ts if last_ts is not None else open_trade.entry_ts
        open_trade.exit_cost = exit_fee * notional
        trades.append(open_trade)

    return summarize(trades, notional)


def summarize(trades, notional) -> dict:
    funding = sum(t.funding_pnl for t in trades)
    entry_cost = sum(t.entry_cost for t in trades)
    exit_cost = sum(t.exit_cost for t in trades)
    basis_cost = sum(t.basis_cost for t in trades)
    net = funding - entry_cost - exit_cost - basis_cost

    peak = 0.0
    max_dd = 0.0
    running = 0.0
    for trade in trades:
        running += trade.net_pnl
        peak = max(peak, running)
        if peak > 0:
            max_dd = max(max_dd, (peak - running) / peak * 100)

    return {
        "trades": len(trades),
        "funding_pnl": round(funding, 4),
        "entry_cost": round(entry_cost, 4),
        "exit_cost": round(exit_cost, 4),
        "basis_cost": round(basis_cost, 4),
        "net_pnl": round(net, 4),
        "roi_pct": round(net / notional * 100, 4) if notional else 0.0,
        "max_drawdown_pct": round(max_dd, 4),
    }


def compare_with_simple(rows, gate: FundingGate, **kwargs) -> dict:
    """El gate sólo se acepta si bate al carry simple con los mismos costes."""
    simple = run_funding_backtest(rows, gate=None, **kwargs)
    filtered = run_funding_backtest(rows, gate=gate, **kwargs)
    accepted = (
        filtered["net_pnl"] > simple["net_pnl"]
        and filtered["trades"] >= 3
    )
    return {
        "simple": simple,
        "gate": filtered,
        "accepted": accepted,
        "delta_net_pnl": round(filtered["net_pnl"] - simple["net_pnl"], 4),
    }
