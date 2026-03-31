#!/usr/bin/env python3
"""
The Vance Daily (thevancedaily.com) - v4
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
    # === TOP TIER (by US traffic) ===
    # LEFT / LEAN LEFT
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://feeds.washingtonpost.com/rss/politics",
    "https://feeds.npr.org/1014/rss.xml",  # NPR Politics
    "https://feeds.nbcnews.com/nbcnews/public/politics",
    "https://feeds.abcnews.com/abcnews/politicsheadlines",
    "https://www.cbsnews.com/latest/rss/politics",
    "https://feeds.politico.com/rss/politicopicks.xml",
    "https://www.latimes.com/politics/feed",
    "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
    "https://www.huffpost.com/section/politics/feed",
    "https://www.vox.com/rss/index.xml",
    "https://www.thedailybeast.com/feed",
    "https://www.msnbc.com/feeds/latest",
    "https://www.salon.com/feed/",
    "https://www.motherjones.com/feed/",
    "https://www.theatlantic.com/feed/all/",
    "https://feeds.newrepublic.com/feed/rss",
    "https://www.vanityfair.com/feed/rss",
    "https://www.rollingstone.com/politics/feed/",
    "https://feeds.bloomberg.com/politics/news.rss",
    
    # CENTER
    "https://feeds.reuters.com/reuters/politicsNews",
    "https://feeds.apnews.com/apnews/politics",
    "https://thehill.com/feed/",
    "https://www.axios.com/feeds/feed.rss",
    "https://www.usatoday.com/rss/news/nation/",
    "https://www.c-span.org/feeds/",
    "https://news.yahoo.com/rss/politics",
    "https://feeds.a]cnews.com/acnews/us",
    "https://www.newsweek.com/rss",
    "https://www.upi.com/rss/TopNews/",
    "https://time.com/feed/",
    "https://fortune.com/feed/",
    "https://www.cnbc.com/id/10000113/device/rss/rss.html",  # CNBC Politics
    "https://www.pbs.org/newshour/feeds/rss/headlines",
    "https://www.csmonitor.com/rss/all",
    
    # LEAN RIGHT / RIGHT
    "https://feeds.foxnews.com/foxnews/politics",
    "https://nypost.com/politics/feed/",
    "https://www.washingtontimes.com/rss/headlines/news/politics/",
    "https://www.washingtonexaminer.com/section/politics/feed",
    "https://www.dailywire.com/feeds/rss.xml",
    "https://www.breitbart.com/politics/feed/",
    "https://www.nationalreview.com/feed/",
    "https://thefederalist.com/feed/",
    "https://www.dailycaller.com/feed",
    "https://www.newsmax.com/rss/Politics/16/",
    "https://www.theblaze.com/feeds/feed.rss",
    "https://townhall.com/feeds/all.xml",
    "https://www.foxbusiness.com/feeds/rss/all",
    "https://www.oann.com/feed/",
    "https://justthenews.com/feed",
    "https://freebeacon.com/feed/",
    "https://www.redstate.com/feed/",
    "https://pjmedia.com/feed",
    "https://hotair.com/feed",
    "https://reason.com/feed/",  # Libertarian
]

MAX_ARTICLES = 200
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
    # Indian outlets
    "timesofindia.com", "timesofindia.indiatimes.com", "indiatimes.com",
    "singju.com", "singjupost.com", "thesingju", "india.com",
    "ndtv.com", "zeenews.india.com", "news18.com",
    # Other international
    "malaysiasun.com", "gbnews.com", "lbc.co.uk", "itv.com",
    "cbc.ca", "globalnews.ca", "thestar.com",
    "smh.com.au", "abc.net.au", "9news.com.au",
    "lavoce", "lavocedinewyork",
    "globalbanking", "gbaf",
    # More international
    "unherd.com", "politico.eu", "hungarianconservative.com",
    "middleeastmonitor.com", "thecatholicspirit.com",
    "rev.com", "arka.am", "voxnews.al", "voi.id",
    "irishstar.com", "channelstv.com", "i24news.tv",
    "rferl.org", "thetimes.com",
}

def get_region(article):
    """Classify article region: US, Europe, Asia, Middle East, etc."""
    domain = article.get("source_domain", "").lower()
    source = article.get("source", "").lower()
    
    # Europe
    eu_domains = ['.co.uk', '.uk', '.ie', '.fr', '.de', '.it', '.es', '.nl', '.be', '.at', '.ch', '.se', '.no', '.dk', '.fi', '.pt', '.pl', '.cz', '.hu', '.ro', '.bg', '.hr', '.gr']
    eu_names = {"unherd", "politico.eu", "irish star", "breakingnews.ie", "irishstar",
                "hungarian conservative", "premier christian news", "the times uk", "bbc",
                "the guardian", "telegraph", "sky news uk", "daily mail"}
    eu_site_domains = {"unherd.com", "politico.eu", "irishstar.com", "breakingnews.ie",
                       "hungarianconservative.com", "thetimes.com", "thetimes.co.uk"}
    
    # Asia
    asia_domains = ['.co.in', '.in', '.pk', '.jp', '.kr', '.cn', '.com.au', '.co.nz', '.ph', '.sg', '.my', '.id', '.th', '.vn', '.tw']
    asia_names = {"times of india", "ndtv", "firstpost", "wion", "wionews",
                  "singju post", "the singju post", "india times", "malaysia sun",
                  "voi.id", "channels television", "channelstv", "india tv news"}
    asia_site_domains = {"firstpost.com", "wionews.com", "channelstv.com", "voi.id",
                         "ndtv.com", "timesofindia.com", "indiatimes.com", "smh.com.au", "abc.net.au", "9news.com.au",
                         "indiatvnews.com", "india.com"}
    
    # Middle East
    me_names = {"al arabiya", "alarabiya", "i24news", "middle east monitor", "al jazeera", "jns", "jta",
                "times of israel"}
    me_site_domains = {"alarabiya.net", "i24news.tv", "middleeastmonitor.com", "aljazeera.com",
                       "timesofisrael.com"}
    me_domains = ['.il', '.ae', '.sa', '.qa', '.iq', '.ir']
    
    # Africa
    africa_domains = ['.co.za', '.ng', '.ke', '.eg', '.gh']
    
    # Americas (non-US)
    americas_domains = ['.ca', '.com.br', '.mx', '.ar', '.cl', '.co']
    americas_names = {"la voce di new york"}
    
    # Check domains
    for d in eu_site_domains:
        if d in domain: return "Europe"
    for d in asia_site_domains:
        if d in domain: return "Asia"
    for d in me_site_domains:
        if d in domain: return "Middle East"
    
    # Check source names
    for n in eu_names:
        if n in source: return "Europe"
    for n in asia_names:
        if n in source: return "Asia"
    for n in me_names:
        if n in source: return "Middle East"
    for n in americas_names:
        if n in source: return "Americas"
    
    # Check TLDs
    for tld in eu_domains:
        if domain.endswith(tld): return "Europe"
    for tld in asia_domains:
        if domain.endswith(tld): return "Asia"
    for tld in me_domains:
        if domain.endswith(tld): return "Middle East"
    for tld in africa_domains:
        if domain.endswith(tld): return "Africa"
    for tld in americas_domains:
        if domain.endswith(tld): return "Americas"
    
    # Check INTL_BLOCK for anything else international
    for blocked in INTL_BLOCK:
        if blocked in domain: return "International"
    
    return "US"

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
    """Fetch OG image with multiple fallback strategies."""
    headers_list = [
        {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
         'Accept-Language': 'en-US,en;q=0.5'},
        {'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'},
        {'User-Agent': 'Twitterbot/1.0'},
    ]
    for headers in headers_list:
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=10, context=SSL_CTX)
            raw = resp.read(120000)  # Read 120KB instead of 60KB
            html_text = raw.decode('utf-8', errors='ignore')
            parser = OGParser()
            parser.feed(html_text)
            img = parser.og.get('og:image') or parser.og.get('twitter:image') or parser.og.get('twitter:image:src', '')
            if img:
                if not img.startswith('http'):
                    p = urlparse(url)
                    img = f"{p.scheme}://{p.netloc}{img}"
                return img
        except:
            continue
    return ''


def clean_source_name(name):
    """Clean RSS feed titles into proper outlet names."""
    if not name:
        return name
    # HTML entity decode
    name = name.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    
    # DIRECT LOOKUP: catch all known messy patterns first (case-insensitive)
    KNOWN = {
        "politics - cbsnews.com": "CBS News",
        "politics – cbsnews.com": "CBS News",
        "politics - washington examiner": "Washington Examiner",
        "politics – washington examiner": "Washington Examiner",
        "politics – latest us political news & headlines | new york post": "New York Post",
        "politics - latest us political news & headlines | new york post": "New York Post",
        "the daily wire - breaking news, videos & podcasts": "The Daily Wire",
        "the daily wire – breaking news, videos & podcasts": "The Daily Wire",
        "latest political news on fox news": "Fox News",
        "nbc news politics": "NBC News",
        "cbs news politics": "CBS News",
        "abc news politics": "ABC News",
        "fox news politics": "Fox News",
        "fox news - latest news & headlines | fox news": "Fox News",
        "global banking & finance review": "Global Banking & Finance Review",
        "the hill news": "The Hill",
        "the washington times stories: politics": "Washington Times",
        "reuters connect": "Reuters",
        "cbsnews.com": "CBS News",
        "nbcnews.com": "NBC News",
        "abcnews.com": "ABC News",
        "foxnews.com": "Fox News",
        "nytimes.com": "New York Times",
        "washingtonpost.com": "Washington Post",
        "nypost.com": "New York Post",
        "al.com": "AL.com",
        "nj.com": "NJ.com",
        "silive.com": "SILive",
        "upi.com": "UPI",
        "ntd.com": "NTD News",
        "wng.org": "World Magazine",
        "tyla.com": "Tyla",
        "whas11.com": "WHAS11",
        "koin.com": "KOIN",
        "newschannel9.com": "NewsChannel 9",
        "newschannel 9": "NewsChannel 9",
        "islandernews.com": "Islander News",
        "elkintribune.com": "Elkin Tribune",
        "malaysiasun.com": "Malaysia Sun",
        "communitynewspapergroup.com": "Community Newspaper Group",
        "aol.com": "AOL News",
        "abc27.com": "ABC27",
        "kpic.com": "KPIC",
        "newsweek.com": "Newsweek",
        "stamfordadvocate.com": "Stamford Advocate",
        "wkyt.com": "WKYT",
        "politics": "Politics",  # bare "Politics" from CBS feed - will be overridden by feed title
        "nbc news politics": "NBC News",
        "bloomberg politics": "Bloomberg",
        "blaze media": "The Blaze",
        "the hill news": "The Hill",
        "the washington times stories: politics": "Washington Times",
        "reuters connect": "Reuters",
        "us weekly": "Us Weekly",
        "wsj.com": "Wall Street Journal",
        "wsj": "Wall Street Journal",
        "axios.com": "Axios",
        "salon.com": "Salon",
        "forbes.com": "Forbes",
        "thedailybeast.com": "The Daily Beast",
        "facebook.com": "Facebook",
        "bloomberg.com": "Bloomberg",
        "democracydocket.com": "Democracy Docket",
        "democrats.org": "Democrats.org",
        "factcheck.org": "FactCheck.org",
        "floridianpress.com": "The Floridian Press",
        "houstonchronicle.com": "Houston Chronicle",
        "houstonpublicmedia.org": "Houston Public Media",
        "nbcmiami.com": "NBC Miami",
        "newscentermaine.com": "NEWS CENTER Maine",
        "washingtonblade.com": "Washington Blade",
        "wisconsinexaminer.com": "Wisconsin Examiner",
        "people.com": "People",
        "cleveland.com": "Cleveland.com",
        "lehighvalleylive.com": "Lehigh Valley Live",
        "mlive.com": "MLive",
        "13wham.com": "13WHAM",
        "cbs17.com": "CBS 17",
        "kare11.com": "KARE 11",
        "wmur.com": "WMUR",
        "wfmz.com": "WFMZ",
        "wtol.com": "WTOL",
        "inkstickmedia.com": "Inkstick Media",
        "foxbusiness.com": "Fox Business",
        "latimes.com": "Los Angeles Times",
        "motherjones.com": "Mother Jones",
        "slate.com": "Slate",
        "thehill.com": "The Hill",
        "reuters.com": "Reuters",
        "reutersconnect.com": "Reuters",
        "politico.com": "Politico",
        "cnn.com": "CNN",
        "msn.com": "MSN",
        "usatoday.com": "USA Today",
        "nymag.com": "New York Magazine",
        "snopes.com": "Snopes",
        "vogue.com": "Vogue",
        "themarysue.com": "The Mary Sue",
        "washingtonexaminer.com": "Washington Examiner",
        "commondreams.org": "Common Dreams",
        "indystar.com": "IndyStar",
        "jsonline.com": "Milwaukee Journal Sentinel",
        "lgbtqnation.com": "LGBTQ Nation",
        "nbcphiladelphia.com": "NBC Philadelphia",
        "orlandosentinel.com": "Orlando Sentinel",
        "post-gazette.com": "Pittsburgh Post-Gazette",
        "newsobserver.com": "The News & Observer",
        "dailyherald.com": "Daily Herald",
        "cincinnati.com": "Cincinnati Enquirer",
        "nysun.com": "New York Sun",
        "statnews.com": "STAT News",
        "punchbowl.news": "Punchbowl News",
        "thenationaldesk.com": "The National Desk",
        "audacy.com": "Audacy",
        "ewtnnews.com": "EWTN News",
        "jta.org": "JTA",
        "jns.org": "JNS",
        "opensecrets.org": "OpenSecrets",
        "poynter.org": "Poynter",
        "edweek.org": "Education Week",
        "wwd.com": "WWD",
        "democracyforward.org": "Democracy Forward",
        "komonews.com": "KOMO News",
        "nationalreview.com": "National Review",
        "13abc.com": "13abc",
        "wcnc.com": "WCNC",
        "cbsaustin.com": "CBS Austin",
        "axios.com": "Axios",
    }
    name_clean = name.strip()
    if name_clean.lower() in KNOWN:
        return KNOWN[name_clean.lower()]
    
    # Check if the name CONTAINS a known messy pattern
    for pattern, clean_name in KNOWN.items():
        if pattern in name_clean.lower():
            return clean_name
    
    # HEURISTIC: if name has separators, try to extract the outlet name
    for sep in [" – ", " - ", " | ", " :: "]:
        if sep in name_clean:
            parts = [p.strip() for p in name_clean.split(sep)]
            generic_words = {"politics", "news", "breaking news", "latest", "opinion", 
                           "world", "us", "headlines", "stories", "home"}
            # Take the first part that isn't generic
            for p in parts:
                if p.lower() not in generic_words and len(p) > 2:
                    name_clean = p
                    break
    
    # Remove " stories:" suffixes  
    if " stories:" in name_clean:
        name_clean = name_clean.split(" stories:")[0].strip()
    if name_clean.lower().endswith(" stories"):
        name_clean = name_clean[:-8].strip()
    
    # Remove ® and similar
    name_clean = name_clean.replace("®", "").strip()
    
    # Final check against KNOWN with cleaned name
    if name_clean.lower() in KNOWN:
        return KNOWN[name_clean.lower()]
    
    # Auto-capitalize domain-style names (e.g. "foxbusiness.com" -> "Foxbusiness.com")
    # and also proper-case names that start with lowercase
    if name_clean and name_clean[0].islower():
        # If it looks like a domain (has a dot), try to make it presentable
        if '.' in name_clean:
            # Strip common TLDs to get the name part
            domain = name_clean
            for tld in ['.com', '.org', '.net', '.gov', '.io', '.news', '.am', '.al', '.id']:
                if domain.endswith(tld):
                    base = domain[:-len(tld)]
                    # Known patterns: fox9 -> FOX 9, abc11 -> ABC 11, nbc -> NBC
                    base_lower = base.lower()
                    # TV station call letters (3-4 uppercase letters + optional digits)
                    if re.match(r'^[a-z]{3,4}\d*$', base_lower) and len(base_lower) <= 8:
                        # Likely a TV station: WKYC, FOX9, ABC11
                        letters = re.match(r'^([a-z]+)(\d*)$', base_lower)
                        if letters:
                            return letters.group(1).upper() + ((' ' + letters.group(2)) if letters.group(2) else '') + tld
                    # Capitalize first letter of each word for others
                    return domain[0].upper() + domain[1:]
            # No known TLD matched, just capitalize
            return name_clean[0].upper() + name_clean[1:]
        else:
            # Not a domain, title-case it (e.g. "the indiana citizen" -> "The Indiana Citizen")
            return name_clean.title()
    
    return name_clean


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
        # Always strip source suffix from title (handles " - Source", " – Source", " | Source")
        for sep in [" - ", " – ", " — ", " | "]:
            if sep in title:
                parts = title.rsplit(sep, 1)
                suffix = parts[1].strip()
                # Only strip if suffix looks like a source name (< 50 chars, not too many words)
                if len(suffix) < 50 and len(suffix.split()) <= 6:
                    if not source_name:
                        source_name = suffix
                    title = parts[0].strip()
                    break

        article_id = hashlib.md5(title.encode()).hexdigest()[:12]
        source_name = clean_source_name(source_name)
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
            image_url = fetch_og_image(real_url)
            if image_url and image_url.startswith('http'):
                article["image"] = image_url
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
                            cleaned = clean_source_name(feed.feed.title)
                            a["source"] = html_module.escape(cleaned)
                            a["bias"] = get_bias(cleaned)
                        # Always re-clean source name (catches cases where process_entry set a messy name)
                        if a["source"]:
                            recleaned = clean_source_name(html_module.unescape(a["source"]))
                            a["source"] = html_module.escape(recleaned)
                            a["bias"] = get_bias(recleaned)
                        articles.append(a)
        except Exception as e:
            print(f"  Feed error {feed_url[:40]}: {e}")
    return articles


def deduplicate(articles):
    """Remove exact duplicates and near-duplicates (same source, similar title)."""
    seen_ids = set()
    seen_titles = []  # list of (normalized_title, source) tuples
    result = []
    for a in articles:
        # Skip exact ID duplicates
        if a["id"] in seen_ids:
            continue
        # Normalize title for fuzzy matching: lowercase, strip source suffixes, punctuation
        title = a.get("title", "").lower().strip()
        source = a.get("source", "").lower().strip()
        # Strip common suffixes like "- NBC News", "| Fox News", "– Washington Post"
        for sep in [" - ", " | ", " – ", " — "]:
            if sep in title:
                title = title.rsplit(sep, 1)[0].strip()
        # Remove punctuation for comparison
        norm = re.sub(r'[^a-z0-9 ]', '', title).strip()
        norm = re.sub(r'\s+', ' ', norm)
        # Check for near-duplicate: same first 60 chars of normalized title
        norm_key = norm[:60]
        is_dup = False
        for prev_norm, prev_source in seen_titles:
            if prev_norm[:60] == norm_key:
                is_dup = True
                break
        if is_dup:
            continue
        seen_ids.add(a["id"])
        seen_titles.append((norm, source))
        result.append(a)
    return result


# ── Social media scraping (X/Twitter via syndication API) ──
SOCIAL_ACCOUNTS = [
    {"handle": "JDVance", "platform": "X / Twitter", "label": "@JDVance", "url": "https://x.com/JDVance",
     "icon": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'},
    {"handle": "VP", "platform": "X / Official", "label": "@VP", "url": "https://x.com/VP",
     "icon": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'},
]

# Static social accounts (no free API/scraping available)
STATIC_SOCIAL = [
    {"platform": "Instagram", "label": "@jdvance", "url": "https://www.instagram.com/jdvance/",
     "icon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/></svg>',
     "foot": "Photos &amp; Stories"},
    {"platform": "TikTok", "label": "@jd", "url": "https://www.tiktok.com/@jd",
     "icon": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.46V13a8.28 8.28 0 005.58 2.15V11.7a4.79 4.79 0 01-3.24-1.26V6.69h3.24z"/></svg>',
     "foot": "2.9M Followers"},
    {"platform": "Truth Social", "label": "@JDVance1", "url": "https://truthsocial.com/@JDVance1",
     "icon": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-4H7l6-8v4h4l-6 8z"/></svg>',
     "foot": "Truth Social"},
    {"platform": "Facebook", "label": "VP Page", "url": "https://www.facebook.com/VicePresident/",
     "icon": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
     "foot": "4.8M Likes"},
]


def fetch_social_posts():
    """Fetch latest posts from X/Twitter via the syndication API (free, no key needed).
    Includes retry logic, varied User-Agents, and JSON cache fallback."""
    import time
    SOCIAL_CACHE = os.path.join(OUTPUT_DIR, "social_cache.json")
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
    ]
    all_posts = []
    for acct_idx, acct in enumerate(SOCIAL_ACCOUNTS):
        success = False
        # Add delay between accounts to avoid rate limits
        if acct_idx > 0:
            time.sleep(3)
        for attempt, ua in enumerate(USER_AGENTS):
            if success:
                break
            try:
                if attempt > 0:
                    time.sleep(2 * attempt)  # Backoff
                url = f'https://syndication.twitter.com/srv/timeline-profile/screen-name/{acct["handle"]}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Cache-Control': 'no-cache',
                })
                resp = urllib.request.urlopen(req, timeout=15, context=SSL_CTX)
                raw_html = resp.read().decode('utf-8', errors='ignore')
                match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw_html, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    entries = data.get('props', {}).get('pageProps', {}).get('timeline', {}).get('entries', [])
                    for entry in entries[:10]:  # Latest 10 per account
                        tweet = entry.get('content', {}).get('tweet', {})
                        text = tweet.get('text', '')
                        created = tweet.get('created_at', '')
                        tweet_id = tweet.get('id_str', '')
                        # Clean up t.co links from text
                        text_clean = re.sub(r'https?://t\.co/\S+', '', text).strip()
                        if not text_clean:
                            continue
                        # Parse date and skip posts older than 30 days
                        try:
                            dt = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y")
                            age_days = (datetime.now(timezone.utc) - dt).days
                            if age_days > 30:
                                continue
                            date_display = dt.strftime("%b %d, %Y - %I:%M %p")
                        except:
                            date_display = ""
                        all_posts.append({
                            "platform": acct["platform"],
                            "handle": acct["label"],
                            "url": f'https://x.com/{acct["handle"]}/status/{tweet_id}' if tweet_id else acct["url"],
                            "icon": acct["icon"],
                            "text": html_module.escape(text_clean[:280]),
                            "time": date_display,
                            "timestamp": created,
                            "foot": f'@{acct["handle"]}',
                        })
                    print(f"  @{acct['handle']}: {len(entries)} posts scraped (attempt {attempt+1})")
                    success = True
                else:
                    print(f"  @{acct['handle']}: no data (attempt {attempt+1})")
            except Exception as e:
                print(f"  @{acct['handle']}: attempt {attempt+1} failed - {e}")

    # Add static social accounts (no live data available)
    for s in STATIC_SOCIAL:
        all_posts.append({
            "platform": s["platform"],
            "handle": s["label"],
            "url": s["url"],
            "icon": s["icon"],
            "text": "",
            "time": "",
            "timestamp": "",
            "foot": s["foot"],
        })

    # Cache: save if we got X posts, load from cache if we didn't
    x_posts = [p for p in all_posts if p.get("timestamp")]
    if x_posts:
        try:
            with open(SOCIAL_CACHE, "w") as f:
                json.dump(x_posts, f)
            print(f"  Cached {len(x_posts)} X posts to {SOCIAL_CACHE}")
        except Exception as e:
            print(f"  Cache save failed: {e}")
    else:
        # Try loading from cache
        try:
            if os.path.exists(SOCIAL_CACHE):
                with open(SOCIAL_CACHE, "r") as f:
                    cached = json.load(f)
                # Insert cached posts before static ones
                static_posts = [p for p in all_posts if not p.get("timestamp")]
                all_posts = cached + static_posts
                print(f"  Loaded {len(cached)} cached X posts (live scrape failed)")
        except Exception as e:
            print(f"  Cache load failed: {e}")

    return all_posts


def generate_social_html(posts):
    """Generate the social card carousel HTML from scraped posts."""
    cards = ""
    for p in posts:
        # Skip cards with no post content (static accounts with no API)
        if not p.get("text"):
            continue
        ga_platform = p["platform"].replace("'", "\\'")
        ga_handle = p["handle"].replace("'", "\\'")
        time_html = f'<span class="soc-card-time"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>{p["time"]}</span>' if p.get("time") else ''
        cards += f'''<a href="{p["url"]}" target="_blank" class="soc-card" onclick="gtag('event','social_click',{{platform:'{ga_platform}',handle:'{ga_handle}'}})">
            <div class="soc-card-hdr">{p["icon"]}<span class="platform">{p["platform"]}</span><span class="handle">{p["handle"]}</span></div>
            <p class="soc-card-text">{p["text"]}</p>
            <div class="soc-card-foot"><span>{p["foot"]}</span>{time_html}</div>
        </a>'''
    # Duplicate for infinite scroll (no static cards - only real posts)
    return cards + cards


def generate_html(articles, build_time, social_posts=None, today=None, daily_dates=None):
    # Generate social carousel HTML
    social_html = generate_social_html(social_posts) if social_posts else ''
    sources = sorted(set(a["source"] for a in articles if a["source"]))
    sources_json = json.dumps(sources)
    topics = sorted(set(a["topic"] for a in articles if a["topic"]))
    topics_json = json.dumps(topics)
    article_meta = json.dumps([{
        "published": a["published"],
        "source": a["source"],
        "bias": a["bias"],
        "topic": a["topic"],
        "region": a.get("region", "US"),
    } for a in articles])

    # Counts for dropdowns and buttons
    from collections import Counter as Ctr
    source_counts_map = Ctr(a["source"] for a in articles)
    source_counts_json = json.dumps(dict(source_counts_map))
    topic_counts_map = Ctr(a["topic"] for a in articles)
    topic_counts_json = json.dumps(dict(topic_counts_map))
    bias_counts_map = Ctr(a["bias"] for a in articles if not a.get("source", "").startswith("Vance on "))
    bias_count_L = bias_counts_map.get("L", 0)
    bias_count_LL = bias_counts_map.get("LL", 0)
    bias_count_C = bias_counts_map.get("C", 0)
    bias_count_LR = bias_counts_map.get("LR", 0)
    bias_count_R = bias_counts_map.get("R", 0)
    region_counts = Ctr(a.get("region", "US") for a in articles if not a.get("source", "").startswith("Vance on "))
    region_us = region_counts.get("US", 0)
    region_counts_json = json.dumps(dict(region_counts))

    # Carousel
    seen_d = set()
    src_items = []
    for a in articles:
        d = a.get("source_domain", "")
        n = a.get("source", "")
        if d and d not in seen_d and n and not n.startswith("Vance on "):
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
        is_social = a.get("source", "").startswith("Vance on ")
        card_class = "card soc-card-item" if is_social else "card"

        if a.get("image"):
            fd = a.get("source_domain", "")
            img_html = f'<div class="card-img" data-fallback-domain="{fd}" data-fallback-name="{a["source"]}"><img src="{a["image"]}" alt="" loading="lazy" style="width:100%;height:100%;object-fit:cover" onerror="imgFail(this)"></div>'
        else:
            fd = a.get("source_domain", "")
            if fd:
                label = a["source"]
                img_html = f'<div class="card-img card-img-source"><img class="src-logo" loading="lazy" src="https://www.google.com/s2/favicons?domain={fd}&sz=64" alt="" onerror="this.style.display=\'none\'"><span class="src-lbl">{label}</span></div>'
            else:
                img_html = '<div class="card-img card-img-empty"></div>'

        # Source display
        source_display = a["source"]

        # GA tracking data
        ga_source = a["source"].replace("'", "\\'")
        ga_title = a["title"][:60].replace("'", "\\'")
        
        # Hide bias badge for social posts (empty bias)
        bias_badge_html = f'<span class="bias-badge" style="background:{bias_color}" title="{bias_label}">{bias_label}</span>' if bias and bias != "" else ''
        
        cards_html += f'''
        <a href="{link}" target="_blank" rel="noopener noreferrer" class="{card_class}" data-idx="{i}" style="animation-delay:{delay}s" onclick="gtag('event','article_click',{{source:'{ga_source}',bias:'{bias}',topic:'{a["topic"]}'}})">
            {img_html}
            <div class="card-body">
                <div class="card-top">
                    <span class="card-source">{source_display}</span>
                    {bias_badge_html}
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
    bias_counts = Counter(a.get("bias","?") for a in articles if not a.get("source", "").startswith("Vance on "))
    total_rated = sum(v for k,v in bias_counts.items() if k != "?")
    topic_counts = Counter(a.get("topic","General") for a in articles)
    top_topics = [t for t in topic_counts.most_common() if t[0] != "General"]
    top_topic = top_topics[0] if top_topics else ("General", 0)
    source_count = len(set(a["source"] for a in articles if a["source"]))
    topic_count = len(topic_counts)

    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <script>if(location.protocol==='http:'&&location.hostname!=='localhost')location.replace('https://'+location.host+location.pathname+location.search)</script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Vance Daily - Every JD Vance Article, Every Day | News Aggregator</title>
    <meta name="description" content="The most comprehensive JD Vance news aggregator. ''' + total + ''' articles from ''' + str(source_count) + ''' sources, updated hourly. Filter by political bias, topic, channel, or date. Left to Right coverage compared.">
    <meta name="keywords" content="JD Vance, Vance news, Vance 2028, VP Vance, Republican news, political news aggregator, media bias, Vance Iran, Vance immigration, Vance policy">
    <meta name="robots" content="index, follow">
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <meta property="og:title" content="The Vance Daily - Every JD Vance Article, Every Day">
    <meta property="og:description" content="''' + total + ''' articles from ''' + str(source_count) + ''' sources. Filter by political bias, topic, channel, or date. Updated hourly.">
    <meta property="og:image" content="https://thevancedaily.com/og-image-v3.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://thevancedaily.com">
    <meta property="og:site_name" content="The Vance Daily">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="The Vance Daily - Every JD Vance Article, Every Day">
    <meta name="twitter:description" content="The most comprehensive JD Vance news aggregator. ''' + total + ''' articles updated hourly.">
    <meta name="twitter:image" content="https://thevancedaily.com/og-image-v3.png">
    <link rel="canonical" href="https://thevancedaily.com">
    <link rel="sitemap" type="application/xml" href="/sitemap.xml">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "The Vance Daily",
        "url": "https://thevancedaily.com",
        "description": "Automated JD Vance news aggregator with political bias ratings",
        "publisher": {
            "@type": "Organization",
            "name": "The Vance Daily",
            "email": "contact@thevancedaily.com"
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
        .hdr{padding:0;border-bottom:1px solid var(--border);background:var(--bg2);position:sticky;top:0;z-index:30}
        .sticky-tb{position:sticky;top:0;z-index:29;background:var(--bg);border-bottom:1px solid var(--border);box-shadow:0 2px 8px rgba(26,23,20,.06);transition:top .1s}
        .hdr-in{max-width:1200px;margin:0 auto;padding:1.6rem 2rem 1.1rem}
        .hdr-top{display:flex;align-items:center;justify-content:space-between;gap:1.2rem;flex-wrap:wrap}
        .hdr-left{display:flex;flex-direction:column;gap:.1rem}
        .logo-row{display:flex;align-items:center;gap:.7rem}
        .logo-flag{width:clamp(48px,6vw,68px);height:clamp(32px,4vw,46px);display:flex;align-items:center;justify-content:center;flex-shrink:0}
        .logo-flag svg{width:100%;height:100%;border-radius:3px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
        .logo{font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:clamp(1.8rem,4.5vw,2.8rem);letter-spacing:-.02em;line-height:1.05;color:var(--text)}
        .logo .a{color:var(--accent)}
        .tagline{font-size:.65rem;font-weight:300;color:var(--text2);letter-spacing:.04em;text-transform:uppercase;margin-top:.2rem}
        .hdr-right{display:flex;align-items:center}
        .cta-row{display:flex;gap:.5rem;align-items:center}
        .cta-email{padding:.45rem .8rem;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;font-size:.82rem;outline:none;flex:1;min-width:220px}
        .cta-email::placeholder{color:var(--text3)}
        .cta-email:focus{border-color:var(--accent)}
        .cta-btn{padding:.45rem 1rem;border-radius:6px;border:none;background:var(--accent);color:#fff;font-family:'DM Sans',sans-serif;font-weight:600;font-size:.82rem;cursor:pointer;transition:background .2s}
        .cta-btn:hover{background:var(--accent-h)}

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
        .soc-card-foot{font-size:.62rem;color:var(--text3);display:flex;align-items:center;justify-content:space-between;gap:.4rem;margin-top:auto}
        .soc-card-time{font-size:.6rem;color:var(--text3);display:flex;align-items:center;gap:.25rem;white-space:nowrap}
        .soc-card-time svg{width:10px;height:10px;flex-shrink:0}
        .soc-card-static{justify-content:center;min-height:auto}

        /* SOURCE CAROUSEL */
        .crs{overflow:hidden;background:var(--bg3);border-bottom:1px solid var(--border);padding:.6rem 0;position:relative}
        .crs::before,.crs::after{content:'';position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none}
        .crs::before{left:0;background:linear-gradient(90deg,var(--bg3),transparent)}
        .crs::after{right:0;background:linear-gradient(270deg,var(--bg3),transparent)}
        .crs-track{display:flex;gap:1.8rem;width:max-content;animation:scrollR 600s linear infinite}
        .crs-track:hover{animation-play-state:paused}
        .crs-item{display:flex;align-items:center;gap:.4rem;flex-shrink:0;text-decoration:none;transition:opacity .2s}
        .crs-item:hover{opacity:.7}
        .crs-item img{width:20px;height:20px;border-radius:3px}
        .crs-item span{font-size:.7rem;font-weight:500;color:var(--text2);white-space:nowrap}
        @keyframes scrollR{0%{transform:translateX(-50%)}100%{transform:translateX(0)}}

        /* TOOLBAR */
        .tb{max-width:1400px;margin:0 auto;padding:.6rem 2rem .3rem;display:flex;gap:.55rem;flex-wrap:nowrap;align-items:center;justify-content:center}
        .tb>.sb,.tb>.sel,.tb>.pills,.tb>.bias-pills,.tb>.count,.tb>.briefing-find-btn{margin-top:0}
        .sb{flex:1;min-width:170px;position:relative}
        .sb svg{position:absolute;left:.7rem;top:50%;transform:translateY(-50%);width:15px;height:15px;color:var(--text3);pointer-events:none}
        .si{width:100%;padding:.48rem .7rem .48rem 2rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.83rem;color:var(--text);outline:none}
        .si::placeholder{color:var(--text3)}
        .si:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .sel{padding:.48rem 1.8rem .48rem .7rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.8rem;color:var(--text);outline:none;cursor:pointer;appearance:none;background-image:url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239e9790' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .6rem center;max-width:220px}
        .sel option{font-size:.82rem}
        .sel:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .sel option.soc-opt{color:var(--accent);font-weight:600}
        /* Custom dropdown for Sources (opens downward) */
        .custom-dd{position:relative;max-width:220px;flex-shrink:0}
        .custom-dd-btn{padding:.48rem 1.8rem .48rem .7rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.8rem;color:var(--text);outline:none;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;text-align:left;background-image:url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239e9790' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right .6rem center}
        .custom-dd-btn:focus,.custom-dd-btn.open{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-soft)}
        .custom-dd-list{display:none;position:absolute;top:calc(100% + 4px);left:0;min-width:100%;max-height:320px;overflow-y:auto;background:var(--bg2);border:1px solid var(--border);border-radius:7px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:50;padding:.3rem 0}
        .custom-dd-list.open{display:block}
        .custom-dd-item{padding:.4rem .7rem;font-family:'DM Sans',sans-serif;font-size:.8rem;color:var(--text);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .custom-dd-item:hover{background:var(--bg3)}
        .custom-dd-item.active{color:var(--accent);font-weight:600}
        .custom-dd-item.soc-opt{color:var(--accent);font-weight:600}
        .custom-dd-search{width:calc(100% - .6rem);margin:.2rem .3rem .3rem;padding:.35rem .5rem;border-radius:5px;border:1px solid var(--border);background:var(--bg);font-family:'DM Sans',sans-serif;font-size:.78rem;color:var(--text);outline:none}
        .custom-dd-search::placeholder{color:var(--text3)}
        .custom-dd-search:focus{border-color:var(--blue)}
        .pills{display:flex;gap:.2rem;flex-shrink:0}
        .pill{padding:.38rem .65rem;border-radius:100px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.74rem;font-weight:500;color:var(--text2);cursor:pointer;transition:all .2s}
        .pill:hover{background:var(--bg3)}
        .pill.on{background:var(--blue);color:#fff;border-color:var(--blue)}

        /* BIAS FILTER */
        .bias-pills{display:flex;gap:.2rem;flex-shrink:0}
        .bpill{padding:.38rem .55rem;border-radius:100px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.7rem;font-weight:500;cursor:pointer;transition:all .2s;white-space:nowrap}
        .bpill:hover{opacity:.85}
        .bpill.on{color:#fff!important}

        .count{font-size:.7rem;color:var(--text3);white-space:nowrap}
        .briefing-btn{display:flex;align-items:center;gap:.35rem;padding:.45rem .9rem;border-radius:6px;border:none;background:#1a3a5c;color:#fff;font-family:'DM Sans',sans-serif;font-size:.82rem;font-weight:600;cursor:pointer;text-decoration:none;white-space:nowrap;transition:background .2s}
        .briefing-btn:hover{background:#234d78}
        .briefing-btn svg{width:14px;height:14px;flex-shrink:0}
        .briefing-find-btn{display:flex;align-items:center;gap:.35rem;padding:.48rem .8rem;border-radius:7px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.8rem;font-weight:500;color:var(--text);cursor:pointer;white-space:nowrap;transition:all .2s;position:relative;overflow:hidden;flex-shrink:0}
        .briefing-find-btn:hover{border-color:var(--blue);color:var(--blue)}
        .briefing-find-btn svg{width:14px;height:14px;flex-shrink:0}

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
        .card-img-source{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.4rem;background:linear-gradient(145deg,#ece8e2 0%,#e2ddd5 50%,#d5cfC6 100%);height:100px}
        .src-logo{width:32px;height:32px;border-radius:6px;background:var(--bg2);padding:2px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
        .src-lbl{font-size:.62rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--text3);text-align:center;max-width:80%}
        .card-img-empty{background:linear-gradient(145deg,#ece8e2 0%,#e2ddd5 50%,#d5cfC6 100%);height:100px}

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
        .load-more-btn{display:block;margin:1.5rem auto;padding:.6rem 2rem;border-radius:8px;border:1px solid var(--border);background:var(--bg2);font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:600;color:var(--text2);cursor:pointer;transition:all .2s}
        .load-more-btn:hover{background:var(--bg3);color:var(--text);border-color:var(--accent)}

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
            /* HEADER - center, hide email field on mobile, show subscribe as popup trigger */
            .hdr{position:sticky;top:0;z-index:30}
            .hdr-in{padding:.7rem .8rem .6rem}
            .hdr-top{flex-direction:column;align-items:center;gap:.4rem}
            .hdr-left{align-items:center;text-align:center}
            .logo{font-size:1.5rem}
            .logo-flag{width:32px;height:22px}
            .tagline{font-size:.5rem;margin-top:.1rem}
            .hdr-right{width:100%}
            .cta-row{width:100%;justify-content:center;gap:.4rem}
            .cta-email{display:none}
            .cta-btn{font-size:.75rem;padding:.38rem .8rem}
            .briefing-btn{font-size:.7rem;padding:.35rem .6rem;white-space:nowrap}
            
            /* CAROUSELS - no gradient edges on mobile */
            .soc-bar{padding:.5rem 0}
            .soc-bar::before,.soc-bar::after{display:none}
            .soc-card{width:250px;padding:.5rem .7rem}
            .crs{padding:.4rem 0}
            .crs::before,.crs::after{display:none}
            
            /* TOOLBAR - mobile grid layout, sticky below header */
            .sticky-tb{position:sticky;z-index:29;border-bottom:1px solid var(--border)}
            .tb{padding:.5rem .6rem .3rem;gap:.35rem;display:grid!important;grid-template-columns:1fr 1fr;max-width:100%}
            .sb{grid-column:1/3;min-width:0;order:1}
            .si{font-size:.75rem;padding:.4rem .5rem .4rem 1.8rem}
            .sb svg{left:.5rem;width:13px;height:13px}
            .custom-dd{max-width:none;width:100%}
            #srcDD{grid-column:1;order:2}
            #regionDD{grid-column:2;order:3}
            #topicDD{grid-column:1;order:4}
            .briefing-find-btn{grid-column:2;width:100%;justify-content:center;font-size:.75rem;padding:.4rem .5rem;order:5}
            .custom-dd-btn{width:100%;font-size:.75rem;padding:.4rem .5rem .4rem .5rem}
            .sel{display:none!important}
            .pills{grid-column:1/3;overflow-x:auto;flex-wrap:nowrap;-webkit-overflow-scrolling:touch;justify-content:center;order:6}
            .pill{flex-shrink:0;font-size:.68rem;padding:.3rem .45rem}
            .bias-pills{grid-column:1/3;overflow-x:auto;flex-wrap:nowrap;-webkit-overflow-scrolling:touch;justify-content:center;order:7}
            .bpill{flex-shrink:0;font-size:.62rem;padding:.28rem .38rem}
            .count{display:none}
            
            /* GRID - single column */
            .main{padding:.3rem .6rem 3rem}
            .grid{grid-template-columns:1fr;gap:.7rem}
            .card-img{height:160px}
            
            /* FOOTER */
            .ft-grid{grid-template-columns:1fr;gap:1rem}
            .ft-inner{padding:2rem 1rem}
            
            /* MODALS */
            .smodal{width:92%;margin:0 auto;padding:1.5rem}
        }
    </style>
<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-88N61Z6BFW"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-88N61Z6BFW");</script>
<!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6910331043242861" crossorigin="anonymous"></script>
</head>
<body>

<header class="hdr">
    <div class="hdr-in">
        <div class="hdr-top">
            <div class="hdr-left">
                <div class="logo-row">
                    <div class="logo-flag"><svg viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect width="60" height="40" fill="#fff"/><g fill="#B22234"><rect y="0" width="60" height="3.08"/><rect y="6.15" width="60" height="3.08"/><rect y="12.31" width="60" height="3.08"/><rect y="18.46" width="60" height="3.08"/><rect y="24.62" width="60" height="3.08"/><rect y="30.77" width="60" height="3.08"/><rect y="36.92" width="60" height="3.08"/></g><rect width="24" height="21.54" fill="#3C3B6E"/><g fill="#fff" font-size="2.8" font-family="sans-serif" text-anchor="middle"><text x="2.4" y="3.5">&#9733;</text><text x="7.2" y="3.5">&#9733;</text><text x="12" y="3.5">&#9733;</text><text x="16.8" y="3.5">&#9733;</text><text x="21.6" y="3.5">&#9733;</text><text x="4.8" y="7">&#9733;</text><text x="9.6" y="7">&#9733;</text><text x="14.4" y="7">&#9733;</text><text x="19.2" y="7">&#9733;</text><text x="2.4" y="10.5">&#9733;</text><text x="7.2" y="10.5">&#9733;</text><text x="12" y="10.5">&#9733;</text><text x="16.8" y="10.5">&#9733;</text><text x="21.6" y="10.5">&#9733;</text><text x="4.8" y="14">&#9733;</text><text x="9.6" y="14">&#9733;</text><text x="14.4" y="14">&#9733;</text><text x="19.2" y="14">&#9733;</text><text x="2.4" y="17.5">&#9733;</text><text x="7.2" y="17.5">&#9733;</text><text x="12" y="17.5">&#9733;</text><text x="16.8" y="17.5">&#9733;</text><text x="21.6" y="17.5">&#9733;</text><text x="4.8" y="21">&#9733;</text><text x="9.6" y="21">&#9733;</text><text x="14.4" y="21">&#9733;</text><text x="19.2" y="21">&#9733;</text></g></svg></div>
                    <h1 class="logo">The <span class="a">Vance</span> Daily</h1>
                </div>
                <p class="tagline">Every JD Vance article. Every channel. Every topic. Every hour.</p>
            </div>
            <div class="hdr-right">
                <div class="cta-row">
                    <input type="email" class="cta-email" placeholder="Get the daily Vance briefing" id="emailIn">
                    <button class="cta-btn" id="emailBtn">Subscribe</button>
                    <a href="/daily/''' + (today or '') + '''.html" class="briefing-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>
                        Read today's briefing
                    </a>
                </div>
            </div>
        </div>
    </div>
</header>

<div class="soc-bar">
    <div class="soc-track">''' + social_html + '''</div>
</div>

<div class="crs">
    <div class="crs-track">''' + carousel_track + '''</div>
</div>

<div class="sticky-tb" id="stickyTb">

<div class="tb">
    <div class="sb">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" class="si" placeholder="Search headlines..." id="si">
    </div>
    <select class="sel" id="srcF" style="display:none"><option value="">All Sources</option></select>
    <div class="custom-dd" id="srcDD">
        <button type="button" class="custom-dd-btn" id="srcDDBtn">All Sources (''' + str(source_count) + ''')</button>
        <div class="custom-dd-list" id="srcDDList">
            <input type="text" class="custom-dd-search" id="srcDDSearch" placeholder="Search sources...">
            <div class="custom-dd-item active" data-val="">All Sources (''' + str(source_count) + ''')</div>
            <div class="custom-dd-item soc-opt" data-val="__vance_social__">&#9733; Vance's Social Media</div>
        </div>
    </div>
    <div class="custom-dd" id="regionDD">
        <button type="button" class="custom-dd-btn" id="regionDDBtn">All Source Areas</button>
        <div class="custom-dd-list" id="regionDDList">
            <div class="custom-dd-item active" data-val="">All Source Areas</div>
        </div>
    </div>
    <select class="sel" id="topicF" style="display:none"><option value="">All Topics</option></select>
    <div class="custom-dd" id="topicDD">
        <button type="button" class="custom-dd-btn" id="topicDDBtn">All Topics (''' + str(topic_count) + ''')</button>
        <div class="custom-dd-list" id="topicDDList">
            <div class="custom-dd-item active" data-val="">All Topics (''' + str(topic_count) + ''')</div>
        </div>
    </div>
    <div class="pills">
        <button class="pill" data-r="all">All</button>
        <button class="pill on" data-r="today">Today</button>
        <button class="pill" data-r="week">Week</button>
        <button class="pill" data-r="month">Month</button>
    </div>
    <button type="button" class="briefing-find-btn" id="briefingFindBtn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        Find a daily briefing
        <input type="date" id="briefingDate" style="position:absolute;top:0;left:0;width:1px;height:1px;opacity:0.01;border:none;padding:0;pointer-events:none" value="''' + (today or '') + '''" min="2026-03-27" max="''' + (today or '') + '''">
    </button>
    <div class="bias-pills">
        <button class="bpill" data-b="L" style="color:#4a90d9;border-color:#4a90d9">Left ''' + str(bias_count_L) + '''</button>
        <button class="bpill" data-b="LL" style="color:#7bb3e0;border-color:#7bb3e0">Leans L ''' + str(bias_count_LL) + '''</button>
        <button class="bpill" data-b="C" style="color:#a0a090;border-color:#a0a090">Center ''' + str(bias_count_C) + '''</button>
        <button class="bpill" data-b="LR" style="color:#e09070;border-color:#e09070">Leans R ''' + str(bias_count_LR) + '''</button>
        <button class="bpill" data-b="R" style="color:#d94a4a;border-color:#d94a4a">Right ''' + str(bias_count_R) + '''</button>
    </div>
    <span class="count" id="cnt"></span>
</div>
<p style="text-align:center;font-size:.65rem;color:#9e9790;margin:0;padding:0 0 .3rem">''' + total + ''' articles &middot; Updated ''' + build_time + '''</p>
</div>

<main class="main">
    <div class="grid" id="g">''' + cards_html + '''
    </div>
</main>

<footer class="ft">
    <div class="ft-inner">
        <div class="ft-grid">
            <div class="ft-col">
                <h4>The Vance Daily</h4>
                <p>The most comprehensive JD Vance news aggregator.<br>Every article from every source, automatically collected daily with political bias ratings.</p>
            </div>
            <div class="ft-col">
                <h4>Topics</h4>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Iran\\']').click();window.scrollTo(0,0);return false">Iran</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Foreign Policy\\']').click();window.scrollTo(0,0);return false">Foreign Policy</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'2028 Race\\']').click();window.scrollTo(0,0);return false">2028 Race</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Immigration\\']').click();window.scrollTo(0,0);return false">Immigration</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Economy\\']').click();window.scrollTo(0,0);return false">Economy</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Domestic\\']').click();window.scrollTo(0,0);return false">Domestic</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Military\\']').click();window.scrollTo(0,0);return false">Military</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Healthcare\\']').click();window.scrollTo(0,0);return false">Healthcare</a>
                <a href="#" onclick="document.querySelector('#topicDDList [data-val=\\'Tech &amp; AI\\']').click();window.scrollTo(0,0);return false">Tech &amp; AI</a>
            </div>
            <div class="ft-col">
                <h4>Contact</h4>
                <a href="#" data-open-contact onclick="return false">Send us a message</a>
                <a href="#" data-open-suggest onclick="return false">Suggest a missing source</a>
                <a href="#" onclick="document.getElementById('biasModal').classList.add('show');return false">Report a bias rating</a>
                <p style="margin-top:.5rem">Bias ratings based on <a href="https://www.allsides.com/media-bias" target="_blank">AllSides</a>.</p>
            </div>
        </div>
        <div class="ft-bottom">
            <p>The Vance Daily - Automated news aggregation. Headlines link to original sources. Not affiliated with any political campaign, party, government or media entity. Just a guy who loves building stuff.</p>
            <p style="margin-top:.4rem"><a href="/disclaimer.html">Disclaimer &amp; Terms</a> &middot; <a href="#" data-open-contact onclick="return false">Contact</a></p>
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
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"/><path d="M14 2v6h6"/><path d="M3 15h6"/><path d="M6 12v6"/></svg>
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
            <p style="font-size:.85rem;color:#6b6560;margin-top:.4rem">We'll review it and add it to The Vance Daily within 24 hours.</p>
        </div>
    </div>
</div>

<div class="smodal-overlay" id="biasModal">
    <div class="smodal">
        <button class="smodal-close" id="biasClose">&times;</button>
        <div class="smodal-icon" style="background:linear-gradient(135deg,#d94a4a,#e06050)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:26px;height:26px;color:#fff"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </div>
        <h2>Report a Bias Rating</h2>
        <p class="smodal-sub">Think we got a source's political bias rating wrong?<br>Let us know and we'll review it.</p>
        <div id="biasForm" class="smodal-form">
            <div class="smodal-field">
                <label>Source Name</label>
                <input type="text" id="biasSource" placeholder="e.g. Reuters">
            </div>
            <div class="smodal-field">
                <label>Current Rating</label>
                <select id="biasCurrent">
                    <option value="">Not sure</option>
                    <option value="Left">Left</option>
                    <option value="Leans Left">Leans Left</option>
                    <option value="Center">Center</option>
                    <option value="Leans Right">Leans Right</option>
                    <option value="Right">Right</option>
                </select>
            </div>
            <div class="smodal-field">
                <label>What should it be?</label>
                <select id="biasSuggested">
                    <option value="">Select...</option>
                    <option value="Left">Left</option>
                    <option value="Leans Left">Leans Left</option>
                    <option value="Center">Center</option>
                    <option value="Leans Right">Leans Right</option>
                    <option value="Right">Right</option>
                </select>
            </div>
            <div class="smodal-field">
                <label>Your Email (optional)</label>
                <input type="email" id="biasEmail" placeholder="So we can follow up">
            </div>
            <button class="smodal-submit" id="biasSubmit">Submit Report</button>
        </div>
        <div id="biasThanks" class="smodal-thanks">
            <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#2a9d5c,#34c06e);display:flex;align-items:center;justify-content:center;margin:1rem auto">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" style="width:28px;height:28px"><path d="M20 6L9 17l-5-5"/></svg>
            </div>
            <h2 style="margin-top:.5rem">Report Submitted!</h2>
            <p style="font-size:.85rem;color:#6b6560;margin-top:.4rem">We'll review the bias rating and update it if needed.</p>
        </div>
    </div>
</div>

<div class="smodal-overlay" id="subModal">
    <div class="smodal">
        <button class="smodal-close" id="subClose">&times;</button>
        <div class="smodal-icon" style="background:linear-gradient(135deg,#b8322a,#d43d33)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:26px;height:26px;color:#fff"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/></svg>
        </div>
        <h2>Get The Vance Daily</h2>
        <p class="smodal-sub">Every morning, the top JD Vance stories delivered to your inbox. No spam.</p>
        <div id="subForm" class="smodal-form">
            <div class="smodal-field">
                <label>Your Email</label>
                <input type="email" id="subEmail" placeholder="your@email.com">
            </div>
            <button class="smodal-submit" id="subSubmit">Subscribe</button>
        </div>
        <div id="subThanks" class="smodal-thanks">
            <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#2a9d5c,#34c06e);display:flex;align-items:center;justify-content:center;margin:1rem auto">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" style="width:28px;height:28px"><path d="M20 6L9 17l-5-5"/></svg>
            </div>
            <h2 style="margin-top:.5rem">You're In!</h2>
            <p style="font-size:.85rem;color:#6b6560;margin-top:.4rem">The Vance Daily is on its way to your inbox.</p>
        </div>
    </div>
</div>

<div class="smodal-overlay" id="contactModal">
    <div class="smodal">
        <button class="smodal-close" id="contactClose">&times;</button>
        <div class="smodal-icon" style="background:linear-gradient(135deg,#1a3a5c,#2a5a8c)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:26px;height:26px;color:#fff"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/></svg>
        </div>
        <h2>Contact Us</h2>
        <p class="smodal-sub">Questions, feedback, or takedown requests — we'll get back to you within 48 hours.</p>
        <div id="contactForm" class="smodal-form">
            <div class="smodal-field">
                <label>Your Name</label>
                <input type="text" id="contactName" placeholder="Your name">
            </div>
            <div class="smodal-field">
                <label>Your Email</label>
                <input type="email" id="contactEmail" placeholder="your@email.com">
            </div>
            <div class="smodal-field">
                <label>Message</label>
                <textarea id="contactMsg" placeholder="How can we help?" style="width:100%;min-height:100px;padding:.55rem .7rem;border-radius:7px;border:1px solid #d4cfc7;font-family:'DM Sans',sans-serif;font-size:.85rem;color:#1a1714;resize:vertical;outline:none;box-sizing:border-box"></textarea>
            </div>
            <button class="smodal-submit" id="contactSubmit">Send Message</button>
        </div>
        <div id="contactThanks" class="smodal-thanks">
            <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#2a9d5c,#34c06e);display:flex;align-items:center;justify-content:center;margin:1rem auto">
                <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" style="width:28px;height:28px"><path d="M20 6L9 17l-5-5"/></svg>
            </div>
            <h2 style="margin-top:.5rem">Message Sent!</h2>
            <p style="font-size:.85rem;color:#6b6560;margin-top:.4rem">We'll get back to you within 48 hours.</p>
        </div>
    </div>
</div>

<script>
function imgFail(img){
    img.onerror=null;
    var p=img.parentElement;
    var d=p.getAttribute('data-fallback-domain');
    var n=p.getAttribute('data-fallback-name')||'';
    if(d){
        p.className='card-img card-img-source';
        p.innerHTML='<img class="src-logo" src="https://www.google.com/s2/favicons?domain='+d+'&sz=64" alt=""><span class="src-lbl">'+n+'</span>';
    }else{
        p.className='card-img card-img-empty';
        img.style.display='none';
    }
}
(function(){
    const cards=Array.from(document.querySelectorAll('.card'));
    const g=document.getElementById('g');
    const si=document.getElementById('si');
    const srcF=document.getElementById('srcF');
    const topicF=document.getElementById('topicF');
    const pills=document.querySelectorAll('.pill[data-r]');
    const bpills=document.querySelectorAll('.bpill');
    const cnt=document.getElementById('cnt');
    const meta=''' + article_meta + ''';
    const srcs=''' + sources_json + ''';
    const topics=''' + topics_json + ''';
    const srcCounts=''' + source_counts_json + ''';
    const topicCounts=''' + topic_counts_json + ''';
    const regionCounts=''' + region_counts_json + ''';

    srcs.forEach(s=>{if(s.startsWith('Vance on '))return;const o=document.createElement('option');o.value=s;o.textContent=s+(srcCounts[s]?' ('+srcCounts[s]+')':'');srcF.appendChild(o)});
    topics.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t+(topicCounts[t]?' ('+topicCounts[t]+')':'');topicF.appendChild(o)});

    // Custom dropdown for sources
    const srcDDBtn=document.getElementById('srcDDBtn');
    const srcDDList=document.getElementById('srcDDList');
    const srcDDSearch=document.getElementById('srcDDSearch');
    // Populate custom dropdown items
    srcs.forEach(s=>{if(s.startsWith('Vance on '))return;const d=document.createElement('div');d.className='custom-dd-item';d.dataset.val=s;d.textContent=s+(srcCounts[s]?' ('+srcCounts[s]+')':'');srcDDList.appendChild(d)});
    // Toggle open/close
    srcDDBtn.addEventListener('click',(e)=>{e.stopPropagation();const isOpen=srcDDList.classList.contains('open');closeAllDD();if(!isOpen){srcDDList.classList.add('open');srcDDBtn.classList.add('open');srcDDSearch.value='';filterDDItems('');setTimeout(()=>srcDDSearch.focus(),50)}});
    // Search within dropdown
    srcDDSearch.addEventListener('input',()=>filterDDItems(srcDDSearch.value.toLowerCase()));
    srcDDSearch.addEventListener('click',(e)=>e.stopPropagation());
    function filterDDItems(q){srcDDList.querySelectorAll('.custom-dd-item').forEach(it=>{const txt=it.textContent.toLowerCase();it.style.display=(!q||txt.includes(q))?'':'none'})}
    // Select item
    let selectedSrc='';
    srcDDList.addEventListener('click',(e)=>{const item=e.target.closest('.custom-dd-item');if(!item)return;const val=item.dataset.val;selectedSrc=val;srcDDBtn.textContent=val==='__vance_social__'?'Vance\\'s Social Media':val||('All Sources ('+srcs.length+')');srcDDList.querySelectorAll('.custom-dd-item').forEach(i=>i.classList.remove('active'));item.classList.add('active');closeAllDD();filter()});

    // Custom dropdown for topics
    const topicDDBtn=document.getElementById('topicDDBtn');
    const topicDDList=document.getElementById('topicDDList');
    topics.forEach(t=>{const d=document.createElement('div');d.className='custom-dd-item';d.dataset.val=t;d.textContent=t+(topicCounts[t]?' ('+topicCounts[t]+')':'');topicDDList.appendChild(d)});
    topicDDBtn.addEventListener('click',(e)=>{e.stopPropagation();const isOpen=topicDDList.classList.contains('open');closeAllDD();if(!isOpen){topicDDList.classList.add('open');topicDDBtn.classList.add('open')}});
    let selectedTopic='';
    topicDDList.addEventListener('click',(e)=>{const item=e.target.closest('.custom-dd-item');if(!item)return;const val=item.dataset.val;selectedTopic=val;topicDDBtn.textContent=val||('All Topics ('+topics.length+')');topicDDList.querySelectorAll('.custom-dd-item').forEach(i=>i.classList.remove('active'));item.classList.add('active');closeAllDD();filter()});
    function closeAllDD(){srcDDList.classList.remove('open');srcDDBtn.classList.remove('open');topicDDList.classList.remove('open');topicDDBtn.classList.remove('open');regionDDList.classList.remove('open');regionDDBtn.classList.remove('open')}
    document.addEventListener('click',(e)=>{if(!e.target.closest('.custom-dd'))closeAllDD()});

    let dateRange='today';
    let activeBias=new Set(); // empty = show all
    let activeRegion='all'; // 'all', 'US', 'International'
    let showLimit=60; // Initial cards to show

    function filter(){
        const q=si.value.toLowerCase();
        const src=selectedSrc;
        const topic=selectedTopic;
        const now=new Date();
        let vis=0;
        let totalMatch=0;
        cards.forEach((c,i)=>{
            const m=meta[i];
            const t=c.querySelector('.card-title').textContent.toLowerCase();
            let ok=true;
            if(q&&!t.includes(q)&&!m.source.toLowerCase().includes(q))ok=false;
            if(src==='__vance_social__'){if(!m.source.startsWith('Vance on '))ok=false}
            else if(src&&m.source!==src)ok=false;
            if(topic&&m.topic!==topic)ok=false;
            if(activeBias.size>0&&!activeBias.has(m.bias))ok=false;
            if(activeRegion!=='all'&&m.region!==activeRegion)ok=false;
            if(dateRange!=='all'&&m.published){
                const d=(now-new Date(m.published))/864e5;
                if(dateRange==='today'&&d>1)ok=false;
                if(dateRange==='week'&&d>7)ok=false;
                if(dateRange==='month'&&d>30)ok=false;
            }
            if(ok){totalMatch++;if(totalMatch<=showLimit){c.style.display='';vis++}else{c.style.display='none'}}
            else{c.style.display='none'}
        });
        cnt.textContent='';
        // Show/hide load more button
        let lb=document.getElementById('loadMoreBtn');
        if(totalMatch>showLimit){
            if(!lb){lb=document.createElement('button');lb.id='loadMoreBtn';lb.className='load-more-btn';lb.addEventListener('click',()=>{showLimit+=60;filter()});g.parentElement.appendChild(lb)}
            lb.textContent='Show more ('+vis+' of '+totalMatch+')';lb.style.display=''
        }else if(lb){lb.style.display='none'}
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

    // Region dropdown
    const regionDDBtn=document.getElementById('regionDDBtn');
    const regionDDList=document.getElementById('regionDDList');
    // Populate region dropdown items
    const regionOrder=['US','Europe','Asia','Middle East','Americas','Africa','International'];
    regionOrder.forEach(r=>{if(regionCounts[r]){const d=document.createElement('div');d.className='custom-dd-item';d.dataset.val=r;d.textContent=r+' ('+regionCounts[r]+')';regionDDList.appendChild(d)}});
    regionDDBtn.addEventListener('click',(e)=>{e.stopPropagation();const isOpen=regionDDList.classList.contains('open');closeAllDD();if(!isOpen){regionDDList.classList.add('open');regionDDBtn.classList.add('open')}});
    let selectedRegion='';
    regionDDList.addEventListener('click',(e)=>{const item=e.target.closest('.custom-dd-item');if(!item)return;const val=item.dataset.val;selectedRegion=val;activeRegion=val||'all';regionDDBtn.textContent=val||'All Source Areas';regionDDList.querySelectorAll('.custom-dd-item').forEach(i=>i.classList.remove('active'));item.classList.add('active');closeAllDD();filter()});

    // Newsletter modal
    const modal=document.getElementById('modal');
    const modalEmail=document.getElementById('modalEmail');
    document.getElementById('modalClose').addEventListener('click',()=>modal.classList.remove('show'));
    modal.addEventListener('click',(e)=>{if(e.target===modal)modal.classList.remove('show')});

    document.getElementById('emailBtn').addEventListener('click',()=>{
        const emailIn=document.getElementById('emailIn');
        // On mobile the email input is hidden, show subscribe modal instead
        if(window.getComputedStyle(emailIn).display==='none'){
            document.getElementById('subModal').classList.add('show');
            return;
        }
        const e=emailIn.value.trim();
        if(e&&e.includes('@')&&e.includes('.')){
            const form=new FormData();
            form.append('email',e);
            fetch('https://buttondown.com/api/emails/embed-subscribe/thevancedaily',{
                method:'POST',
                body:form
            }).then(r=>{
                modalEmail.textContent=e;
                modal.classList.add('show');
                emailIn.value='';
                gtag('event','newsletter_subscribe',{method:'header'});
            }).catch(()=>{
                modalEmail.textContent=e;
                modal.classList.add('show');
                emailIn.value='';
            });
        }
    });

    // Mobile subscribe modal
    const subModal=document.getElementById('subModal');
    document.getElementById('subClose').addEventListener('click',()=>subModal.classList.remove('show'));
    subModal.addEventListener('click',(e)=>{if(e.target===subModal)subModal.classList.remove('show')});
    document.getElementById('subSubmit').addEventListener('click',()=>{
        const email=document.getElementById('subEmail').value.trim();
        if(!email||!email.includes('@')){document.getElementById('subEmail').focus();return}
        const form=new FormData();
        form.append('email',email);
        fetch('https://buttondown.com/api/emails/embed-subscribe/thevancedaily',{
            method:'POST',body:form
        }).then(()=>{}).catch(()=>{});
        document.getElementById('subForm').classList.add('hide');
        document.getElementById('subThanks').classList.add('show');
        gtag('event','newsletter_subscribe',{method:'mobile_modal'});
        setTimeout(()=>{
            subModal.classList.remove('show');
            setTimeout(()=>{
                document.getElementById('subForm').classList.remove('hide');
                document.getElementById('subThanks').classList.remove('show');
                document.getElementById('subEmail').value='';
            },300);
        },2500);
    });

    // Contact modal
    const contactModal=document.getElementById('contactModal');
    document.getElementById('contactClose').addEventListener('click',()=>contactModal.classList.remove('show'));
    contactModal.addEventListener('click',(e)=>{if(e.target===contactModal)contactModal.classList.remove('show')});
    document.querySelectorAll('[data-open-contact]').forEach(el=>el.addEventListener('click',(e)=>{e.preventDefault();contactModal.classList.add('show')}));
    document.getElementById('contactSubmit').addEventListener('click',()=>{
        const name=document.getElementById('contactName').value.trim();
        const email=document.getElementById('contactEmail').value.trim();
        const msg=document.getElementById('contactMsg').value.trim();
        if(!name){document.getElementById('contactName').focus();return}
        if(!email||!email.includes('@')){document.getElementById('contactEmail').focus();return}
        if(!msg){document.getElementById('contactMsg').focus();return}
        // Send via mailto in background
        const subject=encodeURIComponent('Contact from The Vance Daily: '+name);
        const body=encodeURIComponent('Name: '+name+'\\nEmail: '+email+'\\n\\n'+msg);
        window.open('mailto:contact@thevancedaily.com?subject='+subject+'&body='+body,'_blank');
        document.getElementById('contactForm').classList.add('hide');
        document.getElementById('contactThanks').classList.add('show');
        gtag('event','contact_form',{method:'popup'});
        setTimeout(()=>{
            contactModal.classList.remove('show');
            setTimeout(()=>{
                document.getElementById('contactForm').classList.remove('hide');
                document.getElementById('contactThanks').classList.remove('show');
                document.getElementById('contactName').value='';
                document.getElementById('contactEmail').value='';
                document.getElementById('contactMsg').value='';
            },300);
        },2500);
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

    // Briefing date picker - button opens the hidden date input
    const briefingDateInput=document.getElementById('briefingDate');
    document.getElementById('briefingFindBtn').addEventListener('click',function(e){
        e.preventDefault();e.stopPropagation();
        try{briefingDateInput.showPicker()}catch(err){briefingDateInput.click()}
    });
    briefingDateInput.addEventListener('change',function(){
        const d=this.value;
        if(d)window.location.href='/daily/'+d+'.html';
    });

    // Suggest source modal
    const sugModal=document.getElementById('suggestModal');
    const sugBtns=document.querySelectorAll('[data-open-suggest]');
    sugBtns.forEach(b=>b.addEventListener('click',(e)=>{e.preventDefault();sugModal.classList.add('show')}));
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
        window.open('mailto:contact@thevancedaily.com?subject=Source%20Suggestion:%20'+encodeURIComponent(name)+'&body='+body,'_blank');
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

    // Bias report modal
    const biasModal=document.getElementById('biasModal');
    document.getElementById('biasClose').addEventListener('click',()=>biasModal.classList.remove('show'));
    biasModal.addEventListener('click',(e)=>{if(e.target===biasModal)biasModal.classList.remove('show')});
    document.getElementById('biasSubmit').addEventListener('click',()=>{
        const source=document.getElementById('biasSource').value.trim();
        const current=document.getElementById('biasCurrent').value;
        const suggested=document.getElementById('biasSuggested').value;
        const email=document.getElementById('biasEmail').value.trim();
        if(!source){document.getElementById('biasSource').focus();return}
        if(!suggested){document.getElementById('biasSuggested').focus();return}
        const body='Source: '+source+'%0ACurrent rating: '+(current||'Not specified')+'%0ASuggested rating: '+suggested+'%0ASubmitter email: '+(email||'Not provided');
        window.open('mailto:contact@thevancedaily.com?subject=Bias%20Rating%20Report:%20'+encodeURIComponent(source)+'&body='+body,'_blank');
        document.getElementById('biasForm').classList.add('hide');
        document.getElementById('biasThanks').classList.add('show');
        setTimeout(()=>{
            biasModal.classList.remove('show');
            setTimeout(()=>{
                document.getElementById('biasForm').classList.remove('hide');
                document.getElementById('biasThanks').classList.remove('show');
                document.getElementById('biasSource').value='';
                document.getElementById('biasCurrent').value='';
                document.getElementById('biasSuggested').value='';
                document.getElementById('biasEmail').value='';
            },300);
        },2500);
    });

    // Apply default filter on page load (Today)
    filter();

    // Set toolbar sticky position below header
    const hdr=document.querySelector('.hdr');
    const stickyTb=document.getElementById('stickyTb');
    function setTbTop(){if(hdr&&stickyTb)stickyTb.style.top=hdr.offsetHeight+'px'}
    setTbTop();
    window.addEventListener('resize',setTbTop);
})();
</script>
</body>
</html>'''


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=== The Vance Daily Build v5 ===")
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

    # 3. Retroactive title cleaning: strip source suffixes from all articles
    # Must run BEFORE dedup so identical titles get properly deduplicated
    _noise_suffixes = {"watch", "opinion", "world", "video", "photos", "exclusive", "breaking",
                       "analysis", "editorial", "column", "podcast", "live", "update", "updates"}
    title_cleaned = 0
    for a in all_articles:
        t = html_module.unescape(a.get("title", ""))
        changed = False
        for sep in [" - ", " – ", " — ", " | "]:
            if sep in t:
                parts = t.rsplit(sep, 1)
                suffix = parts[1].strip()
                if len(suffix) < 50 and len(suffix.split()) <= 6:
                    t = parts[0].strip()
                    changed = True
                    break
        # Second pass: only strip if suffix looks like a source/noise, not real content
        if changed:
            for sep in [" - ", " – ", " — ", " | "]:
                if sep in t:
                    parts = t.rsplit(sep, 1)
                    suffix = parts[1].strip()
                    if suffix.lower() in _noise_suffixes or (len(suffix.split()) <= 3 and len(suffix) < 30):
                        t = parts[0].strip()
                    break
        if changed:
            title_cleaned += 1
            a["title"] = html_module.escape(t)
            # Rehash article ID so dedup works on the cleaned title
            a["id"] = hashlib.md5(t.encode()).hexdigest()[:12]
    if title_cleaned:
        print(f"Cleaned source suffixes from {title_cleaned} article titles")

    # 4. Deduplicate (now runs on cleaned titles)
    all_articles = deduplicate(all_articles)
    print(f"\nTotal unique (before filter): {len(all_articles)}")

    # 5. Label articles as US or International (no longer blocking)
    us_count = 0
    intl_count = 0
    for a in all_articles:
        a["region"] = get_region(a)
        if a["region"] == "US":
            us_count += 1
        else:
            intl_count += 1
    print(f"Region labeling: {us_count} US, {intl_count} International")

    # 6. Scrape Vance's social media posts (X/Twitter via syndication API)
    print("\nScraping social media posts...")
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    scraped_social = fetch_social_posts()
    # Use scraped X posts for the article grid (with real timestamps)
    for sp in scraped_social:
        if not sp.get("text") or not sp.get("timestamp"):
            continue  # Skip static accounts (no live data)
        try:
            dt = datetime.strptime(sp["timestamp"], "%a %b %d %H:%M:%S %z %Y")
        except:
            dt = now
        # Platform-specific source name
        handle = sp.get("handle", "")
        if "@VP" in handle:
            source_name = "Vance on X (@VP)"
        elif "@JDVance" in handle:
            source_name = "Vance on X (@JDVance)"
        else:
            source_name = f"Vance on {sp.get('platform', 'Social')}"
        sp_article = {
            "id": hashlib.md5(sp["text"].encode()).hexdigest()[:12],
            "title": sp["text"],
            "source": source_name,
            "source_url": sp["url"],
            "source_domain": "x.com",
            "link": sp["url"],
            "published": dt.isoformat(),
            "published_display": dt.strftime("%b %d, %Y"),
            "query": "social",
            "image": "",
            "real_url": sp["url"],
            "bias": "",
            "topic": "General",
        }
        all_articles.append(sp_article)
    print(f"Added {len([s for s in scraped_social if s.get('text') and s.get('timestamp')])} social media posts to articles")

    # 7. Merge with existing articles (incremental — keep old, add new)
    existing_articles = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                existing_articles = json.load(f)
            print(f"\nLoaded {len(existing_articles)} existing articles from cache")
        except:
            print("\nNo existing article cache found")
    # Build set of existing IDs for fast lookup
    existing_ids = set(a.get("id", "") for a in existing_articles)
    new_articles = [a for a in all_articles if a["id"] not in existing_ids]
    print(f"New articles this scrape: {len(new_articles)}")
    
    # Sort all articles by date
    all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)

    # 8. Stats
    from collections import Counter
    bc = Counter(a["bias"] for a in all_articles)
    sc = Counter(a["source"] for a in all_articles)
    print(f"\nBias breakdown: {dict(bc)}")
    print(f"Unique sources: {len(sc)}")

    # 9. Enrich ONLY new articles (existing ones already have images)
    if new_articles:
        print(f"\nEnriching {len(new_articles)} NEW articles...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
            enriched = list(ex.map(enrich_article, new_articles))
        # Update the new articles in all_articles
        enriched_map = {a["id"]: a for a in enriched}
        all_articles = [enriched_map.get(a["id"], a) for a in all_articles]
        img_count = sum(1 for a in new_articles if a.get("image"))
        print(f"  New images: {img_count}/{len(new_articles)}")
    else:
        print("\nNo new articles to enrich")
    
    # Merge: prefer existing cached articles (they have images), add new enriched ones
    merged_ids = set()
    merged = []
    # First add all existing articles (they have images/enrichment from previous builds)
    for a in existing_articles:
        aid = a.get("id", "")
        if aid and aid not in merged_ids:
            merged_ids.add(aid)
            merged.append(a)
    # Then add newly enriched articles
    for a in all_articles:
        if a["id"] not in merged_ids:
            merged_ids.add(a["id"])
            merged.append(a)
    all_articles = sorted(merged, key=lambda a: a.get("published", ""), reverse=True)
    
    # 10. Re-enrich batch: try to fix existing articles missing images (150 per build)
    needs_fix = [a for a in all_articles if not a.get("image") and a.get("real_url") and not a.get("source","").startswith("Vance on ")]
    needs_url = [a for a in all_articles if not a.get("real_url") and "news.google.com" in a.get("link","")]
    fix_batch_size = 150
    if needs_url:
        url_batch = needs_url[:fix_batch_size]
        print(f"\nRe-resolving {len(url_batch)} unresolved Google News URLs...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            resolved = list(ex.map(enrich_article, url_batch))
        resolved_map = {a["id"]: a for a in resolved if a.get("real_url")}
        fixed_urls = 0
        for i, a in enumerate(all_articles):
            if a["id"] in resolved_map:
                all_articles[i] = resolved_map[a["id"]]
                fixed_urls += 1
        print(f"  Resolved {fixed_urls} URLs")
    if needs_fix:
        fix_batch = needs_fix[:fix_batch_size]
        print(f"\nRe-fetching images for {len(fix_batch)} articles (of {len(needs_fix)} needing fix)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            refixed = list(ex.map(enrich_article, fix_batch))
        fixed_count = 0
        refix_map = {a["id"]: a for a in refixed if a.get("image")}
        for i, a in enumerate(all_articles):
            if a["id"] in refix_map:
                all_articles[i] = refix_map[a["id"]]
                fixed_count += 1
        print(f"  Fixed {fixed_count} images")
    
    print(f"Total articles after merge: {len(all_articles)}")
    total_img = sum(1 for a in all_articles if a.get("image"))
    print(f"Total images: {total_img}/{len(all_articles)}")
    
    # 11. Fix source names retroactively on all cached articles
    fixed_names = 0
    for a in all_articles:
        old_name = a.get("source", "")
        new_name = clean_source_name(old_name)
        if new_name != old_name:
            a["source"] = new_name
            fixed_names += 1
    if fixed_names:
        print(f"Fixed {fixed_names} source names")

    build_time = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Find all existing daily briefing dates
    daily_dir_check = os.path.join(OUTPUT_DIR, "daily")
    available_dates = []
    if os.path.exists(daily_dir_check):
        for f in sorted(os.listdir(daily_dir_check), reverse=True):
            if f.endswith(".html"):
                available_dates.append(f.replace(".html", ""))
    html_content = generate_html(all_articles, build_time, social_posts=scraped_social, today=today, daily_dates=available_dates)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\nGenerated: {OUTPUT_FILE}")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=2)
    print(f"Saved: {DATA_FILE}")

    # 12. Generate topic pages
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
    <title>JD Vance &amp; {topic_name} - Latest News | The Vance Daily</title>
    <meta name="description" content="{count} articles about JD Vance and {topic_name} from {len(sources_in_topic)} sources. See how Left, Center, and Right media cover Vance on {topic_name}.">
    <link rel="canonical" href="https://thevancedaily.com/topics/{slug}.html">
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
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-88N61Z6BFW"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-88N61Z6BFW");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to The Vance Daily</a>
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
        <p><a href="/">The Vance Daily</a> — Automated news aggregation. <a href="mailto:contact@thevancedaily.com">contact@thevancedaily.com</a></p>
    </div>
</body>
</html>'''
        filepath = os.path.join(topics_dir, f"{slug}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(topic_html)
        topic_pages.append(slug)
    print(f"Generated {len(topic_pages)} topic pages: {', '.join(topic_pages)}")

    # 13. Generate "The Vance Daily" briefing page
    daily_dir = os.path.join(OUTPUT_DIR, "daily")
    os.makedirs(daily_dir, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_display = datetime.now(timezone.utc).strftime("%B %d, %Y")

    bias_summary_parts = []
    bc2 = Counter(a["bias"] for a in all_articles if not a["source"].startswith("Vance on "))
    for bk, bl in [("L","Left"),("LL","Leans Left"),("C","Center"),("LR","Leans Right"),("R","Right")]:
        if bc2.get(bk, 0) > 0:
            bias_summary_parts.append(f"{bl}: {bc2[bk]}")

    top_topics_list = [t for t in Counter(a["topic"] for a in all_articles).most_common(5) if t[0] != "General"]

    # Try to generate briefing with Claude API
    briefing_text = ""
    top_headlines = [a for a in all_articles if not a["source"].startswith("Vance on ")][:15]
    headline_list = "\n".join(f"- {a['title']} ({a['source']}, {BIAS_LABELS.get(a['bias'],'Unrated')})" for a in top_headlines)

    try:
        import urllib.request, json as j2
        api_body = j2.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": f"""You are writing "The Vance Daily" - a short, factual morning briefing about JD Vance for {today_display}. Based on these top headlines from today:

{headline_list}

Write a briefing with:
1. A one-sentence factual opener summarizing the day's biggest Vance story
2. 4-5 of the most important stories, each as a bold title followed by one tight sentence summarizing the facts. Format each as: **Bold title**: summary sentence.
3. A "Left vs Right" paragraph: 2-3 sentences neutrally describing how Left-leaning and Right-leaning outlets are covering Vance differently today. Do not take sides or editorialize.
4. A neutral one-line sign-off

CRITICAL: You must be completely neutral and unbiased. Do not editorialize. Do not use sarcasm, humor, or loaded language. Do not express any opinion about Vance, his policies, or any political party. Just report the facts as covered by the sources. This is a news aggregator, not an opinion site.

Keep it under 250 words. Write in a clean, professional tone. Do not use em dashes. Do not repeat the same headline twice even if multiple sources cover it."""}]
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
        # Convert ## headers
        if line.startswith("## "):
            briefing_html_body += f"<h2>{line[3:]}</h2>"
        elif line.startswith("# "):
            briefing_html_body += f"<h2>{line[2:]}</h2>"
        # Full-line bold = header
        elif line.startswith("**") and line.endswith("**") and line.count("**") == 2:
            briefing_html_body += f"<h2>{line.strip('*')}</h2>"
        # Bullet points
        elif line.startswith("- "):
            inner = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[2:])
            briefing_html_body += f"<p style='padding-left:1rem;margin-bottom:.4rem'>&#8226; {inner}</p>"
        else:
            # Convert inline **bold** to <strong>
            inner = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            briefing_html_body += f"<p>{inner}</p>"

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
    <title>The Vance Daily - {today_display} | The Vance Daily</title>
    <meta name="description" content="Your daily JD Vance briefing for {today_display}. Top stories, media bias analysis, and what Left and Right are saying about the Vice President.">
    <link rel="canonical" href="https://thevancedaily.com/daily/{today}.html">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'DM Sans',sans-serif;background:#f6f4f0;color:#1a1714;max-width:680px;margin:0 auto;padding:2rem 1.5rem}}
        .back{{font-size:.8rem;color:#6b6560;text-decoration:none;display:inline-flex;align-items:center;gap:.3rem;margin-bottom:1.5rem}}
        .back:hover{{color:#1a1714}}
        .masthead{{text-align:center;margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:3px double #e2ddd5}}
        .masthead-flag{{margin-bottom:.5rem}}
        .masthead-flag svg{{width:60px;height:40px;border-radius:3px;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
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
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-88N61Z6BFW"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-88N61Z6BFW");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to all articles</a>

    <div class="masthead">
        <div class="masthead-flag"><svg viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect width="60" height="40" fill="#fff"/><g fill="#B22234"><rect y="0" width="60" height="3.08"/><rect y="6.15" width="60" height="3.08"/><rect y="12.31" width="60" height="3.08"/><rect y="18.46" width="60" height="3.08"/><rect y="24.62" width="60" height="3.08"/><rect y="30.77" width="60" height="3.08"/><rect y="36.92" width="60" height="3.08"/></g><rect width="24" height="21.54" fill="#3C3B6E"/></svg></div>
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
            <button onclick="var e=document.getElementById('dailyEmail').value;if(e&&e.includes('@')){{var f=new FormData();f.append('email',e);fetch('https://buttondown.com/api/emails/embed-subscribe/thevancedaily',{{method:'POST',body:f}}).then(function(){{alert('Subscribed! The Vance Daily is on its way.');document.getElementById('dailyEmail').value=''}}).catch(function(){{alert('Subscribed! The Vance Daily is on its way.');document.getElementById('dailyEmail').value=''}})}}">Subscribe</button>
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
        <p><a href="/">The Vance Daily</a> &middot; <a href="mailto:contact@thevancedaily.com">contact@thevancedaily.com</a></p>
        <p style="margin-top:.3rem">Not affiliated with any political campaign, party, government or media entity. Just a guy who loves building stuff.</p>
    </div>
</body>
</html>'''
    daily_path = os.path.join(daily_dir, f"{today}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(daily_html)
    print(f"Generated: The Vance Daily /daily/{today}.html")

    # 14. Generate Disclaimer & Terms page
    disclaimer_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Disclaimer &amp; Terms | The Vance Daily</title>
    <meta name="description" content="Legal disclaimer and terms of use for The Vance Daily news aggregator.">
    <link rel="canonical" href="https://thevancedaily.com/disclaimer.html">
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
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-88N61Z6BFW"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","G-88N61Z6BFW");</script>
</head>
<body>
    <a href="/" class="back">&larr; Back to The Vance Daily</a>
    <h1>Disclaimer &amp; Terms of Use</h1>

    <h2>What This Site Is</h2>
    <p>The Vance Daily (thevancedaily.com) is an automated news aggregation service. We collect headlines and links to articles about JD Vance from publicly available news sources and RSS feeds. We do not host, reproduce, or republish article content. All headlines link directly to the original publisher's website.</p>

    <h2>No Affiliation</h2>
    <p>The Vance Daily is not affiliated with, endorsed by, or connected to JD Vance, any political campaign, political party, government office, or any of the news organizations whose content we link to. This is an independent project.</p>

    <h2>Political Bias Ratings</h2>
    <p>The political bias labels displayed on this site (Left, Leans Left, Center, Leans Right, Right) are based on ratings published by <a href="https://www.allsides.com/media-bias" target="_blank">AllSides.com</a>, a third-party media bias rating organization. We report their classifications and do not make independent bias determinations. If you believe a rating is incorrect, please contact AllSides directly or <a href="mailto:contact@thevancedaily.com">let us know</a> and we will review it.</p>

    <h2>Headlines &amp; Fair Use</h2>
    <p>We display article headlines as short factual descriptions to identify linked content. Headlines are not copyrightable under US law as they are too brief to constitute original works of authorship. We link to the original source for every headline, driving traffic to the original publisher. If you are a publisher and would like your content removed from this aggregator, please contact us at <a href="mailto:contact@thevancedaily.com">contact@thevancedaily.com</a> and we will remove it promptly.</p>

    <h2>No Warranty</h2>
    <p>This site is provided "as is" without warranty of any kind. We make no guarantees about the accuracy, completeness, or timeliness of the information displayed. We are not responsible for the content of linked third-party websites.</p>

    <h2>Social Media Content</h2>
    <p>Social media posts attributed to JD Vance are sourced from his publicly available accounts on X (Twitter), Instagram, TikTok, Truth Social, and Facebook. We display brief excerpts and link to the original posts. These are public statements by a public official.</p>

    <h2>User-Submitted Content</h2>
    <p>Source suggestions submitted through our site are used solely for improving our news coverage. We do not share your email address with third parties.</p>

    <h2>Takedown Requests</h2>
    <p>If you believe any content on this site infringes your rights, please contact us at <a href="mailto:contact@thevancedaily.com">contact@thevancedaily.com</a> with details of the specific content and the basis for your concern. We will respond within 48 hours.</p>

    <h2>Contact</h2>
    <p><a href="mailto:contact@thevancedaily.com">contact@thevancedaily.com</a></p>

    <p style="font-size:.78rem;color:#9e9790;margin-top:1.5rem">Last updated: March 27, 2026</p>

    <div class="ft">
        <p><a href="/" style="color:#6b6560;text-decoration:none">The Vance Daily</a></p>
    </div>
</body>
</html>'''
    with open(os.path.join(OUTPUT_DIR, "disclaimer.html"), "w", encoding="utf-8") as f:
        f.write(disclaimer_html)
    print("Generated: disclaimer.html")

    # 13. Generate sitemap.xml (with all pages including daily briefing archive)
    sitemap_urls = [
        f'    <url><loc>https://thevancedaily.com/</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>',
        f'    <url><loc>https://thevancedaily.com/disclaimer.html</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.3</priority></url>',
    ]
    # Add all daily briefing pages
    daily_dir_sitemap = os.path.join(OUTPUT_DIR, "daily")
    if os.path.exists(daily_dir_sitemap):
        for f in sorted(os.listdir(daily_dir_sitemap)):
            if f.endswith(".html"):
                date_str = f.replace(".html", "")
                sitemap_urls.append(f'    <url><loc>https://thevancedaily.com/daily/{f}</loc><lastmod>{date_str}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>')
    for slug in topic_pages:
        sitemap_urls.append(f'    <url><loc>https://thevancedaily.com/topics/{slug}.html</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>')

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(sitemap_urls) + '\n</urlset>'
    with open(os.path.join(OUTPUT_DIR, "sitemap.xml"), "w") as f:
        f.write(sitemap)

    # 13. Generate robots.txt
    robots = '''User-agent: *
Allow: /
Sitemap: https://thevancedaily.com/sitemap.xml
'''
    with open(os.path.join(OUTPUT_DIR, "robots.txt"), "w") as f:
        f.write(robots)

    print(f"Generated: sitemap.xml ({len(sitemap_urls)} URLs), robots.txt")

    # 14. Send daily briefing email via Buttondown (only once per day, at ~12:00 UTC)
    current_hour = datetime.now(timezone.utc).hour
    buttondown_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    sent_flag = os.path.join(OUTPUT_DIR, f".sent_{today}")
    if buttondown_key and briefing_text and current_hour >= 12 and not os.path.exists(sent_flag):
        try:
            # Build branded email HTML
            email_header = '''<div style="text-align:center;padding:20px 0 15px;border-bottom:2px solid #b8322a;margin-bottom:20px">
<a href="https://thevancedaily.com" style="text-decoration:none">
<span style="font-family:Georgia,serif;font-size:28px;font-weight:900;color:#1a1714">The <span style="color:#b8322a">Vance</span> Daily</span>
</a>
<p style="font-size:11px;color:#9e9790;margin:4px 0 0;letter-spacing:0.04em;text-transform:uppercase">The Vance Daily - ''' + today_display + '''</p>
</div>'''
            
            # Convert briefing to HTML paragraphs
            email_body = ""
            for line in briefing_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                email_body += f'<p style="font-family:-apple-system,Arial,sans-serif;font-size:15px;line-height:1.6;color:#1a1714;margin:0 0 12px">{line}</p>'
            
            email_footer = f'''<div style="border-top:1px solid #e2ddd5;margin-top:24px;padding-top:16px;text-align:center">
<p style="font-size:13px;margin:0 0 8px"><a href="https://thevancedaily.com/daily/{today}.html" style="color:#b8322a;text-decoration:none;font-weight:600">Read the full briefing with all headlines</a></p>
<p style="font-size:12px;color:#9e9790;margin:0 0 4px"><a href="https://thevancedaily.com" style="color:#9e9790">The Vance Daily</a> - {len(all_articles)} articles from {len(set(a["source"] for a in all_articles))} sources</p>
<p style="font-size:11px;color:#9e9790;margin:12px 0 0">Not affiliated with any political campaign, party, government or media entity.</p>
</div>'''
            
            full_email = email_header + email_body + email_footer
            
            email_data = json.dumps({
                "subject": f"The Vance Daily - {today_display}",
                "body": full_email,
                "status": "about_to_send",
            }).encode()
            req = urllib.request.Request(
                "https://api.buttondown.com/v1/emails",
                data=email_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Token {buttondown_key}",
                    "X-Buttondown-Live-Dangerously": "true",
                }
            )
            resp = urllib.request.urlopen(req, timeout=15)
            print(f"  Buttondown: daily email sent for {today_display}")
            with open(sent_flag, "w") as f:
                f.write(today)
        except Exception as e:
            print(f"  Buttondown email failed: {e}")
    elif not buttondown_key:
        print("  Buttondown: no API key, skipping email")
    elif os.path.exists(sent_flag):
        print(f"  Buttondown: already sent for {today}")
    else:
        print(f"  Buttondown: waiting until 12:00 UTC to send (current: {current_hour}:00)")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
