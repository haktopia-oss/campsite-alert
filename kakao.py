"""카카오톡 '나에게 보내기'.

  python kakao.py login   → REST API 키 입력 → 브라우저 로그인 → 토큰 저장
  python kakao.py test    → 테스트 메시지 발송
"""
import json
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

ROOT = Path(__file__).parent
SECRET = ROOT / ".secrets" / "kakao.json"
REDIRECT = "http://localhost:8080"
AUTH = "https://kauth.kakao.com/oauth"
MEMO = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def _load() -> dict:
    return json.loads(SECRET.read_text(encoding="utf-8"))


def _save(d: dict) -> None:
    SECRET.parent.mkdir(exist_ok=True)
    SECRET.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _store_tokens(sec: dict, tok: dict) -> dict:
    sec["access_token"] = tok["access_token"]
    sec["access_expires_at"] = time.time() + tok.get("expires_in", 0) - 300
    if tok.get("refresh_token"):  # 만료 1달 전부터만 새로 내려줌
        sec["refresh_token"] = tok["refresh_token"]
    _save(sec)
    return sec


def _refresh(sec: dict) -> dict:
    r = requests.post(f"{AUTH}/token", timeout=15, data={
        "grant_type": "refresh_token", "client_id": sec["rest_api_key"],
        "refresh_token": sec["refresh_token"]})
    if r.status_code != 200:
        raise RuntimeError(f"토큰 갱신 실패 {r.status_code}: {r.text} → 1_카카오로그인.bat 다시 실행")
    return _store_tokens(sec, r.json())


def _token() -> str:
    sec = _load()
    if time.time() >= sec.get("access_expires_at", 0):
        sec = _refresh(sec)
    return sec["access_token"]


def configured() -> bool:
    return SECRET.exists() and "refresh_token" in _load()


def send_me(text: str, link: str, button_title: str = "예약하러 가기") -> None:
    """텍스트(최대 200자) + 버튼 하나."""
    if len(text) > 200:
        text = text[:197] + "..."
    tmpl = {"object_type": "text", "text": text,
            "link": {"web_url": link, "mobile_web_url": link},
            "button_title": button_title}
    for attempt in range(2):
        r = requests.post(MEMO, timeout=15,
                          headers={"Authorization": f"Bearer {_token()}"},
                          data={"template_object": json.dumps(tmpl, ensure_ascii=False)})
        if r.status_code == 401 and attempt == 0:  # 토큰이 서버에서 먼저 만료된 경우
            _refresh(_load())
            continue
        if r.status_code != 200 or r.json().get("result_code") != 0:
            raise RuntimeError(f"카톡 발송 실패 {r.status_code}: {r.text}")
        return


def login() -> None:
    key = (_load().get("rest_api_key") if SECRET.exists() else "") or input("카카오 REST API 키를 붙여넣고 Enter: ").strip()
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "로그인 완료! 이 창은 닫아도 됩니다." if "code" in got else "오류: " + str(got)
            self.wfile.write(f"<h2>{msg}</h2>".encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = HTTPServer(("localhost", 8080), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"{AUTH}/authorize?" + urllib.parse.urlencode({
        "client_id": key, "redirect_uri": REDIRECT,
        "response_type": "code", "scope": "talk_message"})
    print("브라우저에서 카카오 로그인 + '카카오톡 메시지 전송' 동의를 해주세요...")
    webbrowser.open(url)
    for _ in range(300):
        if got:
            break
        time.sleep(1)
    srv.shutdown()
    if "code" not in got:
        sys.exit(f"로그인 실패: {got or '시간 초과'}")

    r = requests.post(f"{AUTH}/token", timeout=15, data={
        "grant_type": "authorization_code", "client_id": key,
        "redirect_uri": REDIRECT, "code": got["code"]})
    if r.status_code != 200:
        sys.exit(f"토큰 발급 실패 {r.status_code}: {r.text}\n"
                 "→ 클라이언트 시크릿이 켜져 있으면 끄고 다시 해주세요.")
    _store_tokens({"rest_api_key": key}, r.json())
    print(f"토큰 저장 완료: {SECRET}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "login":
        login()
    elif cmd == "test":
        send_me("🏕️ 캠핑장 빈자리 알림 테스트입니다.\n이 메시지가 보이면 연동 성공!",
                "https://m.booking.naver.com/booking/5/bizes/387475")
        print("테스트 카톡 발송 완료 — 휴대폰을 확인하세요.")
    else:
        print(__doc__)
