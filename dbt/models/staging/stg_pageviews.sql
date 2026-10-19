select
    bref_id,
    try_cast(date as date)                  as view_date,
    cast({{ num('views') }} as bigint)      as views
from {{ source('raw', 'pageviews_daily') }}
where try_cast(date as date) is not null
