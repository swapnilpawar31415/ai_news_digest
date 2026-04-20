import json
import logging
import os

import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI news analyst for an enterprise AI professional working in financial services in India.

For each article provided, you will do two things:
1. Score its relevance on a scale of 1–10 using this rubric:
   - 9–10: Enterprise AI in Indian financial services (banking, insurance, capital markets, payments),
           RBI/SEBI AI regulation, Indian bank or insurer deploying AI at scale, DPDP compliance + AI
   - 7–8: Enterprise AI in global financial services, OR an Indian company (any sector) deploying AI
           at meaningful scale, OR a significant AI capability announcement from a major AI lab
   - 5–6: Enterprise AI broadly (global, non-finance), OR AI research paper with clear near-term
           enterprise application (RAG, agents, fine-tuning, evaluation, observability)
   - 3–4: India tech or startup news without strong AI angle, or consumer AI product launch
   - 1–2: Hardware/chip news, gaming AI, celebrity AI, academic-only ML theory, general tech news
           with no enterprise AI relevance

2. Write a 1-paragraph summary (3–4 sentences) focused on the enterprise/finance/India angle.
   For articles scoring 1–3, keep it to 2 sentences.
   The summary should explain what happened, why it matters for enterprise AI in financial services or India,
   and any regulatory or strategic implications.

Return ONLY a valid JSON array. Each element must have exactly these keys:
  "id": integer (the article number as given)
  "score": integer 1–10
  "summary": string

Output nothing else — no preamble, no explanation, no markdown fences.\
"""


def _build_prompt(articles: list[dict]) -> str:
    lines = []
    for i, art in enumerate(articles, 1):
        lines.append(
            f"[{i}] Title: {art['title']}\n"
            f"Source: {art['source']}\n"
            f"Snippet: {art['snippet'] or '(no snippet)'}\n"
        )
    return "\n".join(lines)


def score_and_summarize(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": _build_prompt(articles),
                }
            ],
        )
    except Exception as e:
        log.error("Claude API call failed: %s", e)
        return _fallback(articles)

    raw = response.content[0].text.strip()

    # Strip markdown fences if Claude wraps in them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        rankings = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s\nRaw output (first 1000 chars):\n%s", e, raw[:1000])
        return _fallback(articles)

    # Map id → {score, summary} and attach to original articles
    rank_map = {item["id"]: item for item in rankings}
    enriched = []
    for i, art in enumerate(articles, 1):
        ranking = rank_map.get(i, {})
        enriched.append({
            **art,
            "score": int(ranking.get("score", 5)),
            "summary": ranking.get("summary", "(summary unavailable)"),
        })

    usage = response.usage
    log.info(
        "Claude usage — input: %d, output: %d, cache_read: %d",
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", 0),
    )
    return enriched


def _fallback(articles: list[dict]) -> list[dict]:
    return [{**art, "score": 5, "summary": "(summary unavailable)"} for art in articles]


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    test_articles = [
        {
            "title": "RBI issues draft framework for AI governance in banks",
            "source": "Economic Times",
            "snippet": "The Reserve Bank of India released draft guidelines requiring banks to establish AI governance committees and conduct bias audits before deploying customer-facing AI systems.",
            "url": "https://example.com/1",
            "published": "20 Apr 2026",
        },
        {
            "title": "HDFC Bank deploys AI-powered fraud detection across 50M accounts",
            "source": "Business Standard",
            "snippet": "HDFC Bank announced it has rolled out an AI fraud detection system that reduced false positives by 40% and blocked Rs 120 crore in fraudulent transactions in Q4.",
            "url": "https://example.com/2",
            "published": "20 Apr 2026",
        },
        {
            "title": "OpenAI releases GPT-5 with 10x reasoning improvement",
            "source": "TechCrunch AI",
            "snippet": "OpenAI's latest model shows dramatic improvements on enterprise benchmarks including coding, legal document analysis, and financial report summarisation.",
            "url": "https://example.com/3",
            "published": "20 Apr 2026",
        },
        {
            "title": "New study shows AI can play chess better than Magnus Carlsen",
            "source": "Ars Technica",
            "snippet": "Researchers trained an AI model on 100 million chess games and achieved a 3600 ELO rating, surpassing all known human players.",
            "url": "https://example.com/4",
            "published": "20 Apr 2026",
        },
        {
            "title": "Nvidia announces Blackwell Ultra GPU for AI training",
            "source": "The Verge AI",
            "snippet": "Nvidia's new GPU offers 4x the memory bandwidth of H100 and is aimed at large language model training workloads.",
            "url": "https://example.com/5",
            "published": "20 Apr 2026",
        },
    ]

    results = score_and_summarize(test_articles)
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        print(f"[{r['score']}/10] {r['title']}")
        print(f"  {r['summary']}")
        print()
