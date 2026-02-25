# rescore_sentiment.py
from database.db import get_connection
from processors.gpt_processor import score_sentiment

conn = get_connection()
articles = conn.execute("SELECT id, title, summary FROM articles WHERE sentiment = 'neutral'").fetchall()

print(f"Re-scoring {len(articles)} articles...")

for i, (article_id, title, summary) in enumerate(articles, 1):
    if not summary or summary == "Summary unavailable.":
        continue
    
    sentiment, score = score_sentiment(title, summary)
    conn.execute(
        "UPDATE articles SET sentiment = ?, sent_score = ? WHERE id = ?",
        (sentiment, score, article_id)
    )
    
    if i % 5 == 0:
        print(f"  [{i}/{len(articles)}] {sentiment} ({score:+.2f}): {title[:50]}")
        conn.commit()
        import time
        time.sleep(7)  # Rate limit

conn.commit()
conn.close()
print("✅ Done!")