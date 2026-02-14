"""Place orders + TP/SL algo orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from indicator_trade.models.order import OrderResult
from indicator_trade.trade.order_validator import OrderValidator

if TYPE_CHECKING:
    from indicator_trade.models.order import OrderRequest
    from indicator_trade.trade.okx_rest import OKXRestClient

logger = structlog.get_logger()


class OrderExecutor:
    def __init__(self, rest_client: OKXRestClient, validator: OrderValidator) -> None:
        self.rest_client = rest_client
        self.validator = validator

    async def execute(self, request: OrderRequest) -> OrderResult:
        """Full order execution: validate -> place main -> place TP/SL -> return result."""
        # 1. Validate
        validation = self.validator.validate(request)
        if not validation.valid:
            return OrderResult(
                success=False,
                error_message="; ".join(validation.errors),
            )

        try:
            action = request.action.upper()

            if action == "CLOSE":
                return await self._execute_close(request)
            elif action in ("OPEN_LONG", "OPEN_SHORT"):
                return await self._execute_open(request)
            else:
                # ADD, REDUCE: place order only
                return await self._place_main_order(request)
        except Exception as e:
            logger.exception("order_execution_error", symbol=request.symbol, action=request.action)
            return OrderResult(success=False, error_message=str(e))

    async def _execute_open(self, request: OrderRequest) -> OrderResult:
        """OPEN flow: set leverage -> place main order -> place TP/SL."""
        # Set leverage (best-effort, don't fail the order if this fails)
        try:
            await self.rest_client.set_leverage(request.symbol, request.leverage)
        except Exception:
            logger.warning("set_leverage_failed", symbol=request.symbol, leverage=request.leverage)

        # Place main order
        result = await self.rest_client.place_order(request)
        if not result.success:
            return result

        # Place TP/SL algo order if SL is specified
        if request.stop_loss:
            try:
                await self._place_tp_sl(request, result.ord_id or "")
            except Exception:
                logger.warning(
                    "tp_sl_placement_failed",
                    ord_id=result.ord_id,
                    symbol=request.symbol,
                )

        return result

    async def _execute_close(self, request: OrderRequest) -> OrderResult:
        """CLOSE flow: close_position()."""
        result = await self.rest_client.close_position(
            request.symbol, "cross", request.pos_side
        )
        if result and result.get("code") == "0":
            return OrderResult(success=True, status="closed")
        data = result.get("data", [{}])[0] if result.get("data") else {}
        return OrderResult(
            success=False,
            error_code=data.get("sCode", result.get("code")),
            error_message=data.get("sMsg", result.get("msg", "")),
        )

    async def _place_main_order(self, request: OrderRequest) -> OrderResult:
        """Place the main order via REST client."""
        return await self.rest_client.place_order(request)

    async def _place_tp_sl(self, request: OrderRequest, ord_id: str) -> dict:
        """Place TP/SL algo order after main order fills."""
        # Determine the closing side (opposite of opening side)
        close_side = "sell" if request.side == "buy" else "buy"

        kwargs = {
            "instId": request.symbol,
            "tdMode": "cross",
            "side": close_side,
            "posSide": request.pos_side,
            "sz": request.size,
            "slTriggerPx": request.stop_loss,
        }
        if request.take_profit:
            kwargs["tpTriggerPx"] = request.take_profit

        return await self.rest_client.place_algo_order(**kwargs)
