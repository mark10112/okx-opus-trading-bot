"""Settings (pydantic-settings, loaded from env vars)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ADMIN_IDS: list[int] = []

    # --- Infrastructure ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot"
    REDIS_URL: str = "redis://redis:6379"

    # --- Alert Settings ---
    ALERT_ON_TRADE: bool = True
    ALERT_ON_REFLECTION: bool = True
    ALERT_ON_RISK_REJECTION: bool = True
    ALERT_COOLDOWN_SECONDS: int = 60
    SILENT_HOURS_UTC: list[int] = []

    model_config = {"env_prefix": "", "case_sensitive": True}
