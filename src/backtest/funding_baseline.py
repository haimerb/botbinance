import math
from dataclasses import dataclass
from typing import Optional

from src.strategy.event_calendar import EconomicCalendar
from src.strategy.funding_arbitrage import net_annual_pct, should_close
from src.strategy.funding_gate import FundingCandidate, FundingGate
from src.strategy.funding_persistence import FundingPersistenceModel

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


def _default_gate_kwargs():
    return {
        "min_intervals": 3,
        "min_net_annual_pct": 8.0,
        "max_zscore": 2.5,
        "max_abs_basis_pct": 0.5,
        "history_window": 30,
        "calendar": EconomicCalendar(),
        "min_persistence_prob": 0.6,
        "liquidation_enabled": True,
        "max_liquidation_pressure": 0.85,
        "liquidation_target_rate": 0.00005,
    }


def _gate_for_fold(gate_kwargs, persistence_model, *, with_persistence,
                   with_liquidation):
    kwargs = dict(gate_kwargs)
    kwargs["persistence_model"] = persistence_model if with_persistence else None
    kwargs["min_persistence_prob"] = (
        kwargs["min_persistence_prob"] if with_persistence else 0.0
    )
    kwargs["liquidation_enabled"] = with_liquidation
    return FundingGate(**kwargs)


def summarize_walk_forward(fold_results) -> dict:
    """Agrega folds sin mezclar entrenamiento y prueba."""
    if not fold_results:
        return {
            "folds": 0, "winning_folds": 0, "beats_classic_folds": 0,
            "simple_net_pnl": 0.0, "classic_net_pnl": 0.0,
            "gate_net_pnl": 0.0, "delta_net_pnl": 0.0,
            "gate_trades": 0, "accepted": False,
        }

    simple = sum(f["simple"]["net_pnl"] for f in fold_results)
    classic = sum(f["classic"]["net_pnl"] for f in fold_results)
    gate = sum(f["full"]["net_pnl"] for f in fold_results)
    winning = sum(
        f["full"]["net_pnl"] > f["simple"]["net_pnl"] for f in fold_results
    )
    beats_classic = sum(
        f["full"]["net_pnl"] > f["classic"]["net_pnl"] for f in fold_results
    )
    trades = sum(f["full"]["trades"] for f in fold_results)
    needed = math.ceil(len(fold_results) / 2)
    accepted = gate > simple and winning >= needed and trades >= 3

    return {
        "folds": len(fold_results),
        "winning_folds": winning,
        "beats_classic_folds": beats_classic,
        "simple_net_pnl": round(simple, 4),
        "classic_net_pnl": round(classic, 4),
        "gate_net_pnl": round(gate, 4),
        "delta_net_pnl": round(gate - simple, 4),
        "gate_trades": trades,
        "accepted": accepted,
    }


def walk_forward_funding_validation(rows_by_symbol, *, folds=4,
                                    train_size=200, test_size=90,
                                    gate_kwargs=None, persistence_kwargs=None,
                                    notional=100.0, entry_fee=0.0004,
                                    exit_fee=0.0004, min_hold_days=7.0,
                                    max_hold_days=30.0) -> dict:
    """Valida el gate final con ventanas temporales sin look-ahead.

    Entrena el modelo de persistencia sólo con el pasado de cada fold y
    compara tres variantes: carry simple, filtros clásicos y gate completo.
    """
    gate_options = _default_gate_kwargs()
    gate_options.update(gate_kwargs or {})
    persistence_options = {"target_rate": 0.00005, "min_samples": 20}
    persistence_options.update(persistence_kwargs or {})
    simulation = {
        "notional": notional,
        "entry_fee": entry_fee,
        "exit_fee": exit_fee,
        "min_hold_days": min_hold_days,
        "max_hold_days": max_hold_days,
    }

    fold_results = []
    for symbol, raw_rows in sorted(rows_by_symbol.items()):
        rows = sorted(raw_rows, key=lambda row: int(row["funding_time"]))
        for fold in range(folds):
            train_end = min(len(rows), train_size + fold * test_size)
            test_end = min(len(rows), train_end + test_size)
            test_rows = rows[train_end:test_end]
            if len(test_rows) < 3:
                continue

            train_rates = [float(row["funding_rate"]) for row in rows[:train_end]]
            persistence = FundingPersistenceModel(**persistence_options).fit(
                {symbol: train_rates}
            )
            classic_gate = _gate_for_fold(
                gate_options, persistence,
                with_persistence=False, with_liquidation=False,
            )
            full_gate = _gate_for_fold(
                gate_options, persistence,
                with_persistence=True,
                with_liquidation=gate_options["liquidation_enabled"],
            )

            simple = run_funding_backtest(
                test_rows, gate=None, symbol=symbol, **simulation
            )
            classic = run_funding_backtest(
                test_rows, gate=classic_gate, symbol=symbol, **simulation
            )
            full = run_funding_backtest(
                test_rows, gate=full_gate, symbol=symbol, **simulation
            )
            fold_results.append({
                "symbol": symbol,
                "fold": fold,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
                "simple": simple,
                "classic": classic,
                "full": full,
            })

    return {
        "folds": fold_results,
        "summary": summarize_walk_forward(fold_results),
    }
