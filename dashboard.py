"""대시보드 데이터(status.json + 알림기록 → 화면용) 만들기. 로컬 서버와 GitHub Pages 공용.

  python dashboard.py _site   → _site/index.html + _site/status.json (클라우드용 정적 페이지)
"""
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

import requests

import collect
import monitor
from collectors.common import holiday_name

ROOT = Path(__file__).parent


def carry_over(status: dict, previous: dict) -> dict:
    """수집에 실패한 캠핑장은 직전 성공 데이터를 대신 넣는다 (stale_at = 그 데이터 시각)."""
    for src in status.get("errors", {}):
        old = (previous.get("sources") or {}).get(src)
        if old and src not in status.get("sources", {}):
            status.setdefault("sources", {})[src] = {
                **old, "stale_at": old.get("stale_at") or previous.get("checked_at")}
    return status


def build(status: dict, alerts: list, **extra) -> dict:
    days = {}
    for src, _, _ in collect.DATED:
        for sl in (status.get("sources", {}).get(src) or {}).get("slots", []):
            d = date.fromisoformat(sl["date"])
            days[sl["date"]] = {"wd": d.weekday(), "holiday": holiday_name(d)}
    return {**status, "days": days, "dated": [k for k, _, _ in collect.DATED],
            "notify": sorted(monitor.notify_sources()),
            "local_only": sorted(collect.LOCAL_ONLY) if collect.IN_CLOUD else [],
            "alerts": alerts[:20], **extra}


def _read(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    out.mkdir(exist_ok=True)
    shutil.copy(ROOT / "web" / "index.html", out / "index.html")
    status = _read(collect.STATUS, {})
    pages = os.environ.get("PAGES_URL")  # 클라우드: 직전 배포본에서 실패한 곳 데이터 가져오기
    if pages and status.get("errors"):
        try:
            prev = requests.get(pages.rstrip("/") + "/status.json", timeout=15).json()
            status = carry_over(status, prev)
        except Exception as e:
            print("직전 데이터 못 가져옴:", e)
    data = build(status, _read(monitor.ALERTS, []), cloud="github")
    (out / "status.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"사이트 생성: {out}")
