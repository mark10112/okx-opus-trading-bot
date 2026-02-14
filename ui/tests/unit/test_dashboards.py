"""Tests for Grafana dashboard JSON files."""

import json
from pathlib import Path

import pytest

DASHBOARDS_DIR = Path(__file__).resolve().parents[2] / "grafana" / "dashboards"

DASHBOARD_FILES = [
    "portfolio_overview.json",
    "active_positions.json",
    "strategy_performance.json",
    "opus_activity.json",
    "risk_monitor.json",
    "system_health.json",
    "playbook_evolution.json",
]

REQUIRED_TOP_KEYS = {"title", "uid", "tags", "panels"}
REQUIRED_PANEL_KEYS = {"id", "type", "title", "gridPos", "targets"}
DATASOURCE_NAME = "TradingBot-PostgreSQL"


def _load_dashboard(filename: str) -> dict:
    path = DASHBOARDS_DIR / filename
    with open(path) as f:
        return json.load(f)


@pytest.fixture(params=DASHBOARD_FILES)
def dashboard_file(request):
    return request.param


@pytest.fixture
def dashboard(dashboard_file):
    return _load_dashboard(dashboard_file)


@pytest.fixture
def all_dashboards():
    return {f: _load_dashboard(f) for f in DASHBOARD_FILES}


class TestDashboardJsonValid:
    """Each JSON file must be valid JSON."""

    def test_valid_json(self, dashboard_file):
        path = DASHBOARDS_DIR / dashboard_file
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestDashboardFlatFormat:
    """File-based provisioning requires flat format (no 'dashboard' wrapper)."""

    def test_no_dashboard_wrapper(self, dashboard):
        assert "dashboard" not in dashboard, (
            "Dashboard JSON must use flat format for file-based provisioning"
        )


class TestDashboardRequiredKeys:
    """Each dashboard must have required top-level keys."""

    def test_has_required_keys(self, dashboard, dashboard_file):
        for key in REQUIRED_TOP_KEYS:
            assert key in dashboard, f"{dashboard_file} missing required key: {key}"

    def test_title_is_string(self, dashboard):
        assert isinstance(dashboard["title"], str)
        assert len(dashboard["title"]) > 0

    def test_uid_is_string(self, dashboard):
        assert isinstance(dashboard["uid"], str)
        assert len(dashboard["uid"]) > 0

    def test_tags_is_list(self, dashboard):
        assert isinstance(dashboard["tags"], list)
        assert len(dashboard["tags"]) > 0

    def test_panels_is_list(self, dashboard):
        assert isinstance(dashboard["panels"], list)

    def test_has_schema_version(self, dashboard):
        assert "schemaVersion" in dashboard
        assert isinstance(dashboard["schemaVersion"], int)


class TestDashboardPanels:
    """Each panel must have required keys and valid structure."""

    def test_panels_not_empty(self, dashboard, dashboard_file):
        assert len(dashboard["panels"]) > 0, f"{dashboard_file} has no panels"

    def test_panel_required_keys(self, dashboard, dashboard_file):
        for panel in dashboard["panels"]:
            # Row panels don't need targets
            if panel.get("type") == "row":
                continue
            for key in REQUIRED_PANEL_KEYS:
                assert key in panel, (
                    f"{dashboard_file} panel '{panel.get('title', '?')}' missing key: {key}"
                )

    def test_panel_has_grid_pos_fields(self, dashboard):
        for panel in dashboard["panels"]:
            if panel.get("type") == "row":
                continue
            gp = panel["gridPos"]
            for field in ("h", "w", "x", "y"):
                assert field in gp, f"Panel '{panel['title']}' gridPos missing '{field}'"

    def test_panel_targets_have_raw_sql(self, dashboard, dashboard_file):
        for panel in dashboard["panels"]:
            if panel.get("type") == "row":
                continue
            for target in panel["targets"]:
                assert "rawSql" in target, (
                    f"{dashboard_file} panel '{panel['title']}' target missing rawSql"
                )


class TestDatasourceReferences:
    """All targets must reference the correct datasource."""

    def test_datasource_uid(self, dashboard, dashboard_file):
        for panel in dashboard["panels"]:
            if panel.get("type") == "row":
                continue
            for target in panel["targets"]:
                ds = target.get("datasource", {})
                assert ds.get("uid") == DATASOURCE_NAME, (
                    f"{dashboard_file} panel '{panel['title']}' has wrong datasource uid"
                )


class TestUniqueIds:
    """UIDs must be unique across dashboards, panel IDs unique within each."""

    def test_all_uids_unique(self, all_dashboards):
        uids = [d["uid"] for d in all_dashboards.values()]
        assert len(uids) == len(set(uids)), f"Duplicate UIDs found: {uids}"

    def test_panel_ids_unique_within_dashboard(self, dashboard, dashboard_file):
        ids = [p["id"] for p in dashboard["panels"]]
        assert len(ids) == len(set(ids)), (
            f"{dashboard_file} has duplicate panel IDs: {ids}"
        )
