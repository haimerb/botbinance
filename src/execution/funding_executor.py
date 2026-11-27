import time
from dataclasses import dataclass
from typing import Optional

from src.execution.trade_executor import OrderResult
from src.strategy.funding_arbitrage import annualize_funding


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
             mark_price: float = 0.0, *, maker: bool = False,
             maker_timeout: float = 20.0, maker_offset: float = 0.0001,
             min_fallback_annual_pct: float = 15.0) -> FundingExecutionResult:
        if quantity <= 0:
            return FundingExecutionResult(
                ok=False, error="Cantidad debe ser positiva"
            )

        if maker and not self.dry_run:
            return self._open_maker(
                symbol, quantity, funding_rate, mark_price,
                maker_timeout, maker_offset, min_fallback_annual_pct,
            )

        spot = self.spot_executor.execute_order("BUY", quantity, symbol)
        if not spot.ok:
            return FundingExecutionResult(
                ok=False, error=f"Fallo pata spot: {spot.error}", spot_result=spot
            )

        if self.dry_run:
            if spot.order_id is None:
                spot.order_id = -1
            perp = OrderResult(
                ok=True, side="SELL", symbol=symbol, quantity=quantity,
                order_id=-1, status="DRY_RUN", filled_qty=quantity,
                avg_price=mark_price or spot.avg_price,
            )
        else:
            try:
                self._configure_margin(symbol)
                perp_raw = self.futures_client.place_order(symbol, "SELL", quantity)
                perp = OrderResult(
                    ok=True, side="SELL", symbol=symbol, quantity=quantity,
                    order_id=perp_raw.get("orderId"),
                    status=perp_raw.get("status", "NEW"),
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

        return FundingExecutionResult(
            ok=True,
            position=self._position(symbol, quantity, funding_rate, spot, perp, mark_price),
            spot_result=spot,
            perp_result=perp,
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
            rehedged = False
            if perp_result and perp_result.ok and not self.dry_run:
                try:
                    self.futures_client.place_order(
                        position.symbol, "SELL", position.quantity
                    )
                    rehedged = True
                except Exception:
                    pass
            detail = "short reapertado" if rehedged else "short no reapertado"
            return FundingExecutionResult(
                ok=False, error=f"Fallo cierre spot: {spot.error}; {detail}",
                spot_result=spot, perp_result=perp_result,
            )
        if perp_error:
            return FundingExecutionResult(
                ok=False, error=f"Fallo cierre perp: {perp_error}",
                spot_result=spot, perp_result=perp_result,
            )
        return FundingExecutionResult(ok=True, spot_result=spot, perp_result=perp_result)

    def _open_maker(self, symbol, quantity, funding_rate, mark_price,
                    maker_timeout, maker_offset, min_fallback_annual_pct):
        reference = float(mark_price or 0)
        if not reference:
            reference = float(self.spot_executor.get_symbol_price(symbol) or 0)
        if reference <= 0:
            return FundingExecutionResult(
                ok=False, error="Sin precio de referencia para orden maker"
            )

        spot_price = reference * (1 - maker_offset)
        perp_price = reference * (1 + maker_offset)
        spot = self.spot_executor.execute_order(
            "BUY", quantity, symbol, order_type="LIMIT", price=spot_price,
            time_in_force="GTX",
        )
        if not spot.ok:
            return FundingExecutionResult(
                ok=False, error=f"Fallo pata spot maker: {spot.error}",
                spot_result=spot,
            )
        spot.filled_qty = 0.0

        try:
            self._configure_margin(symbol)
            perp_raw = self.futures_client.place_limit_order(
                symbol, "SELL", quantity, perp_price, post_only=True
            )
        except Exception as exc:
            self._close_spot(symbol, quantity)
            return FundingExecutionResult(
                ok=False, error=f"Fallo pata perp maker: {exc}",
                spot_result=spot,
                perp_result=OrderResult.failure("SELL", symbol, quantity, str(exc)),
            )

        perp = OrderResult(
            ok=True, side="SELL", symbol=symbol, quantity=quantity,
            order_id=perp_raw.get("orderId"),
            status=perp_raw.get("status", "NEW"),
            filled_qty=0.0, avg_price=perp_price,
        )
        spot_qty, perp_qty = self._wait_maker_fills(
            symbol, quantity, spot, perp, maker_timeout
        )
        if spot_qty >= quantity and perp_qty >= quantity:
            return FundingExecutionResult(
                ok=True,
                position=self._position(symbol, quantity, funding_rate, spot, perp, reference),
                spot_result=spot,
                perp_result=perp,
            )

        self._cancel_maker_rest(symbol, quantity, spot, perp, spot_qty, perp_qty)
        if annualize_funding(funding_rate) < min_fallback_annual_pct:
            return FundingExecutionResult(
                ok=False, error="Maker sin fill y edge insuficiente para fallback"
            )
        return self.open(
            symbol, quantity, funding_rate, reference, maker=False
        )

    def _wait_maker_fills(self, symbol, quantity, spot, perp, timeout):
        deadline = time.time() + max(timeout, 0)
        spot_qty = 0.0
        perp_qty = 0.0
        while True:
            spot_qty = self._spot_filled_qty(symbol, spot)
            perp_qty = self._perp_filled_qty(symbol, perp)
            if (spot_qty >= quantity and perp_qty >= quantity) or time.time() >= deadline:
                break
            time.sleep(min(0.5, deadline - time.time()))
        return spot_qty, perp_qty

    @staticmethod
    def _executed_qty(raw, order):
        status = str(raw.get("status") or "").upper()
        if status == "FILLED":
            return order.quantity
        value = raw.get("executedQty", raw.get("cumQty", raw.get("filled_qty")))
        try:
            return max(float(value or 0), 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _spot_filled_qty(self, symbol, spot):
        if spot.order_id is None:
            return spot.quantity if spot.status == "FILLED" else spot.filled_qty
        try:
            raw = self.spot_executor.query_order(symbol, spot.order_id)
        except Exception:
            return spot.filled_qty
        queried = self._executed_qty(raw, spot)
        return queried if queried > 0 else spot.filled_qty

    def _perp_filled_qty(self, symbol, perp):
        if perp.order_id is None:
            return perp.quantity if perp.status == "FILLED" else perp.filled_qty
        try:
            raw = self.futures_client.query_order(symbol, perp.order_id)
        except Exception:
            return perp.filled_qty
        queried = self._executed_qty(raw, perp)
        return queried if queried > 0 else perp.filled_qty

    def _cancel_maker_rest(self, symbol, quantity, spot, perp, spot_qty, perp_qty):
        if spot_qty < quantity and spot.order_id is not None:
            try:
                self.spot_executor.cancel_order(symbol, spot.order_id)
            except Exception:
                pass
        if perp_qty < quantity and perp.order_id is not None:
            try:
                self.futures_client.cancel_order(symbol, perp.order_id)
            except Exception:
                pass
        if spot_qty > 0:
            self._close_spot(symbol, spot_qty)
        if perp_qty > 0:
            try:
                self.futures_client.place_order(
                    symbol, "BUY", perp_qty, reduceOnly=True
                )
            except Exception:
                pass

    def _configure_margin(self, symbol):
        self.futures_client.set_margin_type(symbol, "ISOLATED")
        self.futures_client.set_leverage(symbol, 1)

    @staticmethod
    def _position(symbol, quantity, funding_rate, spot, perp, mark_price):
        return FundingPosition(
            symbol=symbol,
            quantity=quantity,
            entry_price=spot.avg_price or mark_price,
            funding_rate=funding_rate,
            spot_order_id=spot.order_id,
            perp_order_id=perp.order_id,
            opened_at=None,
        )

    def _close_spot(self, symbol: str, quantity: float) -> None:
        try:
            self.spot_executor.execute_order("SELL", quantity, symbol)
        except Exception:
            pass
