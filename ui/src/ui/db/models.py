"""Read-only ORM models for UI queries.

Mirrors orchestrator's db/models.py for SELECT queries only.
Avoids cross-repo import dependency.
"""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TradeORM(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(20, 8))
    stop_loss: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Numeric(20, 8))
    size: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    size_pct: Mapped[float | None] = mapped_column(Numeric(5, 4))
    leverage: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    pnl_usd: Mapped[float | None] = mapped_column(Numeric(20, 4))
    pnl_pct: Mapped[float | None] = mapped_column(Numeric(10, 6))
    fees_usd: Mapped[float | None] = mapped_column(Numeric(20, 4))
    strategy_used: Mapped[str | None] = mapped_column(String(50))
    confidence_at_entry: Mapped[float | None] = mapped_column(Numeric(4, 3))
    market_regime: Mapped[str | None] = mapped_column(String(20))
    opus_reasoning: Mapped[str | None] = mapped_column(Text)
    indicators_entry: Mapped[dict | None] = mapped_column(JSONB)
    indicators_exit: Mapped[dict | None] = mapped_column(JSONB)
    research_context: Mapped[dict | None] = mapped_column(JSONB)
    self_review: Mapped[dict | None] = mapped_column(JSONB)
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(10), default="open")
    okx_order_id: Mapped[str | None] = mapped_column(String(50))
    okx_algo_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PlaybookVersionORM(Base):
    __tablename__ = "playbook_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    playbook_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(30), nullable=False)
    performance_at_update: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PerformanceSnapshotORM(Base):
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_type: Mapped[str] = mapped_column(String(20), nullable=False)
    equity: Mapped[float | None] = mapped_column(Numeric(20, 4))
    total_pnl: Mapped[float | None] = mapped_column(Numeric(20, 4))
    win_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    profit_factor: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 4))
    total_trades: Mapped[int | None] = mapped_column(Integer)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ScreenerLogORM(Base):
    __tablename__ = "screener_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    signal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB)
    opus_action: Mapped[str | None] = mapped_column(String(20))
    opus_agreed: Mapped[bool | None] = mapped_column(Boolean)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ReflectionLogORM(Base):
    __tablename__ = "reflection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reflection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    input_prompt: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    playbook_changes: Mapped[dict | None] = mapped_column(JSONB)
    old_version: Mapped[int | None] = mapped_column(Integer)
    new_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
