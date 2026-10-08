# /// script
# requires-python = ">=3.10"
# ///
"""Measure what the ad-revenue-copilot skills add on top of plain data access.

`claude plugin eval` has a built-in baseline arm, but it removes every plugin a case loads,
including the data plugin, so it compares "Claude with data" against "Claude with no data".
This runner compares the two arms that matter instead:

- skill+data: the cases as written (ad-revenue-copilot + ad-revenue-db)
- data-only:  the same cases and graders with only ad-revenue-db loaded

It builds the data-only copy of the suite, runs both arms with `claude plugin eval
--ablation none`, and writes one comparison table. The `skill-loaded` grader is reported
as an indicator (did the skill fire), not scored.

Usage, from ad-revenue-copilot/:
    uv run --script scripts/run_evals.py --runs 3 [--case 09-why-21-june] [--model sonnet] [-j 4]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ad-revenue-copilot"
EVALS = PLUGIN / "evals"
DATA_ONLY = PLUGIN / "evals-data-only"
RESULTS = EVALS / "results"
ARMS = {"skill+data": EVALS, "data-only": DATA_ONLY}
BOTH_PLUGINS = 'plugins: ["../..", "../../../ad-revenue-db"]'
DATA_PLUGIN_ONLY = 'plugins: ["../../../ad-revenue-db"]'
INDICATOR = "skill-loaded"
MCP_TOOLS = "mcp__plugin_ad-revenue-db_ad-revenue-db__*"


def build_data_only_suite() -> None:
    """Copy every case, load only the data plugin, and drop the skill indicator."""
    shutil.rmtree(DATA_ONLY, ignore_errors=True)
    for prompt in sorted(EVALS.glob("*/prompt.md")):
        case_dir = DATA_ONLY / prompt.parent.name
        shutil.copytree(prompt.parent, case_dir)
        text = prompt.read_text(encoding="utf-8")
        if BOTH_PLUGINS not in text:
            sys.exit(f"{prompt}: expected the line {BOTH_PLUGINS!r}")
        (case_dir / "prompt.md").write_text(text.replace(BOTH_PLUGINS, DATA_PLUGIN_ONLY), encoding="utf-8")
        (case_dir / "graders" / f"{INDICATOR}.md").unlink(missing_ok=True)


def run_arm(arm: str, eval_dir: Path, out_dir: Path, args: argparse.Namespace) -> dict:
    claude = shutil.which("claude")
    if not claude:
        sys.exit("claude CLI not found on PATH")
    json_path = out_dir / f"{arm}.json"
    cmd = [
        claude, "plugin", "eval", ".",
        "--eval-dir", eval_dir.relative_to(ROOT).as_posix(),
        "--ablation", "none",
        "--runs", str(args.runs),
        "--mocks", "off",
        "--allow-tools", MCP_TOOLS,
        "--trust-plugin",
        "--no-publish",
        "--threshold", "0",
        "--output-dir", str(out_dir / arm),
        "--json", str(json_path),
        "-j", str(args.concurrency),
    ]
    if args.case:
        cmd += ["--case", args.case]
    if args.model:
        cmd += ["--model", args.model]
    if args.judge_model:
        cmd += ["--judge-model", args.judge_model]
    if args.max_cost_usd:
        cmd += ["--max-cost-usd", str(args.max_cost_usd)]
    print(f"\n== {arm}: {' '.join(cmd[1:])}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=False)
    return json.loads(json_path.read_text(encoding="utf-8"))


def category(case_name: str) -> str:
    text = (EVALS / case_name / "prompt.md").read_text(encoding="utf-8")
    tags = re.search(r"^tags:\s*\[(.*)\]", text, re.M).group(1)
    for name in ("triage", "brief", "diagnosis", "trap"):
        if name in tags:
            return name
    return "lookup"


def score_runs(case: dict) -> dict:
    """Mean weighted score, all-graders pass rate and skill-fired count over a case's runs.

    Runs that ended in an error (a usage limit, a crashed session) are left out of the score
    and counted in `errors`: they say nothing about the answer quality.
    """
    all_runs = case["arms"]["with"]
    runs = [r for r in all_runs if not r.get("error")]
    scores, passes, fired = [], 0, 0
    for run in runs:
        graders = [g for g in run["graders"] if g["name"] != INDICATOR]
        total = sum(g["weight"] for g in graders)
        scores.append(sum(g["weight"] for g in graders if g["passed"]) / total if total else 0.0)
        passes += all(g["passed"] for g in graders)
        fired += any(g["name"] == INDICATOR and g["passed"] for g in run["graders"])
    n = len(runs)
    return {
        "score": sum(scores) / n if n else None,
        "pass_rate": passes / n if n else None,
        "fired": fired,
        "runs": n,
        "errors": len(all_runs) - n,
        "cost": sum(r.get("costUsd", 0) + r.get("judgeCostUsd", 0) for r in all_runs),
        "failed_graders": sorted({g["name"] for r in runs for g in r["graders"]
                                  if g["name"] != INDICATOR and not g["passed"]}),
    }


def comparison_table(results: dict[str, dict]) -> str:
    cases = {c["name"]: c for c in results["skill+data"]["cases"]}
    baseline = {c["name"]: c for c in results["data-only"]["cases"]}
    lines = [
        "| Case | Type | Skill + data | Data only | Δ | Skill fired | Errored runs | Failed graders (data only) |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    by_category: dict[str, list[tuple[float, float]]] = {}
    errors = 0
    for name in sorted(cases):
        if name not in baseline:
            continue
        w, wo = score_runs(cases[name]), score_runs(baseline[name])
        errors += w["errors"] + wo["errors"]
        errored = f"{w['errors']} / {wo['errors']}"
        if w["score"] is None or wo["score"] is None:
            lines.append(f"| {name} | {category(name)} | n/a | n/a | n/a | — | {errored} | — |")
            continue
        by_category.setdefault(category(name), []).append((w["score"], wo["score"]))
        lines.append(
            f"| {name} | {category(name)} | {w['score']:.2f} | {wo['score']:.2f} | "
            f"{w['score'] - wo['score']:+.2f} | {w['fired']}/{w['runs']} | {errored} | "
            f"{', '.join(wo['failed_graders']) or '—'} |"
        )
    lines += ["", "| Type | Skill + data | Data only | Δ |", "|---|---:|---:|---:|"]
    pairs_all = []
    for cat in ("lookup", "trap", "diagnosis", "triage", "brief"):
        pairs = by_category.get(cat, [])
        pairs_all += pairs
        if pairs:
            w = sum(p[0] for p in pairs) / len(pairs)
            wo = sum(p[1] for p in pairs) / len(pairs)
            lines.append(f"| {cat} ({len(pairs)}) | {w:.2f} | {wo:.2f} | {w - wo:+.2f} |")
    if pairs_all:
        w = sum(p[0] for p in pairs_all) / len(pairs_all)
        wo = sum(p[1] for p in pairs_all) / len(pairs_all)
        lines.append(f"| **overall ({len(pairs_all)})** | **{w:.2f}** | **{wo:.2f}** | **{w - wo:+.2f}** |")
    cost = sum(score_runs(c)["cost"] for r in results.values() for c in r["cases"])
    runs = max((len(c["arms"]["with"]) for c in cases.values()), default=0)
    lines += ["", f"Runs per case and arm: {runs}. Errored runs (excluded): {errors}. "
                  f"Total cost incl. judge: ${cost:.2f}."]
    if errors:
        lines.append("**Warning:** some runs errored (e.g. a usage limit); scores use the remaining runs only.")
    return "\n".join(lines)


def run_metadata(results: dict[str, dict], model: str | None, judge_model: str | None) -> list[str]:
    """What is needed to reproduce or compare the run: CLI version, models, date, scoring."""
    first = results["skill+data"]
    return [
        f"- Date: {first.get('startedAt', '?')[:10]}",
        f"- Claude Code: {first.get('claudeVersion', '?')}",
        f"- Agent model: {model or 'not pinned (the CLI default at run time; not recorded by the CLI)'}",
        f"- LLM judge: {judge_model or 'not pinned (claude plugin eval default)'}, 3 votes per grader, pass on 2",
        "- Score: weighted share of graders passed within a run, averaged over runs, then averaged "
        "equally across cases (each question counts once). Errored runs are excluded.",
    ]


def compact_results(results: dict[str, dict]) -> list[dict]:
    """One row per case, arm and run: enough to audit the table without the full traces."""
    rows = []
    for arm, result in results.items():
        for case in result["cases"]:
            for i, run in enumerate(case["arms"]["with"]):
                graders = {g["name"]: g["passed"] for g in run["graders"]}
                rows.append({
                    "case": case["name"],
                    "arm": arm,
                    "run": i + 1,
                    "error": run.get("error"),
                    "turns": run.get("turns"),
                    "cost_usd": round(run.get("costUsd", 0) + run.get("judgeCostUsd", 0), 4),
                    "graders_passed": sorted(k for k, v in graders.items() if v),
                    "graders_failed": sorted(k for k, v in graders.items() if not v),
                })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--case", help="case name glob, e.g. '09-*'")
    parser.add_argument("--model", help="model for the agent runs, e.g. sonnet (recommended: pin it)")
    parser.add_argument("--judge-model", help="model for the LLM graders")
    parser.add_argument("-j", "--concurrency", type=int, default=2)
    parser.add_argument("--max-cost-usd", type=float, help="cost ceiling per arm")
    args = parser.parse_args()

    build_data_only_suite()
    out_dir = RESULTS / f"comparison-{dt.datetime.now():%Y-%m-%dT%H-%M-%S}"
    out_dir.mkdir(parents=True)
    results = {arm: run_arm(arm, eval_dir, out_dir, args) for arm, eval_dir in ARMS.items()}
    table = "\n".join(run_metadata(results, args.model, args.judge_model)) + "\n\n" + comparison_table(results)
    (out_dir / "comparison.md").write_text(table + "\n", encoding="utf-8")
    (out_dir / "compact.json").write_text(json.dumps(compact_results(results), indent=1) + "\n", encoding="utf-8")
    print("\n" + table + f"\n\nSaved to {out_dir / 'comparison.md'}")


if __name__ == "__main__":
    main()
