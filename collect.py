"""캠핑장 전체 수집 1회 실행 → data/status.json 저장 + 요약 출력."""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from collectors import choan, jungnang, nanji, xticket
from collectors.common import holiday_name

ROOT = Path(__file__).parent
DATA = ROOT / os.environ.get("DATA_DIR", "data")
STATUS = DATA / "status.json"
CAT = {"camp": "캠핑", "glamp": "글램핑", "bbq": "바베큐"}
WD = "월화수목금토일"

# (키, 상태키 접두어, 수집함수) — 날짜별 빈자리 소스. 접두어는 state.json 호환 위해 고정.
DATED = [
    ("jungnang", "j", jungnang.collect),
    ("uidong", "u", lambda: xticket.collect(
        "우이동가족캠핑장", "13896b8dd3600159017b0e96c5bd5be7df3236beaa12b8fdb7aa462bab916b2f")),
    ("angbong", "a", lambda: xticket.collect(
        "앵봉산가족캠핑장", "a12d6508ae5ea0562923cb1f2762761f3413ab4c988a6c8aa92ea7873e263bec")),
    ("choan", "c", choan.collect),
]
PREFIX = {k: p for k, p, _ in DATED} | {"nanji": "n"}


def run() -> dict:
    result = {"checked_at": datetime.now().isoformat(timespec="seconds"),
              "sources": {}, "errors": {}}
    for key, fn in [(k, f) for k, _, f in DATED] + [("nanji", nanji.collect)]:
        try:
            result["sources"][key] = fn()
        except Exception as e:  # 한 곳이 실패해도 다른 곳은 계속
            result["errors"][key] = f"{type(e).__name__}: {e}"
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def summary(r: dict) -> None:
    print(f"확인 시각: {r['checked_at']}")
    for k, e in r["errors"].items():
        print(f"[오류] {k}: {e}")

    for key, _, _ in DATED:
        j = r["sources"].get(key)
        if not j:
            continue
        names = {i["id"]: i for i in j["items"]}
        print(f"\n=== {j['name']} ({len(j['items'])}개 품목, 주말 슬롯 {len(j['slots'])}개) ===")
        by_date = {}
        for s in j["slots"]:
            if s["open"] and s["remain"] > 0:
                by_date.setdefault(s["date"], []).append(s)
        if not by_date:
            print("  예약 가능한 주말 빈자리 없음")
        for ymd in sorted(by_date):
            d = date.fromisoformat(ymd)
            hn = holiday_name(d)
            print(f"  {ymd}({WD[d.weekday()]}){' ' + hn if hn else ''}")
            for s in by_date[ymd]:
                it = names[s["item"]]
                print(f"    [{CAT[it['cat']]}] {it['name']}  잔여 {s['remain']}/{s['stock']}")

    n = r["sources"].get("nanji")
    if n:
        print(f"\n=== 난지 ({len(n['zones'])}개 존·월) ===")
        for z in n["zones"]:
            mark = "🟢" if z["open"] else "🔴"
            print(f"  {mark} {z['month']}월 [{CAT[z['cat']]}] {z['zone']} — {z['status']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    summary(run())
