{# Parse a hand-typed follower count: "12,345,678", "12.3M", "850K" or "1.2B" -> 12300000 #}
{% macro parse_count(col) %}
case
    when nullif(trim({{ col }}), '') is null then null
    else round(
        try_cast(regexp_replace(upper(trim({{ col }})), '[^0-9.]', '', 'g') as double)
        * case
            when upper(trim({{ col }})) like '%B' then 1e9
            when upper(trim({{ col }})) like '%M' then 1e6
            when upper(trim({{ col }})) like '%K' then 1e3
            else 1
          end
    )
end
{% endmacro %}


{# Percentile rank (0-100) among the rows where the value is present; null stays null #}
{% macro pct_rank(col) %}
case when {{ col }} is null then null
     else 100 * percent_rank() over (partition by ({{ col }} is null) order by {{ col }})
end
{% endmacro %}


{% macro num(col) %}try_cast({{ col }} as double){% endmacro %}
