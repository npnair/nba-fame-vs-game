-- The chart's player pool, with each player's Wikidata match
select
    p.bref_id,
    nullif(r.wikidata_id, '')                    as wikidata_id,
    nullif(r.wikipedia_title, '')                as wikipedia_title,
    nullif(r.instagram_handle, '')               as instagram_handle,
    nullif(r.tiktok_handle, '')                  as tiktok_handle,
    coalesce(cast({{ num('r.media_credits') }} as integer), 0) as media_credits
from {{ source('raw', 'pool') }} p
left join {{ source('raw', 'registry') }} r using (bref_id)
