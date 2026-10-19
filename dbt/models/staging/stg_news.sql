select
    bref_id,
    try_cast(as_of as date)                     as as_of,
    cast({{ num('articles_30d') }} as bigint)   as articles_30d
from {{ source('raw', 'news_counts') }}
where try_cast(as_of as date) is not null
