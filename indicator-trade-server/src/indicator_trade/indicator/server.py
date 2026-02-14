"""Indicator server main loop: WebSocket data collection + snapshot publishing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from indicator_trade.db.candle_repository import CandleRepository
from indicator_trade.indicator.candle_store import CandleStore
from indicator_trade.indicator.indicators import TechnicalIndicators
from indicator_trade.indicator.regime_detector import RegimeDetector
from indicator_trade.indicator.snapshot_builder import SnapshotBuilder
from indicator_trade.indicator.ws_public import OKXPublicWS
from indicator_trade.models.candle import Candle
from indicator_trade.models.messages import MarketAlertMessage, MarketSnapshotMessage
from indicator_trade.models.snapshot import FundingRate, OpenInterest, OrderBook
from indicator_trade.models.ticker import Ticker

if TYPE_CHECKING:
    from indicator_trade.config import Settings
    from indicator_trade.redis_client import RedisClient

logger = structlog.get_logger()

ANOMALY_PRICE_CHANGE_THRESHOLD = 3.0  # percent
ANOMALY_FUNDING_THRESHOLD = 0.05  # percent


class IndicatorServer:
    def __init__(self, settings: Settings, redis: RedisClient) -> None:
        self.settings = settings
        self.redis = redis
        self.running = False
        self._candle_store: CandleStore | None = None
        self._snapshot_builder: SnapshotBuilder | None = None
        self._ws: OKXPublicWS | None = None
        self._ws_task: asyncio.Task | None = None

    async def start(self) -> None:
        """
        1. Backfill historical candles from REST API (200 candles per TF)
        2. Subscribe WebSocket channels (background task — non-blocking)
        3. Start snapshot_loop (publish every SNAPSHOT_INTERVAL_SECONDS)
        """
        self.running = True
        self._ws_task = None
        logger.info("indicator_server_starting")

        # Initialize components if not already set (allows test injection)
        if self._candle_store is None:
            from indicator_trade.db.engine import create_db_engine, create_session_factory

            engine = create_db_engine(self.settings.DATABASE_URL)
            session_factory = create_session_factory(engine)
            repo = CandleRepository(session_factory)
            self._candle_store = CandleStore(
                db_repo=repo, max_candles=self.settings.CANDLE_HISTORY_LIMIT
            )

        indicators = TechnicalIndicators()
        regime_detector = RegimeDetector()

        if self._snapshot_builder is None:
            self._snapshot_builder = SnapshotBuilder(
                candle_store=self._candle_store,
                indicators=indicators,
                regime_detector=regime_detector,
            )

        # 1. Backfill
        await self._backfill_candles()

        # 2. Subscribe WS as background task (start() blocks the event loop)
        self._ws_task = asyncio.create_task(self._subscribe_ws_background())

        # 3. Snapshot loop (runs immediately, doesn't wait for WS)
        await self._snapshot_loop()

    async def stop(self) -> None:
        """Gracefully close WebSocket connections, flush pending DB writes."""
        self.running = False
        if self._ws is not None:
            await self._ws.disconnect()
        if self._ws_task is not None and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("indicator_server_stopped")

    async def _backfill_candles(self) -> None:
        """Fetch historical candles from OKX REST for each instrument+timeframe."""
        for instrument in self.settings.INSTRUMENTS:
            for tf in self.settings.TIMEFRAMES:
                try:
                    candles = await self._fetch_candles_rest(
                        instrument, tf, self.settings.CANDLE_HISTORY_LIMIT
                    )
                    if candles and self._candle_store is not None:
                        await self._candle_store.backfill(instrument, tf, candles)
                    logger.info(
                        "backfill_complete",
                        instrument=instrument,
                        timeframe=tf,
                        count=len(candles) if candles else 0,
                    )
                except Exception:
                    logger.exception("backfill_failed", instrument=instrument, timeframe=tf)

    async def _fetch_candles_rest(
        self, instrument: str, timeframe: str, limit: int = 200
    ) -> list[Candle]:
        """Fetch candles from OKX REST API using asyncio.to_thread."""
        from okx.MarketData import MarketAPI

        api = MarketAPI(flag=self.settings.OKX_FLAG)

        # OKX bar format: 5m, 1H, 4H
        result = await asyncio.to_thread(
            api.get_candlesticks, instId=instrument, bar=timeframe, limit=str(limit)
        )

        candles = []
        if result and result.get("code") == "0":
            for row in reversed(result.get("data", [])):
                # OKX format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                candles.append(
                    Candle(
                        time=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                        symbol=instrument,
                        timeframe=timeframe,
                        open=Decimal(row[1]),
                        high=Decimal(row[2]),
                        low=Decimal(row[3]),
                        close=Decimal(row[4]),
                        volume=Decimal(row[5]),
                    )
                )
        return candles

    async def _subscribe_ws_background(self) -> None:
        """Connect and subscribe to OKX public WebSocket channels.

        Runs as a background task because WsPublicAsync.start() blocks.
        """
        self._ws = OKXPublicWS(url=self.settings.WS_PUBLIC_URL)
        try:
            await self._ws.connect()
            await self._ws.subscribe_candles(
                self.settings.INSTRUMENTS,
                self.settings.TIMEFRAMES,
                self._on_candle,
            )
            await self._ws.subscribe_tickers(self.settings.INSTRUMENTS, self._on_ticker)
            await self._ws.subscribe_orderbook(self.settings.INSTRUMENTS, self._on_orderbook)
            await self._ws.subscribe_funding(self.settings.INSTRUMENTS, self._on_funding)
            logger.info("ws_subscriptions_complete")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ws_subscribe_failed")

    async def _on_candle(self, data: dict) -> None:
        """Handle incoming candle WS message."""
        try:
            arg = data.get("arg", {})
            channel = arg.get("channel", "")
            inst_id = arg.get("instId", "")

            # Extract timeframe from channel name (e.g., "candle1H" -> "1H")
            tf = channel.replace("candle", "")

            for row in data.get("data", []):
                candle = Candle(
                    time=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                    symbol=inst_id,
                    timeframe=tf,
                    open=Decimal(row[1]),
                    high=Decimal(row[2]),
                    low=Decimal(row[3]),
                    close=Decimal(row[4]),
                    volume=Decimal(row[5]),
                )
                if self._candle_store is not None:
                    await self._candle_store.add(inst_id, tf, candle)
        except Exception:
            logger.exception("candle_processing_error")

    async def _on_ticker(self, data: dict) -> None:
        """Handle incoming ticker WS message."""
        # Store latest ticker for snapshot building
        pass

    async def _on_orderbook(self, data: dict) -> None:
        """Handle incoming orderbook WS message."""
        pass

    async def _on_funding(self, data: dict) -> None:
        """Handle incoming funding rate WS message."""
        pass

    async def _snapshot_loop(self) -> None:
        """Periodically build and publish MarketSnapshot."""
        while self.running:
            for instrument in self.settings.INSTRUMENTS:
                try:
                    ticker = await self._fetch_ticker(instrument)
                    orderbook = await self._fetch_orderbook(instrument)
                    funding = await self._fetch_funding(instrument)
                    oi = await self._fetch_open_interest(instrument)

                    if self._snapshot_builder is not None:
                        snapshot = self._snapshot_builder.build(
                            instrument=instrument,
                            ticker=ticker,
                            orderbook=orderbook,
                            funding=funding,
                            oi=oi,
                            ls_ratio=1.0,
                            taker_volume=1.0,
                        )

                        # Publish to Redis
                        msg = MarketSnapshotMessage(
                            payload=snapshot.model_dump(mode="json"),
                        )
                        await self.redis.publish("market:snapshots", msg)

                        # Check for anomalies
                        await self._detect_anomalies(snapshot)

                        logger.info(
                            "snapshot_published",
                            instrument=instrument,
                            regime=snapshot.market_regime,
                        )
                except Exception:
                    logger.exception("snapshot_loop_error", instrument=instrument)

            await asyncio.sleep(self.settings.SNAPSHOT_INTERVAL_SECONDS)

    async def _fetch_ticker(self, instrument: str) -> Ticker:
        """Fetch ticker from OKX REST API."""
        from okx.MarketData import MarketAPI

        api = MarketAPI(flag=self.settings.OKX_FLAG)
        result = await asyncio.to_thread(api.get_ticker, instId=instrument)

        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return Ticker(
                symbol=instrument,
                last=float(d.get("last", 0)),
                bid=float(d.get("bidPx", 0)),
                ask=float(d.get("askPx", 0)),
                volume_24h=float(d.get("vol24h", 0)),
                change_24h=float(d.get("sodUtc8", 0)),
            )
        return Ticker(symbol=instrument, last=0, bid=0, ask=0, volume_24h=0, change_24h=0)

    async def _fetch_orderbook(self, instrument: str) -> OrderBook:
        """Fetch orderbook from OKX REST API."""
        from okx.MarketData import MarketAPI

        api = MarketAPI(flag=self.settings.OKX_FLAG)
        result = await asyncio.to_thread(api.get_orderbook, instId=instrument, sz="5")

        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            bids = [(float(b[0]), float(b[1])) for b in d.get("bids", [])]
            asks = [(float(a[0]), float(a[1])) for a in d.get("asks", [])]
            spread = (asks[0][0] - bids[0][0]) if bids and asks else 0.0
            bid_depth = sum(b[1] for b in bids)
            ask_depth = sum(a[1] for a in asks)
            return OrderBook(
                bids=bids,
                asks=asks,
                spread=spread,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
            )
        return OrderBook()

    async def _fetch_funding(self, instrument: str) -> FundingRate:
        """Fetch funding rate from OKX REST API."""
        from okx.PublicData import PublicAPI

        api = PublicAPI(flag=self.settings.OKX_FLAG)
        result = await asyncio.to_thread(api.get_funding_rate, instId=instrument)

        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return FundingRate(
                current=float(d.get("fundingRate") or 0),
                predicted=float(d.get("nextFundingRate") or 0),
            )
        return FundingRate()

    async def _fetch_open_interest(self, instrument: str) -> OpenInterest:
        """Fetch open interest from OKX REST API."""
        from okx.PublicData import PublicAPI

        api = PublicAPI(flag=self.settings.OKX_FLAG)
        result = await asyncio.to_thread(api.get_open_interest, instType="SWAP", instId=instrument)

        if result and result.get("code") == "0" and result.get("data"):
            d = result["data"][0]
            return OpenInterest(oi=float(d.get("oi", 0)))
        return OpenInterest()

    async def _detect_anomalies(self, snapshot) -> None:
        """Detect market anomalies and publish alerts."""
        alerts = []

        # Large price change (>3% in 1H)
        if abs(snapshot.price_change_1h) > ANOMALY_PRICE_CHANGE_THRESHOLD:
            alerts.append(
                {
                    "type": "price_anomaly",
                    "message": f"Large 1H price change: {snapshot.price_change_1h:.2f}%",
                    "severity": "WARN",
                }
            )

        # Funding rate spike (>0.05%)
        if abs(snapshot.funding_rate.current) > ANOMALY_FUNDING_THRESHOLD:
            alerts.append(
                {
                    "type": "funding_spike",
                    "message": f"High funding rate: {snapshot.funding_rate.current:.4f}",
                    "severity": "WARN",
                }
            )

        for alert in alerts:
            msg = MarketAlertMessage(payload=alert)
            await self.redis.publish("market:alerts", msg)
            logger.warning("market_anomaly_detected", **alert)
