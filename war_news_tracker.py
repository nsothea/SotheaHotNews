#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
War News Tracker & Khmer Translator (កម្មវិធីតាមដាន និងបកប្រែព័ត៌មានសង្គ្រាមជាភាសាខ្មែរ)
- Fetches real-time news regarding global wars and conflicts.
- Summarizes and translates critical developments into Khmer.
- Retains original source names and direct reference links.
"""

import os
import sys
import argparse
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

# Ensure UTF-8 output in Windows PowerShell/cmd
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Conflict topics and corresponding search queries
CONFLICT_TOPICS = {
    "ukraine": {
        "title_kh": "សង្គ្រាមរុស្ស៊ី និងអ៊ុយក្រែន (Russia-Ukraine War)",
        "query": "Russia Ukraine war battlefield strikes negotiations",
    },
    "middle_east": {
        "title_kh": "ជម្លោះនៅមជ្ឈិមបូព៌ា (Middle East: Israel, Gaza, Lebanon, Iran)",
        "query": "Israel Gaza Lebanon Iran war military strikes",
    },
    "sudan": {
        "title_kh": "សង្គ្រាមស៊ីវិលនៅស៊ូដង់ (Sudan Civil War: SAF vs RSF)",
        "query": "Sudan war SAF RSF clashes humanitarian",
    },
    "myanmar": {
        "title_kh": "ជម្លោះប្រដាប់អាវុធនៅមីយ៉ាន់ម៉ា (Myanmar Armed Conflict)",
        "query": "Myanmar civil war military junta rebels conflict",
    },
}

def fetch_rss_news(query: str, max_items: int = 5) -> List[Dict[str, str]]:
    """Fetch recent news items from Google News RSS feed for a specific query."""
    encoded_query = urllib.parse.quote(query)
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    items = []
    try:
        req = urllib.request.Request(feed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                pub_date = item.findtext("pubDate", default="").strip()
                source_tag = item.find("source")
                source_name = source_tag.text.strip() if source_tag is not None and source_tag.text else "Google News"
                
                # Split title and source if embedded in title (e.g. "Headline - Reuters")
                if " - " in title and source_name == "Google News":
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()
                
                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pubDate": pub_date
                })
    except Exception as e:
        print(f"[!] បរាជ័យក្នុងការទាញយក RSS សម្រាប់ '{query}': {e}", file=sys.stderr)
        
    return items

def translate_and_summarize_with_gemini(all_conflict_data: Dict[str, List[Dict[str, str]]]) -> str:
    """Uses Gemini API (google-genai) to translate and summarize news into professional Khmer."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Prepare context prompt
        context_parts = []
        for topic_key, items in all_conflict_data.items():
            topic_info = CONFLICT_TOPICS.get(topic_key, {})
            title_kh = topic_info.get("title_kh", topic_key)
            context_parts.append(f"### តំបន់ជម្លោះ: {title_kh}")
            for idx, it in enumerate(items, 1):
                context_parts.append(
                    f"{idx}. ចំណងជើងដើម: {it['title']}\n"
                    f"   ប្រភព: {it['source']}\n"
                    f"   កាលបរិច្ឆេទ: {it['pubDate']}\n"
                    f"   Link: {it['link']}"
                )
            context_parts.append("")
        
        prompt = (
            "អ្នកគឺជាអ្នកសារព័ត៌មានជំនាញផ្នែកទំនាក់ទំនងអន្តរជាតិ និងសង្គ្រាមពិភពលោក។\n"
            "សូមបកប្រែ និងសង្ខេបព័ត៌មានសង្គ្រាមសំខាន់ៗខាងក្រោមជា 'ភាសាខ្មែរ' ឱ្យបានច្បាស់លាស់ ត្រឹមត្រូវ និងទាក់ទាញ (Professional & Accurate Khmer Journalism)។\n"
            "លក្ខខណ្ឌកំណត់:\n"
            "1. រៀបចំតាមតំបន់ជម្លោះនីមួយៗ (អ៊ុយក្រែន, មជ្ឈិមបូព៌ា, ស៊ូដង់, មីយ៉ាន់ម៉ា)។\n"
            "2. សម្រាប់ព័ត៌មាននីមួយៗ សូមផ្តល់:\n"
            "   - ចំណងជើងបកប្រែជាភាសាខ្មែរ\n"
            "   - សេចក្តីសង្ខេបខ្លឹមសារសំខាន់ (Bullet points ច្បាស់ៗ)\n"
            "   - ប្រភពដើម និង Link តំណភ្ជាប់ដើម (Clickable markdown link)\n"
            "3. រក្សានូវភាពមិនលម្អៀង និងអព្យាក្រឹត្យខាងព័ត៌មាន។\n\n"
            "ព័ត៌មានដើម៖\n" + "\n".join(context_parts)
        )
        
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"[!] បញ្ហាក្នុងការហៅប្រើ Gemini API: {e}", file=sys.stderr)
        return ""

def format_fallback_report(all_conflict_data: Dict[str, List[Dict[str, str]]]) -> str:
    """Format structured report in Khmer even without Gemini API key."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# របាយការណ៍បច្ចុប្បន្នភាពព័ត៌មានសង្គ្រាមលើពិភពលោក",
        f"**កាលបរិច្ឆេទធ្វើបច្ចុប្បន្នភាព:** {now_str}\n",
        "> [!NOTE]",
        "> ព័ត៌មាននេះត្រូវបានទាញយកដោយស្វ័យប្រវត្តិចេញពីបណ្តាញព័ត៌មានអន្តរជាតិឈានមុខ និងតម្រៀបតាមតំបន់ជម្លោះសំខាន់ៗ។\n",
        "---"
    ]
    
    for topic_key, items in all_conflict_data.items():
        topic_info = CONFLICT_TOPICS.get(topic_key, {})
        title_kh = topic_info.get("title_kh", topic_key)
        lines.append(f"\n## 📌 {title_kh}")
        
        if not items:
            lines.append("_ពុំមានព័ត៌មានថ្មីទាន់ហេតុការណ៍នៅក្នុងតំបន់នេះទេនៅពេលនេះ_")
            continue
            
        for i, item in enumerate(items, 1):
            lines.append(f"### {i}. {item['title']}")
            lines.append(f"- **ប្រភព (Source):** [{item['source']}]({item['link']})")
            lines.append(f"- **កាលបរិច្ឆេទ:** `{item['pubDate']}`")
            lines.append(f"- **តំណភ្ជាប់ផ្ទាល់:** [អានព័ត៌មានលម្អិតនៅទីនេះ]({item['link']})\n")
            
    return "\n".join(lines)

def run_tracking(topic: str = "all", max_per_topic: int = 4, save_dir: str = "reports") -> str:
    """Run tracking across specified topics, synthesize in Khmer, and save report."""
    topics_to_track = (
        CONFLICT_TOPICS.keys() if topic == "all"
        else [topic] if topic in CONFLICT_TOPICS
        else ["ukraine", "middle_east"]
    )
    
    print(f"[*] កំពុងទាញយកព័ត៌មានសង្គ្រាមចុងក្រោយពីបណ្តាញអន្តរជាតិ...")
    all_data = {}
    for t in topics_to_track:
        q = CONFLICT_TOPICS[t]["query"]
        items = fetch_rss_news(q, max_items=max_per_topic)
        all_data[t] = items
        print(f"  + បានទាញយក {len(items)} ព័ត៌មានសម្រាប់ {CONFLICT_TOPICS[t]['title_kh']}")

    # Try translating with Gemini API if configured
    gemini_summary = translate_and_summarize_with_gemini(all_data)
    
    if gemini_summary:
        report_content = f"# របាយការណ៍ព័ត៌មានសង្គ្រាមសំខាន់ៗលើពិភពលោក (បកប្រែជាភាសាខ្មែរ)\n\n"
        report_content += f"**កាលបរិច្ឆេទ:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report_content += gemini_summary
    else:
        report_content = format_fallback_report(all_data)
        
    # Save report
    os.makedirs(save_dir, exist_ok=True)
    filename = f"war_news_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    file_path = os.path.join(save_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n[✓] របាយការណ៍ត្រូវបានរក្សាទុកដោយជោគជ័យនៅក្នុង: {file_path}\n")
    return report_content

def main():
    parser = argparse.ArgumentParser(description="Global War News Monitor & Khmer Translator")
    parser.add_argument("--topic", default="all", choices=["all", "ukraine", "middle_east", "sudan", "myanmar"], help="Topic to track")
    parser.add_argument("--count", type=int, default=3, help="Number of news articles per topic")
    parser.add_argument("--save-dir", default="reports", help="Directory to save markdown reports")
    args = parser.parse_args()
    
    report = run_tracking(topic=args.topic, max_per_topic=args.count, save_dir=args.save_dir)
    print(report)

if __name__ == "__main__":
    main()
