-- Each fame signal per player, plus its percentile within the pool (null when the signal is missing)

with window_end as (
    select max(view_date) as last_day from {{ ref('stg_pageviews') }}
),

pageviews as (
    select v.bref_id, sum(v.views) as pageviews_30d
    from {{ ref('stg_pageviews') }} v, window_end w
    where v.view_date > w.last_day - interval 30 day
    group by 1
),

news_window as (
    select max(news_date) as last_day from {{ ref('stg_news') }}
),

news as (   -- daily counts summed over the last 30 days; a missed day simply adds nothing
    select
        n.bref_id,
        sum(n.articles)         as articles_30d,
        count(*)                as news_days,
        max(n.news_date)        as news_as_of
    from {{ ref('stg_news') }} n, news_window w
    where n.news_date > w.last_day - interval 30 day
    group by 1
),

signals as (
    select
        p.bref_id,
        p.wikipedia_title,
        p.instagram_handle,
        p.tiktok_handle,
        pv.pageviews_30d,
        n.articles_30d                      as news_articles_30d,
        n.news_as_of,
        s.instagram_followers,
        s.tiktok_followers,
        s.as_of                             as social_as_of,
        p.media_credits
    from {{ ref('stg_players') }} p
    left join pageviews pv using (bref_id)
    left join news n using (bref_id)
    left join {{ ref('stg_social') }} s using (bref_id)
)

select
    *,
    {{ pct_rank('pageviews_30d') }}          as pageviews_pct,
    {{ pct_rank('news_articles_30d') }}      as news_pct,
    {{ pct_rank('instagram_followers') }}    as instagram_pct,
    {{ pct_rank('tiktok_followers') }}       as tiktok_pct,
    {{ pct_rank('media_credits') }}          as media_pct
from signals
