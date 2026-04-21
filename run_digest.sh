# /home/ubuntu/ai_news_digest/run_digest.sh
#!/bin/bash
set -e
cd /home/ubuntu/ai_news_digest
source .venv/bin/activate
python digest.py >> /var/log/ai_digest.log 2>&1
