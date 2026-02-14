"""Settings (pydantic-settings, loaded from env vars)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = ""
    OPUS_MODEL: str = "claude-haiku-4-5-20251001"
    HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
    OPUS_MAX_TOKENS: int = 4096
    HAIKU_MAX_TOKENS: int = 100
    MAX_OPUS_TIMEOUT_SECONDS: int = 30

    # --- Perplexity ---
    PERPLEXITY_API_KEY: str = ""
    PERPLEXITY_MODEL: str = "sonar-pro"

    # --- Infrastructure ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot"
    REDIS_URL: str = "redis://redis:6379"

    # --- Decision Cycle ---
    DECISION_CYCLE_SECONDS: int = 300
    INSTRUMENTS: list[str] = ["BTC-USDT-SWAP"]
    REFLECTION_INTERVAL_TRADES: int = 20
    REFLECTION_INTERVAL_HOURS: int = 6
    COOLDOWN_AFTER_LOSS_STREAK: int = 1800

    # --- Haiku Screener ---
    SCREENER_ENABLED: bool = True
    SCREENER_BYPASS_ON_POSITION: bool = True
    SCREENER_BYPASS_ON_NEWS: bool = True
    SCREENER_MIN_PASS_RATE: float = 0.10
    SCREENER_LOG_ALL: bool = True

    # --- Risk Gate (Hardcoded) ---
    MAX_DAILY_LOSS_PCT: float = 0.03
    MAX_SINGLE_TRADE_PCT: float = 0.05
    MAX_TOTAL_EXPOSURE_PCT: float = 0.15
    MAX_CONCURRENT_POSITIONS: int = 3
    MAX_DRAWDOWN_PCT: float = 0.10
    MAX_CONSECUTIVE_LOSSES: int = 3
    MAX_LEVERAGE: float = 3.0
    MAX_SL_DISTANCE_PCT: float = 0.03
    MIN_RR_RATIO: float = 1.5

    model_config = {"env_prefix": "", "case_sensitive": True}
