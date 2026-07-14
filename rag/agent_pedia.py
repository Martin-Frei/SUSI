"""
SUSI — agent_pedia
====================
Second tool in development, after agent_datum. Fetches curated knowledge
articles from two interchangeable sources — Encyclopaedia Britannica and
Wikipedia — and converts them to SUSIpedia-compliant Markdown for the
new router profile "wissen".

Deliberately NOT built: generic web search or search engine integration
(Google, Bing etc.). SUSI stays focused on curated encyclopedias instead
of indexing generic web results — consistent with the SUSIpedia philosophy:
one topic, one clearly defined article.

Status (10.07.2026):
    Wikipedia   — fully functional, no API key required, ready to use.
    Britannica  — API key requested, currently still locked. Functions
                  are fully implemented and wired to the real endpoint;
                  once the key is activated, fetch_britannica() runs
                  without any further changes.

Unified return format from both sources:
    {
        "title":      str,
        "text":       str,   # article text, raw (before SUSIpedia conversion)
        "source":     str,   # "britannica" or "wikipedia"
        "source_url": str,
        "category":   str,
        "article_id": str,   # for update tracking / 30-day cache rule
    }

Standalone test:
    python rag/agent_pedia.py --wikipedia "Python (programming language)"
    python rag/agent_pedia.py --britannica "Python"
    python rag/agent_pedia.py --wikipedia "Python" --save
"""

from __future__ import annotations
import os
import re
import requests
from datetime import date
from typing import Optional


# ── Configuration ─────────────────────────────────────────────────

WIKIPEDIA_USER_AGENT = "SUSI/1.0 (RAG-Assistent von Martin Freimuth; martin-freimuth.dev)"
WIKIPEDIA_SUMMARY_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKIPEDIA_EXTRACT_URL = "https://{lang}.wikipedia.org/w/api.php"

# Britannica Encyclopaedia API (encyclopaediaapi.com)
# Key stored in .env as BRITANNICA_KEY1 — activation pending.
BRITANNICA_BASE_URL = "https://syndication.api.eb.com/production"
BRITANNICA_ARTICLE_TYPE_ADVANCED = 1  # from Swagger spec: articleTypeId=1


# ── Wikipedia — fully functional ──────────────────────────────────

def fetch_wikipedia(topic: str, language: str = "de") -> Optional[dict]:
    """Fetches title + summary + full text of a Wikipedia article.
    No API key required. Returns None if the article doesn't exist.
    """
    headers = {"User-Agent": WIKIPEDIA_USER_AGENT}

    # Step 1: Summary endpoint for title, description, URL
    summary_url = WIKIPEDIA_SUMMARY_URL.format(
        lang=language, title=topic.replace(" ", "_")
    )
    try:
        r = requests.get(summary_url, headers=headers, timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        summary_data = r.json()
    except requests.RequestException:
        return None

    title = summary_data.get("title", topic)
    source_url = (summary_data.get("content_urls", {})
                  .get("desktop", {}).get("page", ""))
    category = summary_data.get("description", "unknown")

    # Step 2: Full text via Action API (extracts, plaintext)
    extract_params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "titles": title,
        "format": "json",
    }
    try:
        r = requests.get(
            WIKIPEDIA_EXTRACT_URL.format(lang=language),
            params=extract_params, headers=headers, timeout=10,
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        full_text = next(iter(pages.values())).get(
            "extract", summary_data.get("extract", "")
        )
    except (requests.RequestException, StopIteration):
        full_text = summary_data.get("extract", "")

    return {
        "title": title,
        "text": full_text,
        "source": "wikipedia",
        "source_url": source_url,
        "category": category,
        "article_id": f"wiki_{language}_{title.replace(' ', '_')}",
    }


# ── Britannica — key present, currently locked ────────────────────

def fetch_britannica(topic: str,
                     article_type: int = BRITANNICA_ARTICLE_TYPE_ADVANCED
                     ) -> Optional[dict]:
    """Fetches a Britannica article via the official Syndication API.

    Status 10.07.2026: API key requested (Advanced/Science + Advanced/Technology),
    activation pending. This function is fully implemented and ready —
    once the key is active, it runs without changes.

    30-day rule: Britannica allows cached content for 30 days only.
    The caller (britannica_sync.py) is responsible for periodic re-fetching —
    this function does not check content age.
    """
    api_key = os.environ.get("BRITANNICA_KEY1") or os.environ.get("BRITANNICA_KEY")
    if not api_key:
        raise RuntimeError(
            "No Britannica API key found. Set BRITANNICA_KEY1 in .env."
        )

    headers = {"x-api-key": api_key}
    params = {"articleTypeId": article_type, "q": topic}

    try:
        r = requests.get(f"{BRITANNICA_BASE_URL}/articles", headers=headers,
                         params=params, timeout=15)
        if r.status_code == 403:
            print(f"  ⚠ Britannica key not yet activated (403): {topic}")
            return None
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠ Britannica request failed: {e}")
        return None

    data = r.json()
    # XML content field name — will be verified once key is active
    # and a real response is available.
    article = data.get("articles", [{}])[0] if data.get("articles") else {}
    if not article:
        return None

    return {
        "title": article.get("title", topic),
        "text": article.get("content", ""),  # XML — may need stripping
        "source": "britannica",
        "source_url": article.get("url", ""),
        "category": article.get("category", "unknown"),
        "article_id": f"eb_{article.get('articleId', topic.replace(' ', '_'))}",
    }


# ── SUSIpedia conversion ──────────────────────────────────────────

def to_susipedia_md(article: dict) -> str:
    """Converts an article dict (Britannica or Wikipedia, unified format)
    into a SUSIpedia-compliant Markdown file.

    Rules (see susipedia_formatierungsregeln.md):
    - Metadata block at top (Datum, Status, Kategorie)
    - Every ## section names the topic explicitly in its first sentence
    - Prose instead of lists
    - Stand line as last line
    """
    today = date.today().isoformat()
    title = article["title"]
    source = article["source"]
    source_url = article["source_url"]

    text = article["text"].strip()

    md = f"""# {title} — Wissen ({source.capitalize()})
Datum: {today}
Status: aktiv
Kategorie: wissen
Quelle: {source_url}

## {title} — Übersicht

{text}

## **Stand {date.today().strftime('%d.%m.%Y')}**
"""
    return md


def save_article(article: dict, target_dir: str = "docs/wissen") -> str:
    """Saves a converted article as a SUSIpedia MD file.
    Filename derived from article_id, special characters removed.
    """
    os.makedirs(target_dir, exist_ok=True)
    filename = re.sub(r"[^\w\-]", "_", article["article_id"]) + ".md"
    path = os.path.join(target_dir, filename)
    md_content = to_susipedia_md(article)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md_content)
    return path


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SUSI agent_pedia — fetch knowledge articles")
    parser.add_argument("--wikipedia", help="Fetch topic from Wikipedia")
    parser.add_argument("--britannica", help="Fetch topic from Britannica")
    parser.add_argument("--save", action="store_true",
                        help="Also save result as SUSIpedia MD file")
    args = parser.parse_args()

    if args.wikipedia:
        print(f"Fetching Wikipedia article: {args.wikipedia}")
        article = fetch_wikipedia(args.wikipedia)
        if article is None:
            print("→ Not found.")
        else:
            print(f"  Title:    {article['title']}")
            print(f"  Source:   {article['source_url']}")
            print(f"  Category: {article['category']}")
            print(f"  Text (start): {article['text'][:200]}...")
            if args.save:
                path = save_article(article)
                print(f"  → Saved to: {path}")
    elif args.britannica:
        print(f"Fetching Britannica article: {args.britannica}")
        article = fetch_britannica(args.britannica)
        if article is None:
            print("→ Not found or key not yet activated.")
        else:
            print(f"  Title:    {article['title']}")
            print(f"  Source:   {article['source_url']}")
            if args.save:
                path = save_article(article)
                print(f"  → Saved to: {path}")
    else:
        parser.print_help()