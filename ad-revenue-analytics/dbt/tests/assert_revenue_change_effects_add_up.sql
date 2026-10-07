-- Volume, price and unattributed effects must add up to the revenue change of every slice.

select *
from {{ ref('mart_revenue_change_drivers') }}
where abs(volume_effect + price_effect + unattributed_effect - revenue_delta) > 0.000001
