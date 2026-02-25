# processors/gpt_processor.py
"""
Uses Google Gemini (gemini-2.5-flash) to:
  1. Categorize each article into one of the predefined themes.
  2. Generate a concise 2-3 sentence summary.
  3. Produce the overall digest headline & intro paragraph.

FREE tier: 15 requests/min, 1500 requests/day — more than enough.
Get your key at: https://aistudio.google.com
"""

import os
import json
import logging
import time
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(override=False)

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Client setup
# ──────────────────────────────────────────────────────────────────────────────

# Load API key with fallback error message
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found — check your .env file exists and contains GEMINI_API_KEY=your-key-here")

client = genai.Client(api_key=api_key)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", 200))


# ──────────────────────────────────────────────────────────────────────────────
# Helper — call Gemini and return raw text
# ──────────────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, temperature: float = 0.3, max_tokens: int = 300) -> str:
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 15 * (attempt + 1)
                log.warning(f"Rate limited — waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise
    return ""

def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences that Gemini sometimes wraps around JSON."""
    return text.replace("```json", "").replace("```", "").strip()

# ──────────────────────────────────────────────────────────────────────────────
# Category classification
# ──────────────────────────────────────────────────────────────────────────────

CLASSIFY_PROMPT_TEMPLATE = """\
You are an expert climate-news analyst.
Classify this article into EXACTLY ONE of these categories:

- policy      : Government policy, legislation, international agreements, regulations, COP summits
- technology  : Renewable energy, EVs, battery storage, carbon capture, green hydrogen, cleantech
- finance     : ESG investing, carbon markets, green bonds, climate risk, sustainable finance
- disasters   : Floods, wildfires, droughts, hurricanes, heatwaves, sea level rise, extreme weather
- science     : Climate research, IPCC reports, emissions data, ocean temperatures, scientific studies
- other       : Climate-related news that doesn't fit the above

Respond with ONLY a JSON object. No explanation, no markdown, just the JSON.
Example: {{"category": "policy"}}

Title: {title}
Excerpt: {snippet}{hint_note}
"""


def classify_article(title: str, text: str, hint: Optional[str] = None) -> str:
    """
    Returns the category string for an article.
    Falls back to `hint` (from source config) or "other" on failure.
    """
    snippet = text[:800] if text else ""
    hint_note = f"\n\nNote: The source suggests this might be '{hint}'." if hint else ""

    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        title=title,
        snippet=snippet,
        hint_note=hint_note,
    )

    try:
        raw = _call_gemini(prompt, temperature=0, max_tokens=30)
        raw = _strip_json_fences(raw)
        data = json.loads(raw)
        category = data.get("category", "other").lower()

        valid = {"policy", "technology", "finance", "disasters", "science", "other"}
        return category if category in valid else (hint or "other")

    except json.JSONDecodeError:
        # Gemini occasionally replies with plain text — try to extract the category
        for cat in ["policy", "technology", "finance", "disasters", "science"]:
            if cat in raw.lower():
                return cat
        log.warning(f"Classification JSON parse failed for '{title[:50]}', raw: {raw[:80]}")
        return hint or "other"

    except Exception as e:
        log.warning(f"Classification failed for '{title[:50]}': {e}")
        return hint or "other"


# ──────────────────────────────────────────────────────────────────────────────
# Article summarization
# ──────────────────────────────────────────────────────────────────────────────

SUMMARIZE_PROMPT_TEMPLATE = """\
You are a climate journalist writing for a busy executive audience.
Summarize the article below in 2-3 punchy sentences that capture:
1. What happened
2. Why it matters for the climate

Rules:
- Be specific — include numbers, names, or locations where relevant
- Do NOT start with "This article..." or "The article discusses..."
- Write in plain, confident prose
- No bullet points, just flowing sentences

Title: {title}

Article text:
{snippet}
"""


def summarize_article(title: str, text: str) -> str:
    """
    Returns a 2-3 sentence Gemini summary of the article.
    Falls back to a truncated version of the raw text on failure.
    """
    snippet = text[:3000] if text else ""
    if not snippet:
        return "No content available for this article."

    prompt = SUMMARIZE_PROMPT_TEMPLATE.format(title=title, snippet=snippet)

    try:
        return _call_gemini(prompt, temperature=0.4, max_tokens=SUMMARY_MAX_TOKENS)

    except Exception as e:
        log.warning(f"Summarization failed for '{title[:50]}': {e}")
        return text[:250].strip() + "…" if text else "Summary unavailable."

# ─────────────────────────────────────────────────────
# Sentiment scoring
# ─────────────────────────────────────────────────────

SENTIMENT_PROMPT = """\
Score this climate news article for its sentiment toward climate action.

Respond ONLY with JSON — no markdown, no extra text:
{{"sentiment": "positive", "score": 0.8, "reason": "one sentence"}}

Rules:
- sentiment: "positive" (good news for climate), "negative" (bad news),
  or "neutral" (factual/mixed)
- score: float from -1.0 (very negative) to +1.0 (very positive)
- reason: one short sentence explaining the score

Title: {title}
Summary: {summary}
"""


def score_sentiment(title: str, summary: str) -> tuple[str, float]:
    """Returns (sentiment_label, score) for an article."""
    prompt = SENTIMENT_PROMPT.format(title=title, summary=summary)
    try:
        raw = _call_gemini(prompt, temperature=0, max_tokens=80)
        raw = _strip_json_fences(raw)
        data = json.loads(raw)
        sentiment = data.get("sentiment", "neutral")
        score = float(data.get("score", 0.0))
        score = max(-1.0, min(1.0, score))  # clamp to [-1, 1]
        return sentiment, score
    except Exception as e:
        log.warning(f"Sentiment scoring failed: {e}")
        return "neutral", 0.0
    

# ──────────────────────────────────────────────────────────────────────────────
# Digest intro generator
# ──────────────────────────────────────────────────────────────────────────────

DIGEST_PROMPT_TEMPLATE = """\
You are the editor of a prestigious climate news digest.
Given today's top climate stories grouped by category, write:
1. A one-sentence punchy headline for the day (start with an emoji)
2. A 3-4 sentence editorial intro highlighting the most important themes

Respond ONLY with a JSON object — no markdown, no extra text:
{{
  "headline": "...",
  "intro": "..."
}}

Today's stories:
{stories_text}
"""


def generate_digest_intro(category_summaries: dict[str, list[str]]) -> dict:
    """
    Given {{category: [summary1, summary2, ...]}} returns {{"headline": ..., "intro": ...}}.
    """
    stories_text = ""
    for cat, summaries in category_summaries.items():
        stories_text += f"\n\n[{cat.upper()}]\n" + "\n".join(f"• {s}" for s in summaries[:3])

    prompt = DIGEST_PROMPT_TEMPLATE.format(stories_text=stories_text)

    try:
        raw = _call_gemini(prompt, temperature=0.7, max_tokens=350)
        raw = _strip_json_fences(raw)
        return json.loads(raw)

    except Exception as e:
        log.warning(f"Digest intro generation failed: {e}")
        return {
            "headline": "🌍 Today's Climate News Digest",
            "intro": "Here is your curated selection of today's most important climate stories.",
        }


# ──────────────────────────────────────────────────────────────────────────────
# Batch processor
# ──────────────────────────────────────────────────────────────────────────────

def process_articles(articles: list, delay: float = 1.0) -> list:
    """
    Runs classification + summarization on every article in-place.
    Returns the same list with `.category` and `.summary` populated.

    Note: delay=1.0s by default to stay within Gemini's free-tier rate limit
    of 15 requests/minute (2 calls per article = 30 req/min max without delay).
    """
    total = len(articles)
    log.info(f"\n🤖  Processing {total} articles with Gemini ({MODEL_NAME})...")

    for i, article in enumerate(articles, 1):
        log.info(f"  [{i}/{total}] {article.title[:65]}")

        # Step 1: Classify
        article.category = classify_article(
            article.title, article.text, article.category_hint
        )
        log.info(f"         → Category: {article.category}")

        # Step 2: Summarize
        article.summary = summarize_article(article.title, article.text)

        # Rate-limit protection — free tier: 15 req/min
        # 2 calls per article + 1s delay ≈ safe margin
       

        # Step 3: Sentiment
        article.sentiment, article.sentiment_score = score_sentiment(
            article.title, article.summary
        )
        log.info(f"         → Sentiment: {article.sentiment} ({article.sentiment_score:+.2f})")
         
        time.sleep(7)
    log.info(f"✅  Done processing {total} articles.")
    return articles