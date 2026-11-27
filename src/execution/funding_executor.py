from dataclasses import dataclass
from typing import Optional

from src.execution.trade_executor import OrderResult


@dataclass
class FundingPosition:
    """Posición delta-neutral: spot long + short perpetuo del mismo activo."""
    symbol: str
    quantity: float
    entry_price: float
    funding_rate: float
    spot_order_id: Optional[int] = None
    perp_order_id: Optional[int] = None
    opened_at: Optional[int] = None
    funding_collected: float = 0.0

    @property
    def is_hedged(self) -> bool:
        return self.spot_order_id is not None and self.perp_order_id is not None


@dataclass
class FundingExecutionResult:
    ok: bool
    position: Optional[FundingPosition] = None
    error: Optional[str] = None
    spot_result: Optional[OrderResult] = None
    perp_result: Optional[OrderResult] = None


class FundingExecutor:
    """Ejecuta la doble pata del arbitraje de funding.

    Regla de oro: si el spot entra pero el short perp falla, se cierra el spot
    de inmediato para no quedar expuesto al precio. En ``dry_run`` no envía
    ninguna orden: ambas patas se simulan.
    """

    def __init__(self, spot_executor, futures_client, *, dry_run: bool = False):
        self.spot_executor = spot_executor
        self.futures_client = futures_client
        self.dry_run = dry_run

    def open(self, symbol: str, quantity: float, funding_rate: float,
             mark_price: float = 0.0) -> FundingExecutionResult:
        if quantity <= 0:
            return FundingExecutionResult(
                ok=False, error="Cantidad debe ser positiva"
            )

        spot = self.spot_executor.execute_order("BUY", quantity, symbol)
        if not spot.ok:
            return FundingExecutionResult(
                ok=False, error=f"Fallo pata spot: {spot.error}", spot_result=spot
            )

        try:
            self.futures_client.set_margin_type(symbol, "ISOLATED")
            self.futures_client.set_leverage(symbol, 1)
            perp_raw = self.futures_client.place_order(symbol, "SELL", quantity)
            perp = OrderResult(
                ok=True, side="SELL", symbol=symbol, quantity=quantity,
                order_id=perp_raw.get("orderId"), status=perp_raw.get("status", "NEW"),
                filled_qty=quantity,
                avg_price=float(mark_price) if mark_price else spot.avg_price,
            )
        except Exception as exc:
            self._close_spot(symbol, quantity)
            return FundingExecutionResult(
                ok=False,
                error=f"Fallo pata perp, spot cerrado: {exc}",
                spot_result=spot,
                perp_result=OrderResult.failure("SELL", symbol, quantity, str(exc)),
            )

        if not perp.ok:
            self._close_spot(symbol, quantity)
            return FundingExecutionResult(
                ok=False, error="Fallo pata perp, spot cerrado",
                spot_result=spot, perp_result=perp,
            )

        position = FundingPosition(
            symbol=symbol,
            quantity=quantity,
            entry_price=spot.avg_price or mark_price,
            funding_rate=funding_rate,
            spot_order_id=spot.order_id,
            perp_order_id=perp.order_id,
            opened_at=None,
        )
        return FundingExecutionResult(
            ok=True, position=position, spot_result=spot, perp_result=perp
        )

    def close(self, position: FundingPosition) -> FundingExecutionResult:
        """Cierra primero el short (BUY en perp) y luego vende el spot."""
        perp_error = None
        perp_result = None
        if not self.dry_run:
            try:
                raw = self.futures_client.place_order(
                    position.symbol, "BUY", position.quantity, reduceOnly=True
                )
                perp_result = OrderResult(
                    ok=True, side="BUY", symbol=position.symbol,
                    quantity=position.quantity, order_id=raw.get("orderId"),
                    status=raw.get("status", "NEW"),
                )
            except Exception as exc:
                perp_error = str(exc)
                perp_result = OrderResult.failure(
                    "BUY", position.symbol, position.quantity, str(exc)
                )

        spot = self.spot_executor.execute_order("SELL", position.quantity, position.symbol)
        if not spot.ok:
            return FundingExecutionResult(
                ok=False, error=f"Fallo cierre spot: {spot.error}",
                spot_result=spot, perp_result=perp_result,
            )
        if perp_error:
            return FundingExecutionResult(
                ok=False, error=f"Fallo cierre perp: {perp_error}",
                spot_result=spot, perp_result=perp_result,
            )
        return FundingExecutionResult(ok=True, spot_result=spot, perp_result=perp_result)

    def _close_spot(self, symbol: str, quantity: float) -> None:
        try:
            self.spot_executor.execute_order("SELL", quantity, symbol)
        except Exception:
            pass
