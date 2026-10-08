# /// script
# requires-python = ">=3.10"
# dependencies = ["duckdb>=1.5", "pyyaml>=6"]
# ///
"""Recompute every reference answer from the database and compare it with answer_key.yaml.

Usage: uv run --script plugins/ad-revenue-copilot/evals/answer-key/check_answer_key.py [path/to/ad_revenue.duckdb]
Exit code 1 if any value differs, so the graders never drift from the data.
"""

import datetime as dt
import math
import sys
from pathlib import Path

import duckdb
import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[4] / "ad-revenue-analytics" / "data" / "ad_revenue.duckdb"


def tolerance_for(expected: float) -> float:
    """Half a unit of the last decimal written in the key, e.g. 2.9395 -> 0.00005."""
    text = repr(expected)
    decimals = len(text.split(".")[1]) if "." in text else 0
    return 0.5 * 10 ** -decimals + 1e-12


def matches(actual, expected) -> bool:
    if isinstance(actual, (dt.date, dt.datetime)):
        actual = actual.isoformat()
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return actual is not None and math.isclose(float(actual), expected, abs_tol=tolerance_for(expected))
    return str(actual) == str(expected)


def main() -> int:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    con = duckdb.connect(str(db), read_only=True)
    key = yaml.safe_load((HERE / "answer_key.yaml").read_text(encoding="utf-8"))
    failures = 0
    for item in key:
        cursor = con.execute(item["sql"])
        row = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
        for name, expected in item["expected"].items():
            actual = row.get(name)
            ok = matches(actual, expected)
            failures += not ok
            shown = round(actual, 6) if isinstance(actual, float) else actual
            print(f"{'ok  ' if ok else 'FAIL'} {item['case']:<24} {name:<32} expected {expected!s:<12} got {shown}")
    print(f"\n{failures} mismatches" if failures else "\nAll reference answers match the database.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
