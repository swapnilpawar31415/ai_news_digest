#!/usr/bin/env python3
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from fetcher import fetch_all, FEEDS
from ranker import score_and_summarize
from emailer import build_html, send_digest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main(dry_run: bool = False, lookback_hours: int = 24) -> None:
    min_score = int(os.getenv("MIN_RELEVANCE_SCORE", "5"))
    max_articles = int(os.getenv("MAX_ARTICLES", "20"))

    log.info("Fetching articles (lookback=%dh)...", lookback_hours)
    raw_articles = fetch_all(lookback_hours=lookback_hours)

    if not raw_articles:
        log.warning("No articles fetched — check feed URLs or lookback window.")
        return

    log.info("Scoring and summarizing %d articles with Claude...", len(raw_articles))
    ranked = score_and_summarize(raw_articles)

    filtered = [a for a in ranked if a["score"] >= min_score]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    filtered = filtered[:max_articles]

    log.info(
        "%d articles kept (score >= %d, cap %d)",
        len(filtered), min_score, max_articles,
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
