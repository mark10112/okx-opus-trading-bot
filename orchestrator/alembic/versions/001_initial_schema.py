"""Initial schema: trades, playbook_versions, reflection_logs, research_cache,
performance_snapshots, risk_rejections, candles (TimescaleDB hypertable).

Revision ID: 001
Revises: None
Create Date: 2026-02-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enable TimescaleDB extension ---
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # --- trades ---
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "trade_id",
            sa.String(36),
            unique=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column(
            "direction",
            sa.String(5),
            sa.CheckConstraint("direction IN ('LONG', 'SHORT')"),
            nullable=False,
        ),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 8)),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(20, 8)),
        sa.Column("size", sa.Numeric(20, 8), nullable=False),
        sa.Column("size_pct", sa.Numeric(5, 4)),
        sa.Column("leverage", sa.Numeric(5, 2), server_default="1.0"),
        sa.Column("pnl_usd", sa.Numeric(20, 4)),
        sa.Column("pnl_pct", sa.Numeric(10, 6)),
        sa.Column("fees_usd", sa.Numeric(20, 4)),
        sa.Column("strategy_used", sa.String(50)),
        sa.Column("confidence_at_entry", sa.Numeric(4, 3)),
        sa.Column("market_regime", sa.String(20)),
        sa.Column("opus_reasoning", sa.Text),
        sa.Column("indicators_entry", JSONB),
        sa.Column("indicators_exit", JSONB),
        sa.Column("research_context", JSONB),
        sa.Column("self_review", JSONB),
        sa.Column("exit_reason", sa.String(30)),
        sa.Column(
            "status",
            sa.String(10),
            sa.CheckConstraint("status IN ('open', 'closed', 'cancelled')"),
            server_default="open",
        ),
        sa.Column("okx_order_id", sa.String(50)),
        sa.Column("okx_algo_id", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_trades_symbol", "trades", ["symbol"])
    op.create_index("idx_trades_status", "trades", ["status"])
    op.create_index("idx_trades_opened_at", "trades", [sa.text("opened_at DESC")])
    op.create_index("idx_trades_strategy", "trades", ["strategy_used"])
    op.create_index("idx_trades_regime", "trades", ["market_regime"])

    # --- playbook_versions ---
    op.create_table(
        "playbook_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer, unique=True, nullable=False),
        sa.Column("playbook_json", JSONB, nullable=False),
        sa.Column("change_summary", sa.Text),
        sa.Column(
            "triggered_by",
            sa.String(30),
            sa.CheckConstraint("triggered_by IN ('reflection', 'manual', 'init')"),
            nullable=False,
        ),
        sa.Column("performance_at_update", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_playbook_version", "playbook_versions", [sa.text("version DESC")])

    # --- reflection_logs ---
    op.create_table(
        "reflection_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "reflection_type",
            sa.String(20),
            sa.CheckConstraint("reflection_type IN ('post_trade', 'periodic')"),
            nullable=False,
        ),
        sa.Column("trade_ids", sa.ARRAY(sa.Integer)),
        sa.Column("input_prompt", sa.Text),
        sa.Column("output_json", JSONB),
        sa.Column("playbook_changes", JSONB),
        sa.Column("old_version", sa.Integer),
        sa.Column("new_version", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_reflection_type", "reflection_logs", ["reflection_type"])
    op.create_index("idx_reflection_created", "reflection_logs", [sa.text("created_at DESC")])

    # --- research_cache ---
    op.create_table(
        "research_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("response_json", JSONB, nullable=False),
        sa.Column("source", sa.String(20), server_default="perplexity"),
        sa.Column("ttl_seconds", sa.Integer, server_default="3600"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_research_query", "research_cache", ["query"])
    op.create_index("idx_research_created", "research_cache", [sa.text("created_at DESC")])

    # --- performance_snapshots ---
    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "snapshot_type",
            sa.String(20),
            sa.CheckConstraint("snapshot_type IN ('hourly', 'daily', 'weekly')"),
            nullable=False,
        ),
        sa.Column("equity", sa.Numeric(20, 4)),
        sa.Column("total_pnl", sa.Numeric(20, 4)),
        sa.Column("win_rate", sa.Numeric(5, 4)),
        sa.Column("profit_factor", sa.Numeric(8, 4)),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4)),
        sa.Column("max_drawdown", sa.Numeric(10, 4)),
        sa.Column("total_trades", sa.Integer),
        sa.Column("metrics_json", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_perf_type", "performance_snapshots", ["snapshot_type"])
    op.create_index("idx_perf_created", "performance_snapshots", [sa.text("created_at DESC")])

    # --- risk_rejections ---
    op.create_table(
        "risk_rejections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("decision_json", JSONB, nullable=False),
        sa.Column("failed_rules", JSONB, nullable=False),
        sa.Column("account_state", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_risk_created", "risk_rejections", [sa.text("created_at DESC")])

    # --- candles (TimescaleDB hypertable) ---
    op.create_table(
        "candles",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(30, 8), nullable=False),
        sa.PrimaryKeyConstraint("time", "symbol", "timeframe"),
    )
    op.execute("SELECT create_hypertable('candles', 'time')")
    op.create_index("idx_candles_symbol_tf", "candles", ["symbol", "timeframe", sa.text("time DESC")])
    op.execute("SELECT add_retention_policy('candles', INTERVAL '6 months')")


def downgrade() -> None:
    op.drop_table("candles")
    op.drop_table("risk_rejections")
    op.drop_table("performance_snapshots")
    op.drop_table("research_cache")
    op.drop_table("reflection_logs")
    op.drop_table("playbook_versions")
    op.drop_table("trades")
