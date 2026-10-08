# Eval run v1-workflow-skills

Skill arm: `alert-triage` + `revenue-morning-brief` + shared `references/`, as in commit 5fd9b42. Cases 10-16, 3 runs per arm. The cases were written alongside the skills (a development set, not held-out).

- Date: 2026-10-08
- Claude Code: 2.1.278
- Agent model: not pinned (the CLI default at run time; not recorded by the CLI)
- LLM judge: not pinned (claude plugin eval default), 3 votes per grader, pass on 2
- Score: weighted share of graders passed within a run, averaged over runs, then averaged equally across cases (each question counts once). Errored runs are excluded.

| Case | Type | Skill + data | Data only | Δ | Skill fired | Errored runs | Failed graders (data only) |
|---|---|---:|---:|---:|---:|---:|---|
| 10-channel-21-alert | diagnosis | 1.00 | 0.83 | +0.17 | 3/3 | 0 / 0 | real-stop-date |
| 11-triage-all-alerts | triage | 1.00 | 0.89 | +0.11 | 3/3 | 0 / 0 | real-timing |
| 12-quiet-22-june | triage | 1.00 | 0.25 | +0.75 | 3/3 | 0 / 0 | cooldown |
| 13-advertiser-16-alert | triage | 1.00 | 0.67 | +0.33 | 3/3 | 0 / 0 | one-day-spike |
| 14-brief-20-june | brief | 0.80 | 0.80 | -0.00 | 3/3 | 0 / 0 | brevity |
| 15-brief-26-june | brief | 0.67 | 0.00 | +0.67 | 3/3 | 0 / 0 | calm |
| 16-brief-10-june | brief | 1.00 | 1.00 | +0.00 | 3/3 | 0 / 0 | — |

| Type | Skill + data | Data only | Δ |
|---|---:|---:|---:|
| diagnosis (1) | 1.00 | 0.83 | +0.17 |
| triage (3) | 1.00 | 0.60 | +0.40 |
| brief (3) | 0.82 | 0.60 | +0.22 |
| **overall (7)** | **0.92** | **0.63** | **+0.29** |

Runs per case and arm: 3. Errored runs (excluded): 0. Total cost incl. judge: $8.75.
