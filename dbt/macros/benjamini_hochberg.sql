{% macro benjamini_hochberg(source, p_value, eligible, tiebreak) -%}
{#-
    Adds `q_value` to every row of `source` where `eligible` is true, using the
    Benjamini-Hochberg procedure. With many buyers, some look "unusual" by chance alone;
    flagging only q < 0.05 keeps the expected share of false alarms among the flagged
    buyers at about 5% (false discovery rate).
-#}
select
    ranked.* exclude (bh_rank, bh_tests),
    case
        when {{ eligible }} then least(1.0, min({{ p_value }} * bh_tests / bh_rank) over (
            partition by {{ eligible }}
            order by {{ p_value }} desc, {{ tiebreak }} desc
            rows between unbounded preceding and current row
        ))
    end as q_value
from (
    select
        *,
        row_number() over (
            partition by {{ eligible }} order by {{ p_value }}, {{ tiebreak }}
        ) as bh_rank,
        count(*) over (partition by {{ eligible }}) as bh_tests
    from {{ source }}
) as ranked
{%- endmacro %}
