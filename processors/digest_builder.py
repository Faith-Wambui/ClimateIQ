# processors/digest_builder.py
"""
Builds a beautiful HTML email digest from processed articles.
Also saves a plain-text version alongside the HTML.
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from config.sources import CATEGORIES

# EAT = UTC+3 (Africa/Nairobi)
EAT = ZoneInfo("Africa/Nairobi")

# ──────────────────────────────────────────────────────────────────────────────
# CSS / HTML Template
# ──────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="icon" type="image/png" href="static/Climate IQ.png"/>
  <title>{title}</title>
  <style>
    /* Reset */
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: 'Georgia', 'Times New Roman', serif;
      background: #f0ede6;
      color: #1a1a1a;
      line-height: 1.65;
    }}

    /* Wrapper */
    .wrapper {{
      max-width: 680px;
      margin: 32px auto;
      background: #fffcf7;
      border: 1px solid #d9d3c7;
      border-radius: 4px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    }}

    /* Header */
    .header {{
      background: #1a3a2a;
      padding: 40px 48px 32px;
      text-align: center;
    }}
    .header .logo {{
      font-size: 11px;
      letter-spacing: 4px;
      text-transform: uppercase;
      color: #7aaa88;
      margin-bottom: 12px;
    }}
    .header h1 {{
      font-size: 28px;
      color: #f5f2ec;
      font-weight: 400;
      letter-spacing: -0.3px;
      margin-bottom: 8px;
    }}
    .header .date {{
      font-size: 13px;
      color: #8aaa96;
      letter-spacing: 1px;
    }}

    /* Intro band */
    .intro-band {{
      background: #eef7f0;
      border-bottom: 3px solid #2d6a4f;
      padding: 24px 48px;
    }}
    .day-headline {{
      font-size: 18px;
      font-weight: 700;
      color: #1a3a2a;
      margin-bottom: 10px;
    }}
    .intro-band p {{
      font-size: 14.5px;
      color: #3a5a48;
      line-height: 1.7;
    }}
    .logo-img {{
    height: 100px;
    width: auto;
    object-fit: contain;
    display: block;
    margin: 0 auto;
    align-items: center;
    }}
    .logo-img-footer {{
    height: 36px;
    /* Footer logos often look better with a brightness boost on dark bg */
    filter: brightness(1.1);

    }}
    /* Stats bar */
    .stats {{
      display: flex;
      border-bottom: 1px solid #e0dbd0;
      background: #f7f4ee;
    }}
    .stat {{
      flex: 1;
      text-align: center;
      padding: 16px 8px;
      border-right: 1px solid #e0dbd0;
    }}
    .stat:last-child {{ border-right: none; }}
    .stat-number {{
      font-size: 22px;
      font-weight: 700;
      color: #2d6a4f;
      display: block;
    }}
    .stat-label {{
      font-size: 10px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #888;
      margin-top: 2px;
    }}

    /* Body */
    .body {{ padding: 40px 48px; }}

    /* Category section */
    .category {{
      margin-bottom: 40px;
      padding-bottom: 40px;
      border-bottom: 1px solid #e8e3da;
    }}
    .category:last-child {{
      border-bottom: none;
      margin-bottom: 0;
      padding-bottom: 0;
    }}
    .category-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
      padding-bottom: 10px;
      border-bottom: 2px solid #2d6a4f;
    }}
    .category-header h2 {{
      font-size: 13px;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: #2d6a4f;
      font-weight: 700;
    }}
    .category-count {{
      font-size: 11px;
      background: #2d6a4f;
      color: white;
      padding: 2px 8px;
      border-radius: 20px;
    }}

    /* Article card */
    .article {{
      margin-bottom: 24px;
      padding: 20px;
      background: #faf8f3;
      border: 1px solid #e8e3da;
      border-left: 3px solid #2d6a4f;
      border-radius: 2px;
    }}
    .article:last-child {{ margin-bottom: 0; }}
    .article-source {{
      font-size: 10px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #999;
      margin-bottom: 6px;
    }}
    .article-title {{
      font-size: 16px;
      font-weight: 700;
      color: #1a1a1a;
      margin-bottom: 10px;
      line-height: 1.4;
    }}
    .article-title a {{
      color: #1a3a2a;
      text-decoration: none;
    }}
    .article-title a:hover {{ text-decoration: underline; }}
    .article-summary {{
      font-size: 13.5px;
      color: #555;
      line-height: 1.65;
      margin-bottom: 10px;
    }}
    .article-meta {{
      font-size: 11px;
      color: #aaa;
    }}

    /* Footer */
    .footer {{
      background: #1a3a2a;
      padding: 24px 48px;
      text-align: center;
    }}
    .footer p {{
      font-size: 11px;
      color: #6a9478;
      margin-bottom: 6px;
    }}
    .footer a {{ color: #7aaa88; }}
  </style>
</head>
<body>
<div class="wrapper">

  <!-- Header -->
  <div class="header">
    <div class="logo">
      <img src="https://raw.githubusercontent.com/Faith-Wambui/ClimateIQ/main/logo.png" alt="Logo" class="logo-img" style="width:64px;height:64px;border-radius:8px"/>
    </div>
    <h1>{title}</h1>
    <div class="date">{date_str}</div>
  </div>

  <!-- Intro -->
  <div class="intro-band">
    <div class="day-headline">{day_headline}</div>
    <p>{intro_text}</p>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat">
      <span class="stat-number">{total_articles}</span>
      <span class="stat-label">Articles</span>
    </div>
    <div class="stat">
      <span class="stat-number">{total_sources}</span>
      <span class="stat-label">Sources</span>
    </div>
    <div class="stat">
      <span class="stat-number">{total_categories}</span>
      <span class="stat-label">Topics</span>
    </div>
  </div>

  {mood_html}
  
  <!-- Content -->
  <div class="body">
    {categories_html}
  </div>

  <!-- Footer -->
  <div class="footer">
    <p>Climate IQ - AI Climate News Aggregator · Powered by Google Gemini</p>
    <p>Generated on {date_str}. Data sourced from public RSS feeds.</p>
  </div>

</div>
</body>
</html>
"""

CATEGORY_BLOCK = """\
<div class="category">
  <div class="category-header">
    <h2>{icon}  {label}</h2>
    <span class="category-count">{count}</span>
  </div>
  {articles_html}
</div>
"""

ARTICLE_BLOCK = """\
<div class="article">
  <div class="article-source">{source}</div>
  <div class="article-title"><a href="{url}" target="_blank">{title}</a></div>
  <div class="article-summary">{summary}</div>
  <div class="article-meta">{date_str}</div>
</div>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_date(dt) -> str:
    """Format a datetime to EAT, falling back gracefully."""
    if not dt:
        return "Date unknown"
    try:
        # If naive, assume UTC then convert; if aware, just convert
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        dt_eat = dt.astimezone(EAT)
        return dt_eat.strftime("%b %d, %Y  %H:%M EAT")
    except Exception:
        return str(dt)


def build_digest(
    articles: list,
    digest_info: dict,
    max_per_category: int = 5,
) -> tuple[str, str]:
    """
    Builds an HTML digest and a plain-text version.
    Returns (html_string, text_string).

    Args:
        articles:          Processed NewsArticle objects.
        digest_info:       {"headline": ..., "intro": ...} from GPT.
        max_per_category:  Max articles shown per category.
    """
    # ── Group articles by category ──────────────────────────────────────────
    grouped: dict[str, list] = defaultdict(list)
    for a in articles:
        grouped[a.category].append(a)

    # Sort categories by priority order
    cat_order = list(CATEGORIES.keys())
    sorted_cats = sorted(
        grouped.keys(),
        key=lambda c: cat_order.index(c) if c in cat_order else 99,
    )

    # ── Build category HTML blocks ──────────────────────────────────────────
    categories_html = ""
    plain_lines = []

    icon_map = {
        "policy":     "🏛️",
        "technology": "⚡",
        "finance":    "💰",
        "disasters":  "🌪️",
        "science":    "🔬",
        "other":      "🌐",
    }

    for cat in sorted_cats:
        arts = grouped[cat][:max_per_category]
        label = CATEGORIES.get(cat, cat.title()).split("  ", 1)[-1]  # strip leading emoji from label
        icon = icon_map.get(cat, "📰")

        articles_html = ""
        plain_lines.append(f"\n{'='*60}")
        plain_lines.append(f"{icon}  {label.upper()}  ({len(arts)} articles)")
        plain_lines.append("="*60)

        for a in arts:
            articles_html += ARTICLE_BLOCK.format(
                source=a.source,
                url=a.url,
                title=a.title,
                summary=a.summary,
                date_str=_fmt_date(a.published),
            )
            plain_lines.append(f"\n▸ {a.title}")
            plain_lines.append(f"  Source : {a.source}")
            plain_lines.append(f"  Link   : {a.url}")
            plain_lines.append(f"  Date   : {_fmt_date(a.published)}")
            plain_lines.append(f"  Summary: {a.summary}\n")

        categories_html += CATEGORY_BLOCK.format(
            icon=icon,
            label=label,
            count=len(arts),
            articles_html=articles_html,
        )

    # ── Assemble full HTML ──────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d, %Y")
    total_sources = len({a.source for a in articles})

    # Mood-o-meter
    scores = [a.sentiment_score for a in articles]
    avg_score = sum(scores) / len(scores) if scores else 0
    pos = sum(1 for a in articles if a.sentiment == "positive")
    neg = sum(1 for a in articles if a.sentiment == "negative")
    neu = sum(1 for a in articles if a.sentiment == "neutral")
    mood_emoji = "😊" if avg_score > 0.2 else "😟" if avg_score < -0.2 else "😐"
    mood_label = "Cautiously Optimistic" if avg_score > 0.2 else \
                 "Concerning News Day" if avg_score < -0.2 else "Mixed Signals"
    mood_bar_pct = int((avg_score + 1) / 2 * 100)  # convert -1..1 to 0..100%
    mood_html = f"""
    <div style="background:#f0f7f4;padding:16px 48px;border-bottom:1px solid #e0dbd0">
      <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;
                  color:#888;margin-bottom:8px">Climate Mood-o-meter {mood_emoji}</div>
      <div style="display:flex;align-items:center;gap:12px">
        <span style="color:#e74c3c;font-size:12px">😟 {neg} negative</span>
        <div style="flex:1;height:8px;background:#e0dbd0;border-radius:4px;overflow:hidden">
          <div style="width:{mood_bar_pct}%;height:100%;
                      background:linear-gradient(90deg,#e74c3c,#f39c12,#27ae60);
                      border-radius:4px"></div>
        </div>
        <span style="color:#27ae60;font-size:12px">😊 {pos} positive</span>
      </div>
      <div style="text-align:center;font-size:12px;color:#666;margin-top:6px">
        {mood_label} — {neu} neutral articles
      </div>
    </div>"""
   
    html = HTML_TEMPLATE.format(
        title=os.getenv("DIGEST_TITLE", "🌍 Daily Climate News Digest"),
        date_str=date_str,
        day_headline=digest_info.get("headline", "Today's Climate News"),
        intro_text=digest_info.get("intro", ""),
        total_articles=len(articles),
        total_sources=total_sources,
        total_categories=len(sorted_cats),
        categories_html=categories_html,
        mood_html=mood_html
    )

    # ── Plain-text version ──────────────────────────────────────────────────
    plain = (
        f"{'='*60}\n"
        f"DAILY CLIMATE NEWS DIGEST — {date_str}\n"
        f"{'='*60}\n\n"
        f"{digest_info.get('headline','')}\n\n"
        f"{digest_info.get('intro','')}\n"
        + "\n".join(plain_lines)
        + f"\n\n{'='*60}\n"
        f"Generated by AI Climate News Aggregator\n"
        f"Articles: {len(articles)}  |  Sources: {total_sources}  |  Topics: {len(sorted_cats)}\n"
    )

    return html, plain


def save_digest(html: str, plain: str, output_dir: str = "output") -> tuple[str, str]:
    """Saves HTML and TXT digest to disk. Returns (html_path, txt_path)."""
    os.makedirs(output_dir, exist_ok=True)
    date_slug = datetime.now().strftime("%Y-%m-%d")
    html_path = os.path.join(output_dir, f"digest_{date_slug}.html")
    txt_path  = os.path.join(output_dir, f"digest_{date_slug}.txt")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(plain)

    return html_path, txt_path