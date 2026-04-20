# Enterprise AI Daily Digest

Fetches RSS feeds from 22 sources, scores and summarizes articles with Claude, and emails a ranked HTML digest daily.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, SMTP_USER, SMTP_APP_PASSWORD, SMTP_TO
```

## Test locally

```bash
# Check feeds are reachable
python fetcher.py

# Check Claude scoring (uses 5 hardcoded test articles)
python ranker.py

# Full dry run — outputs HTML to stdout
python digest.py --dry-run > preview.html
open preview.html   # view in browser

# Send a real email
python digest.py
```

## EC2 cron (7 AM IST = 1:30 AM UTC)

```cron
30 1 * * * cd /home/ec2-user/ai_news_digest && /home/ec2-user/.venv/bin/python digest.py >> /var/log/ai_digest.log 2>&1
```

Add with `crontab -e`.

## CLI flags

| Flag | Default | Description |
|---|---|---|
| `--dry-run` | off | Print HTML to stdout, skip email |
| `--lookback N` | 24 | Fetch articles from last N hours |
