# config/sources.py
"""
Climate news sources — RSS feeds and direct URLs.
Add or remove sources freely; the scraper handles both RSS and HTML.
"""

RSS_FEEDS = [
    # ── General Climate ──────────────────────────────────────────────────────
    {
        "name": "Carbon Brief",
        "url": "https://www.carbonbrief.org/feed",
        "category_hint": "policy",
    },
    {
        "name": "Climate Home News",
        "url": "https://www.climatechangenews.com/feed/",
        "category_hint": None,   # let GPT decide
    },
    {
        "name": "Inside Climate News",
        "url": "https://insideclimatenews.org/feed/",
        "category_hint": None,
    },
    {
        "name": "E&E News (Climate)",
        "url": "https://www.eenews.net/rss/climate",
        "category_hint": "policy",
    },

    # ── Technology ───────────────────────────────────────────────────────────
    {
        "name": "CleanTechnica",
        "url": "https://cleantechnica.com/feed/",
        "category_hint": "technology",
    },
    {
        "name": "Electrek",
        "url": "https://electrek.co/feed/",
        "category_hint": "technology",
    },
    {
        "name": "PV Magazine",
        "url": "https://www.pv-magazine.com/feed/",
        "category_hint": "technology",
    },

    # ── Finance / Markets ────────────────────────────────────────────────────
    {
        "name": "Bloomberg Green (RSS)",
        "url": "https://feeds.bloomberg.com/green/news.rss",
        "category_hint": "finance",
    },
    {
        "name": "Reuters Climate",
        "url": "https://feeds.reuters.com/reuters/environmentNews",
        "category_hint": None,
    },

    # ── Disasters / Extreme Weather ──────────────────────────────────────────
    {
        "name": "NASA Climate",
        "url": "https://climate.nasa.gov/news/rss.xml",
        "category_hint": "disasters",
    },
    {
        "name": "NOAA News",
        "url": "https://www.noaa.gov/news/feed",
        "category_hint": "disasters",
    },

    # ── Science ──────────────────────────────────────────────────────────────
    {
        "name": "Nature Climate Change",
        "url": "https://www.nature.com/nclimate.rss",
        "category_hint": "science",
    },
    {
        "name": "The Guardian – Climate",
        "url": "https://www.theguardian.com/environment/climate-crisis/rss",
        "category_hint": None,
    },
]

# Categories the GPT classifier will assign articles to
CATEGORIES = {
    "policy":     "🏛️  Policy & Regulation",
    "technology": "⚡  Clean Technology",
    "finance":    "💰  Climate Finance",
    "disasters":  "🌪️  Disasters & Extreme Weather",
    "science":    "🔬  Science & Research",
    "other":      "🌐  General Climate News",
}

CATEGORY_DESCRIPTIONS = {
    "policy":     "Government policy, legislation, international agreements, treaties, regulations, COP summits",
    "technology": "Renewable energy, EV, battery storage, carbon capture, green hydrogen, clean tech startups",
    "finance":    "ESG investing, carbon markets, green bonds, climate risk, sustainable finance, net-zero pledges",
    "disasters":  "Floods, wildfires, droughts, hurricanes, heatwaves, sea level rise, extreme weather events",
    "science":    "Climate research, IPCC reports, emissions data, ocean temperatures, ice melt, scientific studies",
    "other":      "Any climate-related news that doesn't fit the above categories",
}