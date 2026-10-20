-- Current team for each rostered player (Basketball-Reference team pages, refreshed daily)
select
    bref_id,
    trim(team) as roster_team
from {{ source('raw', 'rosters') }}
where nullif(trim(bref_id), '') is not null
qualify row_number() over (partition by bref_id order by team) = 1
