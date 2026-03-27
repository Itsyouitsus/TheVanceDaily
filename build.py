#!/usr/bin/env python3
"""
OnlyVance28.com — v4
Dark editorial design, social links, political bias indicators, source carousel.
"""

import feedparser
import json
import os
import hashlib
import urllib.request
import ssl
import concurrent.futures
import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import html as html_module
from urllib.parse import urlparse

QUERIES = [
    "JD Vance",
    "Vance president 2028",
    "Vance Republican",
    "Vance policy",
    "JD Vance speech",
    "Vance Congress",
    "Vance economy",
    "Vance immigration",
    "Vice President Vance",
]

# Direct RSS feeds from major US political outlets (for broader coverage)
DIRECT_FEEDS = [
    # LEFT / LEAN LEFT
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://feeds.washingtonpost.com/rss/politics",
    "https://feeds.npr.org/1014/rss.xml",  # NPR Politics
    "https://feeds.nbcnews.com/nbcnews/public/politics",
    "https://feeds.abcnews.com/abcnews/politicsheadlines",
    "https://www.cbsnews.com/latest/rss/politics",
    "https://feeds.politico.com/rss/politicopicks.xml",
    # CENTER
    "https://feeds.reuters.com/reuters/politicsNews",
    "https://feeds.apnews.com/apnews/politics",
    "https://thehill.com/feed/",
    "https://www.axios.com/feeds/feed.rss",
    # LEAN RIGHT / RIGHT
    "https://feeds.foxnews.com/foxnews/politics",
    "https://nypost.com/politics/feed/",
    "https://www.washingtontimes.com/rss/headlines/news/politics/",
    "https://www.washingtonexaminer.com/section/politics/feed",
    "https://www.dailywire.com/feeds/rss.xml",
    "https://www.breitbart.com/politics/feed/",
]

MAX_ARTICLES = 120
OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")
DATA_FILE = os.path.join(OUTPUT_DIR, "articles.json")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── International source blocklist (domain patterns to exclude) ──
INTL_BLOCK = {
    "ndtv.com", "bbc.com", "bbc.co.uk", "theguardian.com", "telegraph.co.uk",
    "aljazeera.com", "trtworld.com", "france24.com", "dw.com",
    "timesofisrael.com", "jpost.com", "haaretz.com",
    "scmp.com", "thecradle.co", "dailymail.co.uk", "express.co.uk",
    "independent.co.uk", "sky.com", "india.com", "hindustantimes.com",
    "thehindu.com", "tribuneindia.com", "irishtimes.com",
    "rt.com", "sputniknews.com", "globaltimes.cn", "anadolu.com",
    "aa.com.tr", "tribunecontentagency.com", "pressenza.com",
    "palestinechronicle.com", "middleeasteye.net", "lavoce.com",
}

def is_us_source(article):
    """Filter to keep only US-based sources."""
    domain = article.get("source_domain", "").lower()
    for blocked in INTL_BLOCK:
        if blocked in domain:
            return False
    # Block by TLD (non-US country TLDs)
    non_us_tlds = ['.co.uk', '.co.in', '.com.au', '.co.nz', '.co.za', '.ca', '.fr', '.de', '.it', '.es', '.ru', '.cn', '.jp', '.kr', '.in', '.pk', '.tr', '.il', '.ae']
    for tld in non_us_tlds:
        if domain.endswith(tld):
            return False
    return True

# ── Media bias database (based on AllSides 2025/2026 ratings) ──
# L=Left, LL=Lean Left, C=Center, LR=Lean Right, R=Right
BIAS_MAP = {
    # LEFT
    "CNN": "LL", "MSNBC": "L", "The New York Times": "LL", "New York Times": "LL",
    "Washington Post": "LL", "The Washington Post": "LL", "NPR": "LL",
    "HuffPost": "L", "Huffington Post": "L", "The Guardian": "LL",
    "Vox": "L", "Slate": "L", "The Atlantic": "L", "Mother Jones": "L",
    "Daily Beast": "L", "The Daily Beast": "L", "Salon": "L",
    "POLITICO": "LL", "Politico": "LL", "NBC News": "LL",
    "ABC News": "LL", "CBS News": "LL", "PBS": "LL", "PBS NewsHour": "LL",
    "The New Yorker": "L", "BuzzFeed News": "L", "BuzzFeed": "L",
    "The Intercept": "L", "Democracy Now!": "L",
    "Los Angeles Times": "LL", "LA Times": "LL",
    "CNBC": "LL", "Bloomberg": "LL", "Business Insider": "LL",
    "Insider": "LL", "Vice": "L", "Vice News": "L",
    "Rolling Stone": "L", "Vanity Fair": "L", "Newsweek": "LL",
    "Time": "LL", "TIME": "LL", "USA TODAY": "C", "USA Today": "C",
    "The Independent": "LL", "Raw Story": "L",
    "The Boston Globe": "LL", "Chicago Tribune": "LL",
    "ProPublica": "LL", "McClatchy": "LL",

    # CENTER
    "Reuters": "C", "Associated Press": "C", "AP News": "C", "AP": "C",
    "The Hill": "C", "Axios": "C", "BBC": "C", "BBC News": "C",
    "NewsNation": "C", "The Wall Street Journal": "C", "Wall Street Journal": "C",
    "WSJ": "C", "RealClearPolitics": "C", "C-SPAN": "C",
    "Forbes": "C", "MarketWatch": "C", "Al Jazeera": "C",
    "1440 Daily Digest": "C", "Tangle": "C", "Morning Brew": "C",
    "Straight Arrow News": "C", "Christian Science Monitor": "C",

    # LEAN RIGHT / RIGHT
    "Fox News": "R", "Fox Business": "LR",
    "New York Post": "LR", "The New York Post": "LR",
    "Daily Mail": "LR", "The Daily Mail": "LR", "MailOnline": "LR",
    "Washington Times": "LR", "The Washington Times": "LR",
    "Washington Examiner": "LR", "The Washington Examiner": "LR",
    "National Review": "R", "The Federalist": "R",
    "Breitbart": "R", "Breitbart News": "R",
    "The Daily Wire": "R", "Daily Wire": "R",
    "Daily Caller": "R", "The Daily Caller": "R",
    "Newsmax": "R", "OAN": "R", "One America News": "R",
    "Townhall": "R", "The Blaze": "R", "TheBlaze": "R",
    "The Epoch Times": "LR", "Epoch Times": "LR",
    "Just The News": "LR", "The Free Press": "LR",
    "ZeroHedge": "LR", "Reason": "LR",
    "The Daily Signal": "R", "Western Journal": "R",
    "RedState": "R", "PJ Media": "R", "Hot Air": "LR",

    # INTERNATIONAL
    "Al Jazeera English": "C", "Sky News": "C",
    "The Times of Israel": "C", "Times of Israel": "C",
    "The Telegraph": "LR", "The Jerusalem Post": "LR",
    "South China Morning Post": "C", "Deutsche Welle": "C", "DW": "C",
    "France 24": "C", "The Irish Times": "C",
    "NDTV": "LR", "TRT World": "C", "Anadolu Agency": "C",
    "The Express Tribune": "C", "thecradle.co": "L",
    "Palestine Chronicle": "L", "India.Com": "C",

    # LOCAL / REGIONAL US
    "KEYE": "C", "WSMH": "C", "WGXA": "C", "WTOV": "C", "KOMO": "C",
    "WKYT": "C", "WRAL": "C", "WQAD": "C", "KSAT": "C", "WPDE": "C",
    "Northern News Now": "C", "Messenger-Inquirer": "C",
    "Houston Public Media": "C", "The Center Square": "LR",
    "Audacy": "C", "AOL.com": "C", "AOL": "C",
    "nypost.com": "LR",
    "mandatory.com": "LL", "themarysue.com": "L", "The Mary Sue": "L",
    "wng.org": "R", "World Magazine": "R",
    "Premier Christian News": "LR",
    "Yahoo": "C", "Yahoo News": "C",
    "MSN": "C", "Google News": "C",
    "The Times": "C", "Anadolu Ajansı": "C",

    # More outlets from feed
    "nationalreview.com": "R", "The New Republic": "L", "The Bulwark": "LL",
    "Daily Express": "LR", "9News": "C", "KTUL": "C", "WKMG": "C",
    "KABB": "C", "KOIN.com": "C", "WCPO 9 News": "C", "abc27.com": "C",
    "Stamford Advocate": "C", "tyla.com": "C",
}

BIAS_LABELS = {
    "L": "Left",
    "LL": "Leans Left",
    "C": "Center",
    "LR": "Leans Right",
    "R": "Right",
    "?": "Unrated",
}

BIAS_COLORS = {
    "L": "#4a90d9",
    "LL": "#7bb3e0",
    "C": "#a0a090",
    "LR": "#e09070",
    "R": "#d94a4a",
    "?": "#555",
}

# ── Topic classification by keywords in title ──
TOPIC_KEYWORDS = {
    "Iran": ["iran", "tehran", "persian gulf", "ayatollah", "khamenei"],
    "Foreign Policy": ["foreign policy", "diplomacy", "nato", "allies", "summit", "ambassador", "treaty", "sanctions", "tariff", "trade war", "china", "russia", "ukraine", "middle east", "israel", "gaza", "north korea"],
    "Economy": ["economy", "inflation", "jobs", "unemployment", "gdp", "recession", "wall street", "stock", "federal reserve", "interest rate", "deficit", "debt ceiling", "tax"],
    "Healthcare": ["healthcare", "health care", "obamacare", "aca", "medicaid", "medicare", "insurance", "pharmaceutical", "drug prices", "hospital"],
    "Immigration": ["immigration", "border", "migrant", "deportation", "asylum", "ice", "visa", "illegal", "undocumented"],
    "Tech & AI": ["tech", "ai ", "artificial intelligence", "silicon valley", "big tech", "tiktok", "social media", "algorithm", "data privacy", "crypto", "bitcoin"],
    "2028 Race": ["2028", "presidential race", "primary", "campaign", "candidacy", "running mate", "poll", "nomination", "gop primary", "republican primary", "election"],
    "Military": ["military", "defense", "pentagon", "troops", "war", "veterans", "army", "navy", "air force", "marines"],
    "Domestic": ["congress", "senate", "house", "legislation", "bill", "supreme court", "constitution", "fbi", "doj", "government shutdown", "executive order"],
}

def classify_topic(title):
    """Auto-classify article topic from title keywords."""
    t = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return topic
    return "General"


class OGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
        self.done = False
    def handle_starttag(self, tag, attrs):
        if self.done: return
        if tag == 'meta':
            d = dict(attrs)
            prop = d.get('property', d.get('name', ''))
            content = d.get('content', '')
            if prop in ('og:image', 'twitter:image', 'twitter:image:src') and content:
                self.og[prop] = content
        if tag == 'body': self.done = True
    def handle_endtag(self, tag):
        if tag == 'head': self.done = True


def resolve_url(google_url):
    try:
        from googlenewsdecoder import new_decoderv1
        result = new_decoderv1(google_url)
        if result and result.get('status') and result.get('decoded_url'):
            return result['decoded_url']
    except: pass
    try:
        req = urllib.request.Request(google_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=8, context=SSL_CTX)
        if 'news.google.com' not in resp.url: return resp.url
    except: pass
    return None


def fetch_og_image(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=8, context=SSL_CTX)
        raw = resp.read(60000)
        html_text = raw.decode('utf-8', errors='ignore')
        parser = OGParser()
        parser.feed(html_text)
        img = parser.og.get('og:image') or parser.og.get('twitter:image') or parser.og.get('twitter:image:src', '')
        if img and not img.startswith('http'):
            p = urlparse(url)
            img = f"{p.scheme}://{p.netloc}{img}"
        return img
    except: return ''


def get_bias(source_name):
    if source_name in BIAS_MAP: return BIAS_MAP[source_name]
    for key in BIAS_MAP:
        if key.lower() == source_name.lower(): return BIAS_MAP[key]
        if key.lower() in source_name.lower() or source_name.lower() in key.lower():
            return BIAS_MAP[key]
    return "?"


def process_entry(entry, query):
    try:
        pub_date = None
        if hasattr(entry, 'published'):
            try: pub_date = parsedate_to_datetime(entry.published)
            except: pub_date = datetime.now(timezone.utc)
        else: pub_date = datetime.now(timezone.utc)

        title = entry.title
        source_name = ""
        source_url = ""
        if hasattr(entry, 'source'):
            source_name = entry.source.get('title', '')
            source_url = entry.source.get('href', '')
        if not source_name and " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()
            source_name = parts[1].strip()

        article_id = hashlib.md5(title.encode()).hexdigest()[:12]
        bias = get_bias(source_name)
        topic = classify_topic(title)

        return {
            "id": article_id,
            "title": html_module.escape(title),
            "source": html_module.escape(source_name),
            "source_url": source_url,
            "source_domain": urlparse(source_url).netloc if source_url else "",
            "link": entry.link,
            "published": pub_date.isoformat() if pub_date else None,
            "published_display": pub_date.strftime("%b %d, %Y") if pub_date else "Unknown",
            "query": query,
            "image": "",
            "real_url": "",
            "bias": bias,
            "topic": topic,
        }
    except: return None


def enrich_article(article):
    try:
        real_url = resolve_url(article["link"])
        if real_url:
            article["real_url"] = real_url
            image = fetch_og_image(real_url)
            if image and image.startswith('http'):
                article["image"] = image
    except: pass
    return article


def fetch_rss(query):
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    return [a for a in (process_entry(e, query) for e in feed.entries) if a]


def fetch_direct_feeds():
    """Fetch articles from direct outlet RSS feeds, filtering for Vance-related content."""
    vance_keywords = ["vance", "vice president", "vp vance"]
    articles = []
    for feed_url in DIRECT_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:  # Check last 30 per feed
                title = entry.title.lower() if hasattr(entry, 'title') else ""
                summary = entry.get('summary', '').lower()
                text = title + " " + summary
                if any(kw in text for kw in vance_keywords):
                    a = process_entry(entry, "direct_feed")
                    if a:
                        # For direct feeds, set real_url from the entry link
                        if not a.get("real_url") and hasattr(entry, 'link'):
                            a["real_url"] = entry.link
                        # Try to get source from feed title if missing
                        if not a["source"] and hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
                            a["source"] = html_module.escape(feed.feed.title)
                            a["bias"] = get_bias(feed.feed.title)
                        articles.append(a)
        except Exception as e:
            print(f"  Feed error {feed_url[:40]}: {e}")
    return articles


def deduplicate(articles):
    seen = set()
    return [a for a in articles if a["id"] not in seen and not seen.add(a["id"])]


def generate_html(articles, build_time):
    sources = sorted(set(a["source"] for a in articles if a["source"]))
    sources_json = json.dumps(sources)
    topics = sorted(set(a["topic"] for a in articles if a["topic"]))
    topics_json = json.dumps(topics)
    article_meta = json.dumps([{
        "published": a["published"],
        "source": a["source"],
        "bias": a["bias"],
        "topic": a["topic"],
    } for a in articles])

    # Counts for dropdowns and buttons
    from collections import Counter as Ctr
    source_counts_map = Ctr(a["source"] for a in articles)
    source_counts_json = json.dumps(dict(source_counts_map))
    topic_counts_map = Ctr(a["topic"] for a in articles)
    topic_counts_json = json.dumps(dict(topic_counts_map))
    bias_counts_map = Ctr(a["bias"] for a in articles if a["source"] != "Vance Social Media")
    bias_count_L = bias_counts_map.get("L", 0)
    bias_count_LL = bias_counts_map.get("LL", 0)
    bias_count_C = bias_counts_map.get("C", 0)
    bias_count_LR = bias_counts_map.get("LR", 0)
    bias_count_R = bias_counts_map.get("R", 0)

    # Carousel
    seen_d = set()
    src_items = []
    for a in articles:
        d = a.get("source_domain", "")
        n = a.get("source", "")
        if d and d not in seen_d and n and n != "Vance Social Media":
            seen_d.add(d)
            src_items.append({"domain": d, "name": n, "url": a.get("source_url", "")})
    carousel_html = ""
    for item in src_items:
        href = item["url"] if item["url"] else f'https://{item["domain"]}'
        carousel_html += f'<a href="{href}" target="_blank" rel="noopener noreferrer" class="crs-item"><img loading="lazy" src="https://www.google.com/s2/favicons?domain={item["domain"]}&sz=64" alt="{item["name"]}" onerror="this.parentElement.style.display=\'none\'"><span>{item["name"]}</span></a>'
    carousel_track = carousel_html + carousel_html

    # Cards
    cards_html = ""
    for i, a in enumerate(articles):
        link = a.get("real_url") or a["link"]
        delay = min(i * 0.025, 1.0)
        bias = a.get("bias", "?")
        bias_label = BIAS_LABELS.get(bias, "Unknown")
        bias_color = BIAS_COLORS.get(bias, "#555")
        is_social = a.get("source") == "Vance Social Media"
        card_class = "card soc-card-item" if is_social else "card"

        if a.get("image"):
            img_html = f'<div class="card-img card-img-lazy" data-bg="{a["image"]}"></div>'
        else:
            fd = a.get("source_domain", "")
            if fd:
                label = a["source"]
                img_html = f'<div class="card-img card-img-source"><img class="src-logo" loading="lazy" src="https://www.google.com/s2/favicons?domain={fd}&sz=64" alt="" onerror="this.style.display=\'none\'"><span class="src-lbl">{label}</span></div>'
            else:
                img_html = '<div class="card-img card-img-empty"></div>'

        # Source display
        source_display = a["source"]

        cards_html += f'''
        <a href="{link}" target="_blank" rel="noopener noreferrer" class="{card_class}" data-idx="{i}" style="animation-delay:{delay}s">
            {img_html}
            <div class="card-body">
                <div class="card-top">
                    <span class="card-source">{source_display}</span>
                    <span class="bias-badge" style="background:{bias_color}" title="{bias_label}">{bias_label}</span>
                </div>
                <h3 class="card-title">{a["title"]}</h3>
                <div class="card-meta">
                    <time class="card-date">{a["published_display"]}</time>
                    <span class="card-topic">{a["topic"]}</span>
                </div>
            </div>
        </a>'''

    total = str(len(articles))

    # Build bias stats for SEO summary
    from collections import Counter
    bias_counts = Counter(a.get("bias","?") for a in articles if a.get("source") != "Vance Social Media")
    total_rated = sum(v for k,v in bias_counts.items() if k != "?")
    topic_counts = Counter(a.get("topic","General") for a in articles)
    top_topics = [t for t in topic_counts.most_common() if t[0] != "General"]
    top_topic = top_topics[0] if top_topics else ("General", 0)
    source_count = len(set(a["source"] for a in articles if a["source"]))

    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OnlyVance28 — Every JD Vance Article, Every Day | News Aggregator</title>
    <meta name="description" content="The most comprehensive JD Vance news aggregator. ''' + total + ''' articles from ''' + str(source_count) + ''' sources, updated daily. Filter by political bias, topic, source, or date. Left to Right coverage compared.">
    <meta name="keywords" content="JD Vance, Vance news, Vance 2028, VP Vance, Republican news, political news aggregator, media bias, Vance Iran, Vance immigration, Vance policy">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="OnlyVance28 — Every JD Vance Article, Every Day">
    <meta property="og:description" content="''' + total + ''' articles from ''' + str(source_count) + ''' sources. Filter by political bias, topic, or date. Updated daily.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://onlyvance28.com">
    <meta property="og:site_name" content="OnlyVance28">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="OnlyVance28 — Every JD Vance Article, Every Day">
    <meta name="twitter:description" content="The most comprehensive JD Vance news aggregator. ''' + total + ''' articles updated daily.">
    <link rel="canonical" href="https://onlyvance28.com">
    <link rel="sitemap" type="application/xml" href="/sitemap.xml">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "OnlyVance28",
        "url": "https://onlyvance28.com",
        "description": "Automated JD Vance news aggregator with political bias ratings",
        "publisher": {
            "@type": "Organization",
            "name": "OnlyVance28",
            "email": "contact@onlyvance28.com"
        }
    }
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg:#f6f4f0; --bg2:#fff; --bg3:#f0ede8;
            --surface:#fff; --surface-h:#f8f6f2;
            --text:#1a1714; --text2:#6b6560; --text3:#9e9790;
            --accent:#b8322a; --accent-h:#d43d33;
            --blue:#1e3a6e; --blue-soft:#e0e8f4;
            --border:#e2ddd5; --border2:#d5cfC6;
            --r:10px;
            --shadow:0 1px 3px rgba(26,23,20,.05);
            --shadow-h:0 6px 20px rgba(26,23,20,.1);
        }
        *,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}

        /* HEADER */
        .hdr{padding:0;border-bottom:1px solid var(--border);background:var(--bg2)}
        .hdr-in{max-width:1200px;margin:0 auto;padding:1.6rem 2rem 1.1rem}
        .hdr-top{display:flex;align-items:center;justify-content:space-between;gap:1.2rem;flex-wrap:wrap}
        .hdr-left{display:flex;flex-direction:column;gap:.1rem}
        .logo-row{display:flex;align-items:center;gap:.7rem}
        .logo-flag{width:clamp(48px,6vw,68px);height:clamp(32px,4vw,46px);display:flex;align-items:center;justify-content:center;flex-shrink:0}
        .logo-flag svg{width:100%;height:100%;border-radius:3px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
        .logo{font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:clamp(1.8rem,4.5vw,2.8rem);letter-spacing:-.02em;line-height:1.05;color:var(--text)}
        .logo .a{color:var(--accent)}
        .tagline{font-size:.78rem;font-weight:300;color:var(--text2);letter-spacing:.06em;text-transform:uppercase;margin-top:.2rem}
        .hdr-right{display:flex;flex-direction:column;align-items:flex-end;gap:.4rem}
        .cta-row{display:flex;gap:.5rem;align-items:center;width:100%}
        .cta-email{padding:.45rem .8rem;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;font-size:.82rem;outline:none;flex:1;min-width:0}
        .cta-email::placeholder{color:var(--text3)}
        .cta-email:focus{border-color:var(--accent)}
        .cta-btn{padding:.45rem 1rem;border-radius:6px;border:none;background:var(--accent);color:#fff;font-family:'DM Sans',sans-serif;font-weight:600;font-size:.82rem;cursor:pointer;transition:background .2s}
        .cta-btn:hover{background:var(--accent-h)}
        .hdr-meta{font-size:.7rem;color:var(--text3);white-space:nowrap;text-align:right}

        /* SOCIAL POSTS CAROUSEL */
        .soc-bar{overflow:hidden;background:var(--bg2);border-bottom:1px solid var(--border);padding:.8rem 0;position:relative}
        .soc-bar::before,.soc-bar::after{content:'';position:absolute;top:0;bottom:0;width:80px;z-index:2;pointer-events:none}
        .soc-bar::before{left:0;background:linear-gradient(90deg,var(--bg2),transparent)}
        .soc-bar::after{right:0;background:linear-gradient(270deg,var(--bg2),transparent)}
        .soc-label{position:absolute;left:1rem;top:50%;transform:translateY(-50%);z-index:3;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--text3);background:var(--bg2);padding:.2rem .5rem;border-radius:4px}
        .soc-track{display:flex;gap:1rem;width:max-content;animation:scrollR 100s linear infinite}
        .soc-track:hover{animation-play-state:paused}
        .soc-card{flex-shrink:0;width:300px;padding:.7rem .9rem;border-radius:8px;border:1px solid var(--border);background:var(--bg);text-decoration:none;color:var(--text);transition:border-color .2s,box-shadow .2s;display:flex;flex-direction:column;gap:.4rem}
        .soc-card:hover{border-color:var(--border2);box-shadow:var(--shadow-h)}
        .soc-card-hdr{display:flex;align-items:center;gap:.4rem}
        .soc-card-hdr svg{width:14px;height:14px;color:var(--text3);flex-shrink:0}
        .soc-card-hdr .platform{font-size:.65rem;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.04em}
        .soc-card-hdr .handle{font-size:.7rem;font-weight:500;color:var(--accent);margin-left:auto}
        .soc-card-text{font-size:.78rem;line-height:1.45;color:var(--text);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
        .soc-card-foot{font-size:.62rem;color:var(--text3)}

        /* SOURCE CAROUSEL */
        .crs{overflow:hidden;background:var(--bg3);border-bottom:1px solid var(--border);padding:.6rem 0;position:relative}
        .crs::before,.crs::after{content:'';position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none}
        .crs::before{left:0;background:linear-gradient(90deg,var(--bg3),transparent)}
        .crs::after{right:0;background:linear-gradient(270deg,var(--bg3),transparent)}
        .crs-track{display:flex;gap:1.8rem;width:max-content;animation:scrollR 120s linear infinite}
        .crs-track:hover{animation-play-state:paused}
        .crs-item{display:flex;align-items:center;gap:.4rem;flex-shrink:0;text-decoration:none;transition:opacity .2s}
        .crs-item:hover{opacity:.7}
        .crs-item img{width:20px;height:20px;border-radius:3px}
        .crs-item span{font-size:.7rem;font-weight:500;color:var(--text2);white-space:nowrap}
        @keyframes scrollR{0%{transform:translateX(-50%)}100%{transform:translateX(0)}}

        /* TOOLBAR */
        .tb{max-width:1200px;margin:0 auto;padding:.9rem 2rem;display:flex;gap:.55rem;flex-wrap:wrap;align-items:center}
        .sb{flex:1;min-width:170px;position:relative}
        .sb svg{position:absolute;left:.7rem;top:50%;transform:translateY(-50%);width:15px;height:15px;color:var(--text3);pointer-events:none}
        .si{width:100%;padding:.48rem .7rem .48rem 2rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.83rem;color:var(--text);outline:none}
        .si::placeholder{color:var(--text3)}
        .si:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .sel{padding:.48rem 1.8rem .48rem .7rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.8rem;color:var(--text);outline:none;cursor:pointer;appearance:none;background-image:url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239e9790' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .6rem center}
        .sel:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .sel option.soc-opt{color:var(--accent);font-weight:600}
        .pills{display:flex;gap:.2rem}
        .pill{padding:.38rem .65rem;border-radius:100px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.74rem;font-weight:500;color:var(--text2);cursor:pointer;transition:all .2s}
        .pill:hover{background:var(--bg3)}
        .pill.on{background:var(--blue);color:#fff;border-color:var(--blue)}

        /* BIAS FILTER */
        .bias-pills{display:flex;gap:.2rem}
        .bpill{padding:.38rem .55rem;border-radius:100px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.7rem;font-weight:500;cursor:pointer;transition:all .2s}
        .bpill:hover{opacity:.85}
        .bpill.on{color:#fff!important}

        .count{font-size:.7rem;color:var(--text3);white-space:nowrap}

        /* GRID */
        .main{max-width:1200px;margin:0 auto;padding:.5rem 2rem 4rem}
        .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}

        /* CARD */
        .card{display:flex;flex-direction:column;background:var(--bg2);border-radius:var(--r);border:1px solid var(--border);overflow:hidden;text-decoration:none;color:inherit;box-shadow:var(--shadow);transition:transform .25s,box-shadow .25s;animation:fadeUp .4s ease both}
        .card:hover{transform:translateY(-2px);box-shadow:var(--shadow-h)}
        .card:hover .card-title{color:var(--accent)}
        @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

        .card-img{width:100%;height:165px;background-size:cover;background-position:center;background-color:var(--bg3);flex-shrink:0}
        .card-img-lazy{transition:opacity .3s ease;opacity:.6}
        .card-img-lazy.loaded{opacity:1}
        .card-img-source{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5rem;background:linear-gradient(135deg,var(--bg3),var(--border))}
        .src-logo{width:40px;height:40px;border-radius:8px;background:var(--bg2);padding:3px;box-shadow:0 2px 6px rgba(0,0,0,.08)}
        .src-lbl{font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--text3);text-align:center;max-width:80%}
        .card-img-empty{background:linear-gradient(135deg,var(--bg3),var(--border))}

        .card-body{padding:.85rem 1.05rem .95rem;display:flex;flex-direction:column;flex-grow:1}
        .card-top{display:flex;align-items:center;justify-content:space-between;gap:.4rem;margin-bottom:.25rem}
        .card-source{font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--accent)}
        .bias-badge{font-size:.56rem;font-weight:600;padding:.12rem .4rem;border-radius:100px;color:#fff;letter-spacing:.03em;white-space:nowrap;flex-shrink:0}
        .card-title{font-family:'Playfair Display',Georgia,serif;font-size:.9rem;font-weight:700;line-height:1.35;color:var(--text);transition:color .2s;flex-grow:1}
        .card-meta{display:flex;align-items:center;gap:.6rem;margin-top:.45rem}
        .card-date{font-size:.67rem;color:var(--text3)}
        .card-topic{font-size:.6rem;font-weight:600;padding:.1rem .4rem;border-radius:4px;background:var(--bg3);color:var(--text2);white-space:nowrap}

        /* SOCIAL MEDIA CARD */
        .card.soc-card-item{border-color:var(--accent);border-width:1.5px}
        .card.soc-card-item .card-source{color:var(--accent);font-weight:700}
        .card.soc-card-item .card-img-source{background:linear-gradient(135deg,#fdf2f1,#f8e6e4)}

        .no-res{grid-column:1/-1;text-align:center;padding:3rem 2rem;color:var(--text3);background:var(--bg2);border-radius:var(--r);border:1px solid var(--border)}

        /* NEWSLETTER MODAL */
        .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
        .modal-overlay.show{display:flex}
        .modal{background:var(--bg2);border-radius:16px;padding:2.5rem 2rem;max-width:420px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.2);position:relative;animation:modalIn .3s ease}
        @keyframes modalIn{from{opacity:0;transform:scale(.92) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}
        .modal-close{position:absolute;top:.8rem;right:.8rem;width:28px;height:28px;border-radius:50%;border:1px solid var(--border);background:var(--bg);cursor:pointer;display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:1rem;transition:all .2s}
        .modal-close:hover{background:var(--bg3);color:var(--text)}
        .modal-icon{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,var(--accent),#d44a3a);display:flex;align-items:center;justify-content:center;margin:0 auto .9rem}
        .modal-icon svg{width:26px;height:26px;color:#fff}
        .modal h2{font-family:'Playfair Display',Georgia,serif;font-size:1.35rem;font-weight:700;color:var(--text);margin-bottom:.4rem}
        .modal p{font-size:.85rem;color:var(--text2);line-height:1.5;margin-bottom:1.2rem}
        .modal .email-show{font-weight:600;color:var(--accent);font-size:.9rem;margin-bottom:1rem;word-break:break-all}
        .modal-sub{font-size:.7rem;color:var(--text3);margin-top:.8rem}

        /* SUGGEST SOURCE MODAL */
        .smodal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
        .smodal-overlay.show{display:flex}
        .smodal{background:var(--bg2);border-radius:16px;padding:2.5rem 2rem;max-width:440px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.2);position:relative;animation:modalIn .3s ease}
        .smodal-close{position:absolute;top:.8rem;right:.8rem;width:28px;height:28px;border-radius:50%;border:1px solid var(--border);background:var(--bg);cursor:pointer;display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:1rem;transition:all .2s}
        .smodal-close:hover{background:var(--bg3);color:var(--text)}
        .smodal-icon{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,var(--blue),#2a5cc5);display:flex;align-items:center;justify-content:center;margin:0 auto .9rem}
        .smodal-icon svg{width:26px;height:26px;color:#fff}
        .smodal h2{font-family:'Playfair Display',Georgia,serif;font-size:1.25rem;font-weight:700;color:var(--text);margin-bottom:.3rem;text-align:center}
        .smodal .smodal-sub{font-size:.82rem;color:var(--text2);text-align:center;margin-bottom:1.2rem}
        .smodal-field{margin-bottom:.8rem}
        .smodal-field label{display:block;font-size:.72rem;font-weight:600;color:var(--text2);margin-bottom:.25rem;text-transform:uppercase;letter-spacing:.04em}
        .smodal-field input,.smodal-field select{width:100%;padding:.5rem .7rem;border-radius:7px;border:1px solid var(--border);background:var(--bg);font-family:'DM Sans',sans-serif;font-size:.85rem;color:var(--text);outline:none}
        .smodal-field input:focus,.smodal-field select:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .smodal-submit{width:100%;padding:.6rem;border-radius:7px;border:none;background:var(--blue);color:#fff;font-family:'DM Sans',sans-serif;font-weight:600;font-size:.88rem;cursor:pointer;transition:background .2s;margin-top:.4rem}
        .smodal-submit:hover{background:#163260}
        .smodal-thanks{display:none;text-align:center}
        .smodal-thanks.show{display:block}
        .smodal-form.hide{display:none}

        .ft{border-top:1px solid var(--border);font-size:.7rem;color:var(--text3);margin-top:1rem}
        .ft a{color:var(--text2);text-decoration:none}
        .ft a:hover{text-decoration:underline}
        .ft-inner{max-width:1200px;margin:0 auto;padding:2rem}
        .ft-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2rem;margin-bottom:1.5rem}
        .ft-col h4{font-family:'Playfair Display',Georgia,serif;font-size:.85rem;font-weight:700;color:var(--text);margin-bottom:.5rem}
        .ft-col p,.ft-col a{font-size:.75rem;line-height:1.6}
        .ft-col a{display:block;margin-bottom:.2rem}
        .ft-bottom{text-align:center;padding-top:1rem;border-top:1px solid var(--border)}

        @media(max-width:700px){
            .hdr{padding:1.4rem 1rem .9rem}
            .hdr-top{flex-direction:column;align-items:flex-start}
            .hdr-right{align-items:flex-start;width:100%}
            .cta-row{width:100%}.cta-email{flex:1}
            .socials{gap:.25rem;padding:.5rem .8rem}.soc-link{padding:.25rem .4rem;font-size:.63rem}
            .tb{padding:.6rem .8rem}
            .main{padding:.3rem .6rem 3rem}
            .grid{grid-template-columns:1fr;gap:.7rem}
            .card-img{height:140px}
            .pills,.bias-pills{overflow-x:auto;flex-wrap:nowrap;-webkit-overflow-scrolling:touch}
            .pill,.bpill{flex-shrink:0}
            .ft-grid{grid-template-columns:1fr;gap:1rem}
        }
    </style>
<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-6FJK6HBH8C"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-6FJK6HBH8C");</script>
</head>
<body>

<header class="hdr">
    <div class="hdr-in">
        <div class="hdr-top">
            <div class="hdr-left">
                <div class="logo-row">
                    <div class="logo-flag"><svg viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect width="60" height="40" fill="#fff"/><g fill="#B22234"><rect y="0" width="60" height="3.08"/><rect y="6.15" width="60" height="3.08"/><rect y="12.31" width="60" height="3.08"/><rect y="18.46" width="60" height="3.08"/><rect y="24.62" width="60" height="3.08"/><rect y="30.77" width="60" height="3.08"/><rect y="36.92" width="60" height="3.08"/></g><rect width="24" height="21.54" fill="#3C3B6E"/><g fill="#fff" font-size="2.8" font-family="sans-serif" text-anchor="middle"><text x="2.4" y="3.5">&#9733;</text><text x="7.2" y="3.5">&#9733;</text><text x="12" y="3.5">&#9733;</text><text x="16.8" y="3.5">&#9733;</text><text x="21.6" y="3.5">&#9733;</text><text x="4.8" y="7">&#9733;</text><text x="9.6" y="7">&#9733;</text><text x="14.4" y="7">&#9733;</text><text x="19.2" y="7">&#9733;</text><text x="2.4" y="10.5">&#9733;</text><text x="7.2" y="10.5">&#9733;</text><text x="12" y="10.5">&#9733;</text><text x="16.8" y="10.5">&#9733;</text><text x="21.6" y="10.5">&#9733;</text><text x="4.8" y="14">&#9733;</text><text x="9.6" y="14">&#9733;</text><text x="14.4" y="14">&#9733;</text><text x="19.2" y="14">&#9733;</text><text x="2.4" y="17.5">&#9733;</text><text x="7.2" y="17.5">&#9733;</text><text x="12" y="17.5">&#9733;</text><text x="16.8" y="17.5">&#9733;</text><text x="21.6" y="17.5">&#9733;</text><text x="4.8" y="21">&#9733;</text><text x="9.6" y="21">&#9733;</text><text x="14.4" y="21">&#9733;</text><text x="19.2" y="21">&#9733;</text></g></svg></div>
                    <h1 class="logo">Only<span class="a">Vance</span>28</h1>
                </div>
                <p class="tagline">Every article. Every day. Automatically collected.</p>
            </div>
            <div class="hdr-right">
                <div class="cta-row">
                    <input type="email" class="cta-email" placeholder="Get the daily Vance briefing" id="emailIn">
                    <button class="cta-btn" id="emailBtn">Subscribe</button>
                </div>
                <p class="hdr-meta">''' + total + ''' articles &middot; Started on March 27, 2026 - Updated ''' + build_time + '''</p>
            </div>
        </div>
    </div>
</header>

<div class="soc-bar">
    <div class="soc-track">
        <a href="https://x.com/JDVance" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg><span class="platform">X / Twitter</span><span class="handle">@JDVance</span></div>
            <p class="soc-card-text">Republicans are about to vote (again) to reopen the government and every Democrat outside of a few sensible moderates will vote to keep it shut.</p>
            <span class="soc-card-foot">Follow on X for latest posts</span>
        </a>
        <a href="https://x.com/VP" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg><span class="platform">X / Official</span><span class="handle">@VP</span></div>
            <p class="soc-card-text">Vice President Vance celebrates the Administration&#39;s successful deportation efforts: &quot;When you restore sanity at the border it shows up everywhere.&quot;</p>
            <span class="soc-card-foot">Official VP account</span>
        </a>
        <a href="https://www.instagram.com/jdvance/" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/></svg><span class="platform">Instagram</span><span class="handle">@jdvance</span></div>
            <p class="soc-card-text">Behind the scenes at the White House. Family moments, official duties, and life as Vice President.</p>
            <span class="soc-card-foot">Photos &amp; Stories</span>
        </a>
        <a href="https://www.tiktok.com/@jd" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.46V13a8.28 8.28 0 005.58 2.15V11.7a4.79 4.79 0 01-3.24-1.26V6.69h3.24z"/></svg><span class="platform">TikTok</span><span class="handle">@jd</span></div>
            <p class="soc-card-text">&quot;We&#39;re relaunching the VP&#39;s TikTok page. We&#39;ll update y&#39;all on what&#39;s going on in the White House.&quot;</p>
            <span class="soc-card-foot">2.9M Followers</span>
        </a>
        <a href="https://truthsocial.com/@JDVance1" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-4H7l6-8v4h4l-6 8z"/></svg><span class="platform">Truth Social</span><span class="handle">@JDVance1</span></div>
            <p class="soc-card-text">Christian, husband, dad. Vice President of the United States. Follow for direct updates and commentary.</p>
            <span class="soc-card-foot">Truth Social</span>
        </a>
        <a href="https://www.facebook.com/VicePresident/" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg><span class="platform">Facebook</span><span class="handle">VP Page</span></div>
            <p class="soc-card-text">50th Vice President of the United States. Proud to serve the American people with President Donald J. Trump.</p>
            <span class="soc-card-foot">4.8M Likes</span>
        </a>
        <a href="https://x.com/JDVance" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg><span class="platform">X / Twitter</span><span class="handle">@JDVance</span></div>
            <p class="soc-card-text">Republicans are about to vote (again) to reopen the government and every Democrat outside of a few sensible moderates will vote to keep it shut.</p>
            <span class="soc-card-foot">Follow on X for latest posts</span>
        </a>
        <a href="https://x.com/VP" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg><span class="platform">X / Official</span><span class="handle">@VP</span></div>
            <p class="soc-card-text">Vice President Vance celebrates the Administration&#39;s successful deportation efforts: &quot;When you restore sanity at the border it shows up everywhere.&quot;</p>
            <span class="soc-card-foot">Official VP account</span>
        </a>
        <a href="https://www.instagram.com/jdvance/" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/></svg><span class="platform">Instagram</span><span class="handle">@jdvance</span></div>
            <p class="soc-card-text">Behind the scenes at the White House. Family moments, official duties, and life as Vice President.</p>
            <span class="soc-card-foot">Photos &amp; Stories</span>
        </a>
        <a href="https://www.tiktok.com/@jd" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.46V13a8.28 8.28 0 005.58 2.15V11.7a4.79 4.79 0 01-3.24-1.26V6.69h3.24z"/></svg><span class="platform">TikTok</span><span class="handle">@jd</span></div>
            <p class="soc-card-text">&quot;We&#39;re relaunching the VP&#39;s TikTok page. We&#39;ll update y&#39;all on what&#39;s going on in the White House.&quot;</p>
            <span class="soc-card-foot">2.9M Followers</span>
        </a>
        <a href="https://truthsocial.com/@JDVance1" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-4H7l6-8v4h4l-6 8z"/></svg><span class="platform">Truth Social</span><span class="handle">@JDVance1</span></div>
            <p class="soc-card-text">Christian, husband, dad. Vice President of the United States. Follow for direct updates and commentary.</p>
            <span class="soc-card-foot">Truth Social</span>
        </a>
        <a href="https://www.facebook.com/VicePresident/" target="_blank" class="soc-card">
            <div class="soc-card-hdr"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg><span class="platform">Facebook</span><span class="handle">VP Page</span></div>
            <p class="soc-card-text">50th Vice President of the United States. Proud to serve the American people with President Donald J. Trump.</p>
            <span class="soc-card-foot">4.8M Likes</span>
        </a>
    </div>
</div>

<div class="crs">
    <div class="crs-track">''' + carousel_track + '''</div>
</div>

<div class="tb">
    <div class="sb">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" class="si" placeholder="Search headlines..." id="si">
    </div>
    <select class="sel" id="srcF"><option value="">All Sources</option><option value="Vance Social Media" class="soc-opt" style="color:#b8322a;font-weight:bold">&#9733; Vance's Social Media</option></select>
    <select class="sel" id="topicF"><option value="">All Topics</option></select>
    <div class="pills">
        <button class="pill on" data-r="all">All</button>
        <button class="pill" data-r="today">Today</button>
        <button class="pill" data-r="week">Week</button>
        <button class="pill" data-r="month">Month</button>
    </div>
    <div class="bias-pills">
        <button class="bpill" data-b="L" style="color:#4a90d9;border-color:#4a90d9">Left ''' + str(bias_count_L) + '''</button>
        <button class="bpill" data-b="LL" style="color:#7bb3e0;border-color:#7bb3e0">Leans L ''' + str(bias_count_LL) + '''</button>
        <button class="bpill" data-b="C" style="color:#a0a090;border-color:#a0a090">Center ''' + str(bias_count_C) + '''</button>
        <button class="bpill" data-b="LR" style="color:#e09070;border-color:#e09070">Leans R ''' + str(bias_count_LR) + '''</button>
        <button class="bpill" data-b="R" style="color:#d94a4a;border-color:#d94a4a">Right ''' + str(bias_count_R) + '''</button>
    </div>
    <span class="count" id="cnt">''' + total + ''' articles &middot; ''' + str(source_count) + ''' sources &middot; <a href="#" id="suggestBtn" style="color:var(--accent);text-decoration:none">Missing a source?</a></span>
</div>

<main class="main">
    <div class="grid" id="g">''' + cards_html + '''
    </div>
</main>

<footer class="ft">
    <div class="ft-inner">
        <div class="ft-grid">
            <div class="ft-col">
                <h4>OnlyVance28</h4>
                <p>The most comprehensive JD Vance news aggregator. Every article from every source, automatically collected daily with political bias ratings.</p>
            </div>
            <div class="ft-col">
                <h4>Topics</h4>
                <a href="#" onclick="document.getElementById('topicF').value='Iran';document.getElementById('topicF').dispatchEvent(new Event('change'));window.scrollTo(0,0);return false">Iran &amp; Foreign Policy</a>
                <a href="#" onclick="document.getElementById('topicF').value='2028 Race';document.getElementById('topicF').dispatchEvent(new Event('change'));window.scrollTo(0,0);return false">2028 Presidential Race</a>
                <a href="#" onclick="document.getElementById('topicF').value='Immigration';document.getElementById('topicF').dispatchEvent(new Event('change'));window.scrollTo(0,0);return false">Immigration</a>
                <a href="#" onclick="document.getElementById('topicF').value='Economy';document.getElementById('topicF').dispatchEvent(new Event('change'));window.scrollTo(0,0);return false">Economy</a>
                <a href="#" onclick="document.getElementById('topicF').value='Military';document.getElementById('topicF').dispatchEvent(new Event('change'));window.scrollTo(0,0);return false">Military &amp; Defense</a>
            </div>
            <div class="ft-col">
                <h4>Contact</h4>
                <a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a>
                <a href="mailto:contact@onlyvance28.com?subject=Suggest%20a%20Source">Suggest a missing source</a>
                <a href="mailto:contact@onlyvance28.com?subject=Bias%20Rating%20Correction">Report a bias rating</a>
                <p style="margin-top:.5rem">Bias ratings based on <a href="https://www.allsides.com/media-bias" target="_blank">AllSides</a>.</p>
            </div>
        </div>
        <div class="ft-bottom">
            <p>OnlyVance28.com &mdash; Automated news aggregation. Headlines link to original sources. Not affiliated with any political campaign, party, or government entity.</p>
            <p style="margin-top:.4rem"><a href="/disclaimer.html">Disclaimer &amp; Terms</a> &middot; <a href="mailto:contact@onlyvance28.com">Contact</a></p>
        </div>
    </div>
</footer>

<div class="modal-overlay" id="modal">
    <div class="modal">
        <button class="modal-close" id="modalClose">&times;</button>
        <div class="modal-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </div>
        <h2>You're In.</h2>
        <p>The daily Vance briefing is on its way.</p>
        <p style="margin-top:0">Every morning, the top stories about JD Vance,<br>delivered straight to your inbox.</p>
        <div class="email-show" id="modalEmail"></div>
        <p class="modal-sub">Unsubscribe anytime. No spam, ever.</p>
    </div>
</div>

<div class="smodal-overlay" id="suggestModal">
    <div class="smodal">
        <button class="smodal-close" id="suggestClose">&times;</button>
        <div class="smodal-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
        </div>
        <h2>Suggest a Source</h2>
        <p class="smodal-sub">Know a news outlet covering JD Vance that we're missing? We'll add it within 24 hours.</p>
        <div id="suggestForm" class="smodal-form">
            <div class="smodal-field">
                <label>Source Name</label>
                <input type="text" id="sugName" placeholder="e.g. The Daily Wire">
            </div>
            <div class="smodal-field">
                <label>Website URL</label>
                <input type="url" id="sugUrl" placeholder="e.g. https://dailywire.com">
            </div>
            <div class="smodal-field">
                <label>Political Leaning (optional)</label>
                <select id="sugBias">
                    <option value="">Not sure</option>
                    <option value="Left">Left</option>
                    <option value="Leans Left">Leans Left</option>
                    <option value="Center">Center</option>
                    <option value="Leans Right">Leans Right</option>
                    <option value="Right">Right</option>
                </select>
            </div>
            <div class="smodal-field">
                <label>Your Email (optional)</label>
                <input type="email" id="sugEmail" placeholder="So we can let you know when it's added">
            </div>
            <button class="smodal-submit" id="sugSubmit">Submit Source</button>
        </div>
        <div id="suggestThanks" class="smodal-thanks">
            <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#2a9d5c,#34c06e);display:flex;align-items:center;justify-content:center;margin:1rem auto">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" style="width:28px;height:28px"><path d="M20 6L9 17l-5-5"/></svg>
            </div>
            <h2 style="margin-top:.5rem">Source Submitted!</h2>
            <p style="font-size:.85rem;color:#6b6560;margin-top:.4rem">We'll review it and add it to OnlyVance28 within 24 hours.</p>
        </div>
    </div>
</div>

<script>
(function(){
    const cards=Array.from(document.querySelectorAll('.card'));
    const g=document.getElementById('g');
    const si=document.getElementById('si');
    const srcF=document.getElementById('srcF');
    const topicF=document.getElementById('topicF');
    const pills=document.querySelectorAll('.pill');
    const bpills=document.querySelectorAll('.bpill');
    const cnt=document.getElementById('cnt');
    const meta=''' + article_meta + ''';
    const srcs=''' + sources_json + ''';
    const topics=''' + topics_json + ''';
    const srcCounts=''' + source_counts_json + ''';
    const topicCounts=''' + topic_counts_json + ''';

    srcs.forEach(s=>{if(s==='Vance Social Media')return;const o=document.createElement('option');o.value=s;o.textContent=s+(srcCounts[s]?' ('+srcCounts[s]+')':'');srcF.appendChild(o)});
    topics.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t+(topicCounts[t]?' ('+topicCounts[t]+')':'');topicF.appendChild(o)});

    let dateRange='all';
    let activeBias=new Set(); // empty = show all

    function filter(){
        const q=si.value.toLowerCase();
        const src=srcF.value;
        const topic=topicF.value;
        const now=new Date();
        let vis=0;
        cards.forEach((c,i)=>{
            const m=meta[i];
            const t=c.querySelector('.card-title').textContent.toLowerCase();
            let ok=true;
            if(q&&!t.includes(q)&&!m.source.toLowerCase().includes(q))ok=false;
            if(src&&m.source!==src)ok=false;
            if(topic&&m.topic!==topic)ok=false;
            if(activeBias.size>0&&!activeBias.has(m.bias))ok=false;
            if(dateRange!=='all'&&m.published){
                const d=(now-new Date(m.published))/864e5;
                if(dateRange==='today'&&d>1)ok=false;
                if(dateRange==='week'&&d>7)ok=false;
                if(dateRange==='month'&&d>30)ok=false;
            }
            c.style.display=ok?'':'none';
            if(ok)vis++;
        });
        cnt.textContent=vis+' article'+(vis!==1?'s':'');
        let nr=g.querySelector('.no-res');
        if(!vis){
            if(!nr){nr=document.createElement('div');nr.className='no-res';nr.innerHTML='<p>No articles match your filters.</p>';g.appendChild(nr)}
            nr.style.display='';
        }else if(nr)nr.style.display='none';
    }

    si.addEventListener('input',filter);
    srcF.addEventListener('change',filter);
    topicF.addEventListener('change',filter);
    pills.forEach(p=>p.addEventListener('click',()=>{pills.forEach(x=>x.classList.remove('on'));p.classList.add('on');dateRange=p.dataset.r;filter()}));

    // Multi-select bias: toggle on/off, empty = show all
    bpills.forEach(p=>p.addEventListener('click',()=>{
        const b=p.dataset.b;
        if(activeBias.has(b)){
            activeBias.delete(b);
            p.classList.remove('on');
            p.style.background='';
        }else{
            activeBias.add(b);
            p.classList.add('on');
            p.style.background=p.style.borderColor;
        }
        filter();
    }));

    // Newsletter modal
    const modal=document.getElementById('modal');
    const modalEmail=document.getElementById('modalEmail');
    document.getElementById('modalClose').addEventListener('click',()=>modal.classList.remove('show'));
    modal.addEventListener('click',(e)=>{if(e.target===modal)modal.classList.remove('show')});

    document.getElementById('emailBtn').addEventListener('click',()=>{
        const e=document.getElementById('emailIn').value.trim();
        if(e&&e.includes('@')&&e.includes('.')){
            modalEmail.textContent=e;
            modal.classList.add('show');
            document.getElementById('emailIn').value='';
            // TODO: Replace with Mailchimp/Buttondown POST
            // fetch('https://YOUR_MAILCHIMP_FORM_URL',{method:'POST',body:new URLSearchParams({EMAIL:e})});
        }
    });

    // Lazy load images with IntersectionObserver
    const lazyObs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const bg = el.dataset.bg;
                if (bg) {
                    const img = new Image();
                    img.onload = () => { el.style.backgroundImage = 'url(' + bg + ')'; el.classList.add('loaded'); };
                    img.onerror = () => { el.classList.add('card-img-empty'); };
                    img.src = bg;
                }
                lazyObs.unobserve(el);
            }
        });
    }, { rootMargin: '200px' });
    document.querySelectorAll('.card-img-lazy').forEach(el => lazyObs.observe(el));

    // Suggest source modal
    const sugModal=document.getElementById('suggestModal');
    document.getElementById('suggestBtn').addEventListener('click',(e)=>{e.preventDefault();sugModal.classList.add('show')});
    document.getElementById('suggestClose').addEventListener('click',()=>sugModal.classList.remove('show'));
    sugModal.addEventListener('click',(e)=>{if(e.target===sugModal)sugModal.classList.remove('show')});

    document.getElementById('sugSubmit').addEventListener('click',()=>{
        const name=document.getElementById('sugName').value.trim();
        const url=document.getElementById('sugUrl').value.trim();
        const bias=document.getElementById('sugBias').value;
        const email=document.getElementById('sugEmail').value.trim();
        if(!name){document.getElementById('sugName').focus();return}
        // Send via mailto (works without backend)
        const body='Source name: '+name+'%0AURL: '+url+'%0ABias: '+(bias||'Not specified')+'%0ASubmitter email: '+(email||'Not provided');
        window.open('mailto:contact@onlyvance28.com?subject=Source%20Suggestion:%20'+encodeURIComponent(name)+'&body='+body,'_blank');
        // Show thanks
        document.getElementById('suggestForm').classList.add('hide');
        document.getElementById('suggestThanks').classList.add('show');
        // Reset after 3s
        setTimeout(()=>{
            sugModal.classList.remove('show');
            setTimeout(()=>{
                document.getElementById('suggestForm').classList.remove('hide');
                document.getElementById('suggestThanks').classList.remove('show');
                document.getElementById('sugName').value='';
                document.getElementById('sugUrl').value='';
                document.getElementById('sugBias').value='';
                document.getElementById('sugEmail').value='';
            },300);
        },2500);
    });
})();
</script>
</body>
</html>'''


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=== OnlyVance28 Build v5 ===")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    all_articles = []

    # 1. Google News RSS (broad coverage)
    for query in QUERIES:
        print(f"\nGoogle News: '{query}'...")
        arts = fetch_rss(query)
        print(f"  Found {len(arts)} articles")
        all_articles.extend(arts)

    # 2. Direct outlet RSS feeds (targeted major US sources)
    print(f"\nDirect feeds ({len(DIRECT_FEEDS)} outlets)...")
    direct_arts = fetch_direct_feeds()
    print(f"  Found {len(direct_arts)} Vance-related articles from direct feeds")
    all_articles.extend(direct_arts)

    # 3. Deduplicate
    all_articles = deduplicate(all_articles)
    print(f"\nTotal unique (before filter): {len(all_articles)}")

    # 4. US-only filter
    before = len(all_articles)
    all_articles = [a for a in all_articles if is_us_source(a)]
    print(f"US-only filter: {before} -> {len(all_articles)} (dropped {before - len(all_articles)} international)")

    # 5. Inject Vance's social media posts
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    social_posts = [
        {
            "title": "Republicans are about to vote (again) to reopen the government and every Democrat outside of a few sensible moderates will vote to keep it shut. This is the basic fact of the shutdown.",
            "source": "Vance Social Media",
            "platform": "X (@JDVance)",
            "link": "https://x.com/JDVance",
            "source_url": "https://x.com",
            "source_domain": "x.com",
        },
        {
            "title": "When you restore sanity at the border it shows up everywhere. Wages are finally growing, inflation is half of what it was under Democrats.",
            "source": "Vance Social Media",
            "platform": "X (@VP)",
            "link": "https://x.com/VP",
            "source_url": "https://x.com",
            "source_domain": "x.com",
        },
        {
            "title": "We're relaunching the VP's TikTok page. I got a little lazy the last few months, I was focused on the job of being VP, not enough on TikToks. That's about to change.",
            "source": "Vance Social Media",
            "platform": "TikTok (@jd)",
            "link": "https://www.tiktok.com/@jd",
            "source_url": "https://www.tiktok.com",
            "source_domain": "www.tiktok.com",
        },
        {
            "title": "Christian, husband, dad. Vice President of the United States. Proud to serve the American people with President Donald J. Trump.",
            "source": "Vance Social Media",
            "platform": "Facebook",
            "link": "https://www.facebook.com/VicePresident/",
            "source_url": "https://www.facebook.com",
            "source_domain": "www.facebook.com",
        },
        {
            "title": "Follow for direct updates and commentary. Christian, husband, dad. Vice President of the United States.",
            "source": "Vance Social Media",
            "platform": "Truth Social (@JDVance1)",
            "link": "https://truthsocial.com/@JDVance1",
            "source_url": "https://truthsocial.com",
            "source_domain": "truthsocial.com",
        },
    ]
    for i, sp in enumerate(social_posts):
        sp_article = {
            "id": hashlib.md5(sp["title"].encode()).hexdigest()[:12],
            "title": html_module.escape(sp["title"]),
            "source": sp["source"],
            "source_url": sp["source_url"],
            "source_domain": sp["source_domain"],
            "link": sp["link"],
            "published": (now - timedelta(hours=i*2)).isoformat(),
            "published_display": (now - timedelta(hours=i*2)).strftime("%b %d, %Y"),
            "query": "social",
            "image": "",
            "real_url": sp["link"],
            "bias": "?",
            "topic": "General",
        }
        all_articles.insert(i, sp_article)
    print(f"Added {len(social_posts)} social media posts")

    # 6. Sort and limit
    all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)
    all_articles = all_articles[:MAX_ARTICLES]

    # 7. Stats
    from collections import Counter
    bc = Counter(a["bias"] for a in all_articles)
    sc = Counter(a["source"] for a in all_articles)
    print(f"\nBias breakdown: {dict(bc)}")
    print(f"Unique sources: {len(sc)}")

    # 8. Enrich (resolve URLs, fetch images)
    print(f"\nEnriching {len(all_articles)} articles...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        all_articles = list(ex.map(enrich_article, all_articles))
    img_count = sum(1 for a in all_articles if a.get("image"))
    print(f"  Images: {img_count}/{len(all_articles)}")

    build_time = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    html_content = generate_html(all_articles, build_time)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\nGenerated: {OUTPUT_FILE}")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=2)
    print(f"Saved: {DATA_FILE}")

    # 10. Generate topic pages
    from collections import Counter
    topic_counts_all = Counter(a.get("topic","General") for a in all_articles)
    topics_dir = os.path.join(OUTPUT_DIR, "topics")
    os.makedirs(topics_dir, exist_ok=True)
    topic_pages = []
    for topic_name, count in topic_counts_all.most_common():
        if topic_name == "General" or count < 2:
            continue
        slug = topic_name.lower().replace(" & ", "-").replace(" ", "-")
        topic_articles = [a for a in all_articles if a.get("topic") == topic_name]
        sources_in_topic = set(a["source"] for a in topic_articles)
        bias_in_topic = Counter(a["bias"] for a in topic_articles)

        # Build article list HTML
        article_list = ""
        for a in topic_articles[:30]:
            link = a.get("real_url") or a["link"]
            bias_l = BIAS_LABELS.get(a.get("bias","?"), "Unrated")
            bias_c = BIAS_COLORS.get(a.get("bias","?"), "#555")
            img = ""
            if a.get("image"):
                img = f'<img src="{a["image"]}" alt="" style="width:80px;height:55px;object-fit:cover;border-radius:6px;flex-shrink:0">'
            article_list += f'''<a href="{link}" target="_blank" rel="noopener noreferrer" style="display:flex;gap:.8rem;align-items:center;padding:.7rem 0;border-bottom:1px solid #e2ddd5;text-decoration:none;color:#1a1714">
                {img}
                <div style="flex:1;min-width:0">
                    <div style="font-size:.65rem;font-weight:600;text-transform:uppercase;color:#b8322a;margin-bottom:.15rem">{a["source"]} <span style="background:{bias_c};color:#fff;padding:.1rem .35rem;border-radius:100px;font-size:.55rem;margin-left:.3rem">{bias_l}</span></div>
                    <div style="font-family:\'Playfair Display\',Georgia,serif;font-size:.88rem;font-weight:700;line-height:1.3">{a["title"]}</div>
                    <div style="font-size:.65rem;color:#9e9790;margin-top:.2rem">{a["published_display"]}</div>
                </div>
            </a>'''

        topic_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JD Vance &amp; {topic_name} — Latest News | OnlyVance28</title>
    <meta name="description" content="{count} articles about JD Vance and {topic_name} from {len(sources_in_topic)} sources. See how Left, Center, and Right media cover Vance on {topic_name}.">
    <link rel="canonical" href="https://onlyvance28.com/topics/{slug}.html">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'DM Sans',sans-serif;background:#f6f4f0;color:#1a1714;max-width:800px;margin:0 auto;padding:2rem 1.5rem}}
        .back{{font-size:.8rem;color:#6b6560;text-decoration:none;display:inline-flex;align-items:center;gap:.3rem;margin-bottom:1.5rem}}
        .back:hover{{color:#1a1714}}
        h1{{font-family:'Playfair Display',Georgia,serif;font-size:1.8rem;font-weight:900;margin-bottom:.3rem}}
        h1 span{{color:#b8322a}}
        .meta{{font-size:.82rem;color:#6b6560;margin-bottom:1.5rem;line-height:1.6}}
        .meta strong{{color:#1a1714}}
        .bias-bar{{display:flex;gap:.6rem;margin-bottom:1.5rem;flex-wrap:wrap}}
        .bias-tag{{font-size:.72rem;font-weight:600;padding:.25rem .6rem;border-radius:100px;color:#fff}}
        .articles{{margin-bottom:2rem}}
        .ft{{font-size:.7rem;color:#9e9790;border-top:1px solid #e2ddd5;padding-top:1rem}}
        .ft a{{color:#6b6560}}
    </style>
<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-6FJK6HBH8C"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-6FJK6HBH8C");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to OnlyVance28</a>
    <h1>Vance &amp; <span>{topic_name}</span></h1>
    <p class="meta">
        <strong>{count}</strong> articles from <strong>{len(sources_in_topic)}</strong> sources.
        Updated {build_time}.
    </p>
    <div class="bias-bar">'''

        for bias_key, bias_label_name in [("L","Left"),("LL","Leans Left"),("C","Center"),("LR","Leans Right"),("R","Right")]:
            bc = bias_in_topic.get(bias_key, 0)
            if bc > 0:
                topic_html += f'<span class="bias-tag" style="background:{BIAS_COLORS[bias_key]}">{bias_label_name}: {bc}</span>'

        topic_html += f'''
    </div>
    <div class="articles">{article_list}</div>
    <div class="ft">
        <p><a href="/">OnlyVance28.com</a> — Automated news aggregation. <a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a></p>
    </div>
</body>
</html>'''
        filepath = os.path.join(topics_dir, f"{slug}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(topic_html)
        topic_pages.append(slug)
    print(f"Generated {len(topic_pages)} topic pages: {', '.join(topic_pages)}")

    # 11. Generate "The Vance Daily" briefing page
    daily_dir = os.path.join(OUTPUT_DIR, "daily")
    os.makedirs(daily_dir, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_display = datetime.now(timezone.utc).strftime("%B %d, %Y")

    bias_summary_parts = []
    bc2 = Counter(a["bias"] for a in all_articles if a["source"] != "Vance Social Media")
    for bk, bl in [("L","Left"),("LL","Leans Left"),("C","Center"),("LR","Leans Right"),("R","Right")]:
        if bc2.get(bk, 0) > 0:
            bias_summary_parts.append(f"{bl}: {bc2[bk]}")

    top_topics_list = [t for t in Counter(a["topic"] for a in all_articles).most_common(5) if t[0] != "General"]

    # Try to generate briefing with Claude API
    briefing_text = ""
    top_headlines = [a for a in all_articles if a["source"] != "Vance Social Media"][:15]
    headline_list = "\n".join(f"- {a['title']} ({a['source']}, {BIAS_LABELS.get(a['bias'],'Unrated')})" for a in top_headlines)

    try:
        import urllib.request, json as j2
        api_body = j2.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": f"""You are writing "The Vance Daily" — a short, punchy morning briefing about JD Vance for {today_display}. Based on these top headlines from today:

{headline_list}

Write a briefing with:
1. A one-sentence opener that captures the day's biggest Vance story
2. "Top Stories" section: 4-5 of the most important headlines, each as one tight sentence summarizing the story (not just repeating the headline). Include the source name.
3. "Left vs Right" section: 2-3 sentences noting how Left-leaning and Right-leaning outlets are framing Vance differently today
4. A one-line sign-off

Keep it under 250 words. Write like a sharp newsletter editor — conversational, direct, no filler. Do not use em dashes."""}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=api_body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
            }
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = j2.loads(resp.read())
        briefing_text = result["content"][0]["text"]
        print("  Generated AI briefing")
    except Exception as e:
        print(f"  AI briefing failed ({e}), using template")

    # Fallback if API fails: build a simple but readable briefing
    if not briefing_text:
        top5 = top_headlines[:5]
        lines = [f"<strong>{a['source']}</strong>: {a['title']}" for a in top5]
        briefing_text = f"Here are today's top stories about JD Vance.\n\n" + "\n\n".join(lines)
        briefing_text += f"\n\nToday's coverage skewed {bias_summary_parts[0] if bias_summary_parts else 'Center'} overall."

    # Convert markdown-ish to HTML paragraphs
    briefing_html_body = ""
    for line in briefing_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("**") and line.endswith("**"):
            briefing_html_body += f"<h2>{line.strip('*')}</h2>"
        elif line.startswith("# "):
            briefing_html_body += f"<h2>{line[2:]}</h2>"
        elif line.startswith("- "):
            briefing_html_body += f"<p style='padding-left:1rem;margin-bottom:.4rem'>&#8226; {line[2:]}</p>"
        else:
            briefing_html_body += f"<p>{line}</p>"

    # Top stories for the "read more" links
    top_story_links = ""
    for a in top_headlines[:8]:
        link = a.get("real_url") or a["link"]
        bias_l = BIAS_LABELS.get(a.get("bias","?"), "Unrated")
        bias_c = BIAS_COLORS.get(a.get("bias","?"), "#555")
        top_story_links += f'<a href="{link}" target="_blank" rel="noopener noreferrer" class="story-link"><span class="sl-source">{a["source"]} <span style="background:{bias_c};color:#fff;padding:.08rem .3rem;border-radius:100px;font-size:.55rem">{bias_l}</span></span><span class="sl-title">{a["title"]}</span></a>'

    daily_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Vance Daily — {today_display} | OnlyVance28</title>
    <meta name="description" content="Your daily JD Vance briefing for {today_display}. Top stories, media bias analysis, and what Left and Right are saying about the Vice President.">
    <link rel="canonical" href="https://onlyvance28.com/daily/{today}.html">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'DM Sans',sans-serif;background:#f6f4f0;color:#1a1714;max-width:680px;margin:0 auto;padding:2rem 1.5rem}}
        .back{{font-size:.8rem;color:#6b6560;text-decoration:none;display:inline-flex;align-items:center;gap:.3rem;margin-bottom:1.5rem}}
        .back:hover{{color:#1a1714}}
        .masthead{{text-align:center;margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:3px double #e2ddd5}}
        .masthead-flag{{font-size:1.5rem;margin-bottom:.5rem}}
        .masthead h1{{font-family:'Playfair Display',Georgia,serif;font-size:2rem;font-weight:900}}
        .masthead h1 span{{color:#b8322a}}
        .masthead .date{{font-size:.85rem;color:#6b6560;margin-top:.3rem}}
        .masthead .stats{{font-size:.75rem;color:#9e9790;margin-top:.4rem}}

        .briefing{{margin-bottom:2rem;font-size:.92rem;line-height:1.7;color:#2a2520}}
        .briefing h2{{font-family:'Playfair Display',Georgia,serif;font-size:1.15rem;font-weight:700;margin:1.5rem 0 .5rem;color:#1a1714;border-bottom:1px solid #e2ddd5;padding-bottom:.3rem}}
        .briefing p{{margin-bottom:.6rem}}

        .stories-section{{margin-bottom:2rem}}
        .stories-section h2{{font-family:'Playfair Display',Georgia,serif;font-size:1.1rem;margin-bottom:.8rem}}
        .story-link{{display:block;padding:.6rem 0;border-bottom:1px solid #ece8e2;text-decoration:none;color:inherit;transition:background .2s}}
        .story-link:hover{{background:#f0ede8;margin:0 -.5rem;padding-left:.5rem;padding-right:.5rem;border-radius:6px}}
        .sl-source{{display:block;font-size:.65rem;font-weight:600;text-transform:uppercase;color:#b8322a;margin-bottom:.15rem}}
        .sl-title{{font-size:.85rem;color:#1a1714;line-height:1.35}}

        .subscribe-box{{background:#fff;border:2px solid #b8322a;border-radius:12px;padding:1.5rem;text-align:center;margin-bottom:2rem}}
        .subscribe-box h3{{font-family:'Playfair Display',Georgia,serif;font-size:1rem;margin-bottom:.3rem}}
        .subscribe-box p{{font-size:.8rem;color:#6b6560;margin-bottom:.8rem}}
        .subscribe-box .cta-row{{display:flex;gap:.5rem;justify-content:center}}
        .subscribe-box input{{padding:.45rem .8rem;border-radius:6px;border:1px solid #e2ddd5;font-family:'DM Sans',sans-serif;font-size:.82rem;width:220px;outline:none}}
        .subscribe-box button{{padding:.45rem 1rem;border-radius:6px;border:none;background:#b8322a;color:#fff;font-family:'DM Sans',sans-serif;font-weight:600;font-size:.82rem;cursor:pointer}}

        .topics-list{{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:2rem}}
        .topics-list a{{padding:.3rem .7rem;border-radius:100px;border:1px solid #e2ddd5;font-size:.72rem;font-weight:500;color:#6b6560;text-decoration:none}}
        .topics-list a:hover{{border-color:#b8322a;color:#b8322a}}

        .ft{{font-size:.7rem;color:#9e9790;border-top:1px solid #e2ddd5;padding-top:1rem;text-align:center}}
        .ft a{{color:#6b6560}}
    </style>
<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-6FJK6HBH8C"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-6FJK6HBH8C");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to all articles</a>

    <div class="masthead">
        <div class="masthead-flag">&#127482;&#127480;</div>
        <h1>The <span>Vance</span> Daily</h1>
        <p class="date">{today_display}</p>
        <p class="stats">{len(all_articles)} articles &middot; {len(set(a['source'] for a in all_articles))} sources &middot; {', '.join(bias_summary_parts)}</p>
    </div>

    <div class="briefing">
        {briefing_html_body}
    </div>

    <div class="subscribe-box">
        <h3>Get The Vance Daily in your inbox</h3>
        <p>Every morning. The stories that matter. No spam.</p>
        <div class="cta-row">
            <input type="email" placeholder="your@email.com" id="dailyEmail">
            <button onclick="var e=document.getElementById('dailyEmail').value;if(e&&e.includes('@'))alert('Subscribed! The Vance Daily is on its way.')">Subscribe</button>
        </div>
    </div>

    <div class="stories-section">
        <h2>Today's Headlines</h2>
        {top_story_links}
    </div>

    <div>
        <h2 style="font-family:'Playfair Display',Georgia,serif;font-size:1rem;margin-bottom:.6rem">Explore by Topic</h2>
        <div class="topics-list">'''
    for tn, tc in top_topics_list:
        tslug = tn.lower().replace(" & ", "-").replace(" ", "-")
        daily_html += f'<a href="/topics/{tslug}.html">{tn} ({tc})</a>'
    daily_html += f'''
        </div>
    </div>

    <div class="ft">
        <p><a href="/">OnlyVance28.com</a> &middot; <a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a></p>
        <p style="margin-top:.3rem">Not affiliated with any political campaign.</p>
    </div>
</body>
</html>'''
    daily_path = os.path.join(daily_dir, f"{today}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(daily_html)
    print(f"Generated: The Vance Daily /daily/{today}.html")

    # 12. Generate Disclaimer & Terms page
    disclaimer_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Disclaimer &amp; Terms | OnlyVance28</title>
    <meta name="description" content="Legal disclaimer and terms of use for OnlyVance28.com news aggregator.">
    <link rel="canonical" href="https://onlyvance28.com/disclaimer.html">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'DM Sans',sans-serif;background:#f6f4f0;color:#1a1714;max-width:720px;margin:0 auto;padding:2rem 1.5rem}
        .back{font-size:.8rem;color:#6b6560;text-decoration:none;display:inline-flex;align-items:center;gap:.3rem;margin-bottom:1.5rem}
        .back:hover{color:#1a1714}
        h1{font-family:'Playfair Display',Georgia,serif;font-size:1.6rem;font-weight:900;margin-bottom:1.5rem}
        h2{font-family:'Playfair Display',Georgia,serif;font-size:1.05rem;font-weight:700;margin:1.8rem 0 .5rem}
        p{font-size:.88rem;line-height:1.7;color:#2a2520;margin-bottom:.8rem}
        a{color:#b8322a}
        .ft{font-size:.7rem;color:#9e9790;border-top:1px solid #e2ddd5;padding-top:1rem;margin-top:2rem}
    </style>
<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-6FJK6HBH8C"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-6FJK6HBH8C");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to OnlyVance28</a>
    <h1>Disclaimer &amp; Terms of Use</h1>

    <h2>What This Site Is</h2>
    <p>OnlyVance28.com is an automated news aggregation service. We collect headlines and links to articles about JD Vance from publicly available news sources and RSS feeds. We do not host, reproduce, or republish article content. All headlines link directly to the original publisher's website.</p>

    <h2>No Affiliation</h2>
    <p>OnlyVance28.com is not affiliated with, endorsed by, or connected to JD Vance, any political campaign, political party, government office, or any of the news organizations whose content we link to. This is an independent project.</p>

    <h2>Political Bias Ratings</h2>
    <p>The political bias labels displayed on this site (Left, Leans Left, Center, Leans Right, Right) are based on ratings published by <a href="https://www.allsides.com/media-bias" target="_blank">AllSides.com</a>, a third-party media bias rating organization. We report their classifications and do not make independent bias determinations. If you believe a rating is incorrect, please contact AllSides directly or <a href="mailto:contact@onlyvance28.com">let us know</a> and we will review it.</p>

    <h2>Headlines &amp; Fair Use</h2>
    <p>We display article headlines as short factual descriptions to identify linked content. Headlines are not copyrightable under US law as they are too brief to constitute original works of authorship. We link to the original source for every headline, driving traffic to the original publisher. If you are a publisher and would like your content removed from this aggregator, please contact us at <a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a> and we will remove it promptly.</p>

    <h2>No Warranty</h2>
    <p>This site is provided "as is" without warranty of any kind. We make no guarantees about the accuracy, completeness, or timeliness of the information displayed. We are not responsible for the content of linked third-party websites.</p>

    <h2>Social Media Content</h2>
    <p>Social media posts attributed to JD Vance are sourced from his publicly available accounts on X (Twitter), Instagram, TikTok, Truth Social, and Facebook. We display brief excerpts and link to the original posts. These are public statements by a public official.</p>

    <h2>User-Submitted Content</h2>
    <p>Source suggestions submitted through our site are used solely for improving our news coverage. We do not share your email address with third parties.</p>

    <h2>Takedown Requests</h2>
    <p>If you believe any content on this site infringes your rights, please contact us at <a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a> with details of the specific content and the basis for your concern. We will respond within 48 hours.</p>

    <h2>Contact</h2>
    <p><a href="mailto:contact@onlyvance28.com">contact@onlyvance28.com</a></p>

    <p style="font-size:.78rem;color:#9e9790;margin-top:1.5rem">Last updated: March 27, 2026</p>

    <div class="ft">
        <p><a href="/" style="color:#6b6560;text-decoration:none">OnlyVance28.com</a></p>
    </div>
</body>
</html>'''
    with open(os.path.join(OUTPUT_DIR, "disclaimer.html"), "w", encoding="utf-8") as f:
        f.write(disclaimer_html)
    print("Generated: disclaimer.html")

    # 13. Generate sitemap.xml (with all pages)
    sitemap_urls = [
        f'    <url><loc>https://onlyvance28.com/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
        f'    <url><loc>https://onlyvance28.com/daily/{today}.html</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>',
        f'    <url><loc>https://onlyvance28.com/disclaimer.html</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
    ]
    for slug in topic_pages:
        sitemap_urls.append(f'    <url><loc>https://onlyvance28.com/topics/{slug}.html</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(sitemap_urls) + '\n</urlset>'
    with open(os.path.join(OUTPUT_DIR, "sitemap.xml"), "w") as f:
        f.write(sitemap)

    # 13. Generate robots.txt
    robots = '''User-agent: *
Allow: /
Sitemap: https://onlyvance28.com/sitemap.xml
'''
    with open(os.path.join(OUTPUT_DIR, "robots.txt"), "w") as f:
        f.write(robots)

    print(f"Generated: sitemap.xml ({len(sitemap_urls)} URLs), robots.txt\n=== Done ===")


if __name__ == "__main__":
    main()
