import os
import re
import hashlib
import asyncio
import logging
import urllib.request
import urllib.parse
import concurrent.futures

logger = logging.getLogger("tts_service")

AUDIO_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# Deep Neural Khmer Voices (Microsoft Azure Deep Neural Models)
VOICES = {
    "piseth": "km-KH-PisethNeural",    # Male News Anchor (លោក ពិសិដ្ឋ - សំឡេងបុរសរណ្តំ ពិរោះ)
    "sreymom": "km-KH-SreymomNeural",  # Female News Anchor (កញ្ញា ស្រីមុំ - សំឡេងនារីស្រទន់ ច្បាស់)
}
DEFAULT_VOICE = "piseth"

# Major Khmer conjunctions where authentic TV news presenters take natural breathing micro-pauses
KHMER_TRANSITIONS = [
    "ខណៈដែល", "ទន្ទឹមនឹងនេះ", "ប៉ុន្តែ", "ដោយសារតែ", "ដោយសារ",
    "ដើម្បី", "ព្រមទាំង", "លើសពីនេះ", "យ៉ាងណាមិញ", "ជាមួយគ្នានេះ",
    "បើតាមការបញ្ជាក់", "យោងតាមសេចក្តីរាយការណ៍", "យោងតាម"
]

def clean_text_for_speech(text: str) -> str:
    """Cleans Markdown, HTML, URLs, and excess punctuation for fluent spoken Khmer."""
    if not text:
        return ""
    # Strip markdown symbols
    t = re.sub(r'[*_#`\[\]]', ' ', text)
    # Strip URLs
    t = re.sub(r'https?://\S+', ' ', t)
    # Strip HTML tags
    t = re.sub(r'<[^>]+>', ' ', t)
    # Remove awkward brackets or quotation marks
    t = re.sub(r'[\(\)\{\}«»"\'“”’]', ' ', t)
    # Normalize multiple whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def polish_khmer_for_prosody(text: str) -> str:
    """
    Polishes Khmer text for natural Deep Neural prosody, emotional phrasing,
    and realistic news-anchor breathing pauses.
    """
    clean = clean_text_for_speech(text)
    if not clean:
        return ""

    # Ensure natural breathing pauses after Khmer full-stops and punctuation
    clean = re.sub(r'([។៖!?])', r'\1 ', clean)

    # Add subtle breathing space before major conjunctions/transitions if not already spaced
    for trans in KHMER_TRANSITIONS:
        pattern = re.compile(rf'([^\s។៖,])({re.escape(trans)})')
        clean = pattern.sub(r'\1 \2', clean)

    # Clean up duplicated spaces
    clean = re.sub(r'\s{2,}', ' ', clean).strip()
    return clean

def chunk_khmer_text(text: str, target_size: int = 300) -> list:
    """
    Splits long Khmer text into coherent sentence chunks of ~200-300 characters
    so Microsoft Edge TTS WebSocket handles them rapidly without latency or buffer limits.
    """
    clean = polish_khmer_for_prosody(text)
    if not clean:
        return []

    # Split by Khmer full stops '។' or line breaks
    sentences = re.split(r'([។\n]+)', clean)
    chunks = []
    curr = ""

    for s in sentences:
        if not s:
            continue
        if len(curr) + len(s) <= target_size:
            curr += s
        else:
            if curr.strip():
                c_clean = re.sub(r'^[។៖, ]+', '', curr).strip()
                if c_clean:
                    chunks.append(c_clean)
            if len(s) > target_size:
                parts = re.split(r'([ ,]+)', s)
                sub = ""
                for p in parts:
                    if len(sub) + len(p) <= target_size:
                        sub += p
                    else:
                        sub_clean = re.sub(r'^[។៖, ]+', '', sub).strip()
                        if sub_clean:
                            chunks.append(sub_clean)
                        sub = p
                sub_clean = re.sub(r'^[។៖, ]+', '', sub).strip()
                if sub_clean:
                    chunks.append(sub_clean)
                curr = ""
            else:
                curr = s

    if curr.strip():
        c_clean = re.sub(r'^[។៖, ]+', '', curr).strip()
        if c_clean:
            chunks.append(c_clean)

    return chunks

def _generate_edge_neural_tts(chunks: list, voice_id: str, output_path: str, rate: str = "-3%") -> bool:
    """Generates MP3 using Microsoft Edge Deep Neural Khmer Voice with parallel sentence processing."""
    try:
        import edge_tts
        
        async def _gen_chunk(sem, chunk_text, idx):
            async with sem:
                comm = edge_tts.Communicate(chunk_text, voice_id, rate=rate, pitch="+0Hz")
                tmp_chunk = f"{output_path}.chk_{idx}.tmp"
                await comm.save(tmp_chunk)
                data = b""
                if os.path.exists(tmp_chunk):
                    with open(tmp_chunk, "rb") as f:
                        data = f.read()
                    try:
                        os.remove(tmp_chunk)
                    except Exception:
                        pass
                return idx, data

        async def _run():
            sem = asyncio.Semaphore(5)
            tasks = [_gen_chunk(sem, c, i) for i, c in enumerate(chunks)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid = []
            for r in results:
                if isinstance(r, tuple) and r[1]:
                    valid.append(r)
            if not valid:
                return False
            valid.sort(key=lambda x: x[0])
            combined_mp3 = b"".join(v[1] for v in valid)
            if len(combined_mp3) > 1000:
                tmp_out = output_path + ".tmp"
                with open(tmp_out, "wb") as f:
                    f.write(combined_mp3)
                os.replace(tmp_out, output_path)
                return True
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"[TTS] Edge Neural TTS error: {e}")
        return False

def _generate_google_tts_fallback(chunks: list, output_path: str) -> bool:
    """Fallback to Google Translate TTS if Edge Neural network is temporarily unreachable."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        def fetch_chunk(item):
            idx, c_text = item
            try:
                # Limit to 120 chars for Google Translate API
                sub_text = c_text[:120]
                q = urllib.parse.quote(sub_text)
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=km&client=tw-ob&q={q}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return idx, resp.read()
            except Exception:
                return idx, b""

        indexed = list(enumerate(chunks))
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(indexed), 5) or 1) as pool:
            results = list(pool.map(fetch_chunk, indexed))

        results.sort(key=lambda x: x[0])
        combined_mp3 = b"".join(r[1] for r in results if r[1])
        if combined_mp3:
            tmp = output_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(combined_mp3)
            os.replace(tmp, output_path)
            return True
    except Exception as e:
        logger.error(f"[TTS] Google fallback failed: {e}")
    return False

def generate_khmer_audio(text: str, cache_key: str = "", voice: str = "piseth", rate: str = "-3%") -> str:
    """
    Generates ultra-realistic, natural human-like Khmer news speech audio using
    Microsoft Azure Deep Neural voices (Piseth or Sreymom).
    
    Parameters:
        text: The Khmer news text to speak.
        cache_key: Unique identifier for caching.
        voice: 'piseth' (Male Anchor) or 'sreymom' (Female Anchor).
        rate: Speech rate (e.g. '-3%' for authoritative, natural news cadence).
        
    Returns:
        Absolute path to the MP3 audio file.
    """
    chunks = chunk_khmer_text(text, target_size=280)
    if not chunks:
        return ""

    # Resolve voice identifier
    voice_norm = (voice or "").strip().lower()
    if voice_norm in ("sreymom", "female", "srey", "km-kh-sreymomneural"):
        voice_id = VOICES["sreymom"]
        voice_tag = "sreymom"
    else:
        voice_id = VOICES["piseth"]
        voice_tag = "piseth"

    key = f"{voice_tag}_{cache_key or ' '.join(chunks)}_{rate}"
    url_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
    output_path = os.path.join(AUDIO_CACHE_DIR, f"{voice_tag}_{url_hash}.mp3")

    # Return cached audio if already generated and non-empty
    if os.path.exists(output_path) and os.path.getsize(output_path) > 2000:
        return output_path

    # 1. Try Microsoft Edge Deep Neural TTS (Human-grade quality)
    success = _generate_edge_neural_tts(chunks, voice_id, output_path, rate=rate)
    if success and os.path.exists(output_path) and os.path.getsize(output_path) > 2000:
        return output_path

    # 2. Fallback to Google Translate TTS if offline or Edge network glitch
    fallback_success = _generate_google_tts_fallback(chunks, output_path)
    if fallback_success and os.path.exists(output_path):
        return output_path

    return ""

def get_article_audio_path(article: dict, voice: str = "piseth") -> str:
    """
    Constructs an articulate, broadcast-quality news report script and returns
    its cached Deep Neural MP3 path.
    """
    if not article:
        return ""

    source = article.get("source", "ព័ត៌មានអន្តរជាតិ")
    title_kh = article.get("title_kh") or article.get("title_en", "")
    summary_kh = article.get("summary_kh", "")

    # Professional news broadcast script
    clean_summary = clean_text_for_speech(summary_kh)
    script = f"ព័ត៌មានពី {source}។ {title_kh}។ {clean_summary}"

    cache_id = article.get("link") or article.get("title_en") or script
    return generate_khmer_audio(script, cache_key=cache_id, voice=voice, rate="-3%")
