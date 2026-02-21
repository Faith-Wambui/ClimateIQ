"""Builds the Friday weekly digest from SQLite history."""
import os
from datetime import datetime
from collections import defaultdict
from database.db import get_weekly_top_articles
from config.sources import CATEGORIES

TOP_N = 3   # articles per category in weekly digest


def build_weekly_digest() -> tuple[str, str]:
    """Returns (html, plain_text) for the weekly email."""
    articles = get_weekly_top_articles(limit=TOP_N * len(CATEGORIES))

    # Group by category
    grouped = defaultdict(list)
    for a in articles:
        grouped[a['category']].append(a)

    week_str = datetime.now().strftime("Week of %B %d, %Y")
    total = len(articles)

    # Build category blocks
    cat_html = ""
    plain_lines = []
    icon_map = {"policy":"🏛️","technology":"⚡","finance":"💰",
                "disasters":"🌪️","science":"🔬","other":"🌐"}

    for cat, arts in grouped.items():
        icon = icon_map.get(cat, "📰")
        label = CATEGORIES.get(cat, cat.title())
        plain_lines.append(f"\n{'='*50}\n{icon} {label}\n{'='*50}")
        articles_html = ""
        for a in arts[:TOP_N]:
            sent_color = "#27ae60" if a['sentiment']=="positive" else \
                         "#e74c3c" if a['sentiment']=="negative" else "#888"
            articles_html += f"""
            <div style="margin-bottom:20px;padding:16px;background:#faf8f3;
                        border-left:3px solid #2d6a4f;border-radius:2px">
              <div style="font-size:10px;color:#999;letter-spacing:1px;
                          text-transform:uppercase">{a['source']}</div>
              <div style="font-size:16px;font-weight:700;margin:6px 0">
                <a href="{a['url']}" style="color:#1a3a2a">{a['title']}</a></div>
              <div style="font-size:13px;color:#555">{a['summary']}</div>
              <div style="font-size:11px;color:{sent_color};margin-top:8px">
                Sentiment: {a['sentiment']} ({a['sent_score']:+.2f})</div>
            </div>"""
            plain_lines.append(f"▸ {a['title']}\n  {a['url']}\n  {a['summary']}\n")
        cat_html += f"""<div style="margin-bottom:32px">
          <h2 style="font-size:13px;letter-spacing:2px;text-transform:uppercase;
                     color:#2d6a4f;border-bottom:2px solid #2d6a4f;
                     padding-bottom:8px;margin-bottom:16px">{icon} {label}</h2>
          {articles_html}</div>"""

    html = f"""<!DOCTYPE html><html><body style="font-family:Georgia,serif;
        max-width:680px;margin:32px auto;background:#fffcf7">
      <div style="background:#1a3a2a;padding:40px;text-align:center">
        <div style="color:#7aaa88;font-size:11px;letter-spacing:3px">WEEKLY BRIEFING</div>
        <h1 style="color:#f5f2ec;font-size:28px;font-weight:400;margin:10px 0">
          🌍 Climate Week in Review</h1>
        <div style="color:#8aaa96">{week_str} · {total} top stories</div>
      </div>
      <div style="padding:40px">{cat_html}</div>
    </body></html>"""
    plain = f"CLIMATE WEEK IN REVIEW — {week_str}\n" + "\n".join(plain_lines)
    return html, plain