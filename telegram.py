"""텔레그램 봇 알림 (푸시·배너가 확실히 뜸).

  python telegram.py setup   → 봇 토큰 입력 → 봇에게 아무 메시지 보내기 → 연결 저장 + 테스트
  python telegram.py test    → 테스트 메시지
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

SECRET = Path(__file__).parent / ".secrets" / "telegram.json"


def _creds() -> dict | None:
    """로컬은 .secrets/telegram.json, 클라우드(GitHub Actions)는 환경변수."""
    if os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        return {"token": os.environ["TELEGRAM_TOKEN"], "chat_id": os.environ["TELEGRAM_CHAT_ID"]}
    if SECRET.exists():
        return json.loads(SECRET.read_text(encoding="utf-8"))
    return None


def configured() -> bool:
    return _creds() is not None


def _api(token: str, method: str, **params) -> dict:
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=40)
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(f"텔레그램 {method} 실패: {d.get('description')}")
    return d["result"]


def send(text: str, link: str, button_title: str = "예약하러 가기") -> None:
    sec = _creds()
    _api(sec["token"], "sendMessage", chat_id=sec["chat_id"], text=text,
         disable_web_page_preview=True,
         reply_markup={"inline_keyboard": [[{"text": button_title, "url": link}]]})


def setup() -> None:
    token = input("BotFather가 준 봇 토큰을 붙여넣고 Enter: ").strip()
    me = _api(token, "getMe")
    print(f"봇 확인: @{me['username']}")
    print(f"→ 텔레그램에서 @{me['username']} 을 열고 [시작] 버튼(또는 아무 메시지)을 보내주세요. 기다리는 중...")
    offset = None
    for _ in range(120):  # 최대 약 10분
        ups = _api(token, "getUpdates", timeout=5, **({"offset": offset} if offset else {}))
        for u in ups:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            if msg.get("chat", {}).get("type") == "private":
                SECRET.parent.mkdir(exist_ok=True)
                SECRET.write_text(json.dumps({"token": token, "chat_id": msg["chat"]["id"]}), encoding="utf-8")
                _api(token, "getUpdates", offset=offset, timeout=0)  # 처리한 메시지 비우기
                send("🏕️ 캠핑장 빈자리 알림이 연결됐어요!", "https://m.booking.naver.com/booking/5/bizes/387475")
                print("연결 완료! 텔레그램에 테스트 메시지를 보냈어요.")
                return
    sys.exit("시간 초과 — 봇에게 메시지를 보낸 뒤 다시 실행해주세요.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        setup()
    elif cmd == "test":
        send("🏕️ 텔레그램 알림 테스트입니다.", "https://m.booking.naver.com/booking/5/bizes/387475")
        print("발송 완료")
    else:
        print(__doc__)
