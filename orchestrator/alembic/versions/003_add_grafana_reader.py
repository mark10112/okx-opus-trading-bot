"""Add grafana_reader database user with read-only access.

Revision ID: 003
Revises: 002
Create Date: 2026-02-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'grafana_reader') THEN "
        "    EXECUTE format('CREATE USER grafana_reader WITH PASSWORD %L', "
        "      current_setting('app.grafana_db_password', true)); "
        "  END IF; "
        "END $$"
    )
    op.execute("GRANT CONNECT ON DATABASE trading_bot TO grafana_reader")
    op.execute("GRANT USAGE ON SCHEMA public TO grafana_reader")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM grafana_reader"
    )
    op.execute("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM grafana_reader")
    op.execute("REVOKE USAGE ON SCHEMA public FROM grafana_reader")
    op.execute("REVOKE CONNECT ON DATABASE trading_bot FROM grafana_reader")
    op.execute("DROP USER IF EXISTS grafana_reader")
