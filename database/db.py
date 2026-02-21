import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "climate_history.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE NOT NULL,
            title       TEXT,
            source      TEXT,
            category    TEXT,
            sentiment   TEXT,
            sent_score  REAL,
            summary     TEXT,
            published   TEXT,
            scraped_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS digests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT UNIQUE,
            article_count INTEGER,
            top_category  TEXT,
            avg_sentiment REAL,
            html_path   TEXT,
            sent_at     TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_url      ON articles(url);
        CREATE INDEX IF NOT EXISTS idx_category ON articles(category);
        CREATE INDEX IF NOT EXISTS idx_scraped  ON articles(scraped_at);
        """)
    print("✅ Database initialised")


def is_already_processed(url: str) -> bool:
    """True if we've already stored this URL."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE url = ?", (url,)
        ).fetchone()
        return row is not None


def save_article(article) -> bool:
    """Save a NewsArticle to the DB. Returns True if inserted."""
    try:
        pub = article.published.isoformat() if article.published else None
        with get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO articles
                    (url, title, source, category, sentiment,
                     sent_score, summary, published)
                VALUES (?,?,?,?,?,?,?,?)
            """, (article.url, article.title, article.source,
                      article.category, getattr(article, 'sentiment', 'neutral'),
                      getattr(article, 'sentiment_score', 0.0),
                      article.summary, pub))
        return True
    except Exception as e:
        print(f"DB save error: {e}")
        return False


def save_digest_record(date_str, count, top_cat, avg_sent, html_path):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO digests
                (date, article_count, top_category, avg_sentiment, html_path, sent_at)
            VALUES (?,?,?,?,?,?)
        """, (date_str, count, top_cat, avg_sent, html_path,
                  datetime.now(timezone.utc).isoformat()))


def get_weekly_top_articles(limit: int = 3) -> list:
    """Top N articles per category from the last 7 days."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM articles
            WHERE scraped_at >= datetime('now', '-7 days')
            ORDER BY sent_score DESC
            LIMIT ?
        """, (limit * 6,)).fetchall()
    return [dict(r) for r in rows]


def get_category_trends() -> list:
    """Daily article counts per category for the last 14 days."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT date(scraped_at) as day, category, COUNT(*) as count
            FROM articles
            WHERE scraped_at >= datetime('now', '-14 days')
            GROUP BY day, category
            ORDER BY day DESC
        """).fetchall()
    return [dict(r) for r in rows]