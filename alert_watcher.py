#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
War News Alert Watcher (ប្រព័ន្ធជូនដំណឹងព័ត៌មានសង្គ្រាមទាន់ហេតុការណ៍)
- Automatically monitors global war and conflict news feeds
- Detects hot/breaking war developments
- Caches seen articles to avoid duplicate alerts
- Alerts locally (sound/terminal) and logs to alerts/
- Sends instant notifications to Telegram and/or Discord if configured
"""

import os
import sys
import time
import json
import base64
import hashlib
import datetime
import subprocess
import threading
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Set
def is_trusted_source(source_name: str, link: str = "") -> bool:
    """Lazy evaluation to avoid circular import with app.py"""
    try:
        import app
        if hasattr(app, "is_trusted_source"):
            return app.is_trusted_source(source_name, link)
    except Exception:
        pass
    return True

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        import winsound
    except ImportError:
        winsound = None
else:
    winsound = None

# Automatically load .env file if present
def load_dotenv(env_path: str = ".env"):
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            print(f"[!] Warning reading .env: {e}", file=sys.stderr)

load_dotenv()

CACHE_FILE = "seen_articles.json"
ALERTS_DIR = "alerts"
os.makedirs(ALERTS_DIR, exist_ok=True)

IN_MEMORY_ALERTS: List[Dict[str, Any]] = []

def load_recent_alerts_from_disk(limit: int = 30) -> List[Dict[str, Any]]:
    """Loads recent alerts from the latest markdown files in alerts/ directory."""
    alerts = []
    if not os.path.exists(ALERTS_DIR):
        return alerts
    
    files = sorted([f for f in os.listdir(ALERTS_DIR) if f.startswith("alerts_") and f.endswith(".md")], reverse=True)
    if not files:
        return alerts
        
    for fname in files[:2]:
        date_prefix = f"{fname[7:11]}-{fname[11:13]}-{fname[13:15]}" if len(fname) >= 18 and fname[7:15].isdigit() else ""
        fpath = os.path.join(ALERTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                blocks = content.split("### 🚨 ")
                for b in reversed(blocks):
                    b = b.strip()
                    if not b:
                        continue
                    lines = b.splitlines()
                    header = lines[0].strip()
                    timestamp = ""
                    title_kh = header
                    if header.startswith("[") and "]" in header:
                        raw_ts = header[1:header.index("]")]
                        timestamp = f"{date_prefix} {raw_ts}" if date_prefix and len(raw_ts) == 8 and " " not in raw_ts else raw_ts
                        title_kh = header[header.index("]") + 1:].strip()
                    
                    summary_kh = ""
                    title_en = ""
                    source = "News Source"
                    pub_date = ""
                    link = ""
                    
                    for line in lines[1:]:
                        line = line.strip()
                        if line.startswith("- **អត្ថបទសង្ខេប:**"):
                            summary_kh = line.replace("- **អត្ថបទសង្ខេប:**", "").strip()
                        elif line.startswith("- **ចំណងជើងដើម:**"):
                            title_en = line.replace("- **ចំណងជើងដើម:**", "").strip()
                        elif line.startswith("- **ប្រភព:**"):
                            m = re.search(r'\[(.*?)\]\((.*?)\)', line)
                            if m:
                                source = m.group(1)
                                if not link:
                                    link = m.group(2)
                        elif line.startswith("- **កាលបរិច្ឆេទ:**"):
                            pub_date = line.replace("- **កាលបរិច្ឆេទ:**", "").strip().strip("`")
                        elif line.startswith("- **Link:**"):
                            m = re.search(r'\((.*?)\)', line)
                            if m:
                                link = m.group(1)
                    
                    t_lower = (title_en or title_kh).lower()
                    is_nuke = any(k in t_lower for k in ['nuclear', 'atomic', 'uranium', 'plutonium', 'warhead', 'icbm'])
                    is_thai = any(k in t_lower for k in ['thailand', 'bangkok', 'thai'])
                    
                    alerts.append({
                        "timestamp": timestamp,
                        "title_kh": title_kh,
                        "summary_kh": summary_kh,
                        "title_en": title_en or title_kh,
                        "source": source,
                        "pubDate": pub_date,
                        "link": link,
                        "category": "nuclear" if is_nuke else ("thailand" if is_thai else "war"),
                        "is_nuclear": is_nuke,
                        "is_thai": is_thai
                    })
                    if len(alerts) >= limit:
                        break
        except Exception as e:
            print(f"[!] Error reading alert file {fname}: {e}", file=sys.stderr)
        if len(alerts) >= limit:
            break
            
    return alerts

def prune_expired_alerts(max_age_days: int = 7):
    """Purges alert files and in-memory alerts older than 7 days (1 week)."""
    global IN_MEMORY_ALERTS
    now = datetime.datetime.now()
    cutoff_ts = now.timestamp() - (max_age_days * 86400)
    
    # 1. Prune memory alerts
    IN_MEMORY_ALERTS = [
        a for a in IN_MEMORY_ALERTS 
        if a.get("timestamp", 0) >= cutoff_ts
    ]
    
    # 2. Prune old markdown files from alerts/
    if os.path.exists(ALERTS_DIR):
        for fname in os.listdir(ALERTS_DIR):
            if fname.startswith("alerts_") and fname.endswith(".md"):
                date_str = fname[7:-3]
                try:
                    file_date = datetime.datetime.strptime(date_str, "%Y%m%d")
                    if (now - file_date).total_seconds() > (max_age_days * 86400):
                        fpath = os.path.join(ALERTS_DIR, fname)
                        os.remove(fpath)
                        print(f"[*] Purged alert archive older than 7 days: {fname}")
                except Exception:
                    pass

def get_recent_alerts(limit: int = 30) -> List[Dict[str, Any]]:
    global IN_MEMORY_ALERTS
    disk_alerts = load_recent_alerts_from_disk(limit=limit * 2)
    
    now_ts = time.time()
    cutoff_ts = now_ts - (7 * 86400)  # Strictly 7-day retention (1 week)

    seen = set()
    merged = []
    # Merge latest in-memory and disk alerts deduplicated by link and title
    for a in IN_MEMORY_ALERTS + disk_alerts:
        link_key = a.get("link", "").strip()
        title_key = re.sub(r'[^a-zA-Z0-9ក-៿]', '', (a.get("title_en") or a.get("title_kh") or "").lower())
        uid = link_key or title_key
        if uid and uid not in seen:
            seen.add(uid)
            # Ensure timestamp is a valid float and strictly <= 7 days old
            ts_raw = a.get("timestamp", 0)
            ts = 0.0
            try:
                ts = float(ts_raw)
            except (ValueError, TypeError):
                p_str = a.get("pubDate") or str(ts_raw)
                try:
                    ts = parse_rfc_date(p_str).timestamp()
                except Exception:
                    ts = now_ts
            a["timestamp"] = ts
            if ts >= cutoff_ts:
                merged.append(a)
            
    return merged[:limit]


# High priority hot/breaking keywords
HOT_KEYWORDS = [
    "breaking", "urgent", "strike", "strikes", "attack", "attacks",
    "missile", "missiles", "drone", "drones", "explosion", "explosions",
    "killed", "casualties", "offensive", "bombed", "bombing", "invade",
    "invasion", "ceasefire", "nuclear", "atomic", "uranium", "plutonium",
    "warhead", "icbm", "radiation", "nuke", "war", "combat", "clashes",
    "evacuate", "emergency", "air defense", "intercepted", "artillery",
    "thailand", "bangkok", "thai military", "thai border", "cambodia border",
    "airstrikes", "trapped", "rubble", "fighting", "military", "army",
    "myanmar", "sudan", "gaza", "lebanon", "russia", "ukraine", "iran", "syria"
]

FEED_QUERIES = [
    "war Ukraine Russia strikes drone when:12h",
    "Israel Gaza Lebanon Iran war military when:12h",
    "nuclear weapon threat Iran Russia North Korea when:1d",
    "Thailand politics border military when:1d",
    "Sudan war clashes RSF SAF when:1d",
    "Myanmar civil war airstrikes fighting when:1d",
    "breaking war conflict global military when:12h"
]

DIRECT_LIVE_FEEDS = [
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC News"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "New York Times"),
    ("https://www.theguardian.com/world/rss", "The Guardian"),
]

def load_seen_cache() -> Set[str]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception:
            return set()
    return set()

def save_seen_cache(seen: Set[str]):
    try:
        recent_hashes = list(seen)[-5000:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(recent_hashes, f)
    except Exception as e:
        print(f"[!] Error saving seen cache: {e}", file=sys.stderr)

def get_article_id(item: Dict[str, str]) -> str:
    unique_str = f"{item.get('title', '')}|{item.get('link', '')}"
    return hashlib.sha256(unique_str.encode("utf-8")).hexdigest()

def is_hot_news(title: str) -> bool:
    title_lower = title.lower()
    # Exclude civilian wildlife/health/sports noise
    if any(bad in title_lower for bad in ["bear attack", "tiger", "shark", "wildlife", "animal attack", "ebola", "sports", "football", "soccer", "kfc", "restaurant"]):
        return False

    war_regions = ["ukraine", "russia", "kyiv", "moscow", "israel", "gaza", "lebanon", "iran", "tehran", "syria", "sudan", "myanmar", "thailand", "cambodia", "taiwan", "china", "korea", "yemen", "houthi", "nato", "pentagon", "darfur", "kordofan", "belgorod", "zaporizhia"]
    conflict_terms = ["strike", "strikes", "attack", "attacks", "missile", "missiles", "drone", "drones", "explosion", "bomb", "bombed", "bombing", "nuclear", "warhead", "atomic", "icbm", "ceasefire", "truce", "military", "army", "clashes", "offensive", "artillery", "airstrike", "airstrikes", "war", "frontline"]
    
    has_region = any(r in title_lower for r in war_regions)
    has_conflict = any(c in title_lower for c in conflict_terms)
    
    if has_region and has_conflict:
        return True
    if any(k in title_lower for k in ["nuclear strike", "nuclear weapon", "world war", "air raid", "drone attack", "missile strike", "war crime", "bodycam", "airstrike"]):
        return True
        
    return False

def fetch_feed_items(query: str, max_items: int = 6) -> List[Dict[str, str]]:
    encoded_query = urllib.parse.quote(query)
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    items = []
    try:
        req = urllib.request.Request(feed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                pub_date = item.findtext("pubDate", default="").strip()
                source_tag = item.find("source")
                source_name = source_tag.text.strip() if source_tag is not None and source_tag.text else "News Source"
                
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts[1].strip()) <= 45:
                        if source_name == "News Source" or not source_name:
                            source_name = parts[1].strip()
                        title = parts[0].strip()

                if not is_trusted_source(source_name, link):
                    continue

                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pubDate": pub_date
                })
    except Exception as e:
        print(f"[!] Feed fetch error for '{query}': {e}", file=sys.stderr)
    return items

def refine_journalistic_khmer(text: str) -> str:
    """Polishes machine-translated phrases into natural, elegant journalistic Khmer."""
    import re
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
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

def translate_to_khmer(text: str) -> str:
    """Translates a headline into Khmer using Gemini (if key present) or fast web translation."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"Translate this war news headline into natural, accurate Khmer. Output only the translated Khmer sentence without any notes or explanations:\n{text}"
            )
            if resp.text and resp.text.strip():
                return refine_journalistic_khmer(resp.text.strip())
        except Exception:
            pass

    # Multi-client translation fallback
    clients = ["dict-chrome-ex", "webapp", "gtx"]
    for c in clients:
        try:
            url = f'https://translate.googleapis.com/translate_a/single?client={c}&sl=en&tl=km&dt=t&q=' + urllib.parse.quote(text)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                translated = ''.join([part[0] for part in data[0] if part[0]])
                if translated.strip():
                    return refine_journalistic_khmer(translated.strip())
        except Exception:
            continue

    # Fallback to MyMemory
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=en|km"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and translated.strip() and translated.strip().lower() != text.lower():
                return refine_journalistic_khmer(translated.strip())
    except Exception:
        pass

    return text

SUMMARY_CACHE = {}

def generate_khmer_summary(title_en: str, source: str, category_key: str = "") -> str:
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

def send_telegram_alert(item: Dict[str, str], khmer_title: str, khmer_summary: str = ""):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    summary_part = f"\n📝 *សេចក្តីសង្ខេប:* {khmer_summary}\n" if khmer_summary else ""
    text = (
        f"🚨 *[ដំណឹងសង្គ្រាមទាន់ហេតុការណ៍]*\n\n"
        f"🇰🇭 *ចំណងជើង:* {khmer_title}\n"
        f"{summary_part}"
        f"🇬🇧 *ដើម:* {item['title']}\n"
        f"🏢 *ប្រភព:* {item['source']}\n"
        f"⏰ *កាលបរិច្ឆេទ:* {item['pubDate']}\n"
        f"🔗 *Link:* [ចុចអានព័ត៌មានលម្អិត]({item['link']})"
    )
    
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            pass
    except Exception as e:
        print(f"[!] Telegram send error: {e}", file=sys.stderr)

def send_discord_alert(item: Dict[str, str], khmer_title: str, khmer_summary: str = ""):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
        
    summary_part = f"\n📝 **សេចក្តីសង្ខេប:** {khmer_summary}\n" if khmer_summary else ""
    content = (
        f"🚨 **[ដំណឹងសង្គ្រាមទាន់ហេតុការណ៍ - HOT WAR ALERT]**\n"
        f"🇰🇭 **ចំណងជើងខ្មែរ:** {khmer_title}\n"
        f"{summary_part}"
        f"🇬🇧 **English:** {item['title']}\n"
        f"🏢 **Source:** {item['source']}\n"
        f"⏰ **Time:** {item['pubDate']}\n"
        f"🔗 **Link:** {item['link']}"
    )
    
    payload = json.dumps({"content": content}).encode("utf-8")
    try:
        req = urllib.request.Request(webhook_url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "WarNewsNotifier/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            pass
    except Exception as e:
        print(f"[!] Discord send error: {e}", file=sys.stderr)

ALERT_LISTENERS = []

def add_alert_listener(listener):
    """Register a callback that receives every newly triggered hot alert record immediately."""
    if listener not in ALERT_LISTENERS:
        ALERT_LISTENERS.append(listener)

def notify_alert_listeners(record: Dict[str, Any]):
    """Notify all registered listeners about a new breaking alert."""
    for l in list(ALERT_LISTENERS):
        try:
            l(record)
        except Exception as e:
            print(f"[!] Error in alert listener: {e}", file=sys.stderr)

def show_windows_toast(title: str, body: str, article_url: str = "", web_url: str = "http://127.0.0.1:5000"):
    """Pops up a native Windows Toast notification banner in Khmer with TWO buttons: Web Portal and Original Source."""
    if sys.platform != "win32":
        return
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.ps1")
    if not os.path.exists(script_path):
        return
    try:
        web_button_text = "🌐 ចូលវែបសាយ (Web Portal)"
        article_button_text = "🔗 ប្រភពដើម (Source)"
        title_b64 = base64.b64encode(title.encode('utf-8')).decode('ascii')
        body_b64 = base64.b64encode(body.encode('utf-8')).decode('ascii')
        url_b64 = base64.b64encode((article_url or "https://news.google.com").encode('utf-8')).decode('ascii')
        btn_b64 = base64.b64encode(article_button_text.encode('utf-8')).decode('ascii')
        web_url_b64 = base64.b64encode((web_url or "http://127.0.0.1:5000").encode('utf-8')).decode('ascii')
        web_btn_b64 = base64.b64encode(web_button_text.encode('utf-8')).decode('ascii')
        subprocess.Popen(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", script_path,
                "-TitleB64", title_b64,
                "-BodyB64", body_b64,
                "-UrlB64", url_b64,
                "-ButtonB64", btn_b64,
                "-WebUrlB64", web_url_b64,
                "-WebButtonB64", web_btn_b64
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[!] Toast notification error: {e}", file=sys.stderr)

def trigger_alert(item: Dict[str, str], is_test: bool = False):
    """Emit sound, pop up Windows Toast in Khmer with clickable link, print banner, send to Telegram/Discord, and log to file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    khmer_title = translate_to_khmer(item['title'])
    khmer_summary = generate_khmer_summary(item['title'], item['source'])

    t_lower = item['title'].lower()
    is_nuke = any(k in t_lower for k in ['nuclear', 'atomic', 'uranium', 'plutonium', 'warhead', 'icbm'])
    is_thai = any(k in t_lower for k in ['thailand', 'bangkok', 'thai'])
    
    if is_test:
        category_header = "🔔 [សាកល្បងប្រព័ន្ធជូនដំណឹង - TEST ALERT]"
        toast_prefix = "🔔 តេស្តជូនដំណឹង"
    elif is_nuke:
        category_header = "☢️ [សន្តិសុខនុយក្លេអ៊ែរ - NUCLEAR ALERT]"
        toast_prefix = "☢️ អាសន្ននុយក្លេអ៊ែរ"
    elif is_thai:
        category_header = "🇹🇭 [ព័ត៌មានក្នុងស្រុកថៃ - THAILAND NEWS]"
        toast_prefix = "🇹🇭 ព័ត៌មានថៃ"
    else:
        category_header = "🚨 [ដំណឹងសង្គ្រាមទាន់ហេតុការណ៍ - HOT WAR ALERT]"
        toast_prefix = "🚨 ដំណឹងសង្គ្រាម"

    banner = f"""
================================================================================
{category_header} - {timestamp}
================================================================================
🇰🇭 ចំណងជើងខ្មែរ : {khmer_title}
📝 អត្ថបទសង្ខេប : {khmer_summary}
🇬🇧 English Title: {item['title']}
🏢 ប្រភព (Source): {item['source']}
⏰ កាលបរិច្ឆេទ    : {item['pubDate']}
🔗 តំណភ្ជាប់ Link : {item['link']}
================================================================================
"""
    print(banner)
    
    # Sound notification on Windows
    if winsound:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    # Extract authentic media (image and video) directly from source
    try:
        from media_extractor import extract_real_article_media
        media_info = extract_real_article_media(item.get('link', ''), item.get('title', ''))
        if media_info.get('image'):
            item['image'] = media_info['image']
            item['images'] = media_info['images']
        if media_info.get('real_url'):
            item['real_link'] = media_info['real_url']
        item['has_video'] = media_info.get('has_video', False)
        item['video_url'] = media_info.get('video_url', '')
    except Exception:
        pass

    # Visual Windows Desktop Toast Notification in Khmer with Clickable Link
    toast_title = f"{toast_prefix}: {item['source']}"
    toast_body = f"{khmer_title}\n{khmer_summary}"
    show_windows_toast(toast_title, toast_body, item.get('real_link') or item.get('link', ''))
            
    # Send online notifications with Khmer translation and summary (Skip if test)
    if not is_test:
        send_telegram_alert(item, khmer_title, khmer_summary)
        send_discord_alert(item, khmer_title, khmer_summary)

    # In-memory alert store for Web UI API
    alert_record = {
        "timestamp": timestamp,
        "title_kh": khmer_title,
        "summary_kh": khmer_summary,
        "title_en": item['title'],
        "source": item['source'],
        "pubDate": item['pubDate'],
        "link": item.get('real_link') or item.get('link', ''),
        "category": "nuclear" if is_nuke else ("thailand" if is_thai else "war"),
        "is_nuclear": is_nuke,
        "is_thai": is_thai,
        "image": item.get('image', ''),
        "images": item.get('images', []),
        "has_video": item.get('has_video', False),
        "video_url": item.get('video_url', ''),
        "is_test": is_test
    }
    
    # Only store in memory if NOT test, to avoid polluting news grid
    if not is_test:
        IN_MEMORY_ALERTS.insert(0, alert_record)
        if len(IN_MEMORY_ALERTS) > 100:
            IN_MEMORY_ALERTS.pop()
                
        # Append to alert log
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(ALERTS_DIR, f"alerts_{today_str}.md")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n### 🚨 [{timestamp}] {khmer_title}\n")
            f.write(f"- **អត្ថបទសង្ខេប:** {khmer_summary}\n")
            f.write(f"- **ចំណងជើងដើម:** {item['title']}\n")
            f.write(f"- **ប្រភព:** [{item['source']}]({item['link']})\n")
            f.write(f"- **កាលបរិច្ឆេទ:** `{item['pubDate']}`\n")
            f.write(f"- **Link:** [អានព័ត៌មានលម្អិត]({item['link']})\n")

        # Invalidate articles cache in app.py so the website serves the new hot alert immediately!
        try:
            main_mod = sys.modules.get('__main__')
            if main_mod and hasattr(main_mod, "ARTICLES_CACHE"):
                main_mod.ARTICLES_CACHE["timestamp"] = 0
            import app
            if hasattr(app, "ARTICLES_CACHE"):
                app.ARTICLES_CACHE["timestamp"] = 0
        except Exception:
            pass

        # Instantly notify all registered listeners (e.g. app.py news cache)
        notify_alert_listeners(alert_record)

def check_for_hot_news(seen_set: Set[str]) -> int:
    """Scan all queries and live feeds, triggering alerts for new hot items."""
    new_alerts_count = 0
    all_incoming = []
    
    # 1. Direct real-time international RSS feeds
    for feed_url, source_name in DIRECT_LIVE_FEEDS:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall(".//item")[:6]:
                    title = item.findtext("title", default="").strip()
                    link = item.findtext("link", default="").strip()
                    pub_date = item.findtext("pubDate", default="").strip()
                    if title and is_hot_news(title):
                        img_url = ""
                        for child in item:
                            t = child.tag.lower()
                            if any(k in t for k in ["thumbnail", "content", "enclosure"]):
                                u = child.attrib.get("url")
                                if u and any(ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", "ichef.bbci", "guim.co.uk", "static01.nyt"]):
                                    img_url = u
                                    break
                        if not img_url:
                            desc = item.findtext("description", "")
                            m_img = re.search(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', desc, re.I)
                            if m_img:
                                img_url = m_img.group(1)

                        all_incoming.append({
                            "title": title,
                            "link": link,
                            "source": source_name,
                            "pubDate": pub_date,
                            "image": img_url,
                            "images": [img_url] if img_url else []
                        })
        except Exception:
            pass
            
    # 2. Fresh Google News queries (with time windows like when:12h)
    for query in FEED_QUERIES:
        items = fetch_feed_items(query, max_items=5)
        for item in items:
            if is_hot_news(item['title']):
                all_incoming.append(item)
                
    # Deduplicate and alert
    for item in all_incoming:
        if not is_trusted_source(item.get("source", ""), item.get("link", "")):
            continue
        item_id = get_article_id(item)
        if item_id not in seen_set:
            seen_set.add(item_id)
            trigger_alert(item)
            new_alerts_count += 1
            # Small pause so desktop toasts don't flood on top of each other
            time.sleep(1)
                
    save_seen_cache(seen_set)
    return new_alerts_count

def run_loop(interval_seconds: int = 900): # Default 15 minutes (900s)
    print(f"[*] War News Alert Watcher is active!")
    print(f"[*] Checking feeds every {interval_seconds} seconds ({interval_seconds//60} mins).")
    
    tg_status = "ENABLED" if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID") else "DISABLED (Set in .env)"
    dc_status = "ENABLED" if os.environ.get("DISCORD_WEBHOOK_URL") else "DISABLED (Set in .env)"
    print(f"[*] Telegram Notifications : {tg_status}")
    print(f"[*] Discord Webhook Alert  : {dc_status}")
    print("[*] Press Ctrl+C to stop.\n")
    
    seen_set = load_seen_cache()
    
    # First run seed
    if not seen_set:
        print("[*] Initializing baseline cache...")
        for query in FEED_QUERIES:
            for item in fetch_feed_items(query, max_items=10):
                seen_set.add(get_article_id(item))
        save_seen_cache(seen_set)
        print(f"[✓] Baseline initialized with {len(seen_set)} existing articles. Now monitoring for NEW updates!\n")
    
    while True:
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Scanning feeds for breaking war news...")
            count = check_for_hot_news(seen_set)
            if count == 0:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] No new hot war alerts found in this cycle.")
            else:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚨 {count} new breaking war alert(s) dispatched!")
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n[*] Watcher stopped by user.")
            break
        except Exception as e:
            print(f"[!] Error in monitoring cycle: {e}", file=sys.stderr)
            time.sleep(30)

def start_background_watcher_thread(interval_seconds: int = 300) -> threading.Thread:
    """Spawns the alert watcher loop in a background daemon thread so Flask and Watcher run concurrently in one process."""
    def _worker():
        time.sleep(60 if os.environ.get("RENDER") else 25)  # Wait so web server finishes binding and passes initial health checks
        run_loop(interval_seconds=interval_seconds)

    t = threading.Thread(target=_worker, daemon=True, name="WarNewsAlertWatcherThread")
    t.start()
    print(f"[*] War News Desktop Notification Watcher started in background thread (Interval: {interval_seconds//60} mins)!")
    return t

if __name__ == "__main__":
    if "--once" in sys.argv:
        seen_set = load_seen_cache()
        count = check_for_hot_news(seen_set)
        print(f"[*] Single scan complete. {count} new alerts dispatched.")
        sys.exit(0)
        
    interval = 900 # 15 minutes default
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        interval = int(sys.argv[1])
    run_loop(interval)
