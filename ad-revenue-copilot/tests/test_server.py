"""Tests for the MCP server: guardrails on a small temporary database, and the golden-path
tools against the real project database when it has been built."""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "ad-revenue-db" / "server"))
import ad_revenue_mcp as server  # noqa: E402


@pytest.fixture
def tiny_db(tmp_path, monkeypatch):
    path = tmp_path / "tiny.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create table fct_ad_delivery_daily as select range as site_id, range * 1.5 as revenue from range(300)")
    con.close()
    monkeypatch.setenv("AD_REVENUE_DB", str(path))
    return path


def test_select_returns_rows(tiny_db):
    result = server.run_query("select sum(revenue) as revenue from fct_ad_delivery_daily")
    assert result["columns"] == ["revenue"]
    assert result["rows"] == [[67275.0]]
    assert result["truncated"] is False


def test_rows_are_capped(tiny_db):
    result = server.run_query("select * from fct_ad_delivery_daily", max_rows=10_000)
    assert result["row_count"] == server.MAX_ROWS
    assert result["truncated"] is True


@pytest.mark.parametrize("sql", [
    "create table t as select 1",
    "insert into fct_ad_delivery_daily values (1, 1.0)",
    "drop table fct_ad_delivery_daily",
    "set enable_external_access = true",
    "copy fct_ad_delivery_daily to 'out.csv'",
    "attach 'other.duckdb'",
    "select 1; select 2",
])
def test_non_read_statements_are_rejected(tiny_db, sql):
    with pytest.raises(server.QueryError):
        server.run_query(sql)


def test_local_files_cannot_be_read(tiny_db, tmp_path):
    secret = tmp_path / "secret.csv"
    secret.write_text("a\n1\n")
    with pytest.raises(server.QueryError, match="Permission"):
        server.run_query(f"select * from read_csv('{secret.as_posix()}')")


def test_unknown_table_is_rejected(tiny_db):
    with pytest.raises(server.QueryError, match="Unknown table"):
        server.describe_table("fct_ad_delivery_daily; drop table x")


def test_missing_database_explains_how_to_build_it(tmp_path, monkeypatch):
    monkeypatch.setenv("AD_REVENUE_DB", str(tmp_path / "missing.duckdb"))
    with pytest.raises(server.QueryError, match="dbt build"):
        server.list_tables()


real_db = pytest.mark.skipif(not server.DEFAULT_DB.exists(), reason="project database not built")


@real_db
def test_revenue_change_of_21_june(monkeypatch):
    monkeypatch.delenv("AD_REVENUE_DB", raising=False)
    result = server.get_revenue_change("2019-06-21")
    assert result["day"]["revenue_delta"] == pytest.approx(415.46, abs=0.01)
    assert result["top_drivers"]["advertiser_id"][0]["dimension_value"] == "79"
    assert result["top_drivers"]["site_id"][0]["dimension_value"] == "345"
    assert any(a["rule"] == "total revenue" for a in result["alerts"])


@real_db
def test_day_without_baseline_is_explained(monkeypatch):
    monkeypatch.delenv("AD_REVENUE_DB", raising=False)
    result = server.get_revenue_change("2019-06-10")
    assert "No baseline" in result["error"]


@real_db
def test_alerts_in_range(monkeypatch):
    monkeypatch.delenv("AD_REVENUE_DB", raising=False)
    assert len(server.get_alerts()) == 20
    assert {a["dimension_value"] for a in server.get_alerts("2019-06-15", "2019-06-15")} == {"5181", "21", "2644"}
