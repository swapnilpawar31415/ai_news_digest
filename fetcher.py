import re
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Sources that publish hundreds of items daily need a tighter cap
PER_SOURCE_CAP = 15
SOURCE_CAPS = {
    "arXiv cs.AI": 5,
    "arXiv cs.LG": 5,
    "NDTV Gadgets360": 10,
    "Economic Times Tech": 15,
    "Finextra": 15,
}

FEEDS = {
    # Enterprise AI — news sites
    "VentureBeat AI":       "https://venturebeat.com/category/ai/feed/",
    "TechCrunch AI":        "https://techcrunch.com/category/artificial-intelligence/feed/",
    "MIT Tech Review":      "https://www.technologyreview.com/feed/",
    "The Verge AI":         "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica":         "https://feeds.arstechnica.com/arstechnica/index",
    "OpenAI Blog":          "https://openai.com/blog/rss.xml",
    # Enterprise AI — newsletters (Substack)
    "Import AI":            "https://importai.substack.com/feed",
    # Financial Services / Global Banking AI
    "PYMNTS":               "https://www.pymnts.com/feed/",
    "Finextra":             "https://www.finextra.com/rss/channel.aspx?channel=news",
    # India Tech + Indian Companies Deploying AI
    "Economic Times Tech":  "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms",
    "Inc42":                "https://inc42.com/feed/",
    "YourStory":            "https://yourstory.com/feed",
    "NDTV Gadgets360":      "https://feeds.feedburner.com/gadgets360-latest",
    "Livemint Tech":        "https://www.livemint.com/rss/technology",
    # AI Research
    "arXiv cs.AI":          "http://arxiv.org/rss/cs.AI",
    "arXiv cs.LG":          "http://arxiv.org/rss/cs.LG",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _parse_feed(source: str, url: str, lookback_hours: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            log.warning("Feed parse error for %s: %s", source, feed.bozo_exception)
            return []
    except Exception as e:
        log.warning("Failed to fetch %s: %s", source, e)
        return []

    articles = []
    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import calendar
            ts = calendar.timegm(entry.published_parsed)
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            published = datetime.now(timezone.utc)

        if published < cutoff:
            continue

        snippet = ""
        if hasattr(entry, "summary"):
            snippet = _strip_html(entry.summary)[:500]
        elif hasattr(entry, "content") and entry.content:
            snippet = _strip_html(entry.content[0].get("value", ""))[:500]

        url_val = entry.get("link", "")
        if not url_val:
            continue

        articles.append({
            "title": _strip_html(entry.get("title", "(no title)")),
            "url": url_val,
            "source": source,
            "published": published.strftime("%d %b %Y"),
            "snippet": snippet,
        })

        cap = SOURCE_CAPS.get(source, PER_SOURCE_CAP)
        if len(articles) >= cap:
            break

    return articles


def fetch_all(lookback_hours: int = 24) -> list[dict]:
    all_articles = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_parse_feed, source, url, lookback_hours): source
            for source, url in FEEDS.items()
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                results = future.result()
                for art in results:
                    if art["url"] not in seen_urls:
                        seen_urls.add(art["url"])
                        all_articles.append(art)
                log.info("%-22s  %d articles", source, len(results))
            except Exception as e:
                log.warning("Error processing %s: %s", source, e)

    log.info("Total unique articles fetched: %d", len(all_articles))
    return all_articles


if __name__ == "__main__":
    articles = fetch_all()
    for a in articles[:5]:
        print(f"[{a['source']}] {a['title']}")
        print(f"  {a['url']}")
        print(f"  {a['snippet'][:100]}...")
        print()
