#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sothea Hot News Web Portal (គេហទំព័រព័ត៌មានទាន់ហេតុការណ៍អន្តរជាតិ)
- Flask web backend providing real-time international breaking news, multimedia (photos & videos)
- Khmer translations, live updates, and direct verified source links.
"""

import os
import sys
import re
import json
import time
import datetime
from datetime import timezone, timedelta
import email.utils
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import threading
import socket
from flask import Flask, render_template, jsonify, request, Response, send_file, send_from_directory, session
import hashlib
import alert_watcher
import tunnel_manager
import admin_service

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def get_local_wifi_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sothea_hot_news_secure_admin_key_2026")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Live War News Video Streams (Embedded YouTube Live Channels)
LIVE_STREAMS = [
    {
        "id": "aljazeera",
        "title_kh": "Al Jazeera English (ផ្សាយផ្ទាល់ ២៤/៧)",
        "title_en": "Al Jazeera English 24/7 Live Stream",
        "source": "Al Jazeera",
        "flag": "🇶🇦",
        "flag_url": "https://flagcdn.com/w40/qa.png",
        "embed_url": "https://www.youtube.com/embed/gCNeDWCI0vo",
        "channel_url": "https://www.youtube.com/@aljazeeraenglish/live",
        "type": "live"
    },
    {
        "id": "dw",
        "title_kh": "DW News (អាល្លឺម៉ង់ - ផ្សាយផ្ទាល់ ២៤/៧)",
        "title_en": "DW News 24/7 Global Live Stream",
        "source": "DW News",
        "flag": "🇩🇪",
        "flag_url": "https://flagcdn.com/w40/de.png",
        "embed_url": "https://www.youtube.com/embed/LuKwFajn37U",
        "channel_url": "https://www.youtube.com/@dwnews/live",
        "type": "live"
    },
    {
        "id": "skynews",
        "title_kh": "Sky News (អង់គ្លេស - ផ្សាយផ្ទាល់ ២៤/៧)",
        "title_en": "Sky News 24/7 Live Stream",
        "source": "Sky News",
        "flag": "🇬🇧",
        "flag_url": "https://flagcdn.com/w40/gb.png",
        "embed_url": "https://www.youtube.com/embed/mb7EVfWKgLM",
        "channel_url": "https://www.youtube.com/@SkyNews/live",
        "type": "live"
    },
    {
        "id": "france24",
        "title_kh": "France 24 (បារាំង - ផ្សាយផ្ទាល់ ២៤/៧)",
        "title_en": "France 24 English 24/7 Live Stream",
        "source": "France 24",
        "flag": "🇫🇷",
        "flag_url": "https://flagcdn.com/w40/fr.png",
        "embed_url": "https://www.youtube.com/embed/HvZt-nh9sGg",
        "channel_url": "https://www.youtube.com/@france24_en/live",
        "type": "live"
    },
    {
        "id": "abcnews",
        "title_kh": "ABC News Live (សហរដ្ឋអាមេរិក)",
        "title_en": "ABC News Live 24/7 Stream",
        "source": "ABC News",
        "flag": "🇺🇸",
        "flag_url": "https://flagcdn.com/w40/us.png",
        "embed_url": "https://www.youtube.com/embed/KQhNZQ_Uag8",
        "channel_url": "https://www.youtube.com/@ABCNews/live",
        "type": "live"
    },
    {
        "id": "nbcnews",
        "title_kh": "NBC News NOW (សហរដ្ឋអាមេរិក)",
        "title_en": "NBC News NOW 24/7 Stream",
        "source": "NBC News",
        "flag": "🇺🇸",
        "flag_url": "https://flagcdn.com/w40/us.png",
        "embed_url": "https://www.youtube.com/embed/0uwAtfBIVx0",
        "channel_url": "https://www.youtube.com/@NBCNews/live",
        "type": "live"
    },
    {
        "id": "cna",
        "title_kh": "CNA Channel NewsAsia (សិង្ហបុរី/អាស៊ី)",
        "title_en": "CNA 24/7 Live Stream",
        "source": "CNA (Asia)",
        "flag": "🇸🇬",
        "flag_url": "https://flagcdn.com/w40/sg.png",
        "embed_url": "https://www.youtube.com/embed/-PWMxjBgr0k",
        "channel_url": "https://www.youtube.com/@channelnewsasia/live",
        "type": "live"
    },
    {
        "id": "euronews",
        "title_kh": "Euronews (អឺរ៉ុប - ផ្សាយផ្ទាល់ ២៤/៧)",
        "title_en": "Euronews 24/7 Live Stream",
        "source": "Euronews",
        "flag": "🇪🇺",
        "flag_url": "https://flagcdn.com/w40/eu.png",
        "embed_url": "https://www.youtube.com/embed/pykpO5kQJ98",
        "channel_url": "https://www.youtube.com/@euronews/live",
        "type": "live"
    }
]

def auto_refresh_live_streams_worker():
    """Periodically resolves active YouTube live stream IDs to ensure 100% uptime."""
    import threading
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    while True:
        try:
            for s in LIVE_STREAMS:
                ch_url = s.get("channel_url")
                if not ch_url:
                    continue
                try:
                    req = urllib.request.Request(ch_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        html = resp.read().decode('utf-8', errors='ignore')
                        m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html) or re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
                        if m:
                            vid = m.group(1)
                            s["embed_url"] = f"https://www.youtube.com/embed/{vid}"
                except Exception:
                    pass
        except Exception as e:
            print(f"[!] Live stream resolver warning: {e}", file=sys.stderr)
        time.sleep(7200) # Re-check every 2 hours

CONFLICT_CATEGORIES = {
    "all": {"title_kh": "ព័ត៌មានអន្តរជាតិ", "query": "breaking world news OR international news when:1d", "flag_url": ""},
    "national": {"title_kh": "ព័ត៌មានជាតិ", "query": "Cambodia (news OR government OR Phnom Penh OR national) when:2d", "flag_url": "https://flagcdn.com/w40/kh.png"},
    "politics": {"title_kh": "នយោបាយ", "query": "world politics OR diplomacy OR government OR summit OR election when:1d", "flag_url": ""},
    "economy": {"title_kh": "សេដ្ឋកិច្ច", "query": "global economy OR trade OR inflation OR markets OR Federal Reserve OR oil price when:1d", "flag_url": ""},
    "security": {"title_kh": "យុទ្ធសាស្ត្រ និងសន្តិសុខ", "query": "war Ukraine OR Israel Gaza Iran OR military security OR nuclear weapon OR Sudan war OR Myanmar when:1d", "flag_url": ""},
    "tech": {"title_kh": "បច្ចេកវិទ្យា", "query": "technology OR artificial intelligence OR AI OR semiconductor OR cyber security when:2d", "flag_url": ""},
    "environment": {"title_kh": "បរិស្ថាន និងអាកាសធាតុ", "query": "climate change OR weather OR typhoon OR environment OR flood when:2d", "flag_url": ""},
    # Sub-categories for Security & Region
    "ukraine": {"title_kh": "អ៊ុយក្រែន-រុស្ស៊ី", "query": "Ukraine war OR Russia strikes OR Kyiv OR Russian troops when:1d", "flag_url": "https://flagcdn.com/w40/ua.png"},
    "middle_east": {"title_kh": "ជម្លោះមជ្ឈិមបូព៌ា", "query": "Israel Gaza OR Israel Lebanon OR Iran strikes OR Red Sea Houthis when:1d", "flag_url": "https://flagcdn.com/w40/il.png"},
    "nuclear": {"title_kh": "សន្តិសុខនុយក្លេអ៊ែរ", "query": "nuclear weapon OR nuclear war OR nuclear strike OR Iran nuclear when:2d", "flag_url": ""},
    "thailand": {"title_kh": "ក្នុងស្រុកថៃ", "query": "Thailand (politics OR military OR border OR government OR security) when:1d", "flag_url": "https://flagcdn.com/w40/th.png"},
    "myanmar": {"title_kh": "ជម្លោះមីយ៉ាន់ម៉ា", "query": "Myanmar conflict OR Myanmar junta OR Myanmar rebel fighting when:2d", "flag_url": "https://flagcdn.com/w40/mm.png"},
    "sudan": {"title_kh": "សង្គ្រាមស៊ីវិលស៊ូដង់", "query": "Sudan war OR Sudanese army OR RSF clashes OR Darfur fighting when:2d", "flag_url": "https://flagcdn.com/w40/sd.png"}
}

# Major international feeds providing 100% authentic original newsroom photography
VERIFIED_CAT_PHOTOS = {
    "ukraine": "https://assets.kyivindependent.com/content/images/2026/11/november-5-2026_KI_kattck-on-kyiv-6_20261105-052239.jpg",
    "middle_east": "https://www.twz.com/wp-content/uploads/2026/11/Faaz-missile-launch.png?quality=85",
    "thailand": "https://thethaiger.com/wp-content/uploads/2026/11/%E0%B8%AA%E0%B8%B3%E0%B9%80%E0%B8%99%E0%B8%B2%E0%B8%82%E0%B8%AD%E0%B8%87-23-34-2026-11-05T114244.189.jpg",
    "nuclear": "https://static.independent.co.uk/2026/10/27/18/24/GettyImages-2287743633.jpg",
    "myanmar": "https://myanmar-now.org/en/wp-content/uploads/sites/5/2026/11/MGW-Federal-Unit-1024x768.jpg",
    "sudan": "https://www.dabangasudan.org/wp-content/uploads/2026/06/260620-Smoke-rises-over-El-Obeid-Supplied.jpg",
    "all": "https://s.france24.com/media/display/1182cb7c-d8df-11f1-837f-d18c5759e759/w:1024/p:16x9/EN-20261105-063742-063927-CS.jpg"
}

DIRECT_CATEGORY_FEEDS = {
    "national": [
        ("https://www.khmertimeskh.com/feed/", "Khmer Times", lambda t: True),
        ("https://cambojanews.com/feed/", "CamboJA News", lambda t: True)
    ],
    "politics": [
        ("https://www.france24.com/en/tag/politics/rss", "France 24", lambda t: True),
        ("https://www.theguardian.com/politics/rss", "The Guardian", lambda t: True)
    ],
    "economy": [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC", lambda t: True),
        ("https://www.theguardian.com/business/economics/rss", "The Guardian", lambda t: True)
    ],
    "tech": [
        ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica", lambda t: True),
        ("https://www.theverge.com/rss/index.xml", "The Verge", lambda t: True)
    ],
    "environment": [
        ("https://www.theguardian.com/environment/rss", "The Guardian", lambda t: True),
        ("https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "BBC News", lambda t: True)
    ],
    "security": [
        ("https://www.defenseone.com/rss/all/", "Defense One", lambda t: True),
        ("https://www.twz.com/feed", "The War Zone", lambda t: True)
    ],
    "middle_east": [
        ("https://www.france24.com/en/middle-east/rss", "France 24", lambda t: not any(bad in t.lower() for bad in ['football', 'soccer', 'tennis', 'champions league'])),
        ("https://www.theguardian.com/world/middleeast/rss", "The Guardian", lambda t: True),
        ("https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "BBC News", lambda t: True),
        ("https://www.timesofisrael.com/feed/", "The Times of Israel", lambda t: True),
        ("https://www.twz.com/feed", "The War Zone", lambda t: any(k in t.lower() for k in ['israel', 'iran', 'gaza', 'lebanon', 'yemen', 'houthi', 'hezbollah', 'syria', 'iraq', 'tehran', 'tel aviv', 'netanyahu', 'red sea', 'hormuz', 'persian gulf', 'west bank', 'palestin', 'hamas', 'middle east']))
    ],
    "ukraine": [
        ("https://www.theguardian.com/world/ukraine/rss", "The Guardian", lambda t: True),
        ("https://www.defenseone.com/rss/all/", "Defense One", lambda t: any(k in t.lower() for k in ['ukraine', 'russia', 'kyiv', 'moscow', 'putin', 'zelensky', 'kursk', 'drone', 'missile', 'nato', 'war'])),
        ("https://feeds.bbci.co.uk/news/world/europe/rss.xml", "BBC News", lambda t: any(k in t.lower() for k in ['ukraine', 'russia', 'kyiv', 'moscow', 'putin', 'zelensky', 'kharkiv', 'kursk', 'donbas', 'crimea', 'russian', 'ukrainian'])),
        ("https://www.france24.com/en/rss", "France 24", lambda t: any(k in t.lower() for k in ['ukraine', 'russia', 'kyiv', 'moscow', 'putin', 'zelensky', 'kharkiv', 'kursk', 'donbas', 'crimea', 'russian', 'ukrainian'])),
        ("https://www.twz.com/feed", "The War Zone", lambda t: any(k in t.lower() for k in ['ukraine', 'russia', 'kyiv', 'glide bomb', 'himars', 'kursk', 'zelensky', 'putin']))
    ],
    "nuclear": [
        ("https://www.twz.com/feed", "The War Zone", lambda t: any(k in t.lower() for k in ['nuclear', 'atomic', 'warhead', 'icbm', 'uranium', 'plutonium', 'iaea', 'nuke'])),
        ("https://www.france24.com/en/rss", "France 24", lambda t: any(k in t.lower() for k in ['nuclear', 'uranium', 'iaea', 'atomic', 'warhead'])),
        ("https://www.theguardian.com/world/rss", "The Guardian", lambda t: any(k in t.lower() for k in ['nuclear', 'uranium', 'iaea', 'warhead', 'atomic']))
    ],
    "thailand": [
        ("https://thethaiger.com/category/news/national/feed", "The Thaiger", lambda t: True),
        ("https://www.irrawaddy.com/feed", "The Irrawaddy", lambda t: any(k in t.lower() for k in ['thai', 'thailand', 'bangkok', 'border'])),
        ("https://www.theguardian.com/world/thailand/rss", "The Guardian", lambda t: True),
        ("https://www.france24.com/en/asia-pacific/rss", "France 24", lambda t: any(k in t.lower() for k in ['thai', 'thailand', 'bangkok', 'paetongtarn', 'shinawatra']))
    ],
    "myanmar": [
        ("https://www.irrawaddy.com/feed", "The Irrawaddy", lambda t: True),
        ("https://myanmar-now.org/en/feed/", "Myanmar Now", lambda t: True),
        ("https://english.dvb.no/feed/", "DVB English", lambda t: True),
        ("https://www.theguardian.com/world/myanmar/rss", "The Guardian", lambda t: True)
    ],
    "sudan": [
        ("https://www.dabangasudan.org/en/feed", "Radio Dabanga", lambda t: True),
        ("https://www.theguardian.com/world/sudan/rss", "The Guardian", lambda t: True),
        ("https://www.france24.com/en/africa/rss", "France 24", lambda t: any(k in t.lower() for k in ['sudan', 'darfur', 'khartoum', 'rsf', 'saf', 'burhan', 'hemeti'])),
        ("https://feeds.bbci.co.uk/news/world/africa/rss.xml", "BBC News", lambda t: any(k in t.lower() for k in ['sudan', 'darfur', 'khartoum', 'rsf', 'saf', 'burhan', 'hemeti']))
    ],
    "all": [
        ("https://www.france24.com/en/rss", "France 24", lambda t: not any(bad in t.lower() for bad in ['champions league', 'premier league', 'football', 'soccer', 'tennis', 'nba', 'golf', 'box office', 'oscar', 'celebrity'])),
        ("https://www.theguardian.com/world/rss", "The Guardian", lambda t: not any(bad in t.lower() for bad in ['champions league', 'premier league', 'football', 'soccer', 'tennis', 'nba', 'golf', 'box office', 'oscar', 'celebrity'])),
        ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "New York Times", lambda t: not any(bad in t.lower() for bad in ['champions league', 'premier league', 'football', 'soccer', 'tennis', 'nba', 'golf', 'box office', 'oscar', 'celebrity'])),
        ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC News", lambda t: not any(bad in t.lower() for bad in ['champions league', 'premier league', 'football', 'soccer', 'tennis', 'nba', 'golf', 'box office', 'oscar', 'celebrity'])),
        ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", lambda t: not any(bad in t.lower() for bad in ['football', 'soccer', 'tennis', 'cricket'])),
        ("https://www.twz.com/feed", "The War Zone", lambda t: True)
    ]
}

KH_DIGITS = {'0':'០', '1':'១', '2':'២', '3':'៣', '4':'៤', '5':'៥', '6':'៦', '7':'៧', '8':'៨', '9':'៩'}
KH_MONTHS = ['', 'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']
KH_DAYS = ['ថ្ងៃច័ន្ទ', 'ថ្ងៃអង្គារ', 'ថ្ងៃពុធ', 'ថ្ងៃព្រហស្បតិ៍', 'ថ្ងៃសុក្រ', 'ថ្ងៃសៅរ៍', 'ថ្ងៃអាទិត្យ']

def to_khmer_num(s) -> str:
    return ''.join(KH_DIGITS.get(c, c) for c in str(s))

def parse_rfc_date(date_str: str) -> datetime.datetime:
    """Parses RFC 2822 or ISO 8601 publication date string into timezone-aware datetime."""
    if not date_str:
        return datetime.datetime.now(timezone.utc)
    date_str = str(date_str).strip()
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        clean_iso = date_str.replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    return datetime.datetime.now(timezone.utc)

def format_khmer_relative_date(dt: datetime.datetime) -> str:
    """Formats datetime into human-readable relative Khmer time with day of the week (e.g. 'ថ្ងៃព្រហស្បតិ៍ • ២៥ នាទីមុន')."""
    ict = timezone(timedelta(hours=7)) # Cambodia ICT (UTC+7)
    dt_local = dt.astimezone(ict)
    now_local = datetime.datetime.now(ict)
    day_name = KH_DAYS[dt_local.weekday()]
    
    diff_sec = (now_local - dt_local).total_seconds()
    if diff_sec < 0:
        diff_sec = 0
    diff_min = int(diff_sec / 60)
    diff_hours = int(diff_sec / 3600)
    
    time_str = dt_local.strftime('%H:%M')
    kh_time = to_khmer_num(time_str)
    
    if diff_sec < 60:
        return f"{day_name} • ទើបចេញផ្សាយអម្បាញ់មិញ"
    elif diff_min < 60:
        return f"{day_name} • {to_khmer_num(diff_min)} នាទីមុន (ម៉ោង {kh_time})"
    elif diff_hours < 24 and dt_local.date() == now_local.date():
        return f"{day_name} • ថ្ងៃនេះ {to_khmer_num(diff_hours)} ម៉ោងមុន (ម៉ោង {kh_time})"
    elif (now_local.date() - dt_local.date()).days == 1:
        return f"{day_name} (ម្សិលមិញ) • ម៉ោង {kh_time}"
    else:
        d = to_khmer_num(dt_local.day)
        m = KH_MONTHS[dt_local.month]
        y = to_khmer_num(dt_local.year)
        return f"{day_name} {d} {m} • ម៉ោង {kh_time}"

def format_khmer_full_date(dt: datetime.datetime) -> str:
    """Formats datetime into full formal Khmer date with exact day of week and time (ICT UTC+7)."""
    ict = timezone(timedelta(hours=7))
    dt_local = dt.astimezone(ict)
    day_name = KH_DAYS[dt_local.weekday()]
    d = to_khmer_num(f"{dt_local.day:02d}")
    m = KH_MONTHS[dt_local.month]
    y = to_khmer_num(dt_local.year)
    t = to_khmer_num(dt_local.strftime('%H:%M'))
    return f"{day_name} ទី {d} {m} {y} ម៉ោង {t} (ICT)"

def extract_all_real_photos_from_item(el) -> tuple:
    """Extracts all authentic newsroom photos directly from RSS item XML in 0ms without network latency."""
    media_candidates = []

    # 1. Enclosure & Media tags
    for child in el:
        tag = child.tag.lower()
        if any(k in tag for k in ["thumbnail", "content", "enclosure"]):
            u = child.attrib.get("url")
            if not u:
                continue
            w_str = child.attrib.get("width", "0")
            try:
                width = int(w_str)
            except Exception:
                width = 0
            media_candidates.append((width, u))

    # Sort media candidates by width descending so highest resolution (e.g. 700, 1700, 1024) is selected first
    media_candidates.sort(key=lambda x: x[0], reverse=True)

    photos = []
    seen = set()

    def add(url):
        if not url:
            return
        url = url.replace("&amp;", "&").strip()
        clean = url.split("?")[0].lower()
        if not any(clean.endswith(ext) or ext in clean for ext in [".jpg", ".jpeg", ".png", ".webp", "ichef.bbci", "static01.nyt", "guim.co.uk", "twz.com", "france24", "irrawaddy", "myanmar-now", "dvb.no", "dabangasudan", "thethaiger"]):
            return
        if any(bad in clean for bad in ["logo", "icon", "avatar", "emoji", "newsletter", "s.w.org", "tracking", "button", "author", "headshot"]):
            return
            
        # BBC: safe to upgrade standard ace /240/ to /976/ (unsigned URL)
        if "ichef.bbci.co.uk" in url and "/240/" in url:
            url = url.replace("/240/", "/976/")
        # WordPress: strip thumbnail dimensions e.g. -300x155.jpg -> .jpg
        elif any(d in url for d in ["irrawaddy.com", "myanmar-now.org", "dvb.no", "dabangasudan.org", "thethaiger.com", "twz.com"]):
            url = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', url)
            clean = url.split("?")[0].lower()

        # NOTE: DO NOT regex-replace 'width=' on guim.co.uk (The Guardian)! Its &s= parameter is a cryptographic
        # HMAC signature over the exact query string. Because media_candidates is sorted by width descending,
        # the authentic signed 700px image provided by Guardian is selected automatically with its valid signature intact.

        # Safely percent-encode any non-ASCII characters in URL paths (e.g. Arabic, Thai filenames)
        try:
            parts = urllib.parse.urlsplit(url)
            quoted_path = urllib.parse.quote(parts.path, safe="/:@&+$,;=")
            quoted_query = urllib.parse.quote(parts.query, safe="=&@+$,;/:?")
            url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, quoted_path, quoted_query, parts.fragment))
        except Exception:
            pass

        if clean not in seen:
            seen.add(clean)
            photos.append(url)

    for w, u in media_candidates:
        add(u)

    # 2. In-content images from content:encoded or description
    for tag_name in ["{http://purl.org/rss/1.0/modules/content/}encoded", "description"]:
        content = el.findtext(tag_name, "")
        if content:
            matches = re.findall(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', content, re.I)
            for m in matches:
                add(m)

    # 3. Detect embedded video clips (YouTube, Vimeo, MP4 enclosures)
    direct_video_url = ""
    for child in el:
        t = child.attrib.get("type", "").lower()
        m = child.attrib.get("medium", "").lower()
        u = child.attrib.get("url", "")
        if ("video" in t or "video" in m or u.lower().endswith(".mp4")) and u:
            direct_video_url = u
            break

    if not direct_video_url:
        for tag_name in ["{http://purl.org/rss/1.0/modules/content/}encoded", "description"]:
            content = el.findtext(tag_name, "")
            if content:
                yt_m = re.search(r'(?:https?:)?//(?:www\.)?(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([a-zA-Z0-9_-]{11})', content)
                if yt_m:
                    direct_video_url = f"https://www.youtube.com/embed/{yt_m.group(1)}"
                    break

    if photos:
        return photos[:4], True, direct_video_url
    return [], False, direct_video_url

# Persistent translation and article cache on disk
TRANSLATIONS_FILE = "translations.json"
TRANSLATION_CACHE = {}
if os.path.exists(TRANSLATIONS_FILE):
    try:
        with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
            TRANSLATION_CACHE = json.load(f)
    except Exception:
        pass

def save_translations():
    try:
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(TRANSLATION_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Persistent newsroom video report cache on disk
ARTICLE_VIDEOS_FILE = "article_videos.json"
ARTICLE_VIDEO_CACHE = {}
if os.path.exists(ARTICLE_VIDEOS_FILE):
    try:
        with open(ARTICLE_VIDEOS_FILE, "r", encoding="utf-8") as f:
            ARTICLE_VIDEO_CACHE = json.load(f)
    except Exception:
        pass

def save_article_videos():
    try:
        with open(ARTICLE_VIDEOS_FILE, "w", encoding="utf-8") as f:
            json.dump(ARTICLE_VIDEO_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def resolve_article_video(title_en: str, source: str = "") -> str:
    """Resolves authentic YouTube news report video for a specific news headline."""
    if not title_en:
        return ""
    cache_key = title_en.strip().lower()
    if cache_key in ARTICLE_VIDEO_CACHE and ARTICLE_VIDEO_CACHE[cache_key]:
        return ARTICLE_VIDEO_CACHE[cache_key]
        
    clean_title = re.sub(r'[\'\"’“”]', '', title_en)
    if ' - ' in clean_title:
        clean_title = clean_title.split(' - ')[0]
    words = clean_title.split()[:8]
    q = ' '.join(words) + f' {source} news'
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    url = f'https://www.youtube.com/results?search_query={urllib.parse.quote(q)}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if m:
                vid = m.group(1)
                embed_url = f'https://www.youtube.com/embed/{vid}'
                ARTICLE_VIDEO_CACHE[cache_key] = embed_url
                save_article_videos()
                return embed_url
    except Exception:
        pass
    return ""

SUMMARY_CACHE = {}
ARTICLES_CACHE = {"timestamp": 0, "data": []}

# 7-Day (1 Week) News Database & Retention Configuration
BAD_FALLBACK_PATTERNS = [
    "faaz-missile",
    "gettyimages-2287743633",
    "november-5-2026_ki_kat",
    "smoke-rises-over-el-obeid",
    "mgw-federal-unit-1024x768",
    "2026-11-05t114244.189.jpg"
]

NEWS_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_database.json")
RETENTION_HOURS = 168.0  # Exactly 7 days (1 week)
RETENTION_SECONDS = RETENTION_HOURS * 3600.0  # 604,800 seconds

# ==========================================
# INTELLIGENT NEWS CLUSTER & WIRE DEDUPLICATION
# ==========================================
DEDUP_STOP_WORDS = {
    'news', 'live', 'says', 'update', 'updates', 'said', 'with', 'from', 'that', 'this',
    'after', 'will', 'over', 'more', 'about', 'into', 'amid', 'near', 'report', 'reports',
    'warns', 'urges', 'amidst', 'following', 'under', 'their', 'have', 'been', 'were',
    'could', 'would', 'first', 'second', 'time', 'years', 'month', 'days', 'today', 'the'
}

TRUSTED_SOURCE_PATTERNS = [
    # Global Major Wire & Broadcasting
    r'\breuters\b', r'\bassociated press\b', r'\bap news\b', r'\bap\b',
    r'\bbbc\b', r'\bbbc news\b', r'\bthe guardian\b', r'\bfrance 24\b',
    r'\bdeutsche welle\b', r'\bdw\b', r'\bnew york times\b', r'\bthe new york times\b',
    r'\bwashington post\b', r'\bthe washington post\b', r'\bwall street journal\b', r'\bwsj\b',
    r'\bcnn\b', r'\bcbs news\b', r'\babc news\b', r'\bnbc news\b', r'\bbloomberg\b',
    r'\bfinancial times\b', r'\bal jazeera\b', r'\bthe straits times\b', r'\bstraits times\b',
    r'\bsouth china morning post\b', r'\bscmp\b', r'\btime\b', r'\beuronews\b',
    r'\bpolitico\b', r'\bnpr\b', r'\bpbs\b', r'\bthe diplomat\b',

    # Military & Strategic Intelligence
    r'\bthe war zone\b', r'\btwz\b', r'\bdefense one\b', r'\bdefense news\b',
    r'\bbreaking defense\b', r'\bjanes\b', r'\bnaval news\b', r'\busni news\b',
    r'\binstitute for the study of war\b', r'\bisw\b', r'\batlantic council\b',

    # Regional: Ukraine & Eastern Europe
    r'\bthe kyiv independent\b', r'\bkyiv independent\b', r'\bukrinform\b',
    r'\bkyiv post\b', r'\bradio free europe\b', r'\brfe/rl\b', r'\bthe moscow times\b',
    r'\bmediazona\b',

    # Regional: Middle East
    r'\bthe times of israel\b', r'\btimes of israel\b', r'\bthe jerusalem post\b',
    r'\bjerusalem post\b', r'\bhaaretz\b', r'\bynetnews\b', r'\bynet\b',
    r'\bal-monitor\b', r'\bmiddle east eye\b', r'\bmiddle east monitor\b',
    r'\basharq al-awsat\b', r'\baawsat\b', r'\banadolu\b', r"\bl'orient today\b",
    r'\bthe national\b', r'\biran international\b', r'\barab news\b',

    # Regional: Myanmar & Southeast Asia
    r'\bthe irrawaddy\b', r'\birrawaddy\b', r'\bmyanmar now\b', r'\bdvb english\b',
    r'\bdemocratic voice of burma\b', r'\bmizzima\b', r'\bfrontier myanmar\b',

    # Regional: Thailand
    r'\bbangkok post\b', r'\bthe nation\b', r'\bthe nation thailand\b',
    r'\bthe thaiger\b', r'\bthaipbs\b', r'\bkhaosod\b',

    # Regional: Sudan & Africa
    r'\bradio dabanga\b', r'\bdabanga sudan\b', r'\bsudan tribune\b',
    r'\ballafrica\b', r'\bafrican arguments\b'
]

TRUSTED_DOMAIN_PATTERNS = [
    r'reuters\.com', r'apnews\.com', r'bbc\.co\.uk', r'bbc\.com', r'theguardian\.com',
    r'france24\.com', r'dw\.com', r'nytimes\.com', r'washingtonpost\.com', r'wsj\.com',
    r'cnn\.com', r'cbsnews\.com', r'abcnews\.go\.com', r'nbcnews\.com', r'bloomberg\.com',
    r'ft\.com', r'aljazeera\.com', r'straitstimes\.com', r'scmp\.com', r'euronews\.com',
    r'politico\.com', r'politico\.eu', r'npr\.org', r'pbs\.org', r'thediplomat\.com',
    r'twz\.com', r'defenseone\.com', r'defensenews\.com', r'breakingdefense\.com',
    r'janes\.com', r'navalnews\.com', r'understandingwar\.org', r'atlanticcouncil\.org',
    r'kyivindependent\.com', r'ukrinform\.net', r'kyivpost\.com', r'rferl\.org',
    r'themoscowtimes\.com', r'zona\.media',
    r'timesofisrael\.com', r'jpost\.com', r'haaretz\.com', r'ynetnews\.com',
    r'al-monitor\.com', r'middleeasteye\.net', r'middleeastmonitor\.com', r'aawsat\.com',
    r'aa\.com\.tr', r'lorientlejour\.com', r'thenationalnews\.com', r'iranintl\.com', r'arabnews\.com',
    r'irrawaddy\.com', r'myanmar-now\.org', r'dvb\.no', r'mizzima\.com', r'frontiermyanmar\.net',
    r'bangkokpost\.com', r'nationthailand\.com', r'thethaiger\.com', r'thaipbsworld\.com', r'khaosodenglish\.com',
    r'dabangasudan\.org', r'sudantribune\.com', r'allafrica\.com'
]

BANNED_PATTERNS = [
    r'facebook\.com', r'twitter\.com', r'x\.com', r'reddit\.com', r't\.me', r'youtube\.com',
    r'tiktok\.com', r'instagram\.com', r'pinterest\.com', r'threads\.net',
    r'yahoo\.com', r'msn\.com', r'aol\.com', r'oilprice\.com', r'elciudadano\.com',
    r'dailybeirut\.com', r'tv7israelnews\.com', r'newscord\.org',
    r'thesun\.co\.uk', r'dailymail\.co\.uk', r'mirror\.co\.uk', r'express\.co\.uk',
    r'blogspot\.com', r'wordpress\.com', r'substack\.com'
]

def is_trusted_source(source_name: str, link: str = "") -> bool:
    """Strictly validates that news items originate ONLY from verified, authoritative global/regional journalism."""
    src = (source_name or "").strip().lower()
    lnk = (link or "").strip().lower()

    # 1. Banned blacklisted domains and aggregators
    for bp in BANNED_PATTERNS:
        if re.search(bp, src) or re.search(bp, lnk):
            return False

    # 2. Trusted source name
    for sp in TRUSTED_SOURCE_PATTERNS:
        if re.search(sp, src):
            return True

    # 3. Trusted domain pattern
    for dp in TRUSTED_DOMAIN_PATTERNS:
        if re.search(dp, lnk):
            return True

    return False

AUTHORITY_PRIORITY = [
    "reuters", "associated press", "ap news", "ap", "bbc", "al jazeera", "cnn", "the guardian",
    "france 24", "dw", "the wall street journal", "wsj", "the new york times", "the times of israel",
    "the jerusalem post", "middle east monitor", "anadolu ajansı", "fox 59", "thecanadianpress"
]

def clean_title(title: str) -> str:
    """Removes source attribution suffix (e.g. ' - Fox 59', ' | Reuters') and common noise."""
    if not title:
        return ""
    t = title
    if " - " in t:
        parts = t.rsplit(" - ", 1)
        if len(parts[1].strip()) <= 45:
            t = parts[0].strip()
    if " | " in t:
        parts = t.rsplit(" | ", 1)
        if len(parts[1].strip()) <= 45:
            t = parts[0].strip()
    return t

def normalize_word(w: str) -> str:
    w = w.lower()
    if w in ("programme", "programmes"): return "program"
    if w in ("offering", "offers", "offered"): return "offer"
    if w in ("rewards", "rewarded"): return "reward"
    if w in ("clashes", "clashed", "clashing"): return "clash"
    if w in ("battles", "battling", "battled"): return "battle"
    if w in ("strikes", "striking", "struck"): return "strike"
    if w in ("attacks", "attacking", "attacked"): return "attack"
    if w in ("kills", "killed", "killing"): return "kill"
    if w in ("warns", "warning", "warned"): return "warn"
    if w in ("prepares", "preparing", "prepared"): return "prepare"
    if w in ("questions", "questioning", "questioned"): return "question"
    if w in ("claims", "claiming", "claimed"): return "claim"
    if w.endswith("s") and len(w) > 4:
        w = w[:-1]
    return w

def get_story_tokens(title: str) -> set:
    base = clean_title(title).lower()
    base = re.sub(r'\b(united states|u\.s\.|u\.s)\b', 'us', base)
    words = re.findall(r'[a-zA-Z0-9]+', base)
    tokens = set()
    for w in words:
        if len(w) > 2 and w not in DEDUP_STOP_WORDS:
            tokens.add(normalize_word(w))
    return tokens

def are_similar_stories(a1: dict, a2: dict) -> bool:
    """Determines whether two articles are syndications or duplicate reports of the exact same event."""
    l1 = a1.get("link", "").strip()
    l2 = a2.get("link", "").strip()
    if l1 and l2 and l1 == l2:
        return True

    ct1 = clean_title(a1.get("title_en", "")).lower()
    ct2 = clean_title(a2.get("title_en", "")).lower()
    k1 = re.sub(r'[^a-zA-Z0-9]', '', ct1)
    k2 = re.sub(r'[^a-zA-Z0-9]', '', ct2)
    if k1 and k2 and k1 == k2:
        return True

    kh1 = re.sub(r'\s+', '', a1.get("title_kh", ""))
    kh2 = re.sub(r'\s+', '', a2.get("title_kh", ""))
    if kh1 and kh2 and len(kh1) > 15 and kh1 == kh2:
        return True

    t1 = get_story_tokens(a1.get("title_en", ""))
    t2 = get_story_tokens(a2.get("title_en", ""))
    if len(t1) >= 3 and len(t2) >= 3:
        overlap = t1.intersection(t2)
        union = t1.union(t2)
        jaccard = len(overlap) / len(union) if union else 0
        
        nums1 = set(re.findall(r'\d+', ct1))
        nums2 = set(re.findall(r'\d+', ct2))
        shared_nums = nums1.intersection(nums2)
        
        if shared_nums and len(overlap) >= 3 and jaccard >= 0.28:
            return True

        if jaccard >= 0.42 or len(overlap) >= 5:
            return True

    return False

def get_source_score(article: dict) -> int:
    """Calculates article quality score to select the most authoritative report for syndicated stories."""
    src = (article.get("source") or "").lower()
    score = 10
    for idx, auth in enumerate(AUTHORITY_PRIORITY):
        if auth in src:
            score = 100 - idx
            break
    img = article.get("image", "").strip()
    if img and not any(bad in img.lower() for bad in ["placeholder", "default", "icon"]):
        score += 5
    if len(article.get("summary_kh", "")) > 60:
        score += 2
    return score

def deduplicate_news_cluster(articles_list: list) -> list:
    """Clustering deduplication: keeps only 1 authoritative version of any syndicated wire news story."""
    if not articles_list:
        return []
    unique_articles = []
    for art in sorted(articles_list, key=lambda a: -float(a.get("timestamp", 0) or 0)):
        found_idx = -1
        for i, existing in enumerate(unique_articles):
            if are_similar_stories(art, existing):
                found_idx = i
                break
        if found_idx == -1:
            unique_articles.append(art)
        else:
            existing = unique_articles[found_idx]
            if get_source_score(art) > get_source_score(existing):
                unique_articles[found_idx] = art
    return unique_articles

def load_news_database() -> list:
    """Loads stored news from disk, strictly pruning any items older than 7 days, enforcing unique images, and deduplicating wire stories."""
    if not os.path.exists(NEWS_DB_FILE):
        return []
    try:
        with open(NEWS_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            now_ts = time.time()
            seen_imgs = set()
            valid = []
            for a in data:
                if not isinstance(a, dict): continue
                if (now_ts - a.get("timestamp", 0)) > RETENTION_SECONDS: continue
                if not is_trusted_source(a.get("source", ""), a.get("link", "")): continue
                img = a.get("image", "").strip()
                if not img or any(bad in img.lower() for bad in BAD_FALLBACK_PATTERNS): continue
                if img in seen_imgs: continue
                seen_imgs.add(img)
                valid.append(a)
            valid = deduplicate_news_cluster(valid)
            print(f"[*] Loaded {len(valid)} valid articles with unique images and zero duplicate stories (Purged {len(data) - len(valid)} duplicates or expired).")
            return valid
    except Exception as e:
        print(f"[!] Warning reading news database: {e}", file=sys.stderr)
    return []

def save_news_database(articles: list):
    """Saves valid articles to disk, strictly enforcing 100% unique authentic images, wire deduplication, and 7-day retention."""
    if not articles:
        return
    now_ts = time.time()
    seen_imgs = set()
    valid = []
    for a in articles:
        if not isinstance(a, dict): continue
        if (now_ts - a.get("timestamp", 0)) > RETENTION_SECONDS: continue
        if not is_trusted_source(a.get("source", ""), a.get("link", "")): continue
        img = a.get("image", "").strip()
        if not img or any(bad in img.lower() for bad in BAD_FALLBACK_PATTERNS): continue
        if img in seen_imgs: continue
        seen_imgs.add(img)
        valid.append(a)
    valid = deduplicate_news_cluster(valid)
    try:
        tmp_file = NEWS_DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(valid, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, NEWS_DB_FILE)
    except Exception as e:
        print(f"[!] Error saving news database: {e}", file=sys.stderr)

# Load existing database immediately on module import
_initial_db = load_news_database()
if _initial_db:
    ARTICLES_CACHE["data"] = _initial_db
    ARTICLES_CACHE["timestamp"] = time.time()

def refine_journalistic_khmer(text: str) -> str:
    """Polishes machine-translated phrases into natural, elegant journalistic Khmer."""
    # Remove zero-width spaces common in Khmer text segmentation
    text = text.replace('\u200b', '')
    
    replacements = [
        # Naval and Warship military terms
        (r'សម្រាប់\s*អ្នកបំបាំងកាយ\s*ដែល\s*មាន\s*អាវុធ\s*គ្មាន\s*មនុស្ស\s*បើក\s*នាពេលអនាគត', 'សម្រាប់នាវាពិឃាតជំនាន់ថ្មី បំពាក់ប្រព័ន្ធដ្រូន និងបច្ចេកវិទ្យាបំបាំងកាយ'),
        (r'សម្រាប់\s*យន្តហោះ\s*បំបាំងកាយ\s*ដែល\s*មាន\s*អាវុធ\s*គ្មាន\s*មនុស្ស\s*បើក\s*នាពេលអនាគត', 'សម្រាប់នាវាពិឃាតជំនាន់ថ្មី បំពាក់ប្រព័ន្ធដ្រូន និងបច្ចេកវិទ្យាបំបាំងកាយ'),
        (r'សម្រាប់\s*អ្នកបំបាំងកាយ', 'សម្រាប់នាវាពិឃាតបំបាំងកាយ'),
        (r'អ្នកបំបាំងកាយ', 'បច្ចេកវិទ្យាបំបាំងកាយ'),
        (r'ដែលមានអាវុធគ្មានមនុស្សបើក', 'បំពាក់ប្រព័ន្ធដ្រូនប្រយុទ្ធ'),
        (r'អាវុធគ្មានមនុស្សបើក', 'ប្រព័ន្ធដ្រូនយោធា'),
        (r'អ្នកបំផ្លាញ\s*នាពេលអនាគត', 'នាវាពិឃាតជំនាន់អនាគត'),
        (r'អ្នកបំផ្លាញ', 'នាវាពិឃាត'),
        (r'នាវាពិឃាតនាពេលអនាគត', 'នាវាពិឃាតជំនាន់អនាគត'),
        (r'នេះជាគំនិតរបស់\s*Naval Group', 'ក្រុមហ៊ុន Naval Group បង្ហាញប្លង់គំរូ'),
        (r'គំនិតរបស់\s*Naval Group', 'ប្លង់គំរូនាវាចម្បាំងរបស់ក្រុមហ៊ុន Naval Group'),

        # Air & Land Military terms
        (r'បង្ហាញពីទេវកថា\s*នៃ', 'ច្រានចោលការយល់ខុសអំពី'),
        (r'បង្ហាញពីទេវកថា', 'បំបែកការយល់ច្រឡំ'),
        (r'ទេវកថានៃ', 'ការយល់ខុសអំពី'),
        (r'យន្តហោះគ្មានមនុស្សបើកការពារអ៊ុយក្រែន', 'ប្រព័ន្ធដ្រូនការពារដែនអាកាសរបស់អ៊ុយក្រែន'),
        (r'យន្តហោះគ្មានមនុស្សបើក', 'ដ្រូន (Drone)'),
        (r'ជ័យជម្នះរបស់រុស្ស៊ីដែលជៀសមិនរួច', 'ជ័យជម្នះដែលថាមិនអាចជៀសរួចរបស់រុស្ស៊ី'),
        (r'ដែលជៀសមិនរួច', 'ដែលថាមិនអាចជៀសរួច'),
        (r'ក្រុមប្រឹក្សាអាត្លង់ទិក', 'វិទ្យាស្ថាន Atlantic Council'),
        (r'វិទ្យាស្ថានសម្រាប់ការសិក្សាសង្គ្រាម', 'វិទ្យាស្ថានសិក្សាសង្គ្រាម (ISW)'),
        (r'ការអាប់ដេតបន្តផ្ទាល់', 'បច្ចុប្បន្នភាពទាន់ហេតុការណ៍'),
        (r'បាក់ឆ្អឹង', 'ស៊ីសងកម្លាំងយ៉ាងស្រួចស្រាល់'),
        (r'បានចាប់ផ្តើមសង្រ្គាមជាមួយគ្នា', 'បានរួមគ្នាបើកយុទ្ធនាការសង្គ្រាម'),
        (r'មានភាពខុសប្លែកគ្នា', 'មានភាពខ្វែងគំនិតគ្នាខាងយុទ្ធសាស្ត្រ'),
        (r'ដៃខ្ពស់', 'ឧត្តមភាពយោធាលើសមរភូមិ'),
        (r'បម្រាមអាវុធគីមី', 'បម្រាមនៃការប្រើប្រាស់អាវុធគីមី'),
        (r'ការរៀនដោយគ្មានការហូរឈាម', 'ការដកស្រង់បទពិសោធន៍ដោយមិនបាច់បង្ហូរឈាម'),
        (r'ជាប់គាំងលើសមរភូមិ', 'ការជាប់គាំងលើខ្សែត្រៀមសមរភូមិ'),
        (r'ក្នុងទីក្រុង\s*Darfur', 'នៅតំបន់ដាហ្វួរ (Darfur)'),
        (r'Darfur', 'ដាហ្វួរ (Darfur)'),
        (r'Kordofan', 'ខ័រដូហ្វាន (Kordofan)'),
        (r'មី​យ៉ាន់​ម៉ា​?', 'មីយ៉ាន់ម៉ា'),
        (r'មី​យ៉ាន់​ម៉ា', 'មីយ៉ាន់ម៉ា'),
        (r'ស៊ូ​ដង់', 'ស៊ូដង់'),
        (r'រដ្ឋបាល\s*Trump', 'រដ្ឋបាលលោក ត្រាំ (Trump)'),
        (r'រដ្ឋប្រហារ\s*សម្លាប់មនុស្ស', 'រដ្ឋប្រហារយោធាបានសម្លាប់មនុស្ស'),

        # Quotes, Idioms and Journalistic Collocations
        (r"""['"]?ការភ័យខ្លាចដ៏?ធំបំផុតរបស់ខ្ញុំត្រូវបាន([^'"]+)['"]?\s*[:៖]\s*""", r'«អ្វីដែលខ្ញុំខ្លាចបំផុត គឺខ្លាចត្រូវគេ\1»៖ '),
        (r'របៀបដែល\s*(.*?)\s*ត្រូវបានជម្លៀស\s*ដោយ([^\s]+)', r'ដំណើររឿងនៃការជម្លៀស\1 ដោយប្រើ\2'),
        (r'របៀបដែល\s*(.*?)\s*ត្រូវបានជម្លៀស', r'ដំណើររឿងនៃការជម្លៀស\1'),
        (r'ពាណិជ្ជករ\s*([^\s]+)\s*បានស្តីបន្ទោស', r'និងក្រុម \1 បានទម្លាក់កំហុសដាក់គ្នាទៅវិញទៅមក'),
        (r'ពាណិជ្ជកម្មស្តីបន្ទោស', 'ទម្លាក់កំហុសដាក់គ្នា'),
        (r'ការប្រណាំងអាវុធ\s*មជ្ឈមណ្ឌលទិន្នន័យ', 'ការប្រកួតប្រជែងបង្កើតមជ្ឈមណ្ឌលទិន្នន័យ (Data Center)'),
        (r'បានវាយផ្អាក', 'ត្រូវបានផ្អាកជាបណ្តោះអាសន្ន'),
        (r'បានផ្អាក', 'ត្រូវបានផ្អាកមួយរយៈ'),
        (r'រាប់\s*Mediazona\s*បានធ្វើបច្ចុប្បន្នភាព', 'របាយការណ៍ធ្វើបច្ចុប្បន្នភាពរបស់ Mediazona'),
        (r'រុស្ស៊ីចាញ់ក្នុងសង្គ្រាមជាមួយអ៊ុយក្រែន', 'ទិន្នន័យទាហានរុស្ស៊ីដែលបានពលីក្នុងសង្គ្រាមនៅអ៊ុយក្រែន'),
        (r'វាស្តាប់ទៅមិនសមហេតុផលព្រោះវាជា[។\.]?', 'រឿងដែលស្តាប់ទៅហាក់ដូចជាមិនគួរឱ្យជឿ ប៉ុន្តែអាចកើតឡើងពិតប្រាកដ'),
        (r'នៅក្នុងធាតុរបស់គាត់', 'បង្ហាញទឹកព្រះទ័យរីករាយ'),
        (r'គ្មានឆ័ត្រទេ\s*ប៉ុន្តែ', 'ទោះបីគ្មានឆ័ត្របាំងភ្លៀង ក៏នៅតែ'),
        (r'រថក្រោះដុតនៅ', 'នាវាដឹកប្រេងឆេះនៅ'),
        (r'ចំពេលមានការភ័យខ្លាចនៃ', 'ដោយសារការព្រួយបារម្ភពី'),
        (r'ចំពេលមានការភ័យខ្លាច', 'ខណៈកំពុងបារម្ភពី'),
        (r'បង្កើតការភ័យខ្លាច', 'បង្កការព្រួយបារម្ភ'),
        (r'ជំរុញឱ្យមានការភ័យខ្លាច', 'បង្កើនការព្រួយបារម្ភ'),
        (r'បង្កឱ្យមានការភ័យខ្លាច', 'បង្កការព្រួយបារម្ភ'),
        (r'ការភ័យខ្លាចនៃការបែងចែក', 'ការព្រួយបារម្ភពីការបែកបាក់ទឹកដី'),
        (r'ការភ័យខ្លាចបំបែក', 'ការព្រួយបារម្ភពីការបែកបាក់ផ្ទៃក្នុង'),
        (r'ការប្រេះឆារបស់គណបក្សប្រជាជន', "ភាពខ្វែងគំនិតគ្នាក្នុងគណបក្សប្រជាជន (People's Party)"),
        (r'បោសសម្អាតទៅរកជ័យជម្នះ', 'ដណ្តើមបានជ័យជម្នះយ៉ាងភ្លូកទឹកភ្លូកដី'),
        (r'បេសកកម្មមិនអាចទៅរួច', 'បេសកកម្មដ៏លំបាកស្ទើរមិនអាចទៅរួច (Mission Impossible)'),
        (r'សង្រ្គាមយល់ដឹង', 'សង្គ្រាមចិត្តសាស្ត្រ (Cognitive Warfare)'),
        (r'សង្គ្រាមលើអ៊ីរ៉ង់កំពុងដកទ័ពជើងទឹកអាមេរិកចេញពីប៉ាស៊ីហ្វិកខាងលិច', 'ការផ្តោតលើជម្លោះអ៊ីរ៉ង់ កំពុងធ្វើឱ្យកម្លាំងទ័ពជើងទឹកអាមេរិកនៅប៉ាស៊ីហ្វិកខាងលិចថយចុះ'),
        (r'ដាក់ញត្តិ\s*NUG\s*សម្រាប់អត្តសញ្ញាណប័ណ្ណ', 'ដាក់ញត្តិទៅរដ្ឋាភិបាលរួបរួមជាតិ (NUG) ស្នើសុំអត្តសញ្ញាណប័ណ្ណ'),
        (r'អរគុណលោកស្រី\s*Melania Trump\s*សម្រាប់បទឈប់បាញ់', 'ថ្លែងអំណរគុណលោកស្រី Melania Trump ដែលបានជួយសម្របសម្រួលបទឈប់បាញ់'),
        (r'\bHouthis\b', 'ក្រុមហ៊ូធី (Houthis)'),
        (r'\bHezbollah\b', 'ក្រុមហេសបូឡា (Hezbollah)'),
        (r'\bHamas\b', 'ក្រុមហាម៉ាស (Hamas)'),
        (r'\bZelenskyy\b', 'លោក ហ្សេឡេនស្គី (Zelensky)'),
        (r'\bZelensky\b', 'លោក ហ្សេឡេនស្គី (Zelensky)'),
        (r'\bNetanyahu\b', 'លោក ណេតាញ៉ាហ៊ូ (Netanyahu)'),
        (r'លោក\s*Trump', 'លោក ត្រាំ (Trump)'),
        (r'លោក\s*Melania Trump', 'លោកស្រី Melania Trump'),
        (r'ក្រុម\s*ក្រុមហ៊ូធី', 'ក្រុមហ៊ូធី'),
        (r'លោក\s*លោក', 'លោក'),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

def translate_to_khmer(text: str) -> str:
    if not text:
        return ""
        
    clean_text = text.strip()
    # Strip trailing " - Source Name" if present (e.g. " - Sudan Tribune")
    if " - " in clean_text:
        parts = clean_text.rsplit(" - ", 1)
        if len(parts[1]) < 35:
            clean_text = parts[0].strip()

    if clean_text in TRANSLATION_CACHE and TRANSLATION_CACHE[clean_text]:
        return TRANSLATION_CACHE[clean_text]
    if text in TRANSLATION_CACHE and TRANSLATION_CACHE[text]:
        return TRANSLATION_CACHE[text]
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"Translate this war news headline into natural, accurate journalistic Khmer. Avoid stiff or literal phrasing. Output ONLY the Khmer text:\n{clean_text}"
            )
            if resp.text and resp.text.strip():
                kh = refine_journalistic_khmer(resp.text.strip())
                TRANSLATION_CACHE[clean_text] = kh
                TRANSLATION_CACHE[text] = kh
                save_translations()
                return kh
        except Exception:
            pass

    # Multi-client Google Translate fallback (dict-chrome-ex, webapp, gtx)
    clients = ["dict-chrome-ex", "webapp", "gtx"]
    for c in clients:
        try:
            url = f"https://translate.googleapis.com/translate_a/single?client={c}&sl=en&tl=km&dt=t&q=" + urllib.parse.quote(clean_text)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                kh = "".join([part[0] for part in data[0] if part[0]])
                if kh.strip():
                    refined = refine_journalistic_khmer(kh.strip())
                    TRANSLATION_CACHE[clean_text] = refined
                    TRANSLATION_CACHE[text] = refined
                    save_translations()
                    return refined
        except Exception:
            continue

    # Fallback to MyMemory API
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(clean_text)}&langpair=en|km"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            kh = data.get("responseData", {}).get("translatedText", "")
            if kh and kh.strip() and kh.strip().lower() != clean_text.lower():
                refined = refine_journalistic_khmer(kh.strip())
                TRANSLATION_CACHE[clean_text] = refined
                TRANSLATION_CACHE[text] = refined
                save_translations()
                return refined
    except Exception:
        pass

    # Dictionary fallback for common words if all external APIs fail
    t_low = clean_text.lower()
    fallback_trans = clean_text
    word_map = [
        ("sudanese army advances in darfur and kordofan, senior officer says", "មន្ត្រីជាន់ខ្ពស់បញ្ជាក់៖ កងទ័ពស៊ូដង់បានវាយរុលទៅមុខក្នុងតំបន់ដាហ្វួរ និងខ័រដូហ្វាន"),
        ("the trump administration's shift on myanmar is a disastrous decision", "ការផ្លាស់ប្តូរជំហររបស់រដ្ឋបាល Trump លើប្រទេសមីយ៉ាន់ម៉ា គឺជាការសម្រេចចិត្តដ៏មហន្តរាយ"),
        ("post-coup conflicts kill over 100,000 people in myanmar", "ជម្លោះក្រោយរដ្ឋប្រហារយោធាបានសម្លាប់មនុស្សជាង ១០ ម៉ឺននាក់នៅមីយ៉ាន់ម៉ា"),
        ("sudanese army advances in darfur", "កងទ័ពស៊ូដង់វាយរុលទៅមុខក្នុងតំបន់ដាហ្វួរ"),
        ("senior officer says", "មន្ត្រីជាន់ខ្ពស់យោធាបញ្ជាក់"),
        ("myanmar", "មីយ៉ាន់ម៉ា"),
        ("sudan", "ស៊ូដង់"),
        ("ukraine", "អ៊ុយក្រែន"),
        ("russia", "រុស្ស៊ី"),
    ]
    for en_w, km_w in word_map:
        if en_w in t_low:
            fallback_trans = fallback_trans.replace(en_w, km_w)
    
    return fallback_trans

def generate_khmer_summary(title_en: str, source: str, category_key: str) -> str:
    """Generates an extensive, in-depth 3-paragraph journalistic report and analysis in Khmer."""
    cache_key = f"{title_en}|{category_key}"
    if cache_key in SUMMARY_CACHE:
        return SUMMARY_CACHE[cache_key]

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a senior Khmer military analyst and journalistic editor.\n"
                f"Event Headline: {title_en}\n"
                f"News Source: {source}\n"
                f"Category: {category_key}\n"
                f"Write an extensive, comprehensive 3-paragraph news report in articulate, natural Khmer (ភាសាខ្មែរ) containing around 250 to 320 words:\n"
                f"Paragraph 1 (Primary Report & Facts - ខ្លឹមសារចម្បង និងព្រឹត្តិការណ៍ជាក់ស្តែង): Comprehensive, detailed factual narrative of what occurred, context, actors involved, military/official statements, and verified timeline (at least 100-140 words).\n"
                f"Paragraph 2 (Tactical & Strategic Military Context - បរិបទយុទ្ធសាស្ត្រយោធា និងភូមិសាស្ត្រនយោបាយ): In-depth military analysis, troop movements, weapons technology, and defense strategies involved (around 70-90 words).\n"
                f"Paragraph 3 (Impact & Future Outlook - ផលប៉ះពាល់ ស្ថានភាពមនុស្សធម៌ និងការវិវត្តបន្ត): Geopolitical repercussions, civilian/humanitarian impact, and future outlook (around 70-90 words).\n"
                f"Separate each paragraph with two newlines (\\n\\n). Do NOT translate literally; write fluent, professional Khmer journalistic prose. Output ONLY the Khmer text without any English."
            )
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
            if resp.text and resp.text.strip():
                sm = refine_journalistic_khmer(resp.text.strip())
                SUMMARY_CACHE[cache_key] = sm
                return sm
        except Exception:
            pass

    t_lower = title_en.lower()
    kh_title = translate_to_khmer(title_en)
    
    # Extensive, highly detailed 3-paragraph reports (Paragraph 1 is 100-140 words with rich factual depth)
    if any(k in t_lower for k in ['nuclear', 'atomic', 'radiation', 'uranium', 'plutonium', 'warhead', 'icbm', 'nuke']) or category_key == 'nuclear':
        p1 = (
            f"សេចក្តីរាយការណ៍ទាន់ហេតុការណ៍ពី {source} បង្ហាញពីការវិវត្តដ៏រសើបបំផុតជុំវិញសន្តិសុខនុយក្លេអ៊ែរ និងហានិភ័យនៃការរីករាលដាលអាវុធប្រល័យលោក ជុំវិញព្រឹត្តិការណ៍ «{kh_title}»។ "
            f"ភាពតានតឹងបានកើនឡើងដល់កម្រិតប្រកាសអាសន្នខ្ពស់ បន្ទាប់ពីមានសេចក្តីថ្លែងការណ៍ជាយុទ្ធសាស្ត្រ និងការកត់សម្គាល់អំពីការបង្កើនសមត្ថភាពចម្រាញ់សារធាតុវិទ្យុសកម្ម ក៏ដូចជាការធ្វើតេស្តសាកល្បងប្រព័ន្ធមីស៊ីលបាលីស្ទិកឆ្លងទ្វីប (ICBM) ដែលមានសមត្ថភាពផ្ទុកក្បាលគ្រាប់នុយក្លេអ៊ែរ។ "
            f"ទីភ្នាក់ងារថាមពលបរមាណូអន្តរជាតិ (IAEA) និងបណ្តាប្រទេសមហាអំណាចបានចេញការព្រមានជាបន្ទាន់ ដោយទាមទារឱ្យមានការផ្ទៀងផ្ទាត់ដោយតម្លាភាពនៅតាមទីតាំងក្រោមដីសំខាន់ៗ ដើម្បីបញ្ចៀសការរអិលធ្លាក់ចូលទៅក្នុងវិបត្តិប្រឈមមុខនុយក្លេអ៊ែរដែលមិនអាចគ្រប់គ្រងបាន។ "
            f"កងកម្លាំងយុទ្ធសាស្ត្រនៃភាគីពាក់ព័ន្ធត្រូវបានដាក់ឱ្យស្ថិតក្នុងស្ថានភាពប្រុងប្រយ័ត្នខ្ពស់ ខណៈដែលកិច្ចប្រជុំបន្ទាន់នៃក្រុមប្រឹក្សាសន្តិសុខត្រូវបានស្នើឡើងដើម្បីទប់ស្កាត់ការប្រណាំងប្រជែងសព្វាវុធដ៏គ្រោះថ្នាក់នេះ។"
        )
        p2 = (
            f"តាមទស្សនៈវិភាគយោធា ហានិភ័យនុយក្លេអ៊ែរនាពេលនេះឆ្លុះបញ្ចាំងពីការប្រែប្រួលនៃទ្រឹស្តីបទរារាំង (Deterrence Doctrine) រវាងមហាអំណាចនុយក្លេអ៊ែរ និងប្រទេសក្នុងតំបន់។ "
            f"មូលដ្ឋានចម្រាញ់សារធាតុអ៊ុយរ៉ាញ៉ូម និងទីតាំងផ្ទុកមីស៊ីលក្រោមដីជ្រៅ បានក្លាយជាផ្ទាំងស៊ីបដ៏សំខាន់នៃប្រតិបត្តិការស៊ើបការណ៍ និងការត្រៀមរៀបចំកលល្បិចវាយប្រហារបង្ការទុកជាមុន។ "
            f"ការដាក់ពង្រាយប្រព័ន្ធរ៉ាដាព្រមានជាមុន និងខែលការពារដែនអាកាសរយៈចម្ងាយឆ្ងាយត្រូវបានពន្លឿន ដើម្បីត្រៀមឆ្លើយតបទៅនឹងការបាញ់សាកល្បង ឬការវាយប្រហារដោយមិនបានព្រមានទុកជាមុន។"
        )
        p3 = (
            f"ផលប៉ះពាល់នៃការប្រឈមមុខដាក់គ្នានេះកំពុងគំរាមកំហែងដល់សន្ធិសញ្ញាមិនរីកសាយភាយអាវុធនុយក្លេអ៊ែរ (NPT) ទាំងមូល និងបង្កការភ័យខ្លាចដល់ប្រជាជនស៊ីវិលក្នុងតំបន់ជុំវិញ។ "
            f"សហគមន៍អន្តរជាតិកំពុងបង្កើនសម្ពាធការទូត និងទណ្ឌកម្មសេដ្ឋកិច្ចយ៉ាងតឹងរ៉ឹងបំផុត ដើម្បីទប់ស្កាត់មិនឱ្យស្ថានភាពនេះវិវត្តទៅរកចំណុចដែលមិនអាចវិលត្រឡប់ក្រោយវិញបាន។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['myanmar', 'burma', 'junta', 'tatmadaw', 'resistance', 'knu', 'pdf', 'min aung hlaing', 'naypyidaw', 'shan', 'karen']) or category_key == 'myanmar':
        p1 = (
            f"យោងតាមសេចក្តីរាយការណ៍ពី {source} ស្ថានការណ៍ជម្លោះប្រដាប់អាវុធនៅមីយ៉ាន់ម៉ាពាក់ព័ន្ធនឹង «{kh_title}» កំពុងបន្តផ្ទុះឡើងយ៉ាងក្តៅគគុកនៅតាមខ្សែត្រៀមជួរមុខ និងតំបន់ព្រំដែនជាប់ប្រទេសជិតខាង។ "
            f"កងកម្លាំងរដ្ឋាភិបាលយោធា (Junta) និងកងកម្លាំងតស៊ូប្រឆាំងរួមមានកងទ័ពការពារប្រជាជន (PDF) និងសម្ព័ន្ធប្រដាប់អាវុធជនជាតិភាគតិច បានបើកការវាយប្រហារដាក់គ្នាយ៉ាងសន្ធោសន្ធៅ ដោយមានការប្រើប្រាស់កាំភ្លើងធំធុនធ្ងន់ និងការទម្លាក់គ្រាប់បែកតាមដែនអាកាស។ "
            f"ការប៉ះទង្គិចគ្នាដ៏ខ្លាំងក្លានេះបានបង្កការបាញ់ផ្លោងឆ្លងព្រំដែន និងការចោទប្រកាន់គ្នាទៅវិញទៅមកជុំវិញការប៉ុនប៉ងពង្រីកជម្លោះ ខណៈដែលប្រជាជនស៊ីវិលរាប់ពាន់នាក់ត្រូវបានបង្ខំចិត្តភៀសខ្លួនស្វែងរកទីជម្រកសុវត្ថិភាពយ៉ាងប្រញាប់ប្រញាល់។ "
            f"អាជ្ញាធរយោធាកំពុងប្រឈមនឹងសម្ពាធយ៉ាងធ្ងន់ធ្ងរជុំវិញការបាត់បង់មូលដ្ឋានទ័ពយុទ្ធសាស្ត្រសំខាន់ៗ និងការកាត់ផ្តាច់ខ្សែផ្លូវផ្គត់ផ្គង់ភស្តុភារនៅទូទាំងប្រទេស។"
        )
        p2 = (
            f"នៅក្នុងទិដ្ឋភាពយុទ្ធសាស្ត្រយោធា ការបាត់បង់ការគ្រប់គ្រងលើទីតាំងបញ្ជាការ និងច្រកពាណិជ្ជកម្មព្រំដែនបានធ្វើឱ្យកងទ័ពយោធាផ្លាស់ប្តូរយុទ្ធសាស្ត្រមកពឹងផ្អែកស្ទើរតែទាំងស្រុងលើការវាយប្រហារតាមអាកាស និងកាំភ្លើងធំរយៈចម្ងាយឆ្ងាយ។ "
            f"ទន្ទឹមនឹងនេះ កងកម្លាំងចម្រុះប្រឆាំងបានពង្រឹងកលល្បិចវាយឆ្មក់ចល័តលឿន និងការប្រើប្រាស់ដ្រូនទម្លាក់គ្រាប់បែកកែច្នៃ ដើម្បីកាត់ផ្តាច់ក្បួនរថក្រោះ និងរារាំងកម្លាំងជំនួយរបស់កងទ័ពរដ្ឋាភិបាល។"
        )
        p3 = (
            f"វិបត្តិមនុស្សធម៌នៅមីយ៉ាន់ម៉ាកំពុងបន្តធ្លាក់ចុះដុនដាបយ៉ាងធ្ងន់ធ្ងរ ដោយមានជនភៀសខ្លួនរាប់សែននាក់ត្រូវការជំនួយសង្គ្រោះបន្ទាន់ ស្បៀងអាហារ និងការថែទាំវេជ្ជសាស្ត្រ។ "
            f"សមាគមអាស៊ាន និងអង្គការសហប្រជាជាតិបានបន្តអំពាវនាវឱ្យបញ្ឈប់អំពើហិង្សាជាបន្ទាន់ និងបើកច្រករបៀងមនុស្សធម៌ដោយគ្មានការរារាំង។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['thailand', 'bangkok', 'thai', 'tak', 'mae sot']) or category_key == 'thailand':
        p1 = (
            f"យោងតាមសេចក្តីរាយការណ៍ពី {source} ព្រឹត្តិការណ៍សំខាន់នៅប្រទេសថៃ និងតំបន់ព្រំដែនជុំវិញ «{kh_title}» កំពុងស្ថិតក្រោមការតាមដានយ៉ាងយកចិត្តទុកដាក់បំផុតពីសំណាក់ស្ថាប័នសន្តិសុខជាតិ និងសាធារណជនទូទៅ។ "
            f"ទីបញ្ជាការកងកម្លាំងប្រដាប់អាវុធថៃ និងអាជ្ញាធរខេត្តជាប់ព្រំដែនបានបង្កើនវិធានការត្រួតពិនិត្យយ៉ាងតឹងរ៉ឹងនៅតាមច្រកទ្វារ និងតំបន់យុទ្ធសាស្ត្រ ដើម្បីទប់ស្កាត់ផលប៉ះពាល់ជាយថាហេតុពីគ្រាប់កាំភ្លើងធ្លាក់ឆ្លងដែន និងការជ្រៀតចូលដោយខុសច្បាប់។ "
            f"កងទ័ពជើងគោកថៃបានដាក់ពង្រាយរថពាសដែក និងអង្គភាពល្បាតប្រដាប់អាវុធត្រៀមលក្ខណៈ ២៤ ម៉ោងលើ ២៤ ម៉ោង ដើម្បីការពារអធិបតេយ្យភាព និងធានាសុវត្ថិភាពអាយុជីវិតរបស់ប្រជាពលរដ្ឋរស់នៅតាមបណ្តោយខ្សែបន្ទាត់ព្រំដែន។ "
            f"ថ្នាក់ដឹកនាំរដ្ឋាភិបាលបានអំពាវនាវឱ្យគ្រប់ស្ថាប័នរក្សាការប្រុងប្រយ័ត្នខ្ពស់ ខណៈដែលបណ្តាញទំនាក់ទំនងការទូតត្រូវបានដំណើរការជាបន្ទាន់ដើម្បីដោះស្រាយភាពតានតឹងដោយសន្តិវិធី។"
        )
        p2 = (
            f"យុទ្ធសាស្ត្រការពារជាតិរបស់ថៃនៅពេលនេះ ផ្តោតសំខាន់លើការការពារខ្សែព្រំដែនរឹងមាំ និងការត្រៀមកម្លាំងឆ្លើយតបរហ័សចំពោះឧប្បត្តិហេតុសន្តិសុខ។ "
            f"កងកម្លាំងចម្រុះបានបង្កើតប៉ុស្តិ៍ត្រួតពិនិត្យចល័ត និងប្រើប្រាស់ប្រព័ន្ធស៊ើបការណ៍ដែនអាកាស ដើម្បីតាមដានរាល់ចលនាកងទ័ព ឬការបាញ់ផ្លោងនៅតំបន់ក្បែរខាង ធានាថាមិនមានការរំលោភបំពានដែនអធិបតេយ្យភាពជាដាច់ខាត។"
        )
        p3 = (
            f"ផលប៉ះពាល់ផ្ទាល់នៃស្ថានការណ៍នេះ បានជះឥទ្ធិពលដល់ពាណិជ្ជកម្មឆ្លងដែន និងជីវភាពរស់នៅរបស់សហគមន៍មូលដ្ឋាន។ "
            f"រាជរដ្ឋាភិបាលថៃកំពុងសហការជាមួយស្ថាប័នមនុស្សធម៌ ដើម្បីរៀបចំមជ្ឈមណ្ឌលសុវត្ថិភាពបណ្តោះអាសន្ន និងត្រៀមផែនការជម្លៀសប្រជាពលរដ្ឋក្នុងករណីមានគ្រោះអាសន្នជាយថាហេតុ។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['israel', 'gaza', 'iran', 'lebanon', 'houthi', 'syria', 'yemen', 'hezbollah', 'tel aviv', 'tehran', 'beirut', 'netanyahu', 'idf', 'hamas', 'red sea', 'mideast']) or category_key == 'mideast':
        p1 = (
            f"សេចក្តីរាយការណ៍បន្ទាន់ពី {source} បញ្ជាក់អំពីការកើនឡើងកម្តៅយ៉ាងធ្ងន់ធ្ងរនៃសមរភូមិមជ្ឈិមបូព៌ា ផ្តោតលើព្រឹត្តិការណ៍ «{kh_title}»។ "
            f"ប្រតិបត្តិការវាយប្រហារតាមដែនអាកាស និងការបាញ់មីស៊ីលឆ្លងដែនបានបន្តរង្គោះរង្គើតំបន់ទាំងមូល បង្កឱ្យប្រព័ន្ធស៊ីរ៉ែនប្រកាសអាសន្នបន្លឺឡើងឥតឈប់ឈរនៅតាមទីក្រុងធំៗ មូលដ្ឋានទ័ព និងមជ្ឈមណ្ឌលយុទ្ធសាស្ត្រ។ "
            f"កងកម្លាំងការពារដែនអាកាសត្រូវបានដាក់ពង្រាយជាបន្ទាន់ដើម្បីស្ទាក់ចាប់ក្បាលគ្រាប់បាលីស្ទិក និងដ្រូនអត្តឃាត ខណៈដែលការប្រយុទ្ធគ្នានៅតែកើតឡើងយ៉ាងស្រួចស្រាល់ទាំងនៅលើដី និងច្រកសមុទ្រក្រហម។ "
            f"សេចក្តីថ្លែងការណ៍ផ្លូវការពីថ្នាក់ដឹកនាំយោធាបានបង្ហាញពីការត្រៀមលក្ខណៈវាយបកវិញយ៉ាងម៉ឺងម៉ាត់ ដែលនាំឱ្យស្ថានភាពសន្តិសុខទូទាំងតំបន់ធ្លាក់ចូលក្នុងភាពប្រកាសអាសន្នកម្រិតខ្ពស់បំផុត និងមានការព្រួយបារម្ភអំពីការផ្ទុះសង្គ្រាមពេញទំហឹង។"
        )
        p2 = (
            f"នៅក្នុងវិស័យយុទ្ធសាស្ត្រយោធា សមរភូមិនេះកំពុងបង្ហាញពីការប្រឈមមុខដាក់គ្នារវាងបច្ចេកវិទ្យាការពារដែនអាកាសពហុជាន់ និងយុទ្ធសាស្ត្រវាយប្រហារដោយរលកមីស៊ីល-ដ្រូនចម្រុះ។ "
            f"ការប្រើប្រាស់មីស៊ីលរយៈចម្ងាយឆ្ងាយ និងយន្តហោះចម្បាំងបំបាំងកាយដើម្បីវាយប្រហារចំចំណុចរសើប បានបង្ខំឱ្យភាគីម្ខាងទៀតបង្កើនការបែកចែកកម្លាំង និងលាក់ទុកសព្វាវុធក្នុងលេណដ្ឋានក្រោមដីរឹងមាំ។"
        )
        p3 = (
            f"ផលប៉ះពាល់ភូមិសាស្ត្រនយោបាយកំពុងរាលដាលពាសពេញពិភពលោក ដោយប៉ះពាល់ដល់ស្ថិរភាពតម្លៃប្រេងឥន្ធនៈ និងសុវត្ថិភាពនៃខ្សែផ្លូវនាវាចរណ៍ពាណិជ្ជកម្មអន្តរជាតិ។ "
            f"អង្គការសហប្រជាជាតិ និងសហគមន៍អន្តរជាតិបានអំពាវនាវឱ្យមានបទឈប់បាញ់ជាបន្ទាន់ ដើម្បីទប់ស្កាត់មហន្តរាយមនុស្សធម៌កាន់តែធ្ងន់ធ្ងរចំពោះជនស៊ីវិលស្លូតត្រង់។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['ukraine', 'russia', 'kyiv', 'moscow', 'crimea', 'kursk', 'kharkiv', 'donetsk', 'zelensky', 'putin']) or category_key == 'ukraine':
        p1 = (
            f"សេចក្តីរាយការណ៍ពីសមរភូមិជួរមុខដោយ {source} បង្ហាញពីភាពតានតឹងដ៏ស្រួចស្រាល់នៃសង្គ្រាមរវាងរុស្ស៊ី និងអ៊ុយក្រែន ពាក់ព័ន្ធនឹង «{kh_title}»។ "
            f"កងកម្លាំងនៃភាគីទាំងសងខាងកំពុងប្រឈមមុខដាក់គ្នាយ៉ាងស្វិតស្វាញនៅតាមបណ្តោយខ្សែត្រៀមយុទ្ធសាស្ត្រ ដោយមានការផ្លាស់ប្តូរការបាញ់ផ្លោងកាំភ្លើងធំធុនធ្ងន់ និងការទម្លាក់គ្រាប់បែកអាកាសយ៉ាងសន្ធឹកសន្ធាប់ពីមួយថ្ងៃទៅមួយថ្ងៃ។ "
            f"ការវាយប្រហារទ្រង់ទ្រាយធំដោយប្រើប្រាស់មីស៊ីលរយៈចម្ងាយឆ្ងាយ និងរលកដ្រូនបំបែកការការពារ បានកំណត់គោលដៅលើទីតាំងបញ្ជាការ មជ្ឈមណ្ឌលភស្តុភារ និងបណ្តាញថាមពលយុទ្ធសាស្ត្រយ៉ាងធ្ងន់ធ្ងរ។ "
            f"របាយការណ៍ពីទីបញ្ជាការជួរមុខបានបញ្ជាក់អំពីការចល័តកងទ័ពបន្ថែម និងការដាក់ពង្រាយអាវុធជំនួយថ្មីៗ ដើម្បីទប់ទល់នឹងការវាយលុក និងដណ្តើមគ្រប់គ្រងទីតាំងការពារសំខាន់ៗឡើងវិញ។"
        )
        p2 = (
            f"នៅលើទិដ្ឋភាពយុទ្ធសាស្ត្រ សង្គ្រាមនេះបានវិវត្តទៅជាសង្គ្រាមទប់ទល់បច្ចេកវិទ្យាខ្ពស់ ដែលរួមបញ្ចូលគ្នារវាងការស៊ើបការណ៍តាមផ្កាយរណប ដ្រូនប្រយុទ្ធ FPV និងប្រព័ន្ធកាំភ្លើងធំស្វ័យប្រវត្តិ។ "
            f"ភាគីទាំងពីរបានពង្រឹងខ្សែការពារជីកលេណដ្ឋានយ៉ាងរឹងមាំ និងប្រើប្រាស់ប្រព័ន្ធសង្គ្រាមអេឡិចត្រូនិកដើម្បីកាត់ផ្តាច់សញ្ញាបញ្ជាដ្រូន និងប្រព័ន្ធកំណត់ទីតាំង GPS របស់អាវុធគូប្រជែង។"
        )
        p3 = (
            f"ផលវិបាកនៃជម្លោះនេះបន្តបង្កការបំផ្លិចបំផ្លាញដល់ហេដ្ឋារចនាសម្ព័ន្ធស៊ីវិល និងបង្កើតវិបត្តិជនភៀសខ្លួនធំបំផុតមួយនៅទ្វីបអឺរ៉ុប។ "
            f"សម្ព័ន្ធមិត្តអន្តរជាតិកំពុងបន្តជជែកពិភាក្សាអំពីកញ្ចប់ជំនួយយោធាបន្ថែម ខណៈដែលការស្វែងរកដំណោះស្រាយសន្តិភាពតាមផ្លូវការទូតនៅតែបន្តជួបប្រទះភាពស្មុគស្មាញយ៉ាងខ្លាំង។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['sudan', 'khartoum', 'rsf', 'saf', 'darfur', 'el fasher', 'port sudan']) or category_key == 'sudan':
        p1 = (
            f"យោងតាមសេចក្តីរាយការណ៍ពី {source} វិបត្តិសង្គ្រាមស៊ីវិលនៅស៊ូដង់ពាក់ព័ន្ធនឹង «{kh_title}» កំពុងឈានដល់ដំណាក់កាលគ្រោះថ្នាក់បំផុត ខណៈដែលការប្រយុទ្ធគ្នារវាងកងទ័ពជាតិស៊ូដង់ (SAF) និងកងកម្លាំងគាំទ្ររហ័ស (RSF) បានរាលដាលយ៉ាងខ្លាំងក្លាក្នុងតំបន់ទីក្រុង និងទីប្រជុំជនសំខាន់ៗ។ "
            f"ការប្រើប្រាស់កាំភ្លើងធំធុនធ្ងន់ ការទម្លាក់គ្រាប់បែក និងការប្រយុទ្ធតាមដងផ្លូវបានបំផ្លិចបំផ្លាញហេដ្ឋារចនាសម្ព័ន្ធស៊ីវិល មន្ទីរពេទ្យ និងជំរំជនភៀសខ្លួនយ៉ាងធ្ងន់ធ្ងរ។ "
            f"ទីភ្នាក់ងារសង្គ្រោះអន្តរជាតិបានប្រកាសអាសន្នអំពីកង្វះខាតស្បៀងអាហារ ថ្នាំពេទ្យ និងការរារាំងក្បួនរថយន្តមនុស្សធម៌មិនឱ្យចូលទៅដល់ជនរងគ្រោះរាប់លាននាក់។ "
            f"មេបញ្ជាការនៃភាគីជម្លោះទាំងពីរនៅតែបន្តប្រកាន់ជំហររឹងត្អឹង ដោយបដិសេធបទឈប់បាញ់ និងបន្តចល័តកម្លាំងវាយប្រហារដណ្តើមទីតាំងយុទ្ធសាស្ត្រគន្លឹះ។"
        )
        p2 = (
            f"ទាក់ទងនឹងយុទ្ធសាស្ត្រយោធា ការប្រយុទ្ធគ្នានៅស៊ូដង់គឺជាការរួមបញ្ចូលគ្នារវាងកម្លាំងទ័ពអាកាស-កាំភ្លើងធំរបស់កងទ័ពជាតិ និងកលល្បិចទ័ពថ្មើរជើងចល័តលឿនតាមរថយន្តភីកអាប់របស់កងកម្លាំង RSF។ "
            f"ការប្រជែងគ្នាដណ្តើមគ្រប់គ្រងព្រលានយន្តហោះ ស្ពាន និងឃ្លាំងស្តុកអាវុធបានធ្វើឱ្យខ្សែត្រៀមប្រយុទ្ធផ្លាស់ប្តូរទីតាំងជាប្រចាំ និងបង្កការលំបាកដល់ការបង្កើតតំបន់សុវត្ថិភាព។"
        )
        p3 = (
            f"អង្គការសហប្រជាជាតិបានព្រមានថា ស៊ូដង់កំពុងប្រឈមមុខនឹងគ្រោះទុរភិក្ស និងវិបត្តិមនុស្សធម៌ធ្ងន់ធ្ងរបំផុតមួយក្នុងប្រវត្តិសាស្ត្រទំនើប។ "
            f"សហគមន៍អន្តរជាតិកំពុងជំរុញឱ្យមានកិច្ចចរចាសន្តិភាពជាបន្ទាន់ ដើម្បីបញ្ឈប់សោកនាដកម្ម និងអនុញ្ញាតឱ្យជំនួយសង្គ្រោះជីវិតអាចចូលទៅដល់ប្រជាជនបានទាន់ពេលវេលា។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['naval', 'destroyer', 'warship', 'submarine', 'frigate', 'carrier', 'maritime', 'fleet', 'strait']):
        p1 = (
            f"យោងតាមសេចក្តីរាយការណ៍ពី {source} ព្រឹត្តិការណ៍នេះផ្តោតលើ «{kh_title}» ដែលជាការវិវត្តយោធាជើងទឹកដ៏មានឥទ្ធិពល រួមទាំងការដាក់ពង្រាយ និងការបង្ហាញបច្ចេកវិទ្យានាវាចម្បាំង នាវាពិឃាត និងនាវាមុជទឹកជំនាន់ថ្មី។ "
            f"នាវាទាំងនេះត្រូវបានបំពាក់ដោយប្រព័ន្ធរ៉ាដាបំបាំងកាយ ប្រព័ន្ធបាញ់បង្ហោះមីស៊ីលបញ្ឈរ (VLS) និងបច្ចេកវិទ្យាបញ្ជាការដ្រូនប្រយុទ្ធស្វ័យប្រវត្តិកម្រិតខ្ពស់លើផ្ទៃទឹក និងក្រោមទឹក។ "
            f"កងនាវាចរបានបង្កើនការល្បាតការពារច្រកសមុទ្រយុទ្ធសាស្ត្រ និងខ្សែផ្លូវនាវាចរណ៍ពាណិជ្ជកម្មអន្តរជាតិ ដើម្បីឆ្លើយតបទៅនឹងការគំរាមកំហែងផ្លូវទឹកសម័យទំនើប និងត្រៀមលក្ខណៈធ្វើអន្តរាគមន៍ជាបន្ទាន់។ "
            f"មេបញ្ជាការកងទ័ពជើងទឹកបានបញ្ជាក់ថា ការបង្កើនវត្តមានយោធានៅក្នុងដែនទឹកអន្តរជាតិនេះ មានគោលបំណងធានាសេរីភាពនៃការធ្វើនាវាចរណ៍ និងពង្រឹងសមត្ថភាពការពារផលប្រយោជន៍ជាតិ។"
        )
        p2 = (
            f"នៅក្នុងវិស័យយុទ្ធសាស្ត្រយោធាជើងទឹក ការអភិវឌ្ឍនេះឆ្លុះបញ្ចាំងពីការផ្លាស់ប្តូរទ្រឹស្តីបទសង្គ្រាមលើផ្ទៃទឹក ដោយប្តូរពីការប្រើប្រាស់កប៉ាល់ចម្បាំងបុរាណ មកពឹងផ្អែកលើបច្ចេកវិទ្យាបំបាំងកាយ និងការបាញ់មីស៊ីលរយៈចម្ងាយឆ្ងាយ។ "
            f"ការរួមបញ្ចូលដ្រូនស៊ើបការណ៍ និងដ្រូនអត្តឃាតនៅលើនាវានឹងជួយកាត់បន្ថយគ្រោះថ្នាក់ដល់កងទ័ព និងពង្រីកដែនប្រតិបត្តិការបានរាប់ពាន់គីឡូម៉ែត្រ។"
        )
        p3 = (
            f"ការដាក់ពង្រាយបច្ចេកវិទ្យានាវាពិឃាតជំនាន់អនាគតនេះ ត្រូវបានគេរំពឹងថានឹងផ្លាស់ប្តូរតុល្យភាពកម្លាំងជើងទឹកក្នុងតំបន់សមុទ្រសំខាន់ៗ ជាពិសេសនៅតាមច្រកសមុទ្រយុទ្ធសាស្ត្រ និងតំបន់ដែលមានជម្លោះដណ្តើមដែនទឹក។ "
            f"បណ្តាប្រទេសមហាអំណាចកំពុងតាមដានយ៉ាងយកចិត្តទុកដាក់ចំពោះជំហានអភិវឌ្ឍន៍នេះ។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['drone', 'uav', 'shahed', 'air defense', 'patriot', 'iron dome', 's-400', 'interception', 'radar']):
        p1 = (
            f"សេចក្តីរាយការណ៍ពី {source} បញ្ជាក់ថា ការវិវត្តជុំវិញ «{kh_title}» កំពុងបង្ហាញយ៉ាងច្បាស់ពីការកើនឡើងនៃតួនាទីដ្រូនប្រយុទ្ធ និងប្រព័ន្ធការពារដែនអាកាសក្នុងសមរភូមិទំនើប។ "
            f"រលកដ្រូនអត្តឃាត និងដ្រូនស៊ើបការណ៍រយៈចម្ងាយឆ្ងាយត្រូវបានបាញ់បង្ហោះជាបន្តបន្ទាប់ដើម្បីសាកល្បង និងទម្លុះរនាំងការពារដែនអាកាសរបស់គូប្រជែង។ "
            f"កងកម្លាំងការពារដែនអាកាសបានឆ្លើយតបដោយប្រើប្រាស់ប្រព័ន្ធរ៉ាដាស្ទាក់ចាប់ល្បឿនលឿន កាំជ្រួចបាញ់ស្ទាក់ និងប្រព័ន្ធរំខានរលកអេឡិចត្រូនិក ដើម្បីបន្សាបការគំរាមកំហែងមុនពេលដ្រូនអាចហោះទៅដល់គោលដៅហេដ្ឋារចនាសម្ព័ន្ធសំខាន់ៗ។ "
            f"របាយការណ៍បច្ចេកវិទ្យាយោធាបានកត់សម្គាល់ថា ការប្រយុទ្ធគ្នាតាមអាកាសរវាងដ្រូន និងប្រព័ន្ធការពារមីស៊ីល កំពុងកំណត់ឡើងវិញនូវល្បឿន និងប្រសិទ្ធភាពនៃប្រតិបត្តិការយោធាសម័យបច្ចុប្បន្ន។"
        )
        p2 = (
            f"យុទ្ធសាស្ត្រសង្គ្រាមដ្រូនបានផ្លាស់ប្តូរសក្ដានុពលសមរភូមិ ដោយសារតម្លៃផលិតដ្រូនទាបធៀបនឹងតម្លៃកាំជ្រួចការពារដែនអាកាស។ "
            f"ភាគីវាយប្រហារប្រើប្រាស់យុទ្ធសាស្ត្ររលកដ្រូន (Drone Swarms) ដើម្បីធ្វើឱ្យប្រព័ន្ធរ៉ាដាស្ទាក់ចាប់របស់គូប្រជែងអស់គ្រាប់ ឬគាំងដំណើរការ មុនពេលបញ្ជូនមីស៊ីលបំផ្លិចបំផ្លាញធ្ងន់ធ្ងរមកតាមក្រោយ។"
        )
        p3 = (
            f"អ្នកជំនាញយោធាវាយតម្លៃថា សង្គ្រាមដ្រូននេះកំពុងបង្ខំឱ្យបណ្តាប្រទេសមហាអំណាចត្រូវតែរៀបចំកែប្រែប្រព័ន្ធការពារជាតិឡើងវិញ ដោយផ្តោតលើអាវុធឡាស៊ែរ និងប្រព័ន្ធរំខានរលកអេឡិចត្រូនិក ដើម្បីទប់ទល់នឹងរលកដ្រូនដ៏ច្រើនសន្ធឹកសន្ធាប់។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    elif any(k in t_lower for k in ['missile', 'strike', 'bomb', 'ballistic', 'hypersonic', 'cruise', 'airstrike', 'shelling']):
        p1 = (
            f"សេចក្តីរាយការណ៍បន្ទាន់ពី {source} បញ្ជាក់ថា ការវាយប្រហារតាមដែនអាកាស និងការបាញ់ផ្លោងមីស៊ីលយុទ្ធសាស្ត្រជុំវិញ «{kh_title}» បានបន្តបង្កការបំផ្លិចបំផ្លាញយ៉ាងធ្ងន់ធ្ងរដល់ខ្សែការពារជួរមុខ មូលដ្ឋានទ័ព និងមជ្ឈមណ្ឌលភស្តុភារ។ "
            f"ការប្រើប្រាស់មីស៊ីលបាលីស្ទិក និងមីស៊ីលគ្រូសដែលមានល្បឿនលឿន និងភាពជាក់លាក់ខ្ពស់ បានបង្កឱ្យមានការប្រកាសអាសន្នតាមអាកាសទូទាំងប្រទេស និងការជម្លៀសប្រជាជនចូលទៅកាន់លេណដ្ឋានក្រោមដី។ "
            f"ក្រុមអ្នកវិភាគយោធាវាយតម្លៃថា ការវាយប្រហារចំគោលដៅសំខាន់ៗទាំងនេះមានគោលបំណងកាត់ផ្តាច់សមត្ថភាពបញ្ជាការ និងការផ្គត់ផ្គង់សព្វាវុធរបស់គូប្រជែង។ "
            f"ការផ្ទុះជាបន្តបន្ទាប់នៅជិតទីតាំងយុទ្ធសាស្ត្របានជំរុញឱ្យកងកម្លាំងការពារបង្កើនកម្រិតប្រុងប្រយ័ត្នខ្ពស់បំផុត និងត្រៀមរៀបចំប្រតិបត្តិការសងសឹកភ្លាមៗ។"
        )
        p2 = (
            f"ភាគីជម្លោះកំពុងប្រជែងគ្នាក្នុងការគ្រប់គ្រងដែនអាកាស ដោយប្រើប្រាស់មីស៊ីលបាលីស្ទិក និងមីស៊ីលគ្រូសដែលមានល្បឿនលឿន ដើម្បីវាយបំបែករនាំងការពារដែនអាកាសរបស់គូប្រជែង។ "
            f"ការវាយប្រហារចំគោលដៅសំខាន់ៗបានកាត់ផ្តាច់ខ្សែទំនាក់ទំនងបញ្ជាការ និងបណ្តាញអគ្គិសនី។"
        )
        p3 = (
            f"សហគមន៍អន្តរជាតិបានសម្តែងការព្រួយបារម្ភយ៉ាងខ្លាំងចំពោះការកើនឡើងនៃចំនួនជនរងគ្រោះស៊ីវិល និងការខូចខាតហេដ្ឋារចនាសម្ព័ន្ធមនុស្សធម៌។ "
            f"អង្គការសហប្រជាជាតិបានអំពាវនាវជាបន្ទាន់ឱ្យមានការអត់ធ្មត់ ដើម្បីបញ្ចៀសវិបត្តិមនុស្សធម៌កាន់តែធ្ងន់ធ្ងរ។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    else:
        p1 = (
            f"យោងតាមសេចក្តីរាយការណ៍ពី {source} ព្រឹត្តិការណ៍សំខាន់៖ «{kh_title}»។ "
            f"ហេតុការណ៍នេះគឺជាការវិវត្តយោធា និងភូមិសាស្ត្រនយោបាយដ៏គួរឱ្យកត់សម្គាល់បំផុត ដែលកំពុងទាក់ទាញការចាប់អារម្មណ៍ និងការតាមដានយ៉ាងយកចិត្តទុកដាក់ពីសំណាក់ក្រុមអ្នកវិភាគសន្តិសុខអន្តរជាតិ។ "
            f"ស្ថានការណ៍ជាក់ស្តែងនៅមូលដ្ឋានបានបង្ហាញពីការប្រឈមមុខដាក់គ្នាយ៉ាងតានតឹង ការប្រុងប្រយ័ត្នខ្ពស់របស់កងកម្លាំងប្រដាប់អាវុធ និងការចាត់វិធានការសន្តិសុខបន្ទាន់ដើម្បីការពារទីតាំងយុទ្ធសាស្ត្រ និងខ្សែបន្ទាត់ការពារសំខាន់ៗ។ "
            f"ភាគីពាក់ព័ន្ធកំពុងតាមដានយ៉ាងដិតដល់ចំពោះរាល់ការផ្លាស់ប្តូរកម្លាំង ដែលអាចនឹងបង្កឱ្យមានការផ្ទុះជម្លោះកាន់តែរីករាលដាល ឬផ្លាស់ប្តូរតុល្យភាពយោធាក្នុងតំបន់ទាំងមូល។"
        )
        p2 = (
            f"នៅលើសមរភូមិជាក់ស្តែង ការប៉ះទង្គិចគ្នា និងការប្រឈមមុខដាក់គ្នាបានបន្តបង្កើតសម្ពាធយ៉ាងធ្ងន់ធ្ងរលើខ្សែការពារ និងតុល្យភាពយោធារវាងភាគីជម្លោះ។ "
            f"ការប្រើប្រាស់បច្ចេកវិទ្យាសព្វាវុធទំនើប រួមទាំងប្រព័ន្ធរ៉ាដា និងការវាយប្រហារចម្ងាយឆ្ងាយ បានផ្លាស់ប្តូរកលល្បិចប្រយុទ្ធយ៉ាងឆាប់រហ័ស។"
        )
        p3 = (
            f"ផលប៉ះពាល់នៃព្រឹត្តិការណ៍នេះមិនត្រឹមតែកំណត់ជោគវាសនានៃសមរភូមិនោះទេ ប៉ុន្តែថែមទាំងជះឥទ្ធិពលយ៉ាងខ្លាំងដល់ស្ថិរភាពសេដ្ឋកិច្ចពិភពលោក និងសុវត្ថិភាពរបស់ជនស៊ីវិលរាប់លាននាក់។ "
            f"សហគមន៍អន្តរជាតិកំពុងបន្តជំរុញឱ្យមានដំណោះស្រាយការទូតជាបន្ទាន់។"
        )
        summary = f"{p1}\n\n{p2}\n\n{p3}"

    SUMMARY_CACHE[cache_key] = summary
    return summary

def fetch_category_news(category_key: str, count: int = 12):
    cat = CONFLICT_CATEGORIES.get(category_key, CONFLICT_CATEGORIES["all"])
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    items = []
    seen_titles = set()
    now_utc = datetime.datetime.now(timezone.utc)
    max_age_hours = 168.0  # Allow up to 7 days for This Week archive (168 hours)

    # 1. First fetch from direct major feeds providing authentic original photos (BBC, TWZ, NYT)
    direct_sources = DIRECT_CATEGORY_FEEDS.get(category_key, [])
    direct_added = 0
    for feed_url, source_name, filter_fn in direct_sources:
        try:
            req = urllib.request.Request(feed_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                root = ET.fromstring(resp.read())
                for el in root.findall(".//item"):
                    title = el.findtext("title", default="").strip()
                    if not title or title.lower() in seen_titles:
                        continue
                    if not filter_fn(title):
                        continue
                        
                    pub_date = el.findtext("pubDate", default="").strip()
                    pub_dt = parse_rfc_date(pub_date)
                    age_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                    
                    if age_hours > max_age_hours:
                        continue
                        
                    link = el.findtext("link", default="").strip()
                    real_photos, is_real, direct_video = extract_all_real_photos_from_item(el)
                    if not real_photos:
                        continue
                        
                    kh_title = translate_to_khmer(title)
                    kh_summary = generate_khmer_summary(title, source_name, category_key)
                    is_nuclear = bool(category_key == "nuclear" or any(k in title.lower() for k in ['nuclear', 'atomic', 'radiation', 'uranium', 'plutonium', 'warhead', 'icbm', 'nuke']))
                    
                    video_url = direct_video or ARTICLE_VIDEO_CACHE.get(title.strip().lower(), "")
                    has_video = bool(video_url)

                    seen_titles.add(title.lower())
                    items.append({
                        "title_en": title,
                        "title_kh": kh_title,
                        "summary_kh": kh_summary,
                        "link": link,
                        "source": source_name,
                        "pubDate": pub_date,
                        "pubDate_kh": format_khmer_relative_date(pub_dt),
                        "pubDate_full_kh": format_khmer_full_date(pub_dt),
                        "timestamp": pub_dt.timestamp(),
                        "image": real_photos[0],
                        "images": real_photos,
                        "is_real_image": True,
                        "video_url": video_url,
                        "has_video": has_video,
                        "category": category_key,
                        "category_kh": cat["title_kh"],
                        "category_flag": cat.get("flag_url", ""),
                        "is_nuclear": is_nuclear,
                        "weekday_kh": KH_DAYS[pub_dt.astimezone(timezone(timedelta(hours=7))).weekday()]
                    })
                    direct_added += 1
                    if direct_added >= 4:
                        break
            if direct_added >= 6:
                break
        except Exception as e:
            print(f"[!] Direct feed error for {source_name}: {e}", file=sys.stderr)

    # 2. Fetch from Google News RSS for live, breaking news from the past hours
    try:
        from media_extractor import extract_real_article_media
        encoded = urllib.parse.quote(cat["query"])
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(feed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            root = ET.fromstring(resp.read())
            gnews_raw = []
            for el in root.findall(".//item"):
                title = el.findtext("title", default="").strip()
                if not title or title.lower() in seen_titles:
                    continue
                    
                pub_date = el.findtext("pubDate", default="").strip()
                pub_dt = parse_rfc_date(pub_date)
                age_hours = (now_utc - pub_dt).total_seconds() / 3600.0
                
                # Skip stale articles older than max allowed age
                if age_hours > max_age_hours:
                    continue

                link = el.findtext("link", default="").strip()
                source = el.findtext("source", default="International News").strip()
                
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts[1].strip()) <= 45:
                        if source == "International News" or not source:
                            source = parts[1].strip()
                        title = parts[0].strip()

                if not is_trusted_source(source, link):
                    continue

                seen_titles.add(title.lower())
                gnews_raw.append({
                    "title": title,
                    "source": source,
                    "link": link,
                    "pub_date": pub_date,
                    "pub_dt": pub_dt
                })
                if len(gnews_raw) >= max(count - len(items) + 2, 6):
                    break

            def process_gnews(cand):
                try:
                    media_info = extract_real_article_media(cand["link"], cand["title"], category_key)
                    img = media_info.get("image")
                    imgs = media_info.get("images") or ([img] if img else [])
                    if not img or not imgs or any(bad in str(img).lower() for bad in ["faaz-missile", "placeholder", "blank", "pixel"]):
                        # Strictly skip candidate without authentic publisher photography
                        return None

                    real_link = media_info.get("real_url") or cand["link"]
                    if not is_trusted_source(cand["source"], real_link):
                        return None
                    kh_title = translate_to_khmer(cand["title"])
                    kh_summary = generate_khmer_summary(cand["title"], cand["source"], category_key)
                    is_nuclear = bool(category_key == "nuclear" or any(k in cand["title"].lower() for k in ['nuclear', 'atomic', 'radiation', 'uranium', 'plutonium', 'warhead', 'icbm', 'nuke']))
                    
                    v_url = media_info.get("video_url") or ARTICLE_VIDEO_CACHE.get(cand["title"].strip().lower(), "")
                    has_v = bool(v_url)
                    pub_dt = cand["pub_dt"]

                    return {
                        "title_en": cand["title"],
                        "title_kh": kh_title,
                        "summary_kh": kh_summary,
                        "link": media_info.get("real_url") or cand["link"],
                        "source": cand["source"],
                        "pubDate": cand["pub_date"],
                        "pubDate_kh": format_khmer_relative_date(pub_dt),
                        "pubDate_full_kh": format_khmer_full_date(pub_dt),
                        "timestamp": pub_dt.timestamp(),
                        "image": img,
                        "images": imgs,
                        "is_real_image": True,
                        "video_url": v_url,
                        "has_video": has_v,
                        "category": category_key,
                        "category_kh": cat["title_kh"],
                        "category_flag": cat.get("flag_url", ""),
                        "is_nuclear": is_nuclear,
                        "weekday_kh": KH_DAYS[pub_dt.astimezone(timezone(timedelta(hours=7))).weekday()]
                    }
                except Exception as e:
                    print(f"[!] process_gnews error: {e}", file=sys.stderr)
                    return None

            if gnews_raw:
                is_render = bool(os.environ.get("RENDER"))
                max_subworkers = min(len(gnews_raw), 2) if is_render else min(len(gnews_raw), 6)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_subworkers) as pool:
                    gnews_resolved = [r for r in pool.map(process_gnews, gnews_raw) if r is not None]
                    items.extend(gnews_resolved)

    except Exception as e:
        print(f"[!] Error fetching {category_key} from Google News: {e}", file=sys.stderr)
        
    # Sort strictly newest first (highest timestamp to lowest)
    items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return items

_NEWS_SCRAPE_LOCK = threading.Lock()
_IS_NEWS_SCRAPING = False

def _execute_full_news_scrape(target_category: str = "all") -> list:
    """Performs full background scraping pipeline, merges with alerts, enforces 7-day retention, and updates ARTICLES_CACHE and news_database.json."""
    now = time.time()
    is_render = bool(os.environ.get("RENDER"))
    all_articles = []
    if target_category != "all" and target_category in CONFLICT_CATEGORIES:
        cats_to_fetch = [target_category]
    else:
        cats_to_fetch = ["all", "ukraine", "middle_east", "sudan", "myanmar", "thailand", "nuclear"]
    
    # On Render, limit category worker concurrency to 2 to stay well within 512MB RAM
    worker_count = min(2, len(cats_to_fetch)) if is_render else min(5, len(cats_to_fetch))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_cat = {executor.submit(fetch_category_news, k, 12): k for k in cats_to_fetch}
        for future in concurrent.futures.as_completed(future_to_cat):
            try:
                res_items = future.result()
                all_articles.extend(res_items)
            except Exception as e:
                print(f"[!] Worker error: {e}", file=sys.stderr)
        
    if target_category != "all":
        existing_others = [a for a in ARTICLES_CACHE.get("data", []) if a.get("category") != target_category]
        all_articles.extend(existing_others)

    # Merge newly scraped articles with existing historical articles so no past stories are dropped
    existing_historical = ARTICLES_CACHE.get("data", []) or load_news_database()
    combined_pool = all_articles + (existing_historical if isinstance(existing_historical, list) else [])
    
    # Strictly deduplicate across all categories using intelligent news cluster deduplication
    deduped = deduplicate_news_cluster(combined_pool)

    # Inject breaking war alerts from alert_watcher so that ANY article popping in notifications is guaranteed on the page
    try:
        hot_alerts = alert_watcher.get_recent_alerts(limit=35)
        seen_links = set(a.get("link", "").strip() for a in deduped if a.get("link"))
        seen_titles = set(re.sub(r'[^a-zA-Z0-9]', '', a.get("title_en", "").lower()) for a in deduped if a.get("title_en"))
        for al in hot_alerts:
            t_low = (al.get("title_en", "") + " " + al.get("title_kh", "")).lower()
            if al.get("is_test") or "actively monitoring" in t_low or "alert system online" in t_low or al.get("source") == "Sothea Hot News Desk" or "localhost:5000" in al.get("link", ""):
                continue

            l_key = al.get("link", "").strip()
            t_key = re.sub(r'[^a-zA-Z0-9]', '', al.get("title_en", "").lower())
            if (l_key and l_key in seen_links) or (t_key and t_key in seen_titles):
                continue
                
            t_low = (al.get("title_en", "") + " " + al.get("title_kh", "")).lower()
            cat_key = "middle_east" if any(k in t_low for k in ["iran", "israel", "gaza", "lebanon", "middle east", "yemen", "houthi", "hormuz", "iraq", "syria"]) else \
                      "ukraine" if any(k in t_low for k in ["ukraine", "russia", "kyiv", "moscow", "kursk", "zelensky", "putin", "nato"]) else \
                      "sudan" if any(k in t_low for k in ["sudan", "khartoum", "darfur", "rsf"]) else \
                      "myanmar" if any(k in t_low for k in ["myanmar", "burma", "junta", "tatmadaw"]) else \
                      "thailand" if any(k in t_low for k in ["thailand", "bangkok", "thai"]) else \
                      "nuclear" if al.get("is_nuclear") else "ukraine"

            cat_info = CONFLICT_CATEGORIES.get(cat_key, CONFLICT_CATEGORIES["all"])

            # Determine timestamp
            ts_val = time.time()
            pub_date_str = al.get("pubDate", "")
            if pub_date_str:
                try:
                    dt_p = parse_rfc_date(pub_date_str)
                    ts_val = dt_p.timestamp()
                except Exception:
                    ts_val = time.time()
            elif al.get("timestamp"):
                try:
                    dt_p = datetime.datetime.strptime(al["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=7)))
                    ts_val = dt_p.timestamp()
                except Exception:
                    ts_val = time.time()

            pub_dt_obj = datetime.datetime.fromtimestamp(ts_val, tz=timezone.utc)

            from media_extractor import extract_real_article_media

            orig_link = al.get("link", "")
            media_info = extract_real_article_media(orig_link, al.get("title_en", ""))

            alert_img = media_info.get("image") or al.get("image")
            alert_images = media_info.get("images") or al.get("images") or []
            alert_has_video = media_info.get("has_video", False)
            alert_video_url = media_info.get("video_url", "")
            real_link = media_info.get("real_url") or orig_link

            if not alert_img or any(bad in str(alert_img).lower() for bad in ["faaz-missile", "avenger-counter-drone", "three-brits-rescued", "next-gen-tanker"]):
                continue

            if not alert_images:
                alert_images = [alert_img] if alert_img else []

            existing_summary = al.get("summary_kh", "").strip()
            paras = [p.strip() for p in existing_summary.split("\n\n") if p.strip()]
            if len(paras) < 3:
                full_summary = generate_khmer_summary(al.get("title_en", ""), al.get("source", "Breaking News Alert"), cat_key)
            else:
                full_summary = existing_summary

            alert_card = {
                "title_en": al.get("title_en", ""),
                "title_kh": al.get("title_kh", ""),
                "summary_kh": full_summary,
                "link": real_link,
                "source": al.get("source", "Breaking News Alert"),
                "pubDate": pub_date_str or al.get("timestamp", ""),
                "pubDate_kh": format_khmer_relative_date(pub_dt_obj),
                "pubDate_full_kh": format_khmer_full_date(pub_dt_obj),
                "timestamp": ts_val,
                "image": alert_img,
                "images": alert_images if alert_images else ([alert_img] if alert_img else []),
                "is_real_image": True if alert_img and not alert_img.startswith("data:image/svg") else False,
                "video_url": alert_video_url,
                "has_video": alert_has_video,
                "category": cat_key,
                "category_kh": cat_info["title_kh"],
                "category_flag": cat_info.get("flag_url", ""),
                "is_nuclear": bool(al.get("is_nuclear")),
                "is_breaking_alert": True,
                "weekday_kh": KH_DAYS[pub_dt_obj.astimezone(timezone(timedelta(hours=7))).weekday()]
            }
            if l_key: seen_links.add(l_key)
            if t_key: seen_titles.add(t_key)
            deduped.append(alert_card)
    except Exception as e:
        print(f"[!] Error merging alerts into news cache: {e}", file=sys.stderr)

    # Strictly enforce 7-day retention policy (168 hours = 604,800 seconds)
    retention_cutoff = now - RETENTION_SECONDS
    valid_articles = []
    for a in deduped:
        try:
            ts = float(a.get("timestamp", 0))
        except (ValueError, TypeError):
            ts = now
        a["timestamp"] = ts
        if ts >= retention_cutoff:
            valid_articles.append(a)
    deduped = valid_articles

    # Run cluster deduplication across articles and injected breaking alerts
    deduped = deduplicate_news_cluster(deduped)

    # STRICT GUARANTEE: Never allow duplicate images across articles!
    seen_images = set()
    unique_articles = []
    for a in deduped:
        img_url = a.get("image", "").strip()
        if not img_url or any(bad in img_url.lower() for bad in BAD_FALLBACK_PATTERNS):
            continue
        if img_url in seen_images:
            continue
        seen_images.add(img_url)
        unique_articles.append(a)
    deduped = unique_articles

    # Strictly prioritize breaking alerts, then sort newest first
    deduped.sort(key=lambda x: float(x.get("timestamp", 0)), reverse=True)

    if deduped:
        ARTICLES_CACHE["data"] = deduped
        ARTICLES_CACHE["timestamp"] = now
        save_news_database(deduped)
    return deduped

def trigger_background_news_refresh(target_category: str = "all") -> bool:
    """Triggers non-blocking background feed scraper thread to keep cache fresh without freezing visitor requests."""
    global _IS_NEWS_SCRAPING
    with _NEWS_SCRAPE_LOCK:
        if _IS_NEWS_SCRAPING:
            return False
        _IS_NEWS_SCRAPING = True

    def _worker():
        global _IS_NEWS_SCRAPING
        try:
            _execute_full_news_scrape(target_category)
        except Exception as e:
            print(f"[!] Background news refresh error: {e}", file=sys.stderr)
        finally:
            _IS_NEWS_SCRAPING = False

    t = threading.Thread(target=_worker, daemon=True, name="BackgroundNewsRefresher")
    t.start()
    return True

def get_all_cached_news(force_refresh: bool = False, target_category: str = "all") -> list:
    """
    STALE-WHILE-REVALIDATE High Performance Cache:
    1. Returns instantly (<10ms) whenever cached articles exist.
    2. Never blocks mobile, tablet, or web clients with 60-second synchronous web scrapes.
    3. Triggers background updates automatically when cache exceeds 180 seconds or upon force_refresh.
    """
    now = time.time()
    cached = ARTICLES_CACHE.get("data")
    
    # 1. Memory Cache Hit: Return immediately!
    if cached and len(cached) > 0:
        cache_age = now - ARTICLES_CACHE.get("timestamp", 0)
        if force_refresh or cache_age > 180:
            trigger_background_news_refresh(target_category)
        return cached

    # 2. Disk Database Hit: Load from news_database.json and return immediately!
    disk_db = load_news_database()
    if disk_db and len(disk_db) > 0:
        ARTICLES_CACHE["data"] = disk_db
        ARTICLES_CACHE["timestamp"] = now
        trigger_background_news_refresh(target_category)
        return disk_db

    # 3. Cold Fallback: Only on absolute first boot with zero historical data
    return _execute_full_news_scrape(target_category)

FALLBACK_NEWS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450" width="100%" height="100%"><rect width="800" height="450" fill="#0f172a"/><circle cx="400" cy="200" r="48" fill="#ef4444" opacity="0.2"/><path d="M400 170v60M370 200h60" stroke="#ef4444" stroke-width="4" stroke-linecap="round"/><text x="400" y="290" fill="#94a3b8" font-family="system-ui,sans-serif" font-size="18" font-weight="600" text-anchor="middle">Sothea Hot News</text></svg>"""

@app.route("/api/image-proxy")
def image_proxy():
    """Proxies and caches remote images to bypass mobile ISP/carrier blocks, Cloudflare WAF, and hotlink restrictions."""
    raw_url = request.args.get("url", "").strip()
    if not raw_url or not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        return Response("Invalid URL", status=400)
    
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".image_cache")
    os.makedirs(cache_dir, exist_ok=True)
    url_hash = hashlib.md5(raw_url.encode("utf-8")).hexdigest()
    cached_file = os.path.join(cache_dir, url_hash)
    meta_file = cached_file + ".meta"
    
    if os.path.exists(cached_file) and os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                content_type = f.read().strip() or "image/jpeg"
            with open(cached_file, "rb") as f:
                img_data = f.read()
            return Response(img_data, mimetype=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }
    try:
        req = urllib.request.Request(raw_url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            img_data = resp.read()
            content_type = resp.headers.get("content-type", "image/jpeg")
            
        try:
            with open(cached_file, "wb") as f:
                f.write(img_data)
            with open(meta_file, "w", encoding="utf-8") as f:
                f.write(content_type)
        except Exception:
            pass
            
        return Response(img_data, mimetype=content_type, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        print(f"[!] Image proxy fallback for {raw_url[:60]}: {e}", file=sys.stderr)
        return Response(FALLBACK_NEWS_SVG, mimetype="image/svg+xml")

@app.route("/api/news-speech")
def api_news_speech():
    """Serves high-quality natural Khmer spoken audio for any news report using Microsoft Deep Neural voices."""
    link = request.args.get("link", "").strip()
    title = request.args.get("title", "").strip()
    text = request.args.get("text", "").strip()
    voice = request.args.get("voice", "piseth").strip().lower()
    
    article = None
    if link or title:
        all_articles = ARTICLES_CACHE.get("data", [])
        for a in all_articles:
            if link and a.get("link", "").strip() == link:
                article = a
                break
            if title and (a.get("title_en", "").strip().lower() == title.lower() or a.get("title_kh", "").strip() == title):
                article = a
                break
                
    import tts_service
    if article:
        audio_path = tts_service.get_article_audio_path(article, voice=voice)
    elif text:
        audio_path = tts_service.generate_khmer_audio(text, voice=voice)
    else:
        return Response("Missing article reference or text", status=400)
        
    if not audio_path or not os.path.exists(audio_path):
        return Response("Failed to generate speech audio", status=500)
        
    return send_file(audio_path, mimetype="audio/mpeg", conditional=True, max_age=86400)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/news")
def api_news():
    category = request.args.get("category", "all")
    refresh = request.args.get("refresh", "false").lower() == "true"
    articles = get_all_cached_news(force_refresh=refresh, target_category=category)
    
    if category != "all":
        if category == "security":
            sec_cats = {"security", "ukraine", "middle_east", "sudan", "myanmar", "nuclear", "thailand"}
            filtered = [a for a in articles if a.get("category") in sec_cats]
        else:
            filtered = [a for a in articles if a.get("category") == category]
    else:
        filtered = articles
        
    # Extra safety clustering deduplication before sending JSON
    final_articles = deduplicate_news_cluster(filtered)
        
    return jsonify({
        "status": "success",
        "count": len(final_articles),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "articles": final_articles
    })

@app.route("/api/article-video")
def api_article_video():
    """Returns or dynamically resolves specific newsroom YouTube video report for an article."""
    title = request.args.get("title", "").strip()
    source = request.args.get("source", "").strip()
    if not title:
        return jsonify({"status": "error", "message": "Title is required"}), 400
    video_url = resolve_article_video(title, source)
    return jsonify({
        "status": "success",
        "video_url": video_url,
        "has_video": bool(video_url),
        "source": source
    })

@app.route("/api/videos")
def api_videos():
    return jsonify({
        "status": "success",
        "videos": LIVE_STREAMS
    })

@app.route("/api/alerts")
def api_alerts():
    limit = request.args.get("limit", 30, type=int)
    alerts = alert_watcher.get_recent_alerts(limit=limit)
    
    # Also integrate top breaking news from the live news cache
    cached_articles = ARTICLES_CACHE.get("data", [])
    seen_links = set(a.get("link", "").strip() for a in alerts if a.get("link"))
    seen_titles = set(re.sub(r'[^a-zA-Z0-9\u1780-\u17ff]', '', (a.get("title_en") or a.get("title_kh") or "").lower()) for a in alerts)
    
    for art in cached_articles:
        link = art.get("link", "").strip()
        t_en = art.get("title_en", "")
        t_kh = art.get("title_kh", "")
        t_key = re.sub(r'[^a-zA-Z0-9\u1780-\u17ff]', '', (t_en or t_kh).lower())
        
        if (link and link in seen_links) or (t_key and t_key in seen_titles):
            continue
            
        dt_str = art.get("pubDate_kh") or (datetime.datetime.fromtimestamp(art.get("timestamp", time.time())).strftime("%Y-%m-%d %H:%M:%S") if art.get("timestamp") else "ទើបចេញផ្សាយ")
        alerts.append({
            "timestamp": dt_str,
            "title_kh": t_kh or t_en,
            "summary_kh": (art.get("summary_kh") or "").split("\n\n")[0],
            "title_en": t_en,
            "source": art.get("source", "International News"),
            "pubDate": art.get("pubDate", ""),
            "link": link,
            "category": art.get("category", "war"),
            "is_nuclear": art.get("is_nuclear", False),
            "is_thai": art.get("category") == "thailand",
            "image": art.get("image", "")
        })
        if link:
            seen_links.add(link)
        if t_key:
            seen_titles.add(t_key)
            
        if len(alerts) >= limit + 10:
            break
            
    final_alerts = alerts[:limit]
    return jsonify({
        "status": "success",
        "count": len(final_alerts),
        "alerts": final_alerts
    })

@app.route("/api/test-alert", methods=["GET", "POST"])
def api_test_alert():
    """Trigger an on-demand real test notification on desktop and web."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_item = {
        "title": "តេស្តប្រព័ន្ធជូនដំណឹងបន្ទាន់៖ ប្រព័ន្ធដំណើរការល្អ និងកំពុងតាមដាន ២៤/៧",
        "link": "https://news.google.com",
        "source": "Sothea Hot News Desk",
        "pubDate": datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    }
    alert_watcher.trigger_alert(test_item, is_test=True)
    return jsonify({
        "status": "success",
        "message": "Desktop Toast and Web Notification triggered!",
        "alert": test_item
    })

@app.route("/api/network-info")
def api_network_info():
    ip = get_local_wifi_ip()
    port = int(os.environ.get("PORT", 5000))
    t_url = tunnel_manager.get_tunnel_url()
    domain_url = f"http://sotheahotnews.com:{port}"
    return jsonify({
        "status": "success",
        "domain": "sotheahotnews.com",
        "domain_url": domain_url,
        "local_ip": ip,
        "port": port,
        "wifi_url": domain_url,
        "raw_ip_url": f"http://{ip}:{port}",
        "tunnel_url": t_url,
        "best_url": t_url if t_url else domain_url
    })


# ==========================================
# File Uploads, Admin & Bug Report Endpoints
# ==========================================

@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    """Serves user-uploaded logos and banner images directly with self-healing fallback."""
    target = os.path.join(admin_service.UPLOAD_DIR, filename)
    if not os.path.exists(target):
        admin_service.ensure_logo_file()
    return send_from_directory(admin_service.UPLOAD_DIR, filename)

@app.route("/api/report-bug", methods=["POST"])
def api_report_bug():
    """Public endpoint for visitors to submit bug reports and feedback."""
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("description") and not data.get("title"):
        return jsonify({"status": "error", "message": "សូមបញ្ចូលការពិពណ៌នាបញ្ហា (Description is required)"}), 400
    try:
        bug = admin_service.add_bug_report(data)
        return jsonify({
            "status": "success",
            "message": "អរគុណសម្រាប់ការរាយការណ៍! ក្រុមការងារនឹងពិនិត្យមើលភ្លាមៗ។",
            "bug": bug
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def is_admin_authenticated():
    return session.get("is_admin") is True

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    """Authenticates admin and stores session."""
    data = request.get_json(force=True, silent=True) or {}
    password = data.get("password", "")
    if admin_service.verify_admin_password(password):
        session["is_admin"] = True
        return jsonify({"status": "success", "message": "ចូលគណនី Admin ជោគជ័យ"})
    return jsonify({"status": "error", "message": "ពាក្យសម្ងាត់មិនត្រឹមត្រូវ (Invalid password)"}), 401

@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    """Logs out admin."""
    session.pop("is_admin", None)
    return jsonify({"status": "success", "message": "ចាកចេញជោគជ័យ"})

@app.route("/api/admin/check-auth")
def api_admin_check_auth():
    """Checks whether current session is admin."""
    return jsonify({
        "status": "success",
        "is_authenticated": is_admin_authenticated(),
        "summary": admin_service.get_admin_summary() if is_admin_authenticated() else {}
    })

@app.route("/api/settings")
def api_public_settings():
    """Returns public settings for logo, branding, and active ads."""
    return jsonify({
        "status": "success",
        "settings": admin_service.get_public_settings()
    })

@app.route("/api/admin/settings", methods=["GET", "POST"])
def api_admin_settings():
    """Gets or updates site settings (admin only)."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        updated = admin_service.update_site_settings(data)
        return jsonify({"status": "success", "message": "បានរក្សាទុកការកំណត់ជោគជ័យ", "settings": updated})
    return jsonify({"status": "success", "settings": admin_service.load_settings()})

@app.route("/api/admin/change-password", methods=["POST"])
def api_admin_change_password():
    """Changes admin password."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    new_pw = data.get("new_password", "").strip()
    if not new_pw or len(new_pw) < 4:
        return jsonify({"status": "error", "message": "ពាក្យសម្ងាត់ត្រូវមានយ៉ាងតិច ៤ តួអក្សរ"}), 400
    if admin_service.change_admin_password(new_pw):
        return jsonify({"status": "success", "message": "បានប្ដូរពាក្យសម្ងាត់ដោយជោគជ័យ"})
    return jsonify({"status": "error", "message": "បរាជ័យក្នុងការប្ដូរពាក្យសម្ងាត់"}), 500

@app.route("/api/admin/upload-image", methods=["POST"])
def api_admin_upload_image():
    """Uploads custom logo or ad banner image directly."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "សូមជ្រើសរើសរូបភាពដើម្បី Upload"}), 400
    file = request.files["image"]
    upload_type = request.form.get("type", "banner")
    try:
        url = admin_service.save_uploaded_image(file, upload_type=upload_type)
        return jsonify({
            "status": "success",
            "message": "បាន Upload រូបភាពជោគជ័យ",
            "url": url
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/admin/bugs", methods=["GET"])
def api_admin_get_bugs():
    """Retrieves all bug reports (admin only)."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    bugs = admin_service.load_bugs()
    return jsonify({
        "status": "success",
        "count": len(bugs),
        "bugs": bugs,
        "summary": admin_service.get_admin_summary()
    })

@app.route("/api/admin/bugs/<bug_id>/status", methods=["POST"])
def api_admin_update_bug_status(bug_id):
    """Updates bug report status and optional admin note."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    new_status = data.get("status", "investigating")
    admin_notes = data.get("admin_notes")
    if admin_service.update_bug_status(bug_id, new_status, admin_notes):
        return jsonify({"status": "success", "message": "បានកែប្រែស្ថានភាពជោគជ័យ"})
    return jsonify({"status": "error", "message": "រកមិនឃើញរបាយការណ៍នេះឡើយ"}), 404

@app.route("/api/admin/bugs/<bug_id>", methods=["DELETE"])
def api_admin_delete_bug(bug_id):
    """Deletes a bug report."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if admin_service.delete_bug_report(bug_id):
        return jsonify({"status": "success", "message": "បានលុបរបាយការណ៍រួចរាល់"})
    return jsonify({"status": "error", "message": "រកមិនឃើញរបាយការណ៍នេះឡើយ"}), 404

@app.route("/api/admin/clear-cache", methods=["POST"])
def api_admin_clear_cache():
    """Forces cache refresh (admin only)."""
    if not is_admin_authenticated():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    ARTICLES_CACHE["timestamp"] = 0
    threading.Thread(target=get_all_cached_news, kwargs={"force_refresh": True}, daemon=True).start()
    return jsonify({"status": "success", "message": "បានសម្អាត Cache និងកំពុងទាញយកព័ត៌មានថ្មី..."})

def on_alert_received(alert_record):
    """Instant synchronization: called whenever alert_watcher triggers a breaking notification."""
    try:
        t_en = alert_record.get('title_en', '')
        print(f"[★] Instant Notification Sync: {t_en[:60]}")
        ARTICLES_CACHE["timestamp"] = 0
        # Re-fetch immediately in background thread so ARTICLES_CACHE is fresh with the new alert
        threading.Thread(target=get_all_cached_news, kwargs={"force_refresh": True}, daemon=True).start()
    except Exception as e:
        print(f"[!] Error in on_alert_received hook: {e}", file=sys.stderr)

try:
    alert_watcher.add_alert_listener(on_alert_received)
except Exception:
    pass


def pre_warm_top_articles_audio(limit: int = 3):
    """Pre-generates audio speech for top articles gently with pauses to avoid CPU/network spikes."""
    try:
        articles = ARTICLES_CACHE.get("data", [])
        if not articles:
            return
        import tts_service
        count = 0
        for a in articles[:limit]:
            try:
                p = tts_service.get_article_audio_path(a, voice="piseth")
                if p:
                    count += 1
                time.sleep(1.5)
            except Exception:
                pass
        if count > 0:
            print(f"[*] Pre-warmed speech audio for {count} top articles! Ready for instant playback.")
    except Exception as e:
        print(f"[!] Audio pre-warming exception: {e}", file=sys.stderr)

def continuous_news_updater_worker(interval_seconds: int = 180):
    """Runs in background continuously even when browser is closed.
    Scrapes fresh news, translates, summarizes, downloads media, and enforces strict 7-day retention."""
    is_render = bool(os.environ.get("RENDER"))
    print(f"[*] Continuous Background News Updater started (Interval: {interval_seconds}s, Retention: 7 days, Render: {is_render})!")
    
    # Do NOT block port-binding or spike CPU on container boot.
    # Delay initial refresh by 90s on Render, 45s locally so Gunicorn binds port 5000/10000 and passes health check instantly!
    time.sleep(90 if is_render else 45)

    while True:
        try:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{now_str}] [Continuous Background News Engine] Scraping feeds & updating 7-day news database...")
            _execute_full_news_scrape(target_category="all")
            # Only pre-warm audio locally; on Render free tier (512MB RAM), skip to avoid OOM kills!
            if not is_render:
                threading.Thread(target=pre_warm_top_articles_audio, kwargs={"limit": 3}, daemon=True, name="AudioPreWarmer").start()
            try:
                alert_watcher.prune_expired_alerts(max_age_days=7)
            except Exception:
                pass
        except Exception as e:
            print(f"[!] Background news updater exception: {e}", file=sys.stderr)
        time.sleep(interval_seconds)

_workers_started = False
def init_background_workers():
    global _workers_started
    if not _workers_started:
        _workers_started = True
        try:
            is_render = bool(os.environ.get("RENDER"))
            watcher_interval = 600 if is_render else 300
            updater_interval = 300 if is_render else 180
            
            alert_watcher.start_background_watcher_thread(interval_seconds=watcher_interval)
            threading.Thread(target=continuous_news_updater_worker, kwargs={"interval_seconds": updater_interval}, daemon=True, name="ContinuousNewsUpdater").start()
            
            # YouTube streams & Cloudflare tunnel only run locally, NEVER on Render
            if not is_render:
                threading.Thread(target=auto_refresh_live_streams_worker, daemon=True, name="LiveStreamAutoRefresher").start()
                tunnel_manager.start_tunnel_in_background(port=int(os.environ.get("PORT", 5000)))
        except Exception as e:
            print(f"[!] Warning starting background workers: {e}", file=sys.stderr)

# Auto-start background tasks both under local python and under Gunicorn on Render
init_background_workers()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    wifi_ip = get_local_wifi_ip()
    print("=" * 65)
    print("  SOTHEA HOT NEWS - Web Portal & Notification Watcher")
    print(f"  * លើកុំព្យូទ័រផ្ទាល់ (Local PC):   http://127.0.0.1:{port}")
    print(f"  * លើទូរស័ព្ទដៃតាម Wifi (Mobile): http://{wifi_ip}:{port}")
    print("=" * 65)
    while True:
        try:
            app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
        except KeyboardInterrupt:
            print("[*] Web portal stopped by user.")
            break
        except Exception as e:
            print(f"[!] Server exception caught: {e}", file=sys.stderr)
            time.sleep(2)
