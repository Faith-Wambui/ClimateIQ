# scrapers/news_scraper.py
"""
Fetches articles from RSS feeds using feedparser.
Falls back to newspaper3k for full-text extraction.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

import feedparser
import requests
from newspaper import Article
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Represents a single news article."""
    title: str
    url: str
    source: str
    published: Optional[datetime] = None
    text: str = ""
    summary: str = ""          # filled by GPT later
    category: str = "other"    # filled by GPT later
    category_hint: Optional[str] = None
    sentiment: str = "neutral"   # positive / negative / neutral
    sentiment_score: float = 0.0    # -1.0 to +1.0
    tags: list = field(default_factory=list)

    def is_recent(self, hours: int = 24) -> bool:
        """True if the article was published within the last N hours."""
        if not self.published:
            return True   # include if no date available
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        pub = self.published
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        return pub >= cutoff


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}


def _parse_date(entry) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _fetch_full_text(url: str, timeout: int = 15) -> str:
    """
    Try newspaper3k first; fall back to BeautifulSoup paragraph extraction.
    Returns empty string on failure.
    """
    # ── Attempt 1: newspaper3k ───────────────────────────────────────────────
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = article.text.strip()
        if len(text) > 200:
            return text
    except Exception as e:
        log.debug(f"newspaper3k failed for {url}: {e}")

    # ── Attempt 2: BeautifulSoup ─────────────────────────────────────────────
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove boilerplate
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text()) > 40)
        return text[:5000]   # cap at 5 000 chars to avoid huge tokens
    except Exception as e:
        log.debug(f"BeautifulSoup failed for {url}: {e}")

    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Main scraper
# ──────────────────────────────────────────────────────────────────────────────

def scrape_feed(feed_config: dict, max_articles: int = 10, hours: int = 24) -> list[NewsArticle]:
    """
    Fetch and parse a single RSS feed.
    Returns a list of NewsArticle objects published within `hours`.
    """
    name = feed_config["name"]
    url = feed_config["url"]
    hint = feed_config.get("category_hint")

    log.info(f"📡  Fetching feed: {name}")
    articles: list[NewsArticle] = []

    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            log.warning(f"  ⚠  Feed parse error for {name}: {feed.bozo_exception}")
            return []

        for entry in feed.entries[:max_articles]:
            article = NewsArticle(
                title=entry.get("title", "Untitled").strip(),
                url=entry.get("link", ""),
                source=name,
                published=_parse_date(entry),
                category_hint=hint,
            )

            if not article.url:
                continue

            if not article.is_recent(hours):
                log.debug(f"  ⏭  Skipping old article: {article.title[:60]}")
                continue

            # Prefer RSS summary over full-text fetch when available
            summary_html = entry.get("summary", "") or entry.get("description", "")
            if summary_html:
                article.text = BeautifulSoup(summary_html, "lxml").get_text(strip=True)

            # Fetch full text if summary is too short
            if len(article.text) < 300 and article.url:
                log.debug(f"  🔍  Fetching full text for: {article.title[:60]}")
                article.text = _fetch_full_text(article.url) or article.text
                time.sleep(0.5)   # gentle rate-limit

            articles.append(article)
            log.info(f"  ✅  {article.title[:70]}")

    except Exception as e:
        log.error(f"  ❌  Failed to scrape {name}: {e}")

    return articles


def scrape_all_feeds(
    sources: list[dict],
    max_per_feed: int = 10,
    hours: int = 24,
    delay: float = 1.0,
) -> list[NewsArticle]:
    """
    Scrape every source in the list.
    Returns deduplicated articles sorted newest-first.
    """
    all_articles: list[NewsArticle] = []
    seen_urls: set[str] = set()

    for source in sources:
        batch = scrape_feed(source, max_articles=max_per_feed, hours=hours)
        for a in batch:
            if a.url not in seen_urls:
                seen_urls.add(a.url)
                all_articles.append(a)
        time.sleep(delay)

    # Sort newest first (articles without dates go last)
    all_articles.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    log.info(f"\n✨  Total unique articles collected: {len(all_articles)}")
    return all_articles