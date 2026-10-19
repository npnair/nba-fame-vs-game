-- One row per player: production and fame percentiles, the gap between them, and the verdict.
{% set w = var('fame_weights') %}
{% set signals = [('pageviews', w.pageviews), ('news', w.news), ('instagram', w.instagram),
                  ('tiktok', w.tiktok), ('media', w.media)] %}

with joined as (
    select p.*, f.* exclude (bref_id)
    from {{ ref('int_production') }} p
    join {{ ref('int_fame_signals') }} f using (bref_id)
),

fame as (
    select
        *,
        ( {% for name, weight in signals %}coalesce({{ weight }} * {{ name }}_pct, 0){% if not loop.last %} + {% endif %}{% endfor %} )
        / nullif( {% for name, weight in signals %}(case when {{ name }}_pct is not null then {{ weight }} else 0 end){% if not loop.last %} + {% endif %}{% endfor %}, 0)
            as fame_raw,
        ( {% for name, _ in signals %}(case when {{ name }}_pct is not null then 1 else 0 end){% if not loop.last %} + {% endif %}{% endfor %} )
            as fame_signals_used
    from joined
),

ranked as (   -- re-rank both scores so each axis runs evenly from 0 to 100
    select
        *,
        round(100 * percent_rank() over (order by production_raw), 1)   as production_score,
        round(100 * percent_rank() over (order by fame_raw), 1)         as fame_score
    from fame
    where fame_raw is not null
)

select
    bref_id,
    player_name,
    team,
    position,
    age,
    games,
    bpm,
    vorp,
    cur_minutes,
    cur_season_weight,
    production_score,
    fame_score,
    round(production_score - fame_score, 1)                             as gap,
    case
        when production_score >= 50 and fame_score >= 50 then 'Stars'
        when fame_score >= 50                             then 'Hype'
        when production_score >= 50                       then 'Hidden gems'
        else 'Under the radar'
    end                                                                 as quadrant,
    case
        when production_score - fame_score >=  {{ var('verdict_threshold') }} then 'Underrated'
        when production_score - fame_score <= -{{ var('verdict_threshold') }} then 'Overrated'
        else 'Fairly rated'
    end                                                                 as verdict,
    fame_signals_used,
    wikipedia_title,
    instagram_handle,
    tiktok_handle,
    pageviews_30d,
    news_articles_30d,
    instagram_followers,
    tiktok_followers,
    media_credits,
    round(pageviews_pct, 1)     as pageviews_pct,
    round(news_pct, 1)          as news_pct,
    round(instagram_pct, 1)     as instagram_pct,
    round(tiktok_pct, 1)        as tiktok_pct,
    round(media_pct, 1)         as media_pct,
    news_as_of,
    social_as_of
from ranked
