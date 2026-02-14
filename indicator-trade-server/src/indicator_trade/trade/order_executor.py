"""Place orders + TP/SL algo orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from indicator_trade.models.order import OrderRequest, OrderResult
    from indicator_trade.trade.okx_rest import OKXRestClient
    from indicator_trade.trade.order_validator import OrderValidator

logger = structlog.get_logger()


class OrderExecutor:
    def __init__(self, rest_client: OKXRestClient, validator: OrderValidator) -> None:
        self.rest_client = rest_client
        self.validator = validator

    async def execute(self, request: OrderRequest) -> OrderResult:
        """Full order execution: validate -> place main -> place TP/SL -> return result."""
        ...

    async def _place_main_order(self, request: OrderRequest) -> OrderResult: ...

    async def _place_tp_sl(self, request: OrderRequest, ord_id: str) -> dict: ...

    async def _handle_error(self, error: dict, request: OrderRequest) -> OrderResult: ...
