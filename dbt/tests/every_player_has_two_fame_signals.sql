-- A fame score built from a single signal is too fragile; flag the run if more than 10% of players have that
select count(*) as thin_players
from {{ ref('fct_fame_vs_game') }}
where fame_signals_used < 2
having count(*) > 0.1 * (select count(*) from {{ ref('fct_fame_vs_game') }})
