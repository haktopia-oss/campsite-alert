"""로컬 웹 + 백그라운드 감시.

  python server.py   → http://localhost:8765 (켜져 있는 동안 5분마다 감시·카톡)
"""
import json
import sys
import threading
import time
import traceback
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

import collect
import dashboard
import monitor
import telegram

ROOT = Path(__file__).parent
PORT = 8765
INTERVAL = 5 * 60  # 초

CONFIG = ROOT / "config.json"

_lock = threading.Lock()
_info = {"running": False, "last_error": None, "next_check": None}
_cloud_cache = {"at": 0.0, "alerts": []}


def cloud_repo() -> str:
    """config.json 의 cloud_repo("사용자/저장소")가 있으면 알림은 클라우드가 담당."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("cloud_repo", "")
    except (OSError, ValueError):
        return ""


def cloud_alerts(repo: str) -> list:
    if time.time() - _cloud_cache["at"] > 60:
        try:
            r = requests.get(f"https://raw.githubusercontent.com/{repo}/main/cloud/alerts.json",
                             params={"t": int(time.time())}, timeout=10)
            _cloud_cache["alerts"] = r.json() if r.status_code == 200 else []
        except Exception:
            pass
        _cloud_cache["at"] = time.time()
    return _cloud_cache["alerts"]


def check_now() -> None:
    if not _lock.acquire(blocking=False):
        return  # 이미 확인 중
    _info["running"] = True
    try:
        if cloud_repo():
            collect.run()   # 화면용 수집만 — 알림은 클라우드(GitHub Actions)가 보냄
        else:
            monitor.run()
        _info["last_error"] = None
    except Exception as e:
        _info["last_error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    finally:
        _info["running"] = False
        _lock.release()


def loop() -> None:
    while True:
        check_now()
        _info["next_check"] = (datetime.now() + timedelta(seconds=INTERVAL)).isoformat(timespec="seconds")
        time.sleep(INTERVAL)


def status() -> dict:
    s = json.loads(collect.STATUS.read_text(encoding="utf-8")) if collect.STATUS.exists() else {}
    repo = cloud_repo()
    if repo:
        alerts = cloud_alerts(repo)
    else:
        alerts = json.loads(monitor.ALERTS.read_text(encoding="utf-8")) if monitor.ALERTS.exists() else []
    return dashboard.build(s, alerts, interval=INTERVAL,
                           telegram=telegram.configured(), cloud=repo, **_info)


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj) -> None:
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._json(status())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path == "/api/check":
            threading.Thread(target=check_now, daemon=True).start()
            self._json({"ok": True})
        elif self.path == "/api/quit":  # stop.bat
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if sys.stdout is None:  # pythonw(창 없이 실행) → 로그 파일로
        log = open(ROOT / "data" / "server.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:  # 이미 켜져 있으면 창만 연다
        webbrowser.open(f"http://localhost:{PORT}")
        sys.exit(0)
    threading.Thread(target=loop, daemon=True).start()
    print(f"캠핑 빈자리 감시 중 → http://localhost:{PORT}  (창을 닫으면 감시도 멈춥니다)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://localhost:{PORT}")
    srv.serve_forever()
