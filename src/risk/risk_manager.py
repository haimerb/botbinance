from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ExitReason(Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"
    PARTIAL_TP = "partial_tp"
    SIGNAL_REVERSAL = "signal_reversal"
    MANUAL = "manual"


@dataclass
class Position:
    side: str
    entry_price: float
    quantity: float
    entry_time: datetime
    highest_price: float = 0.0
    lowest_price: float = 0.0
    partial_exits: List[Tuple[float, float, ExitReason]] = field(default_factory=list)
    trailing_stop_price: Optional[float] = None
    take_profit_levels: List[Tuple[float, float]] = field(default_factory=list)


class RiskManager:
    def __init__(
        self,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.03,
        max_position_size: float = 0.01,
        trailing_stop_pct: float = 0.01,
        trailing_activation_pct: float = 0.015,
        time_exit_hours: int = 24,
        partial_tp_levels: List[Tuple[float, float]] = None,
        enable_trailing: bool = True,
        enable_time_exit: bool = True,
        enable_partial_tp: bool = True,
    ):
        self.base_stop_loss_pct = stop_loss_pct
        self.base_take_profit_pct = take_profit_pct
        self.max_position_size = max_position_size

        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_activation_pct = trailing_activation_pct
        self.time_exit_hours = time_exit_hours
        self.partial_tp_levels = partial_tp_levels or [
            (0.01, 0.3),  # TP1: 1% -> close 30%
            (0.02, 0.3),  # TP2: 2% -> close 30%
            (0.03, 0.4),  # TP3: 3% -> close 40%
        ]
        self.enable_trailing = enable_trailing
        self.enable_time_exit = enable_time_exit
        self.enable_partial_tp = enable_partial_tp

        self.position: Optional[Position] = None
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def open_position(self, price: float, quantity: float) -> bool:
        if quantity > self.max_position_size:
            return False

        self.position = Position(
            side="BUY",
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now(),
            highest_price=price,
            lowest_price=price,
            trailing_stop_price=None,
        )

        if self.enable_partial_tp:
            self.position.take_profit_levels = [
                (price * (1 + pct), qty_pct * quantity)
                for pct, qty_pct in self.partial_tp_levels
            ]

        return True

    def close_position(self, reason: ExitReason = ExitReason.MANUAL) -> Optional[Position]:
        closed = self.position
        self.position = None
        return closed

    def check_stop_loss(self, current_price: float) -> bool:
        if self.position is None:
            return False
        loss_pct = (self.position.entry_price - current_price) / self.position.entry_price
        if loss_pct >= self.stop_loss_pct:
            return True
        return False

    def check_take_profit(self, current_price: float) -> bool:
        if self.position is None:
            return False
        gain_pct = (current_price - self.position.entry_price) / self.position.entry_price
        if gain_pct >= self.take_profit_pct:
            return True
        return False

    def check_trailing_stop(self, current_price: float) -> bool:
        if self.position is None or not self.enable_trailing:
            return False

        self.position.highest_price = max(self.position.highest_price, current_price)
        self.position.lowest_price = min(self.position.lowest_price, current_price)

        gain_pct = (current_price - self.position.entry_price) / self.position.entry_price

        if gain_pct >= self.trailing_activation_pct:
            new_trailing = current_price * (1 - self.trailing_stop_pct)
            if (self.position.trailing_stop_price is None or
                    new_trailing > self.position.trailing_stop_price):
                self.position.trailing_stop_price = new_trailing

            if current_price <= self.position.trailing_stop_price:
                return True

        return False

    def check_time_exit(self) -> bool:
        if self.position is None or not self.enable_time_exit:
            return False
        elapsed = datetime.now() - self.position.entry_time
        return elapsed >= timedelta(hours=self.time_exit_hours)

    def check_partial_take_profit(self, current_price: float) -> List[Tuple[float, float, ExitReason]]:
        if self.position is None or not self.enable_partial_tp:
            return []

        executed = []
        remaining_levels = []

        for tp_price, tp_qty in self.position.take_profit_levels:
            if current_price >= tp_price:
                executed.append((tp_price, tp_qty, ExitReason.PARTIAL_TP))
                self.position.quantity -= tp_qty
            else:
                remaining_levels.append((tp_price, tp_qty))

        self.position.take_profit_levels = remaining_levels
        return executed

    def check_all_exits(self, current_price: float) -> List[Tuple[ExitReason, str]]:
        exits = []

        if self.check_stop_loss(current_price):
            exits.append((ExitReason.STOP_LOSS, f"Stop loss hit at {current_price:.2f}"))

        if self.check_trailing_stop(current_price):
            exits.append((ExitReason.TRAILING_STOP, f"Trailing stop hit at {current_price:.2f}"))

        if self.check_time_exit():
            exits.append((ExitReason.TIME_EXIT, f"Time exit after {self.time_exit_hours}h"))

        if self.check_take_profit(current_price):
            exits.append((ExitReason.TAKE_PROFIT, f"Take profit hit at {current_price:.2f}"))

        partials = self.check_partial_take_profit(current_price)
        for tp_price, tp_qty, reason in partials:
            exits.append((reason, f"Partial TP at {tp_price:.2f} for {tp_qty}"))

        return exits

    def set_dynamic_levels(self, stop_loss_pct: float, take_profit_pct: float):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def has_position(self) -> bool:
        return self.position is not None

    def get_position_info(self) -> Optional[dict]:
        if self.position is None:
            return None
        return {
            "side": self.position.side,
            "entry_price": self.position.entry_price,
            "quantity": self.position.quantity,
            "entry_time": self.position.entry_time.isoformat(),
            "highest_price": self.position.highest_price,
            "lowest_price": self.position.lowest_price,
            "trailing_stop": self.position.trailing_stop_price,
            "remaining_tp_levels": len(self.position.take_profit_levels),
        }