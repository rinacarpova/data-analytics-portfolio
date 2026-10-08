# Eval run v0-semantic-layer-skill

Skill arm: the first version of the plugin, one `ad-revenue-semantic-layer` skill (definitions, baseline rules, data traps), removed after this run. Cases 01-10, 1 run per arm. The skill was replaced before the first commit, so its text is not in the repository; its design is described in the project README.

- Date: 2026-10-08
- Claude Code: 2.1.278
- Agent model: not pinned (the CLI default at run time; not recorded by the CLI)
- LLM judge: not pinned (claude plugin eval default), 3 votes per grader, pass on 2
- Score: weighted share of graders passed within a run, averaged over runs, then averaged equally across cases (each question counts once). Errored runs are excluded.

| Case | Type | Skill + data | Data only | Δ | Skill fired | Errored runs | Failed graders (data only) |
|---|---|---:|---:|---:|---:|---:|---|
| 01-total-revenue | lookup | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 02-site-ecpm-on-a-day | trap | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 03-top-channel | lookup | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 04-viewability | trap | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 05-device-ecpm | trap | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 06-wednesday-drop | trap | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 07-dedupe | trap | 0.00 | 0.00 | +0.00 | 1/1 | 0 / 0 | do-not-dedupe |
| 08-most-unusual-day | trap | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 09-why-21-june | diagnosis | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |
| 10-channel-21-alert | diagnosis | 1.00 | 1.00 | +0.00 | 1/1 | 0 / 0 | — |

| Type | Skill + data | Data only | Δ |
|---|---:|---:|---:|
| lookup (2) | 1.00 | 1.00 | +0.00 |
| trap (6) | 0.83 | 0.83 | +0.00 |
| diagnosis (2) | 1.00 | 1.00 | +0.00 |
| **overall (10)** | **0.90** | **0.90** | **+0.00** |

Runs per case and arm: 1. Errored runs (excluded): 0. Total cost incl. judge: $2.33.
