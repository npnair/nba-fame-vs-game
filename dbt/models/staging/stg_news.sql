-- Articles mentioning each player, one row per player per day
select
    bref_id,
    try_cast(date as date)                  as news_date,
    cast({{ num('articles') }} as bigint)   as articles
from {{ source('raw', 'news_daily') }}
where try_cast(date as date) is not null
