---
name: revenue-morning-brief
description: >
  Write the daily ad revenue brief for one day of the ad-revenue-analytics publisher data
  (June 2019, queried through the ad-revenue-db MCP server): how the day compares with normal,
  what drove it, which alerts fired, and whether anyone needs to act, in a fixed short format.
  Use for "morning report / daily brief / daily summary for <date>", "how did <date> go",
  "what moved revenue on <date>", "write the revenue update for <date>".
---

# Revenue morning brief

The reader is an ad ops lead with two minutes. They need to know: was the day normal, if not
why, and is there anything to do. The brief must read the same every day, so a quiet day is
recognisable at a glance and a real event stands out.

Data and definitions: [models](../../references/models.md), [metrics](../../references/metrics.md),
[data traps](../../references/data-traps.md).

## Procedure

1. Call `get_revenue_change` for the day (`top_n` 3). It returns the day against the average
   of the same weekday over the previous 2–3 weeks, the traffic / mix / rate split, the top
   drivers per dimension and the day's alerts.
2. **No baseline** (1–14 June): do not invent one. Say the standard comparison is not
   available, give the day's revenue, impressions and eCPM, and at most a clearly labelled
   comparison with the same weekday one week earlier. Mention that the week of 10 June had
   an eCPM dip across the board if the day falls in it. Skip to the verdict.
3. **Classify the day** by the change against the baseline:
   - **normal**: within ±10% and no alerts;
   - **watch**: beyond ±10%, or any alert;
   - **act**: an alert whose triage verdict would be "act" (a material slice stopped, or a
     move ≥ 5% of the day's revenue that is not explained by traffic).
4. **Pick at most three drivers.** Many dimensions show the same delivery (the main buyer
   moves the top geo, device and channel at once), so do not list facets of one driver as
   separate drivers: name the root slice (an advertiser or a site) and say what it moved.
   For each, say whether it was volume (impressions) or price (eCPM) and give the ratio
   (e.g. "2.1× its usual Friday impressions", "eCPM +17%").
5. **Alerts**: list the day's alerts grouped into events (see the `alert-triage` skill for
   grouping). If the day is far off its baseline but has no total alert, check the previous
   7 days: the 7-day cooldown can silence a continuing event.
6. **What the data cannot tell**: one line, only when it matters (e.g. why a buyer paid more:
   there are no bids or floor prices in this data).

## Format

Exactly this shape, no other sections. Under 180 words; a normal day takes 4 lines.

```
**<Weekday> <d Month>: revenue <X> (<±p%> vs <n> previous <weekday>s) — <normal | watch | act>**

Why: traffic <±a>, mix <±b>, rate <±c>. <one sentence on what that means>

Drivers:
- <root slice>: <±revenue> — <volume | price>, <ratio>
- …

Alerts: <events, or "none">

Not in the data: <one line, optional>

Next step: <one concrete action with an owner, or "none">
```

Revenue to whole units (no currency symbol: the currency is not stated), shares and changes
to whole percent, eCPM to 2 decimals.
