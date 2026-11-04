{% macro poisson_upper_tail(observed, expected) -%}
{#-
    P(X >= observed) for X ~ Poisson(expected): how likely it is to see at least this
    many events by chance alone. Summed in log space (lgamma) so large counts do not
    overflow. For a sum of independent yes/no events with different probabilities this
    is a conservative approximation (the Poisson spread is a bit wider).
-#}
case
    when {{ observed }} <= 0 then 1.0
    when {{ expected }} <= 0 then 0.0
    else greatest(
        0.0,
        1.0 - list_sum(list_transform(
            range(cast({{ observed }} as bigint)),
            lambda i: exp(-({{ expected }}) + i * ln({{ expected }}) - lgamma(i + 1))
        ))
    )
end
{%- endmacro %}
