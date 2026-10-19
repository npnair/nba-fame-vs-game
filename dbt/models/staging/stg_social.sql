-- Hand-entered follower counts; accepts "12,345,678", "12.3M" or "850K"
select
    bref_id,
    {{ parse_count('instagram_followers') }}    as instagram_followers,
    {{ parse_count('tiktok_followers') }}       as tiktok_followers,
    try_cast(as_of as date)                     as as_of
from {{ source('manual', 'social_followers') }}
where nullif(trim(bref_id), '') is not null
