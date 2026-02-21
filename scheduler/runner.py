# scheduler/runner.py
"""
Orchestrates the full pipeline:
  1. Scrape all RSS feeds
  2. Process with GPT (classify + summarize)
  3. Build HTML digest
  4. Email the digest
  5. Schedule daily execution

Usage:
  python -m scheduler.runner               # Start scheduler (runs forever)
  python -m scheduler.runner --now         # Run immediately once and exit
  python -m scheduler.runner --test-email  # Send a test email and exit
"""

import os
import sys
import logging
import argparse
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv
from database.db import init_db, is_already_processed, save_article, save_digest_record

load_dotenv()

# Fix imports when run as a module from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.sources import RSS_FEEDS
from scrapers.news_scraper import scrape_all_feeds
from processors.gpt_processor import process_articles, generate_digest_intro
from processors.digest_builder import build_digest, save_digest
from mailer.email_sender import send_digest, send_test_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("climate_aggregator.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(hours: int = 24, dry_run: bool = False) -> bool:
    """
    Runs the full scrape → process → digest → email pipeline.

    Args:
        hours:   How far back to look for articles (default 24h).
        dry_run: If True, skip sending the email (saves the digest locally).

    Returns:
        True on success.
    """
    log.info("\n" + "═"*60)
    log.info("🌍  CLIMATE NEWS AGGREGATOR — STARTING PIPELINE")
    log.info("═"*60)

    # ── Step 1: Scrape ───────────────────────────────────────────────────────
    log.info("\n📡  STEP 1: Scraping news feeds…")
    articles = scrape_all_feeds(
        sources=RSS_FEEDS,
        max_per_feed=int(os.getenv("MAX_ARTICLES_PER_CATEGORY", 10)),
        hours=hours,
        delay=1.0,
    )

    if not articles:
        log.warning("⚠  No articles found. Aborting pipeline.")
        return False

      # ── DB: Init + skip already-seen articles ────────────
    init_db()
    new_articles = [a for a in articles
                    if not is_already_processed(a.url)]
    log.info(f"  {len(new_articles)} new articles (skipping {len(articles)-len(new_articles)} already seen)")

    # Only process NEW articles with Gemini (saves quota!)
    articles = new_articles
    if not articles:
        log.info("⚠  No new articles today. Aborting.")
        return False
    
    # ── Step 2: GPT Processing ───────────────────────────────────────────────
    log.info("\n🤖  STEP 2: Processing with GPT…")
    articles = process_articles(articles)


    # ── Step 3: Generate intro ───────────────────────────────────────────────
    log.info("\n✍️   STEP 3: Generating digest intro…")
    from collections import defaultdict
    cat_summaries = defaultdict(list)
    for a in articles:
        cat_summaries[a.category].append(a.summary)

    digest_info = generate_digest_intro(dict(cat_summaries))
    log.info(f"  Headline: {digest_info.get('headline','')}")

    # ── Step 4: Build digest ─────────────────────────────────────────────────
    log.info("\n📄  STEP 4: Building HTML digest…")
    max_per_cat = int(os.getenv("MAX_ARTICLES_PER_CATEGORY", 5))
    html, plain = build_digest(articles, digest_info, max_per_category=max_per_cat)

    html_path, txt_path = save_digest(html, plain, output_dir="output")
    log.info(f"  💾 Saved: {html_path}")
    log.info(f"  💾 Saved: {txt_path}")

    # ── Step 5: Send email ───────────────────────────────────────────────────
    if dry_run:
        log.info("\n📧  STEP 5: Dry run — skipping email send.")
        log.info(f"  Open {html_path} in a browser to preview the digest.")
        return True

    log.info("\n📧  STEP 5: Sending email digest…")
    success = send_digest(html, plain, attachments=[txt_path])

     # ── Save to database ──────────────────────────────────────────────────
    log.info("\n💾  Saving to database...")
    for a in articles:
        save_article(a)
    
    from collections import Counter
    top_cat = Counter(a.category for a in articles).most_common(1)[0][0] if articles else "other"
    avg_sent = sum(getattr(a, 'sentiment_score', 0) for a in articles) / len(articles) if articles else 0
    save_digest_record(
        datetime.now().strftime("%Y-%m-%d"),
        len(articles), 
        top_cat, 
        avg_sent, 
        html_path
    )
    log.info("✅  Articles saved to database.")

    log.info("\n" + "═"*60)
    log.info(f"✅  PIPELINE COMPLETE — {len(articles)} articles processed")
    log.info("═"*60 + "\n")
    return success

 

def run_weekly_pipeline():
    """Runs every Friday — sends week's top articles per category."""
    log.info("\n📅  WEEKLY DIGEST PIPELINE STARTING...")
    from processors.weekly_builder import build_weekly_digest
    html, plain = build_weekly_digest()
    from mailer.email_sender import send_digest
    week_str = datetime.now().strftime("%B %d, %Y")
    send_digest(html, plain, subject=f"🌍 Climate Week in Review — {week_str}")
    log.info("✅  Weekly digest sent.")

# ──────────────────────────────────────────────────────────────────────────────
# Scheduler
# ──────────────────────────────────────────────────────────────────────────────

def start_scheduler():
    """Starts the recurring daily scheduler."""
    send_time = os.getenv("DIGEST_SEND_TIME", "08:00")
    log.info(f"⏰  Scheduler started — digest will run daily at {send_time}")
    log.info(f"   Press Ctrl+C to stop.\n")

    schedule.every().day.at(send_time).do(run_pipeline)
    schedule.every().friday.at("08:30").do(run_weekly_pipeline)
    # Run immediately on start too
    run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Climate News Aggregator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scheduler.runner              Start daily scheduler
  python -m scheduler.runner --now        Run pipeline once immediately
  python -m scheduler.runner --dry-run    Run pipeline but don't send email
  python -m scheduler.runner --test-email Send a test email to verify SMTP
  python -m scheduler.runner --hours 48   Look back 48 hours for articles
        """,
    )
    parser.add_argument("--now",         action="store_true", help="Run pipeline immediately and exit")
    parser.add_argument("--dry-run",     action="store_true", help="Run pipeline but skip sending email")
    parser.add_argument("--test-email",  action="store_true", help="Send a test email and exit")
    parser.add_argument("--hours",       type=int, default=24, help="Hours to look back (default: 24)")
    parser.add_argument("--weekly", action="store_true",help="Send weekly digest now and exit")
    args = parser.parse_args()

    if args.test_email:
        log.info("📧  Sending test email…")
        ok = send_test_email()
        sys.exit(0 if ok else 1)

    elif args.now or args.dry_run:
        ok = run_pipeline(hours=args.hours, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)
    
    elif args.weekly:
        run_weekly_pipeline()

    else:
        start_scheduler()