from flask import Flask, render_template_string, jsonify
import os, json
from database.db import get_connection, get_category_trends

app = Flask(__name__)

# ── Routes ────────────────────────────────────────────

@app.route("/")
def index():
    # Get filter parameter (default: today)
    from flask import request
    days = request.args.get('days', 'today')
    
    if days == 'today':
        date_filter = "DATE(scraped_at) = DATE('now')"
    elif days == 'week':
        date_filter = "scraped_at >= datetime('now', '-7 days')"
    elif days == 'month':
        date_filter = "scraped_at >= datetime('now', '-30 days')"
    else:
        date_filter = "1=1"  # all time
    
    with get_connection() as conn:
        articles = conn.execute(f"""
            SELECT * FROM articles
            WHERE {date_filter}
            ORDER BY scraped_at DESC
        """).fetchall()
        digests = conn.execute("""
            SELECT * FROM digests ORDER BY date DESC LIMIT 30
        """).fetchall()
        stats = conn.execute("""
            SELECT
              COUNT(*) as total,
              AVG(sent_score) as avg_sentiment,
              COUNT(DISTINCT source) as sources
            FROM articles
        """).fetchone()
    return render_template_string(DASHBOARD_HTML,
        articles=[dict(a) for a in articles],
        digests=[dict(d) for d in digests],
        stats=dict(stats))


@app.route("/api/trends")
def trends():
    return jsonify(get_category_trends())


@app.route("/digest/<date>")
def view_digest(date):
    path = f"output/digest_{date}.html"
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return "Digest not found", 404


# ── Dashboard HTML template ───────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"/>
<title>Climate Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body{font-family:Georgia,serif;background:#0f1117;color:#e8e8f0;margin:0;padding:24px}
  h1{font-size:28px;color:#3d9eff;margin-bottom:4px}
  .stats{display:flex;gap:16px;margin:20px 0}
  .stat{background:#161b22;border:1px solid #30363d;border-radius:8px;
        padding:16px 24px;text-align:center}
  .stat-n{font-size:28px;font-weight:700;color:#3d9eff}
  .stat-l{font-size:11px;color:#6b6b85;text-transform:uppercase;letter-spacing:1px}
  table{width:100%;border-collapse:collapse;margin-top:20px;font-size:13px}
  th{background:#161b22;padding:10px 12px;text-align:left;color:#6b6b85;
     font-size:10px;letter-spacing:1.5px;text-transform:uppercase}
  td{padding:10px 12px;border-bottom:1px solid #21262d;vertical-align:top}
  td a{color:#3d9eff;text-decoration:none}
  td a:hover{text-decoration:underline}
  .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px}
  .pos{background:rgba(74,222,128,.15);color:#4ade80}
  .neg{background:rgba(248,113,113,.15);color:#f87171}
  .neu{background:rgba(107,107,133,.15);color:#9999bb}
  .chart-wrap{background:#161b22;border:1px solid #30363d;border-radius:8px;
              padding:20px;margin:20px 0;max-height:300px}
  h2{font-size:16px;color:#e8e8f0;margin:28px 0 12px}
</style>
</head><body>

<h1>🌍 Climate News Dashboard</h1>
<p style="color:#6b6b85">Real-time view of your aggregated climate news</p>

<div class="stats">
  <div class="stat">
    <div class="stat-n">{{ stats.total or 0 }}</div>
    <div class="stat-l">Total Articles</div>
  </div>
  <div class="stat">
    <div class="stat-n">{{ stats.sources or 0 }}</div>
    <div class="stat-l">News Sources</div>
  </div>
  <div class="stat">
    <div class="stat-n">{{ "%.2f"|format(stats.avg_sentiment or 0) }}</div>
    <div class="stat-l">Avg Sentiment</div>
  </div>
  <div class="stat">
    <div class="stat-n">{{ digests|length }}</div>
    <div class="stat-l">Digests Sent</div>
  </div>
</div>

<h2>📊 Category Trends (14 days)</h2>
<div class="chart-wrap"><canvas id="trendChart"></canvas></div>

<h2>📰 Recent Articles</h2>
<div style="margin-bottom:12px">
  <select onchange="window.location.href='/?days='+this.value" 
          style="background:#161b22;color:#e8e8f0;border:1px solid #30363d;
                 padding:6px 12px;border-radius:4px;font-size:13px">
    <option value="today">Today</option>
    <option value="week">Last 7 days</option>
    <option value="month">Last 30 days</option>
    <option value="all">All time</option>
  </select>
</div>
<table>
  <tr><th>Title</th><th>Source</th><th>Category</th><th>Sentiment</th><th>Date</th></tr>
  {% for a in articles %}
  <tr>
    <td><a href="{{ a.url }}" target="_blank">{{ a.title[:80] }}</a></td>
    <td style="color:#6b6b85">{{ a.source }}</td>
    <td>{{ a.category }}</td>
    <td><span class="pill {{ a.sentiment[:3] }}">{{ a.sentiment }}</span></td>
    <td style="color:#6b6b85">{{ a.scraped_at[:10] }}</td>
  </tr>
  {% endfor %}
</table>

<h2>📧 Past Digests</h2>
<table>
  <tr><th>Date</th><th>Articles</th><th>Top Category</th><th>Avg Sentiment</th><th>View</th></tr>
  {% for d in digests %}
  <tr>
    <td>{{ d.date }}</td>
    <td>{{ d.article_count }}</td>
    <td>{{ d.top_category }}</td>
    <td>{{ "%.2f"|format(d.avg_sentiment or 0) }}</td>
    <td><a href="/digest/{{ d.date }}">Open HTML</a></td>
  </tr>
  {% endfor %}
</table>

<script>
fetch('/api/trends').then(r=>r.json()).then(data=>{
  const days=[...new Set(data.map(d=>d.day))].sort();
  const cats=[...new Set(data.map(d=>d.category))];
  const colors={'policy':'#7c6aff','technology':'#3d9eff','finance':'#00d4aa',
                'disasters':'#f87171','science':'#fbbf24','other':'#9999bb'};
  const datasets=cats.map(cat=>({
    label:cat,
    data:days.map(day=>{
      const row=data.find(d=>d.day===day && d.category===cat);
      return row?row.count:0;
    }),
    borderColor:colors[cat]||'#888',
    backgroundColor:(colors[cat]||'#888')+'22',
    tension:0.3,fill:true
  }));
  new Chart(document.getElementById('trendChart'),{
    type:'line',
    data:{labels:days,datasets},
    options:{responsive:true,maintainAspectRatio:false,
             scales:{y:{beginAtZero:true,grid:{color:'#21262d'}},
                     x:{grid:{color:'#21262d'}}},
             plugins:{legend:{labels:{color:'#e8e8f0'}}}}
  });
});
</script>
</body></html>"""


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)