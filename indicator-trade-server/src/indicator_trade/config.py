"""Settings (pydantic-settings, loaded from env vars)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- OKX ---
    OKX_API_KEY: str = ""
    OKX_SECRET_KEY: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_FLAG: str = "1"  # 1 = Demo Trading

    # --- WebSocket URLs ---
    WS_PUBLIC_URL: str = "wss://wspap.okx.com:8443/ws/v5/public"
    WS_PRIVATE_URL: str = "wss://wspap.okx.com:8443/ws/v5/private"

    # --- Infrastructure ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot"
    REDIS_URL: str = "redis://redis:6379"

    # --- Instruments ---
    INSTRUMENTS: list[str] = ["BTC-USDT-SWAP"]
    TIMEFRAMES: list[str] = ["5m", "1H", "4H"]

    # --- Indicator ---
    CANDLE_HISTORY_LIMIT: int = 200
    SNAPSHOT_INTERVAL_SECONDS: int = 300
    ORDERBOOK_DEPTH: int = 20

    # --- Trade ---
    ORDER_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3

    model_config = {"env_prefix": "", "case_sensitive": True}
