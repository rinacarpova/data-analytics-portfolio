# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2.3,<3", "duckdb>=1.5"]
# ///
"""Read-only MCP server over the ad-revenue-analytics DuckDB database.

The server gives Claude access to the data and runs the project's method in code; the
procedures and report formats live in the ad-revenue-copilot skills. Two kinds of tools:

- generic: list_tables, describe_table, run_query
- golden path: get_revenue_change, get_alerts. They run the project's own method
  (same-weekday baseline, traffic / mix / rate split, volume / price drivers), so the
  standard morning questions get the same answer every time.

Safety does not rely on parsing SQL with regexes. The database is opened read-only with
file system access and extensions disabled and the configuration locked, so a query
cannot write, read local files, attach other databases or turn the limits back off.
On top of that, only single SELECT statements are accepted, results are capped and
long queries are interrupted.

Database path: env AD_REVENUE_DB, else ad-revenue-analytics/data/ad_revenue.duckdb at the
root of the portfolio repository (the layout when the plugin is used from a clone).
"""

from __future__ import annotations

import datetime as dt
import decimal
import os
import threading
from pathlib import Path
from typing import Any

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

DEFAULT_DB = Path(__file__).resolve().parents[4] / "ad-revenue-analytics" / "data" / "ad_revenue.duckdb"
MAX_ROWS = 200
QUERY_TIMEOUT_SECONDS = 30
DRILLDOWN_DIMENSIONS = (
    "site_id", "ad_unit_id", "ad_type_id", "monetization_channel_id",
    "advertiser_id", "geo_id", "device_category_id", "os_id",
)

mcp = MCPServer(
    "ad-revenue-db",
    instructions=(
        "Read-only access to a publisher's ad delivery data (June 2019, public Kaggle dataset) "
        "modelled in dbt."
    ),
)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


class QueryError(ToolError):
    """A query was rejected or failed. ToolError passes the message on to the model;
    any other exception would reach it only as a generic error."""


def db_path() -> Path:
    path = Path(os.environ.get("AD_REVENUE_DB", DEFAULT_DB))
    if not path.exists():
        raise QueryError(
            f"Database not found at {path}. Build it first: in ad-revenue-analytics/ run "
            "`python scripts/download_data.py` and `dbt build` from dbt/, or set AD_REVENUE_DB."
        )
    return path


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(
        str(db_path()),
        read_only=True,
        config={"enable_external_access": False, "lock_configuration": True},
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _execute(sql: str, params: list | None = None, max_rows: int = MAX_ROWS) -> dict:
    """Run one statement and return columns, rows and whether the result was cut."""
    con = connect()
    timer = threading.Timer(QUERY_TIMEOUT_SECONDS, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(sql, params or [])
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchmany(max_rows + 1)
    except duckdb.InterruptException as exc:
        raise QueryError(f"Query stopped after {QUERY_TIMEOUT_SECONDS}s; aggregate more or filter.") from exc
    except duckdb.Error as exc:
        raise QueryError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        timer.cancel()
        con.close()
    truncated = len(rows) > max_rows
    return {
        "columns": columns,
        "rows": [[_jsonable(v) for v in row] for row in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": truncated,
    }


def _records(result: dict) -> list[dict]:
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


def _table_names() -> list[str]:
    result = _execute(
        "select table_name from information_schema.tables where table_schema = 'main' order by 1"
    )
    return [row[0] for row in result["rows"]]


@mcp.tool(annotations=READ_ONLY)
def list_tables() -> list[dict]:
    """List the tables of the ad revenue database with their row counts.

    Layers follow dbt naming: stg_ (typed source rows), int_ (intermediate),
    fct_ (facts at a declared grain), mart_ (answers: revenue change, drivers, alerts).
    """
    return [
        {"table": name, "rows": _execute(f'select count(*) from "{name}"')["rows"][0][0]}
        for name in _table_names()
    ]


@mcp.tool(annotations=READ_ONLY)
def describe_table(table: str) -> dict:
    """Show the columns, types and three sample rows of one table."""
    if table not in _table_names():
        raise QueryError(f"Unknown table {table!r}. Call list_tables to see what exists.")
    columns = _execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = 'main' and table_name = ? order by ordinal_position",
        [table],
    )
    sample = _execute(f'select * from "{table}" limit 3')
    return {"table": table, "columns": _records(columns), "sample_rows": _records(sample)}


@mcp.tool(annotations=READ_ONLY)
def run_query(sql: str, max_rows: int = 50) -> dict:
    """Run one read-only SQL query (DuckDB dialect) and return at most max_rows rows (cap 200).

    Only a single SELECT-type statement is accepted (SELECT, WITH ... SELECT, DESCRIBE,
    SUMMARIZE, SHOW). Aggregate in SQL instead of pulling raw rows: the fact table has
    258K rows. `truncated: true` means there were more rows than returned.
    """
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as exc:
        raise QueryError(f"Could not parse the query: {exc}") from exc
    if len(statements) != 1:
        raise QueryError(f"Send exactly one statement, got {len(statements)}.")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise QueryError(f"Only read queries are allowed, got a {statements[0].type.name} statement.")
    return _execute(sql, max_rows=max(1, min(int(max_rows), MAX_ROWS)))


@mcp.tool(annotations=READ_ONLY)
def get_revenue_change(report_date: str, top_n: int = 3) -> dict:
    """Explain one day's revenue against the same weekday of the previous 2-3 weeks.

    Returns the day's change split into traffic, mix and rate effects, the top_n slices
    of every drill-down dimension ranked by the size of their change (each split into
    volume and price effects), and the alerts raised that day. Only 2019-06-15 to
    2019-06-30 have a baseline; earlier days return an explanation instead.
    """
    day = _records(_execute(
        "select * from mart_revenue_change_daily where report_date = cast(? as date)", [report_date]
    ))
    if not day:
        available = _execute(
            "select min(report_date), max(report_date) from mart_revenue_change_daily"
        )["rows"][0]
        return {
            "report_date": report_date,
            "error": (
                f"No baseline for {report_date}. A day is compared with the same weekday of "
                f"at least 2 previous weeks, so only {available[0]} to {available[1]} can be explained."
            ),
        }
    drivers = _records(_execute(
        """
        select dimension, dimension_value, driver_rank, baseline_revenue, revenue, revenue_delta,
               volume_effect, price_effect, unattributed_effect, share_of_total_delta,
               baseline_impressions, impressions, baseline_ecpm, ecpm
        from mart_revenue_change_drivers
        where report_date = cast(? as date) and dimension <> 'total' and driver_rank <= ?
        order by dimension, driver_rank
        """,
        [report_date, max(1, min(int(top_n), 10))],
    ))
    alerts = _records(_execute(
        "select rule, dimension, dimension_value, main_driver, alert_text "
        "from mart_revenue_alerts where report_date = cast(? as date) order by share_of_day_revenue desc",
        [report_date],
    ))
    by_dimension: dict[str, list[dict]] = {d: [] for d in DRILLDOWN_DIMENSIONS}
    for row in drivers:
        by_dimension.setdefault(row.pop("dimension"), []).append(row)
    return {"day": day[0], "top_drivers": by_dimension, "alerts": alerts}


@mcp.tool(annotations=READ_ONLY)
def get_alerts(date_from: str = "2019-06-01", date_to: str = "2019-06-30") -> list[dict]:
    """List the revenue alerts between two dates (inclusive), with their effects and text.

    Rules: 'total revenue' (the day off its usual noise), 'stopped delivering' (a material
    slice below 10% of its baseline), 'large slice moved' (a big, unusual move of one slice).
    One real event often raises several alerts on different dimensions of the same slice.
    """
    return _records(_execute(
        "select * from mart_revenue_alerts "
        "where report_date between cast(? as date) and cast(? as date) "
        "order by report_date, share_of_day_revenue desc",
        [date_from, date_to],
    ))


if __name__ == "__main__":
    mcp.run()
