import os
import json
import re
import ssl
import urllib.parse
import requests
from bs4 import BeautifulSoup
import googlenewsdecoder

CACHE_FILE = "article_metadata_cache.json"
METADATA_CACHE = {}

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            METADATA_CACHE = json.load(f)
    except Exception:
        METADATA_CACHE = {}

def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(METADATA_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Persistent newsroom video report cache
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
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
            if m:
                vid = m.group(1)
                embed_url = f'https://www.youtube.com/embed/{vid}'
                ARTICLE_VIDEO_CACHE[cache_key] = embed_url
                save_article_videos()
                return embed_url
    except Exception:
        pass
    return ""

# User-Agents for robust extraction:
# Social crawler user-agents (Facebook, Twitter) are whitelisted by virtually all major news publishers
# to allow reading og:image and article metadata without 403 Forbidden.
CRAWLER_HEADERS = [
    {
        'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    },
    {
        'User-Agent': 'Twitterbot/1.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }
]

def extract_real_article_media(url: str, title: str = "", category_hint: str = "") -> dict:
    """
    Decodes Google News redirect if needed, fetches the original article webpage
    using social crawler headers, and extracts authentic og:image and embedded video.
    Returns: {
        'real_url': str,
        'image': str or None,
        'images': list of str,
        'has_video': bool,
        'video_url': str or None
    }
    """
    if not url:
        return {'real_url': '', 'image': None, 'images': [], 'has_video': False, 'video_url': None}

    cache_key = url.strip()
    if cache_key in METADATA_CACHE:
        cached = METADATA_CACHE[cache_key]
        img = cached.get('image')
        # Only use cache if it's not the old dummy missile image
        if img and 'Faaz-missile' not in img and 'twz.com' not in img:
            return cached

    real_url = url
    if "news.google.com" in url:
        try:
            decoded = googlenewsdecoder.gnewsdecoder(url)
            if decoded.get("success") and decoded.get("decoded_url"):
                real_url = decoded["decoded_url"]
        except Exception:
            pass

    result = {
        'real_url': real_url,
        'image': None,
        'images': [],
        'has_video': False,
        'video_url': None
    }

    # Fetch publisher webpage with smart user-agents
    html = ""
    for headers in CRAWLER_HEADERS:
        try:
            resp = requests.get(real_url, headers=headers, timeout=6.0, verify=False)
            if resp.status_code == 200 and resp.text:
                html = resp.text[:400000]
                break
        except Exception:
            pass

    if html:
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Authentic og:image or twitter:image
        found_images = []
        for prop in ['og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src']:
            tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
            if tag and tag.get('content'):
                img_cand = tag.get('content').strip()
                if img_cand.startswith('//'):
                    img_cand = 'https:' + img_cand
                elif img_cand.startswith('/'):
                    parsed = urllib.parse.urlparse(real_url)
                    img_cand = f"{parsed.scheme}://{parsed.netloc}{img_cand}"
                
                # Filter out useless logos, icons, avatars
                bad_tokens = ['logo', 'icon', 'avatar', 'placeholder', 'blank', 'transparent', 'pixel', 'advertisement', 'tracking']
                if img_cand not in found_images and not any(bad in img_cand.lower() for bad in bad_tokens):
                    found_images.append(img_cand)

        # Look for in-article lead/hero img tag if og:image was missing
        if not found_images:
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src') or ''
                src = src.strip()
                if src and any(src.lower().endswith(ext) or ext in src.lower() for ext in ['.jpg', '.jpeg', '.webp', '.png']):
                    bad_tokens = ['logo', 'icon', 'author', 'avatar', 'share', 'button']
                    if not any(bad in src.lower() for bad in bad_tokens):
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            parsed = urllib.parse.urlparse(real_url)
                            src = f"{parsed.scheme}://{parsed.netloc}{src}"
                        found_images.append(src)
                        break

        if found_images:
            result['image'] = found_images[0]
            result['images'] = found_images

        # 2. Check for authentic video in original story
        og_video = soup.find('meta', attrs={'property': 'og:video'}) or soup.find('meta', attrs={'property': 'og:video:url'})
        if og_video and og_video.get('content'):
            v_url = og_video.get('content').strip()
            result['has_video'] = True
            result['video_url'] = v_url
        else:
            for ifr in soup.find_all('iframe'):
                src = ifr.get('src', '')
                yt_match = re.search(r'(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([a-zA-Z0-9_-]{11})', src)
                if yt_match:
                    result['has_video'] = True
                    result['video_url'] = f"https://www.youtube.com/embed/{yt_match.group(1)}"
                    break

    # If authentic news report video not embedded, resolve via YouTube
    if not result['video_url'] and title:
        try:
            v = resolve_article_video(title, "")
            if v:
                result['has_video'] = True
                result['video_url'] = v
        except Exception:
            pass

    # Save to cache only if a real authentic image was extracted
    if result.get('image'):
        METADATA_CACHE[cache_key] = result
        save_cache()

    return result
