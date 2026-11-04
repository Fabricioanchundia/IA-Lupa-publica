{% macro signal_level(enough_data, significant, ratio) -%}
{#-
    Review level of one indicator for one buyer: the excess must be beyond chance
    (significant) AND large enough to matter (observed / expected ratio).
-#}
case
    when not coalesce({{ enough_data }}, false) then 'insufficient_data'
    when {{ significant }} and {{ ratio }} >= {{ var('priority_high_ratio') }} then 'high'
    when {{ significant }} and {{ ratio }} >= {{ var('priority_medium_ratio') }} then 'medium'
    when {{ significant }} then 'low'
    else 'none'
end
{%- endmacro %}
