-- Fails if any score falls outside 0-100 or the pool is suspiciously small
select bref_id, production_score, fame_score
from {{ ref('fct_fame_vs_game') }}
where production_score not between 0 and 100
   or fame_score not between 0 and 100

union all

select 'pool too small', count(*), null
from {{ ref('fct_fame_vs_game') }}
having count(*) < 100
