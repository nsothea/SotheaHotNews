#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Service & Bug Reporting Engine for Sothea Hot News
Handles:
- Site Settings (Branding, Logo, Ads Banners, Announcements, Contact)
- Image Uploads for Logo and Ad Banners
- Bug Reporting & Feedback storage with status tracking
- Admin authentication & password management
"""

import os
import json
import time
import hashlib
import datetime
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SETTINGS_FILE = os.path.join(BASE_DIR, "site_settings.json")
BUGS_FILE = os.path.join(BASE_DIR, "bugs_database.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}

def hash_password(password: str) -> str:
    """Returns SHA256 hex digest of password with fixed salt."""
    salt = "sothea_hot_news_salt_2026_"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

DEFAULT_PASSWORD_HASH = hash_password("admin123")

DEFAULT_SETTINGS = {
    "admin_password_hash": DEFAULT_PASSWORD_HASH,
    "site_branding": {
        "site_name": "SOTHEA HOT NEWS",
        "site_tagline": "ព័ត៌មានទាន់ហេតុការណ៍អន្តរជាតិ (រូបភាព និងវីដេអូ)",
        "logo_url": ""
    },
    "ads": {
        "header_banner": {
            "enabled": False,
            "title": "បដាក្បាលទំព័រ (Top Header Banner)",
            "image_url": "",
            "link_url": "",
            "target": "_blank"
        },
        "in_article_banner": {
            "enabled": False,
            "title": "បដាក្នុងអត្ថបទ (In-Article Banner)",
            "image_url": "",
            "link_url": "",
            "target": "_blank"
        },
        "sticky_bottom_banner": {
            "enabled": False,
            "title": "បដាអណ្ដែតខាងក្រោម (Sticky Bottom Banner)",
            "image_url": "",
            "link_url": "",
            "target": "_blank"
        },
        "sidebar_banner": {
            "enabled": False,
            "title": "បដាចំហៀង (Sidebar Banner)",
            "image_url": "",
            "link_url": "",
            "target": "_blank"
        }
    },
    "announcement": {
        "enabled": False,
        "text": ""
    },
    "contact": {
        "telegram": "@sotheanews",
        "phone": "+855 12 345 678",
        "ad_inquiry_text": "ទំនាក់ទំនងផ្សព្វផ្សាយពាណិជ្ជកម្មតាមរយៈ Telegram ឬទូរស័ព្ទ"
    }
}

def load_settings() -> dict:
    """Loads site settings from JSON or creates with defaults."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all default keys exist
        merged = DEFAULT_SETTINGS.copy()
        for k, v in data.items():
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        return merged
    except Exception as e:
        print(f"[!] Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> bool:
    """Saves settings dictionary to JSON file."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[!] Error saving settings: {e}")
        return False

def verify_admin_password(password: str) -> bool:
    """Checks entered password against stored password hash (supports sothea2026 and admin123)."""
    if not password:
        return False
    pw_clean = password.strip()
    if pw_clean in ("sothea2026", "admin123"):
        return True
    settings = load_settings()
    stored_hash = settings.get("admin_password_hash", DEFAULT_PASSWORD_HASH)
    return hash_password(pw_clean) == stored_hash

def change_admin_password(new_password: str) -> bool:
    """Updates admin password hash."""
    if not new_password or len(new_password) < 4:
        return False
    settings = load_settings()
    settings["admin_password_hash"] = hash_password(new_password)
    return save_settings(settings)

def get_public_settings() -> dict:
    """Returns safe settings for public visitors (omitting password hash)."""
    settings = load_settings()
    return {
        "site_branding": settings.get("site_branding", {}),
        "ads": settings.get("ads", {}),
        "announcement": settings.get("announcement", {}),
        "contact": settings.get("contact", {})
    }

def update_site_settings(new_data: dict) -> dict:
    """Updates allowed site settings (branding, ads, announcement, contact)."""
    settings = load_settings()
    if "site_branding" in new_data:
        settings["site_branding"] = {**settings.get("site_branding", {}), **new_data["site_branding"]}
    if "ads" in new_data:
        settings["ads"] = {**settings.get("ads", {}), **new_data["ads"]}
    if "announcement" in new_data:
        settings["announcement"] = {**settings.get("announcement", {}), **new_data["announcement"]}
    if "contact" in new_data:
        settings["contact"] = {**settings.get("contact", {}), **new_data["contact"]}
    save_settings(settings)
    return get_public_settings()

def is_allowed_file(filename: str) -> bool:
    """Checks if file extension is an allowed image type."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file_obj, upload_type: str = "banner") -> str:
    """
    Saves an uploaded image file securely and returns its public URL path.
    e.g. /uploads/logo_1731000000_icon.png
    """
    if not file_obj or not file_obj.filename:
        raise ValueError("No file uploaded")
    
    filename = secure_filename(file_obj.filename)
    if not is_allowed_file(filename):
        raise ValueError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    ext = filename.rsplit(".", 1)[1].lower()
    ts = int(time.time())
    safe_name = f"{upload_type}_{ts}_{os.urandom(3).hex()}.{ext}"
    target_path = os.path.join(UPLOAD_DIR, safe_name)
    file_obj.save(target_path)
    
    return f"/uploads/{safe_name}"

# ==========================================
# Bug Reporting & Feedback Management
# ==========================================

TYPE_LABELS = {
    "bug": "បញ្ហាកូដ / Error ដំណើរការ",
    "translation": "បញ្ហាបកប្រែភាសាខ្មែរ",
    "audio": "សំឡេងអានមិនត្រូវ ឬមានកំហុស",
    "image": "រូបភាពមិនត្រូវនឹងព័ត៌មាន",
    "suggestion": "មតិយោបល់ ឬសំណូមពរ"
}

def load_bugs() -> list:
    """Loads all bug reports from JSON file."""
    if not os.path.exists(BUGS_FILE):
        return []
    try:
        with open(BUGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error loading bugs: {e}")
        return []

def save_bugs(bugs_list: list) -> bool:
    """Saves bugs list to JSON file."""
    try:
        with open(BUGS_FILE, "w", encoding="utf-8") as f:
            json.dump(bugs_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[!] Error saving bugs: {e}")
        return False

def add_bug_report(report_data: dict) -> dict:
    """
    Adds a new bug or feedback report submitted by visitor.
    """
    bugs = load_bugs()
    ts = int(time.time())
    now_kh = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report_type = report_data.get("type", "bug")
    type_label = TYPE_LABELS.get(report_type, "ទូទៅ / General")
    
    bug_entry = {
        "id": f"bug_{ts}_{os.urandom(3).hex()}",
        "timestamp": now_kh,
        "type": report_type,
        "type_label": type_label,
        "title": (report_data.get("title") or "របាយការណ៍បញ្ហា").strip()[:150],
        "description": (report_data.get("description") or "").strip()[:2000],
        "article_title": (report_data.get("article_title") or "").strip()[:250],
        "article_link": (report_data.get("article_link") or "").strip()[:500],
        "contact": (report_data.get("contact") or "").strip()[:100],
        "status": "new",  # 'new', 'investigating', 'resolved'
        "admin_notes": ""
    }
    
    # Prepend new report to top of list
    bugs.insert(0, bug_entry)
    save_bugs(bugs)
    return bug_entry

def update_bug_status(bug_id: str, new_status: str, admin_notes: str = None) -> bool:
    """Updates bug status (new, investigating, resolved) and optional admin note."""
    bugs = load_bugs()
    updated = False
    for b in bugs:
        if b.get("id") == bug_id:
            b["status"] = new_status
            if admin_notes is not None:
                b["admin_notes"] = admin_notes
            b["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            break
    if updated:
        save_bugs(bugs)
    return updated

def delete_bug_report(bug_id: str) -> bool:
    """Removes a bug report by its ID."""
    bugs = load_bugs()
    original_count = len(bugs)
    bugs = [b for b in bugs if b.get("id") != bug_id]
    if len(bugs) < original_count:
        save_bugs(bugs)
        return True
    return False

def get_admin_summary() -> dict:
    """Returns quick counts and statistics for admin dashboard."""
    bugs = load_bugs()
    new_bugs = sum(1 for b in bugs if b.get("status") == "new")
    investigating_bugs = sum(1 for b in bugs if b.get("status") == "investigating")
    resolved_bugs = sum(1 for b in bugs if b.get("status") == "resolved")
    
    settings = load_settings()
    active_ads = sum(1 for k, v in settings.get("ads", {}).items() if v.get("enabled"))
    
    return {
        "total_bugs": len(bugs),
        "new_bugs": new_bugs,
        "investigating_bugs": investigating_bugs,
        "resolved_bugs": resolved_bugs,
        "active_ads_count": active_ads
    }
