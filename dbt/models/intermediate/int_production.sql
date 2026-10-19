-- How well each player plays, as a 0-100 percentile within the pool.
-- Each season: half VORP (total value, rewards minutes) and half BPM (value per possession).
-- 2025-26 carries the score early on; 2026-27 takes over as minutes pile up.

with qualified as (
    select *
    from {{ ref('stg_season_stats') }}
    where (season = {{ var('prev_season') }} and minutes >= {{ var('prev_min_minutes') }})
       or (season = {{ var('cur_season') }}  and minutes >= {{ var('cur_min_minutes') }})
),

season_scores as (
    select
        *,
        100 * (0.5 * percent_rank() over (partition by season order by vorp)
             + 0.5 * percent_rank() over (partition by season order by bpm)) as season_score
    from qualified
),

latest_info as (   -- name and team from the most recent season the player appears in
    select bref_id, player_name, team, position, age
    from {{ ref('stg_season_stats') }}
    qualify row_number() over (partition by bref_id order by season desc) = 1
),

pivoted as (
    select
        p.bref_id,
        prev.season_score                       as prev_score,
        cur.season_score                        as cur_score,
        coalesce(cur_all.minutes, 0)            as cur_minutes,
        prev.minutes                            as prev_minutes,
        coalesce(cur_all.bpm, prev.bpm)         as bpm,
        coalesce(cur_all.vorp, prev.vorp)       as vorp,
        coalesce(cur_all.games, prev.games)     as games
    from {{ ref('stg_players') }} p
    left join season_scores prev
        on prev.bref_id = p.bref_id and prev.season = {{ var('prev_season') }}
    left join season_scores cur
        on cur.bref_id = p.bref_id and cur.season = {{ var('cur_season') }}
    left join {{ ref('stg_season_stats') }} cur_all
        on cur_all.bref_id = p.bref_id and cur_all.season = {{ var('cur_season') }}
),

blended as (
    select
        *,
        case
            when cur_score is null then 0.0
            when prev_score is null then 1.0
            else cur_minutes / (cur_minutes + {{ var('blend_half_minutes') }})
        end as cur_weight
    from pivoted
)

select
    b.bref_id,
    i.player_name,
    i.team,
    i.position,
    i.age,
    b.games,
    b.bpm,
    b.vorp,
    b.cur_minutes,
    b.prev_minutes,
    round(b.cur_weight, 3)                                                       as cur_season_weight,
    b.cur_weight * coalesce(b.cur_score, 0) + (1 - b.cur_weight) * coalesce(b.prev_score, 0) as production_raw
from blended b
join latest_info i using (bref_id)
where b.prev_score is not null or b.cur_score is not null
