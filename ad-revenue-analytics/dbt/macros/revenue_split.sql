{#
    Midpoint split of a revenue change into volume and rate, used by the revenue change marts.

    revenue = impressions * eCPM / 1000, so
      volume effect = change in impressions * average eCPM of the two periods / 1000
      rate effect   = change in eCPM * average impressions of the two periods / 1000
    add up to the revenue change exactly, with no interaction term.
    A slice with an eCPM on one side only (it appeared or disappeared) uses that eCPM for
    both sides, so its whole change is volume. Revenue with no impressions on either side
    cannot be split and is returned by unattributed_effect.
#}

{% macro volume_effect(impressions, baseline_impressions, ecpm, baseline_ecpm) -%}
    coalesce(
        ({{ impressions }} - {{ baseline_impressions }})
        * (coalesce({{ ecpm }}, {{ baseline_ecpm }}) + coalesce({{ baseline_ecpm }}, {{ ecpm }})) / 2 / 1000,
        0
    )
{%- endmacro %}

{% macro rate_effect(impressions, baseline_impressions, ecpm, baseline_ecpm) -%}
    coalesce(
        (coalesce({{ ecpm }}, {{ baseline_ecpm }}) - coalesce({{ baseline_ecpm }}, {{ ecpm }}))
        * ({{ impressions }} + {{ baseline_impressions }}) / 2 / 1000,
        0
    )
{%- endmacro %}

{% macro unattributed_effect(revenue_delta, ecpm, baseline_ecpm) -%}
    case when {{ ecpm }} is null and {{ baseline_ecpm }} is null then {{ revenue_delta }} else 0 end
{%- endmacro %}
