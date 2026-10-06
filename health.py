"""감시 자체의 건강 점검 → 텔레그램 (클라우드에서만 실행).

1) 고장 감지: 한 캠핑장이 3시간 넘게 연속으로 실패하면 "⚠️ 조회 고장", 회복되면 "✅ 복구".
   (각 수집기가 접속 실패·응답 형식 변경을 오류로 올린다. 월말처럼 빈 날짜가 0개인 건 정상.)
2) 생존 신호: 7일 동안 텔레그램을 한 번도 안 보냈으면 "🟢 정상 작동 중" + 현재 빈자리 요약.
3) 토큰 만료: notify.json 의 token_expires 30일 전부터 일주일에 한 번 "🔑 토큰 만료 D-n".
"""
import json
from datetime import date, datetime, timedelta

import collect

HEALTH = collect.DATA / "health.json"
BROKEN_AFTER = timedelta(hours=3)
HEARTBEAT_EVERY = timedelta(days=7)
TOKEN_WARN_DAYS = 30
NAMES = {"jungnang": "중랑", "uidong": "우이동", "angbong": "앵봉산", "choan": "초안산",
         "sagimak": "사기막", "gangdong": "강동그린웨이", "seoulpark": "서울대공원",
         "nanji": "난지", "jingwan": "진관글램핑", "dulle": "둘레캠프"}


def _load() -> dict:
    try:
        return json.loads(HEALTH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _problem(src: str, result: dict) -> str | None:
    """이번 회차에 이 캠핑장이 비정상이면 이유, 정상이면 None."""
    err = result["errors"].get(src)
    if not err:
        return None
    return "사이트 형식 변경 의심" if "형식" in err or "구조" in err or "못" in err else "접속 실패"


def check(result: dict, now: datetime, sent_alerts: int, available: dict,
          token_expires: str | None, link: str) -> list[tuple[str, str]]:
    """보낼 메시지 목록을 돌려주고 health.json 을 갱신한다."""
    h = _load()
    broken = h.get("broken", {})          # src → 처음 이상해진 시각
    reported = set(h.get("reported", []))  # 이미 고장 알림 보낸 src
    msgs = []

    sources = [k for k, _, _ in collect.DATED] + ["nanji"]
    for src in sources:
        why = _problem(src, result)
        if why:
            since = datetime.fromisoformat(broken.setdefault(src, now.isoformat(timespec="seconds")))
            if src not in reported and now - since >= BROKEN_AFTER:
                hours = int((now - since).total_seconds() // 3600)
                msgs.append((f"⚠️ 감시 고장: {NAMES.get(src, src)}\n{hours}시간째 {why}.\n"
                             "화면에는 직전 데이터가 표시돼요. 계속되면 확인이 필요해요.", link))
                reported.add(src)
        else:
            broken.pop(src, None)
            if src in reported:
                msgs.append((f"✅ 감시 복구: {NAMES.get(src, src)} 다시 정상 조회돼요.", link))
                reported.discard(src)

    # 토큰 만료 예고 (일주일에 한 번)
    if token_expires:
        left = (date.fromisoformat(token_expires) - now.date()).days
        last = h.get("token_warned")
        if left <= TOKEN_WARN_DAYS and (not last or now.date() - date.fromisoformat(last) >= timedelta(days=7)):
            msgs.append((f"🔑 GitHub 토큰 만료 D-{max(left, 0)} ({token_expires})\n"
                         "만료되면 10분 감시가 멈춰요. 새 토큰을 만들어 cron-job.org 에 넣어야 해요.", link))
            h["token_warned"] = now.date().isoformat()

    # 생존 신호: 이번 회차에 보낼 게 하나도 없고, 마지막 발송이 7일 넘었으면
    last_msg = h.get("last_msg")
    if sent_alerts or msgs:
        h["last_msg"] = now.isoformat(timespec="seconds")
    elif not last_msg:
        h["last_msg"] = now.isoformat(timespec="seconds")   # 첫 실행: 기준만 잡기
    elif now - datetime.fromisoformat(last_msg) >= HEARTBEAT_EVERY:
        counts = {}
        for v in available.values():
            counts[v["src"]] = counts.get(v["src"], 0) + 1
        summary = " · ".join(f"{NAMES.get(s, s)} {n}" for s, n in sorted(counts.items(), key=lambda x: -x[1]))
        msgs.append((f"🟢 캠핑 감시 정상 작동 중\n최근 7일 동안 보낼 알림이 없었어요.\n"
                     f"지금 예약 가능: {summary or '없음'}", link))
        h["last_msg"] = now.isoformat(timespec="seconds")

    h.update(broken=broken, reported=sorted(reported))
    HEALTH.write_text(json.dumps(h, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return msgs
