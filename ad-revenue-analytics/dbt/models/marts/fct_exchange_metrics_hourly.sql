-- Hourly ad exchange metrics with the benchmark's anomaly labels attached,
-- ready for fitting and scoring anomaly detectors.

with metrics as (

    select * from {{ ref('stg_nab__exchange_metrics') }}

),

windows as (

    select * from {{ ref('stg_nab__anomaly_windows') }}

)

select
    metrics.exchange,
    metrics.metric,
    metrics.observed_at,
    metrics.metric_value,
    exists (
        select 1
        from windows
        where windows.exchange = metrics.exchange
          and windows.metric = metrics.metric
          and metrics.observed_at between windows.window_start and windows.window_end
    ) as is_labelled_anomaly
from metrics
