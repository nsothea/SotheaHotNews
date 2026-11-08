import os
import sys
import re
import time
import subprocess
import threading

TUNNEL_URL = ""
_process = None
_tunnel_started = False
_tunnel_lock = threading.Lock()

def get_tunnel_url() -> str:
    global TUNNEL_URL
    if not TUNNEL_URL:
        url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_url.txt")
        if os.path.exists(url_file):
            try:
                with open(url_file, "r", encoding="utf-8") as f:
                    TUNNEL_URL = f.read().strip()
            except Exception:
                pass
    return TUNNEL_URL

def kill_orphan_cloudflared():
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "cloudflared"], capture_output=True)
    except Exception:
        pass

def start_tunnel_in_background(port: int = 5000) -> threading.Thread:
    global TUNNEL_URL, _process, _tunnel_started
    if os.environ.get("RENDER"):
        return None
    with _tunnel_lock:
        if _tunnel_started:
            return None
        _tunnel_started = True

    cloudflared_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "cloudflared.exe")
    if not os.path.exists(cloudflared_bin):
        return None

    def _worker():
        global TUNNEL_URL, _process
        kill_orphan_cloudflared()
        time.sleep(1)
        cmd = [cloudflared_bin, "tunnel", "--url", f"http://127.0.0.1:{port}"]
        while True:
            try:
                _process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="ignore"
                )
                for line in _process.stdout:
                    line_str = line.strip()
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line_str)
                    if m:
                        TUNNEL_URL = m.group(0)
                        print(f"\n[★] Cloudflare Mobile Public URL: {TUNNEL_URL}\n", flush=True)
                        try:
                            url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_url.txt")
                            with open(url_file, "w", encoding="utf-8") as f:
                                f.write(TUNNEL_URL)
                        except Exception:
                            pass
                _process.wait()
            except Exception as e:
                print(f"[!] Cloudflare tunnel exception: {e}", file=sys.stderr)
            time.sleep(5)

    t = threading.Thread(target=_worker, daemon=True, name="CloudflareTunnelDaemon")
    t.start()
    return t
