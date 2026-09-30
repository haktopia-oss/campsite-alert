"""샘플 알림 1건 (클라우드 동작 확인용). 지정 날짜가 아니면 아무것도 안 함."""
import json
import sys
from datetime import date

import collect
import monitor
import telegram

ONLY_ON = "2026-09-30"

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if date.today().isoformat() != ONLY_ON:
        print("예정일 아님 — 건너뜀")
        sys.exit(0)
    state = json.loads(monitor.STATE.read_text(encoding="utf-8"))
    picks = {k: v for k, v in state.items() if not k.startswith(("_", "n:"))}
    picks = dict(list(picks.items())[:3])
    msgs = monitor.messages(picks) or [("(현재 빈자리 없음)", "https://github.com")]
    text, link = msgs[0]
    telegram.send("[테스트 · PC 꺼진 상태 클라우드 발송]\n" + text, link)
    print("샘플 발송 완료")
