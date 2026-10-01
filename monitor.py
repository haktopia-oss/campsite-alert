"""수집 → 지난번과 비교 → 새 빈자리만 카톡.

  python monitor.py          감시 1회 (새 빈자리 있으면 카톡)
  python monitor.py --dry    카톡 대신 화면에 출력만
첫 실행은 기준선만 저장하고 알림을 보내지 않는다.
"""
import json
import sys
from datetime import date
from pathlib import Path

import collect
import kakao
import telegram
from collectors.common import holiday_name

STATE = collect.DATA / "state.json"
ALERTS = collect.DATA / "alerts.json"
ERRORS = collect.DATA / "errors.json"
CAT = collect.CAT
WD = collect.WD


def available(result: dict) -> dict:
    """지금 예약 가능한 것들 {key: 설명정보}."""
    out = {}
    for src, pre, _ in collect.DATED:
        j = result["sources"].get(src)
        if not j:
            continue
        names = {i["id"]: i for i in j["items"]}
        for s in j["slots"]:
            if s["open"] and s["remain"] > 0:
                it = names[s["item"]]
                out[f"{pre}:{s['item']}:{s['date']}"] = {
                    "src": src, "place": j["name"], "home": j["url"], "date": s["date"],
                    "cat": it["cat"], "name": it["name"], "remain": s["remain"], "url": it["url"]}
    n = result["sources"].get("nanji")
    if n:
        for z in n["zones"]:
            if z["open"]:
                out[f"n:{z['id']}"] = {"src": "nanji", "month": z["month"],
                                       "cat": z["cat"], "name": z["zone"], "url": z["url"]}
    return out


def _day(ymd: str) -> str:
    d = date.fromisoformat(ymd)
    hn = holiday_name(d)
    return f"{d.month}/{d.day}({WD[d.weekday()]}{', ' + hn if hn else ''})"


def messages(new: dict) -> list[tuple[str, str]]:
    """새 항목 → [(텍스트, 링크)] — 캠핑장별 1건씩 (카톡 200자 제한)."""
    msgs = []
    for src, _, _ in collect.DATED:
        j = [v for v in new.values() if v["src"] == src]
        if not j:
            continue
        j.sort(key=lambda v: (v["date"], v["cat"]))
        lines = [f"• {_day(v['date'])} [{CAT[v['cat']]}] {v['name'][:18]} {v['remain']}자리" for v in j]
        text = f"🏕️ {j[0]['place']} 주말 빈자리!\n" + "\n".join(lines[:6])
        if len(lines) > 6:
            text += f"\n…외 {len(lines) - 6}건"
        link = j[0]["url"] if len({v["url"] for v in j}) == 1 else j[0]["home"]
        msgs.append((text, link))
    for kind, title, tail in (
            ("open", "🏕️ 난지캠핑장 새 달 예약 오픈!", "(주말 여부는 달력에서 확인)"),
            ("reopen", "🏕️ 난지캠핑장 마감→접수중 (취소표)", "⚠️ 날짜는 몰라요 — 평일일 수도 있으니 달력에서 확인")):
        n = [v for v in new.values() if v["src"] == "nanji" and v.get("kind") == kind]
        if not n:
            continue
        n.sort(key=lambda v: (v["month"] or 0, v["cat"]))
        lines = [f"• {v['month']}월 [{CAT[v['cat']]}] {v['name'][:20]}" for v in n]
        text = title + "\n" + "\n".join(lines[:6])
        if len(lines) > 6:
            text += f"\n…외 {len(lines) - 6}건"
        text += "\n" + tail
        msgs.append((text, n[0]["url"]))
    return msgs


def _log_alerts(at: str, msgs: list, err: str | None, keep: int = 50) -> None:
    log = json.loads(ALERTS.read_text(encoding="utf-8")) if ALERTS.exists() else []
    for text, link in msgs:
        log.insert(0, {"at": at, "text": text, "link": link, "error": err})
    ALERTS.write_text(json.dumps(log[:keep], ensure_ascii=False, indent=1), encoding="utf-8")


def run(dry: bool = False) -> list[tuple[str, str]]:
    result = collect.run()
    now = available(result)
    first = not STATE.exists()
    prev = {} if first else json.loads(STATE.read_text(encoding="utf-8"))
    # 처음 보는 캠핑장은 이번엔 기준선만 저장 (추가 직후 알림 폭탄 방지)
    seen = set(prev.pop("_sources", ["jungnang", "nanji"] if prev else []))
    # 난지는 날짜를 모름 → 새 달 오픈(모든 존) + 마감→접수중(캠핑·글램핑 존만, 날짜는 직접 확인)
    had_nanji = "_nanji_opened" in prev
    nanji_opened = set(prev.pop("_nanji_opened", []))

    # 수집 실패한 소스는 이전 상태 유지 (실패를 '빈자리 사라짐'으로 오판하지 않게)
    for src in result["errors"]:
        prefix = collect.PREFIX[src] + ":"
        now.update({k: v for k, v in prev.items() if k.startswith(prefix)})

    new = {}
    for k, v in now.items():
        if k in prev or v["src"] not in seen:
            continue
        if v["src"] == "nanji":
            if not had_nanji:
                continue
            if k not in nanji_opened:
                v = {**v, "kind": "open"}        # 새 달 예약 오픈 (모든 존)
            elif v["cat"] in ("camp", "glamp"):
                v = {**v, "kind": "reopen"}      # 마감 → 접수중 = 취소표 (캠핑·글램핑만)
            else:
                continue                         # 바베큐·캠프파이어 재오픈은 무시
        new[k] = v
    # 접수중·예약마감·접수종료 = 이미 한 번 열린 달 ('안내중'만 아직 안 열림)
    nj = result["sources"].get("nanji") or {}
    nanji_opened |= {f"n:{z['id']}" for z in nj.get("zones", []) if z["status"] != "안내중"}
    msgs = [] if first else messages(new)
    channels = [(name, fn) for name, ok, fn in (
        ("텔레그램", telegram.configured(), telegram.send),
        ("카톡", kakao.configured(), kakao.send_me)) if ok]
    errs = []
    for text, link in msgs:
        if dry or not channels:
            print("---- (미발송)\n" + text + "\n→ " + link)
            continue
        for name, send in channels:
            try:
                send(text, link)
            except Exception as e:  # 한 채널이 실패해도 나머지·기록은 계속
                errs.append(f"{name}: {e}")
    sent_err = "; ".join(errs) or None
    ok_sources = seen | {s for s in result["sources"]}
    STATE.write_text(json.dumps({**now, "_sources": sorted(ok_sources),
                                 "_nanji_opened": sorted(nanji_opened)}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    if msgs and not dry:
        _log_alerts(result["checked_at"], msgs, sent_err)
    # 수집 오류 현황 (내용이 바뀔 때만 파일이 바뀌도록 시각은 넣지 않음)
    ERRORS.write_text(json.dumps(result["errors"], ensure_ascii=False, indent=1, sort_keys=True),
                      encoding="utf-8")

    print(f"[{result['checked_at']}] 가능 {len(now)}건, 새로 생김 {len(new)}건"
          + (" (첫 실행: 기준선 저장, 알림 없음)" if first else f", 알림 {len(msgs)}건")
          + (f", 오류 {result['errors']}" if result["errors"] else ""))
    return msgs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run(dry="--dry" in sys.argv)
