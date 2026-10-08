# Ad Revenue Copilot: Claude Plugins for Ad Revenue Analytics

Two Claude Code plugins on top of the [Ad Revenue Analytics](../ad-revenue-analytics/) dbt model,
and an eval suite that measures which part of the setup actually makes Claude's answers right.
Built on public data only.

## Result

**Deterministic knowledge belongs in the data model and its tools; skills earn their place in
procedures and judgement.** This is a development-set result (see [Limits of the evidence](#limits-of-the-evidence)):
a direction worth testing, not a measured effect size.

The project started as one plugin with a "semantic layer" skill: metric definitions, the
same-weekday baseline, data traps (**v0**). The eval showed that this skill added nothing. With
read-only access to the dbt marts and two tools that run the project's method in code, Claude
answered the number questions just as well without it. The skills were then rewritten as
**workflows**: triaging alerts and writing a daily brief (**v1**), and those changed the answers:

| Run | Questions | Cases × runs | Skill arm | Data only | Δ |
|---|---|---:|---:|---:|---:|
| v0: semantic-layer skill | Numbers: lookups, data traps, a revenue diagnosis | 9 × 1 | 0.89 | 0.89 | 0.00 |
| v1: workflow skills | Alert triage (incl. one stop alert) | 4 × 3 | **1.00** | 0.66 | **+0.34** |
| v1: workflow skills | Daily revenue brief | 3 × 3 | **0.82** | 0.60 | **+0.22** |

Score: the weighted share of graders passed within a run, averaged over runs, then averaged
equally across cases, so each question counts once. Per-case tables, every run's passed and
failed graders, errors and cost are committed in [`evals/reported/`](plugins/ad-revenue-copilot/evals/reported/).

| Run metadata | |
|---|---|
| Date | 8 October 2026 |
| Claude Code | 2.1.278 |
| Agent model | not pinned: the CLI default at run time, which the CLI does not record |
| LLM judge | not pinned: the `claude plugin eval` default; 3 votes per grader, pass on 2 |
| Cost | v0 $2.33 (20 runs), v1 $8.75 (42 runs), incl. the judge |

What the workflow skills changed, from the graders and traces:

- **Silence is not "all clear".** On 22 June only two small alerts fired, yet revenue was +30%
  against previous Saturdays: the main buyer was still paying more. The total-revenue alert was
  muted by its 7-day cooldown after 21 June. With the triage skill Claude explained that in 3 of 3
  runs; without it, in 0 of 3.
- **Alert date is not event date.** A delivery that "stopped" on 15 June had stopped on 12–13 June;
  alerts cannot fire before a baseline exists. Without the skill Claude dated it in 1 of 3 runs.
- **A normal day reads as normal.** For an ordinary Wednesday (−5% against previous Wednesdays,
  no alerts) the data-only briefs failed the "calm, short, no action" check in 3 of 3 runs; with the
  brief skill, 2 of 3 passed.
- **One driver, not five.** Without the skill, the 20 June brief failed the brevity check (too long,
  or the main buyer repeated under its geo, channel and ad type) in 3 of 3 runs; with it, 0 of 3.

And what the v0 skill did not change: on lookups, eCPM and viewability definitions, the
same-weekday baseline and the 21 June diagnosis, both arms scored the same. Claude computes ratios
from sums unprompted, and `get_revenue_change` already returns the same-weekday comparison and the
traffic / mix / rate split. Putting that method in code made a prompt for it unnecessary.

### Limits of the evidence

- **Development set, not held-out.** The v1 skills were written after v0 failed, and cases 11–16
  were written alongside them by the same author. The v1 numbers show the skills work on the cases
  they were built for. Held-out cases written after the skills are frozen are the next step.
- **The skill arm also gets reference knowledge, not only procedure.** Both skills link to shared
  [`references/`](plugins/ad-revenue-copilot/references/) that the data-only arm never sees, and these
  contain dataset facts some cases touch: `mart_revenue_alerts` has 20 rows (case 11), there is no
  baseline before 15 June (cases 06, 16), the week of 10 June had an eCPM dip (case 16, also named in
  the brief skill, where it stays until the next run). So the Δ measures *workflow + reference knowledge* against data access, not the
  workflow alone. The skills contain no eval answers as such (the one SQL example uses placeholders),
  but they are not free of dataset facts either.
- **Small samples.** v1 ran 3 times per case and arm, v0 once. Read a Δ of one case as a direction.
- **The judge votes on criteria I wrote.** They are explicit and their numbers are checked against
  computed references, but they encode my view of a good triage and a good brief.
- In cases 14 and 15 the skill arm failed one of three runs; those traces were not kept.
- One month of one publisher's data. The skills' thresholds (±10% for a "normal" day, ≥ 5% of daily
  revenue to act) are reasonable defaults, not calibrated.

## Design

| Plugin | What it is | Role |
|---|---|---|
| [`ad-revenue-db`](plugins/ad-revenue-db/) | Read-only MCP server over the project's DuckDB database | **Data and method in code**: `list_tables`, `describe_table`, `run_query`, plus `get_revenue_change` (a day against the same weekday of previous weeks, traffic / mix / rate split, top drivers, alerts) and `get_alerts` |
| [`ad-revenue-copilot`](plugins/ad-revenue-copilot/) | Two skills and shared [references](plugins/ad-revenue-copilot/references/) | **Procedure and judgement**: [`alert-triage`](plugins/ad-revenue-copilot/skills/alert-triage/SKILL.md) groups alerts into events, finds the real start, checks what the cooldown hides, sizes and rates each event; [`revenue-morning-brief`](plugins/ad-revenue-copilot/skills/revenue-morning-brief/SKILL.md) writes a fixed two-minute brief with a normal / watch / act verdict |

They are separate plugins so the eval can remove the skills while keeping data access.

### Guardrails of the MCP server

Safety is enforced by the database engine, not by matching SQL with regexes:

- the database is opened **read-only**, with **file system access and extensions disabled** and the
  **configuration locked**, so a query cannot write, read local files, attach other databases or
  turn the limits back off;
- only a single SELECT-type statement is accepted (checked with DuckDB's own parser);
- results are capped at 200 rows and queries are interrupted after 30 seconds;
- rejected queries return the reason to the model, so it can correct itself.

[`tests/test_server.py`](tests/test_server.py) covers each of these (writes, DDL, `COPY TO`, `ATTACH`,
`SET`, reading a local CSV, multiple statements) and checks the method tools against known answers.

## Evals

16 cases in the format of [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals),
written as a stakeholder would ask, with no hints:

| Case | Type | What it checks |
|---|---|---|
| 01–05 | lookup, trap | Totals, eCPM and viewability from sums, top channel, segment comparison |
| 06 | trap | A Wednesday is −5% against previous Wednesdays, not the −33% of a trailing average |
| 07 | trap | Duplicate-looking rows are fragments of a finer grain; deduplication loses 6–10% of revenue |
| 08 | trap | The most unusual day (21 June) is not the highest-revenue day (24 June) |
| 09 | diagnosis | Both drivers of 21 June: a traffic surge on site 345 and the main buyer paying more |
| 10 | triage | A real but small stop that began 3 days before its alert |
| 11 | triage | 20 alerts → about 6 events, with real timing and priorities |
| 12 | triage | A "quiet" day hiding a +30% move behind the alert cooldown |
| 13 | triage | A one-day spike that reverted: watch, not act |
| 14–16 | brief | A busy day, an ordinary day, and a day without a baseline |

Each case has deterministic `regex` graders for key numbers and `llm` judges with explicit PASS / FAIL
criteria. A `tool_used: Skill` grader records whether a skill fired; it is an indicator, not scored.

**Reference answers are computed, not typed.**
[`answer_key.yaml`](plugins/ad-revenue-copilot/evals/answer-key/answer_key.yaml) holds the SQL and the
expected value of every number the graders rely on, and
[`check_answer_key.py`](plugins/ad-revenue-copilot/evals/answer-key/check_answer_key.py) recomputes
all 71 from the database and fails on any mismatch. It caught two of my own errors: a hand-estimated
baseline, and a deduplication query whose result changed between runs (`DISTINCT ON` without
`ORDER BY` keeps an arbitrary row).

### Validating the eval itself

The first run scored 10 / 10 with the plugin and 0 / 10 without, which was too good to be true.
The traces showed why: the built-in baseline arm of `claude plugin eval` removes **every** plugin a
case loads, so the "without" runs had no data and answered "please point me to the data". The
comparison measured data access, not knowledge.
[`scripts/run_evals.py`](scripts/run_evals.py) fixes this: it builds a copy of the suite that loads
only `ad-revenue-db`, runs both arms with `--ablation none`, and merges the results into one table.

## Run

Requires [uv](https://docs.astral.sh/uv/) and the database of
[ad-revenue-analytics](../ad-revenue-analytics/#run) (`python scripts/download_data.py`, then
`dbt build` from `dbt/`). The MCP server finds it at `ad-revenue-analytics/data/ad_revenue.duckdb`
in this repository, or at the path in `AD_REVENUE_DB`.

Use the plugins from a clone:

```bash
claude --plugin-dir ad-revenue-copilot/plugins
```

or install them from this repository as a marketplace (installed plugins are copied to Claude
Code's cache, so set `AD_REVENUE_DB` to the database path):

```
/plugin marketplace add rinacarpova/data-analytics-portfolio
/plugin install ad-revenue-db@rinacarpova-analytics
/plugin install ad-revenue-copilot@rinacarpova-analytics
```

Tests, reference answers and the eval comparison, from `ad-revenue-copilot/`:

```bash
uv run --no-project --with-requirements requirements-dev.txt python -m pytest
uv run --script plugins/ad-revenue-copilot/evals/answer-key/check_answer_key.py
uv run --script scripts/run_evals.py --runs 3 -j 4
```

The eval starts the real MCP server, which runs as you outside the eval sandbox; it is read-only
by construction (see Guardrails). On Windows, call `claude.cmd` from PowerShell if script execution
is disabled.

## Next steps

In order of how much they would strengthen the evidence:

- [ ] **Held-out cases**: 4–6 new stakeholder questions on triage and briefs, written after the
      skills are frozen and run once, with no skill edits in between
- [ ] **Three arms** instead of two: data only → data + references → data + references + workflow
      skills, to separate what comes from data access, from domain knowledge and from procedure
- [ ] Move dataset facts out of the skills into the references (the eCPM-dip line in the brief
      skill), and pin `--model` and `--judge-model` in every reported run. The line is kept on
      purpose until then: the reported v1 numbers were produced with it, and the code in the
      repository should match the reported run
- [ ] Rerun the number cases 3 times per arm on the workflow-skills version, keeping traces of
      failed runs (`--keep-temp`)
- [ ] Ablation of the method tools: data only without `get_revenue_change` / `get_alerts`, to
      measure how much comes from putting the method in code
- [ ] Cases the data cannot answer (why a buyer paid more): Claude should say so and say who can

## Structure

```
├── plugins/
│   ├── ad-revenue-db/                    # data and method in code
│   │   ├── .claude-plugin/plugin.json
│   │   ├── .mcp.json                     # starts the server with uv
│   │   └── server/ad_revenue_mcp.py      # read-only MCP server (PEP 723 script)
│   └── ad-revenue-copilot/               # procedures and judgement
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       │   ├── alert-triage/SKILL.md
│       │   └── revenue-morning-brief/SKILL.md
│       ├── references/                   # models, metrics, data traps (shared by both skills)
│       └── evals/
│           ├── 01-total-revenue/ … 16-brief-10-june/   # prompt.md + graders/
│           ├── answer-key/               # reference SQL + checker
│           └── reported/                 # per-case tables and per-run grader results of the reported runs
├── scripts/run_evals.py                  # skills + data vs data only
├── tests/test_server.py                  # guardrails and method tools
├── pyproject.toml
└── requirements-dev.txt
```

The marketplace manifest is at the repository root: [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).

## Tech

Claude Code plugins and skills · MCP (Python SDK 2.x) · DuckDB · dbt · pytest · `claude plugin eval`
