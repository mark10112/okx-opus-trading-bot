"""Add screener_logs table.

Revision ID: 002
Revises: 001
Create Date: 2026-02-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "screener_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("signal", sa.Boolean, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("snapshot_json", JSONB),
        sa.Column("opus_action", sa.String(20)),
        sa.Column("opus_agreed", sa.Boolean),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_screener_created", "screener_logs", [sa.text("created_at DESC")])
    op.create_index("idx_screener_signal", "screener_logs", ["signal"])


def downgrade() -> None:
    op.drop_table("screener_logs")
