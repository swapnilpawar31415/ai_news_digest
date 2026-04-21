#!/usr/bin/env python3
import argparse
import logging
import os
import re
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

from fetcher import fetch_all, FEEDS
from ranker import score_and_summarize
from emailer import build_html, send_digest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_STOPWORDS = {'a','an','the','in','on','at','to','for','of','and','or','is','are','was','with','by','from','its','as'}

def _title_tokens(title: str) -> set:
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}

def _dedup_titles(articles: list[dict], threshold: float = 0.6) -> list[dict]:
    kept, seen_tokens = [], []
    for art in articles:
        tokens = _title_tokens(art["title"])
        if not any(tokens and t and len(tokens & t) / len(tokens | t) >= threshold for t in seen_tokens):
            kept.append(art)
            seen_tokens.append(tokens)
    if len(kept) < len(articles):
        log.info("Deduped %d near-duplicate titles", len(articles) - len(kept))
    return kept


def main(dry_run: bool = False, lookback_hours: int = 24) -> None:
    min_score = int(os.getenv("MIN_RELEVANCE_SCORE", "7"))
    max_per_section = int(os.getenv("MAX_ARTICLES_PER_SECTION", "5"))

    log.info("Fetching articles (lookback=%dh)...", lookback_hours)
    raw_articles = fetch_all(lookback_hours=lookback_hours)

    if not raw_articles:
        log.warning("No articles fetched — check feed URLs or lookback window.")
        return

    raw_articles = _dedup_titles(raw_articles)
    log.info("Scoring and summarizing %d articles with Claude...", len(raw_articles))
    ranked = score_and_summarize(raw_articles)

    # Filter by score, then cap at max_per_section per section (highest scores kept)
    filtered = [a for a in ranked if a["score"] >= min_score]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    section_counts: dict = defaultdict(int)
    capped = []
    for art in filtered:
        sec = art.get("section", "startups")
        if section_counts[sec] < max_per_section:
            capped.append(art)
            section_counts[sec] += 1
    filtered = capped

    log.info(
        "%d articles kept (score >= %d, max %d/section): %s",
        len(filtered), min_score, max_per_section,
        dict(section_counts),
    )

    if not filtered:
        log.warning("No articles passed the relevance threshold — nothing to send.")
        return

    source_count = len({a["source"] for a in filtered})

    if dry_run:
        html = build_html(filtered, total_fetched=len(raw_articles), source_count=source_count)
        sys.stdout.write(html)
        log.info("Dry run complete — HTML written to stdout.")
    else:
        send_digest(filtered, total_fetched=len(raw_articles), source_count=source_count)
        log.info("Digest sent to %s", os.environ.get("SMTP_TO", "?"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send daily enterprise AI digest email")
    parser.add_argument("--dry-run", action="store_true", help="Print HTML to stdout instead of sending")
    parser.add_argument("--lookback", type=int, default=24, help="Hours of articles to fetch (default: 24)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, lookback_hours=args.lookback)
