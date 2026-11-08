#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Sync script: Syncs clean, deployable files from D:\\AI_Project\\News to D:\\SotheaHotNews_Upload.
Excludes large environments (.venv), temp caches (.image_cache, .audio_cache), and binaries.
"""

import os
import shutil
import sys

SRC_DIR = r"D:\AI_Project\News"
DST_DIR = r"D:\SotheaHotNews_Upload"

EXCLUDE_DIRS = {".venv", "venv", "env", ".git", ".audio_cache", ".image_cache", "__pycache__", "scratch", "bin"}
EXCLUDE_FILES = {"tunnel_url.txt", "rendered.html", "server.log", "server_err.log"}
INCLUDE_EXTENSIONS = {".py", ".html", ".css", ".js", ".json", ".txt", ".yaml", ".yml", ".md", ".png", ".jpg", ".jpeg", ".svg", ".bat", ".vbs", ".ps1"}
EXACT_INCLUDE_FILES = {"Procfile", ".gitignore", ".env.example", ".gitkeep"}

def sync_folders():
    if not os.path.exists(DST_DIR):
        os.makedirs(DST_DIR, exist_ok=True)

    copied_count = 0

    # 1. Sync files & directories from SRC to DST
    for root, dirs, files in os.walk(SRC_DIR):
        # Exclude blacklisted directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        rel_path = os.path.relpath(root, SRC_DIR)
        target_dir = DST_DIR if rel_path == "." else os.path.join(DST_DIR, rel_path)
        os.makedirs(target_dir, exist_ok=True)

        for file in files:
            if file in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in INCLUDE_EXTENSIONS or file in EXACT_INCLUDE_FILES:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_dir, file)

                # Copy if missing or modified
                if not os.path.exists(dst_file) or os.path.getmtime(src_file) > os.path.getmtime(dst_file):
                    shutil.copy2(src_file, dst_file)
                    copied_count += 1

    # 2. Ensure uploads folder has .gitkeep
    uploads_dir = os.path.join(DST_DIR, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    gitkeep = os.path.join(uploads_dir, ".gitkeep")
    if not os.path.exists(gitkeep):
        with open(gitkeep, "w") as f:
            pass

    # 3. Clean up deleted files from DST that no longer exist in SRC
    deleted_count = 0
    for root, dirs, files in os.walk(DST_DIR, topdown=False):
        rel_path = os.path.relpath(root, DST_DIR)
        src_corresponding_dir = SRC_DIR if rel_path == "." else os.path.join(SRC_DIR, rel_path)

        for file in files:
            src_file = os.path.join(src_corresponding_dir, file)
            if not os.path.exists(src_file) and file != ".gitkeep":
                dst_file = os.path.join(root, file)
                try:
                    os.remove(dst_file)
                    deleted_count += 1
                except Exception:
                    pass

        # Remove empty directory if not in SRC
        if rel_path != "." and rel_path != "uploads":
            if not os.path.exists(src_corresponding_dir):
                try:
                    os.rmdir(root)
                except Exception:
                    pass

    total_files = sum(len(files) for _, _, files in os.walk(DST_DIR))
    print(f"[✓] Sync Complete! {copied_count} updated, {deleted_count} purged. Total files in {DST_DIR}: {total_files}")
    return total_files

if __name__ == "__main__":
    sync_folders()
