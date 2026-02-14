"""Trade server main loop: Redis subscriber + order execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from indicator_trade.models.messages import StreamMessage, TradeFillMessage
from indicator_trade.models.order import OrderRequest, OrderResult
from indicator_trade.models.position import AccountState
from indicator_trade.trade.okx_rest import OKXRestClient
from indicator_trade.trade.order_executor import OrderExecutor
from indicator_trade.trade.order_validator import OrderValidator
from indicator_trade.trade.position_manager import PositionManager
from indicator_trade.trade.ws_private import OKXPrivateWS

if TYPE_CHECKING:
    from indicator_trade.config import Settings
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()


class TradeServer:
    def __init__(self, settings: Settings, redis: RedisClient) -> None:
        self.settings = settings
        self.redis = redis
        self.running = False
        self._rest_client: OKXRestClient | None = None
        self._ws: OKXPrivateWS | None = None
        self._executor: OrderExecutor | None = None
        self._position_manager: PositionManager | None = None
        self._account_state: AccountState = AccountState()

    async def start(self) -> None:
        """
        1. Initialize OKX REST client
        2. Connect OKX Private WebSocket
        3. Subscribe to orders, positions, account channels
        4. Subscribe Redis "trade:orders" for incoming commands
        """
        self.running = True
        logger.info("trade_server_starting")

        # 1. Initialize REST client
        self._rest_client = OKXRestClient(
            api_key=self.settings.OKX_API_KEY,
            secret_key=self.settings.OKX_SECRET_KEY,
            passphrase=self.settings.OKX_PASSPHRASE,
            flag=self.settings.OKX_FLAG,
        )

        # Initialize validator, executor, position manager
        validator = OrderValidator()
        self._executor = OrderExecutor(self._rest_client, validator)
        self._position_manager = PositionManager(self.redis)

        # 2. Connect OKX Private WebSocket
        self._ws = OKXPrivateWS(
            url=self.settings.WS_PRIVATE_URL,
            api_key=self.settings.OKX_API_KEY,
            passphrase=self.settings.OKX_PASSPHRASE,
            secret_key=self.settings.OKX_SECRET_KEY,
        )
        try:
            await self._ws.connect()
            # 3. Subscribe channels
            await self._ws.subscribe_orders("SWAP", self._on_order_update)
            await self._ws.subscribe_positions("SWAP", self._on_position_update)
            await self._ws.subscribe_account(self._on_account_update)
            logger.info("trade_ws_subscriptions_complete")
        except Exception:
            logger.exception("trade_ws_connect_failed")

        # 4. Subscribe Redis "trade:orders"
        logger.info("trade_server_started")
        await self.redis.subscribe(["trade:orders"], self._on_trade_order)

    async def stop(self) -> None:
        """Close all connections."""
        self.running = False
        if self._ws is not None:
            await self._ws.disconnect()
        logger.info("trade_server_stopped")

    async def _on_trade_order(self, stream: str, message: StreamMessage) -> None:
        """Redis subscriber callback for trade:orders."""
        if self._executor is None:
            logger.warning("trade_order_received_but_no_executor")
            return

        try:
            payload = message.payload
            request = OrderRequest(**payload)

            logger.info(
                "trade_order_received",
                action=request.action,
                symbol=request.symbol,
                size=request.size,
            )

            result = await self._executor.execute(request)

            # Publish fill result to trade:fills
            fill_msg = TradeFillMessage(
                payload=result.model_dump(mode="json"),
                metadata={
                    "action": request.action,
                    "symbol": request.symbol,
                    "decision_id": request.decision_id,
                },
            )
            await self.redis.publish("trade:fills", fill_msg)

            logger.info(
                "trade_order_executed",
                success=result.success,
                ord_id=result.ord_id,
                symbol=request.symbol,
            )
        except Exception:
            logger.exception("trade_order_processing_error", stream=stream)

    async def _on_order_update(self, data: dict) -> None:
        """OKX Private WS callback for orders channel."""
        for order_data in data.get("data", []):
            logger.info(
                "order_update",
                ordId=order_data.get("ordId"),
                state=order_data.get("state"),
                instId=order_data.get("instId"),
                fillPx=order_data.get("fillPx"),
                fillSz=order_data.get("fillSz"),
            )

    async def _on_position_update(self, data: dict) -> None:
        """OKX Private WS callback for positions channel."""
        if self._position_manager is None:
            return
        for pos_data in data.get("data", []):
            try:
                await self._position_manager.update(pos_data)
            except Exception:
                logger.exception("position_update_error", data=pos_data)

    async def _on_account_update(self, data: dict) -> None:
        """OKX Private WS callback for account channel."""
        for acct_data in data.get("data", []):
            equity = float(acct_data.get("totalEq", 0))
            available = 0.0
            for detail in acct_data.get("details", []):
                if detail.get("ccy") == "USDT":
                    available = float(detail.get("availBal", 0))
                    break
            self._account_state = AccountState(
                equity=equity,
                available_balance=available,
            )
            logger.info(
                "account_update",
                equity=equity,
                available=available,
            )
