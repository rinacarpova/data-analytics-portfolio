# Data Analytics Portfolio

This repository contains selected analytics projects based on real-world business problems.

The projects focus on:
- SQL
- Python
- dbt
- data modeling
- analytics automation
- data quality
- business analysis
- AI-assisted analytics (Claude Code plugins, MCP, evals)

All projects use public or synthetic data and do not contain confidential company information.

## Projects

### [Annual Revenue Plan by Segment](annual-revenue-planning/)
A Python/Jupyter project that builds a 12-month revenue plan from public transaction data, preserves seasonal patterns, reconciles rounding, validates the final target, and exports the plan to Excel.

### [Ad Revenue Analytics: Data Model and Anomaly Detection](ad-revenue-analytics/)
A dbt + DuckDB project on public ad delivery data: a tested data model, a breakdown of every revenue change into traffic, mix and rate effects against a same-weekday baseline, anomaly detectors scored against labelled ad exchange data, and daily alerts that each come with their explanation.

### [Ad Revenue Copilot: Claude Plugins for Ad Revenue Analytics](ad-revenue-copilot/)
Two Claude Code plugins on top of the ad revenue model: a read-only MCP server that runs the analysis method in code, and workflow skills for alert triage and a daily revenue brief. An eval suite of 16 cases with computed reference answers shows where each layer helps: the data layer alone gets the numbers right, and the skills raise triage and briefing scores from 0.63 to 0.92.
