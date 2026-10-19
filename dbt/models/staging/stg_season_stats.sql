-- One row per player per season (2025-26 and 2026-27)
with unioned as (
    select *, {{ var('prev_season') }} as season from {{ source('raw', 'bref_advanced_2026') }}
    union all by name
    select *, {{ var('cur_season') }} as season from {{ source('raw', 'bref_advanced_2027') }}
)

select
    bref_id,
    trim(player)                        as player_name,
    nullif(trim(team), '')              as team,
    nullif(trim(pos), '')               as position,
    season,
    {{ num('age') }}                    as age,
    cast({{ num('g') }} as integer)     as games,
    {{ num('mp') }}                     as minutes,
    {{ num('bpm') }}                    as bpm,
    {{ num('vorp') }}                   as vorp,
    {{ num('ws') }}                     as win_shares,
    {{ num('ts_pct') }}                 as true_shooting,
    {{ num('usg_pct') }}                as usage_rate
from unioned
where nullif(trim(bref_id), '') is not null
