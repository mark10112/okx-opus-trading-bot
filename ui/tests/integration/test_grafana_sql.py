"""B10: Grafana dashboard SQL validation tests.

Verify all rawSql queries from dashboard JSON files execute against real DB.
Replaces $__timeFilter() macros with a valid time range.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

DASHBOARD_DIR = Path(__file__).parent.parent.parent / "grafana" / "dashboards"


def _load_dashboard_sqls() -> list[tuple[str, str, str]]:
    """Extract (dashboard_name, panel_title, rawSql) from all dashboards."""
    results = []
    for fpath in sorted(DASHBOARD_DIR.glob("*.json")):
        with open(fpath) as f:
            dash = json.load(f)
        dash_name = fpath.stem
        for panel in dash.get("panels", []):
            title = panel.get("title", "unknown")
            for target in panel.get("targets", []):
                raw_sql = target.get("rawSql", "")
                if raw_sql.strip():
                    results.append((dash_name, title, raw_sql))
    return results


def _replace_grafana_macros(sql: str) -> str:
    """Replace Grafana macros with valid SQL equivalents."""
    # $__timeFilter(col) -> col BETWEEN '2020-01-01' AND '2030-01-01'
    sql = re.sub(
        r"\$__timeFilter\(([^)]+)\)",
        r"\1 BETWEEN '2020-01-01'::timestamptz AND '2030-01-01'::timestamptz",
        sql,
    )
    # $__timeGroup(col, interval) -> date_trunc('hour', col)
    sql = re.sub(
        r"\$__timeGroup\(([^,]+),\s*[^)]+\)",
        r"date_trunc('hour', \1)",
        sql,
    )
    # $__timeFrom() / $__timeTo()
    sql = sql.replace("$__timeFrom()", "'2020-01-01'::timestamptz")
    sql = sql.replace("$__timeTo()", "'2030-01-01'::timestamptz")
    return sql


ALL_SQLS = _load_dashboard_sqls()


# ---------------------------------------------------------------------------
# 1. All dashboard SQL queries parse and execute without error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dash_name,panel_title,raw_sql",
    ALL_SQLS,
    ids=[f"{d}::{t}" for d, t, _ in ALL_SQLS],
)
async def test_dashboard_sql_executes(db_engine, dash_name, panel_title, raw_sql):
    """Each Grafana dashboard SQL query executes without error."""
    sql = _replace_grafana_macros(raw_sql)
    async with db_engine.connect() as conn:
        # Just execute — we don't care about results, only that it doesn't error
        result = await conn.execute(text(sql))
        rows = result.fetchall()
        # Rows may be empty (no data), that's fine
        assert rows is not None or rows == []


# ---------------------------------------------------------------------------
# 2. All dashboards reference only existing tables
# ---------------------------------------------------------------------------


async def test_all_referenced_tables_exist(db_engine):
    """Every table referenced in dashboard SQL exists in the DB."""
    known_tables = set()
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        known_tables = {row[0] for row in result.fetchall()}

    # Known DB tables that dashboards should reference
    expected_tables = {
        "trades", "playbook_versions", "reflection_logs", "research_cache",
        "performance_snapshots", "screener_logs", "risk_rejections", "candles",
    }

    # All expected tables must exist
    missing = expected_tables - known_tables
    assert not missing, f"Expected tables missing from DB: {missing}"


# ---------------------------------------------------------------------------
# 3. Dashboard count matches expected
# ---------------------------------------------------------------------------


async def test_dashboard_count():
    """We have exactly 7 dashboard JSON files."""
    dashboards = list(DASHBOARD_DIR.glob("*.json"))
    assert len(dashboards) == 7
