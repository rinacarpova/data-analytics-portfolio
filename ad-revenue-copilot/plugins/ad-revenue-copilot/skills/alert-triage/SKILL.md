---
name: alert-triage
description: >
  Triage revenue alerts of the ad-revenue-analytics publisher data (June 2019, queried through
  the ad-revenue-db MCP server): group alerts that describe one event, find when each event
  really started and ended, size it, check what the alert cooldown hides, and give a verdict
  per event. Use for any question about alerts: "is this alert real or noise", "triage the
  alerts", "what do these alerts mean", "which alerts need action", "was day X quiet", "why
  did N alerts fire", "stopped delivering", "large slice moved".
---

# Alert triage

An alert says *a number crossed a threshold on a day*. Triage turns alerts into **events**:
what happened, since when, how big, and whether anyone should act. The usual failure is to
report alerts one by one: twelve alerts can be one buyer paying more, and three can be one
small delivery that stopped days earlier.

Data and definitions: [models](../../references/models.md), [metrics](../../references/metrics.md),
[data traps](../../references/data-traps.md).

## How the alerts work

`mart_revenue_alerts` (tool `get_alerts`) compares each day with the same weekday of the
previous 2–3 weeks, so alerts exist only from **15 June**. Three rules:

- `total revenue`: the day is off its baseline by more than 2× the usual error;
- `stopped delivering`: a slice normally worth ≥ 1% of the day delivers < 10% of its baseline;
- `large slice moved`: a slice moved by ≥ 5% of the day's revenue and by more than 2× its
  dimension's usual error.

After an alert, **the same rule on the same slice stays silent for 7 days**. So the days after
an event can look quiet in the alert feed while the event continues.

## Procedure

1. **Collect.** `get_alerts` for the window asked about, plus the 7 days before it, because
   an earlier alert can explain the silence.

2. **Group alerts into events.** Alerts on the same day are often facets of one delivery: a
   slice that is one advertiser on one ad unit alerts on the advertiser, the unit and the
   channel; a buyer with most of the day's revenue moves the geo, device, OS and channel it
   buys on. For each day with several alerts, measure how much of each alerted slice belongs
   to the largest alerted slices:

   ```sql
   -- <day>, <A>, <B>: the day and the two largest alerted slices (here an advertiser and a site)
   with day as (select * from fct_ad_delivery_daily where report_date = date '<day>')
   select device_category_id,
          sum(revenue) as revenue,
          sum(revenue) filter (where advertiser_id = <A>) / sum(revenue) as share_of_advertiser_a,
          sum(revenue) filter (where site_id = <B>) / sum(revenue)       as share_of_site_b
   from day
   group by 1
   ```

   Repeat with each alerted dimension in place of `device_category_id`.

   A slice that is mostly (≳ 60%) another alerted slice belongs to its event. Name each event
   by its root slice (e.g. "advertiser 79 paying more"), not by the alert list.

3. **Find the real start and end.** Pull the daily series of the root slice over the whole
   month from `int_delivery__by_dimension_daily` (revenue and impressions). The event starts
   when the series breaks from its weekday pattern, which can be **before the alert**: nothing
   can alert before 15 June, and a stop alerts only once its baseline exists. Check whether it
   reverted the next day (a one-day spike) or persisted.

4. **Check what the cooldown hides.** For every event, call `get_revenue_change` for the
   following 1–3 days. If the total or the root slice is still far off its baseline, say the
   event continued even though no alert fired.

5. **Size it.** Revenue effect against the baseline and its share of the day's revenue;
   volume (impressions) vs price (eCPM) from the alert's effects. For a stop, the loss per day.

6. **Verdict per event**, one of:
   - **act**: real and material (≥ 5% of daily revenue, or a stop that is still going);
   - **watch**: real but small or already reverted; worth a note to the owner of the slice;
   - **noise**: within the slice's normal weekday pattern once the series is examined.
   Say what the data cannot tell (e.g. *why* a buyer paid more: revenue-level data has no bids
   or floor prices) and who could find out.

## Output

Start with one line: how many alerts, how many events, how many need action. Then one row
per event, ordered by size:

| Event | Alerts | Real start → end | Size | Volume / price | Verdict |
|---|---|---|---|---|---|

Then a short paragraph per event that needs action or explanation, and a final line on
anything the cooldown hid. Keep numbers to the precision the data supports (revenue to whole
units, shares to 1 decimal %); revenue currency is unknown, so no currency symbols.
