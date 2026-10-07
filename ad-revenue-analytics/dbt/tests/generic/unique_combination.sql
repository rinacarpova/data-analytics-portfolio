{% test unique_combination(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as row_count
from {{ model }}
group by all
having count(*) > 1

{% endtest %}
