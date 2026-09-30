"""대시보드 데이터(status.json + 알림기록 → 화면용) 만들기. 로컬 서버와 GitHub Pages 공용.

  python dashboard.py _site   → _site/index.html + _site/status.json (클라우드용 정적 페이지)
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import collect
import monitor
from collectors.common import holiday_name

ROOT = Path(__file__).parent


def build(status: dict, alerts: list, **extra) -> dict:
    days = {}
    for src, _, _ in collect.DATED:
        for sl in (status.get("sources", {}).get(src) or {}).get("slots", []):
            d = date.fromisoformat(sl["date"])
            days[sl["date"]] = {"wd": d.weekday(), "holiday": holiday_name(d)}
    return {**status, "days": days, "dated": [k for k, _, _ in collect.DATED],
            "alerts": alerts[:20], **extra}


def _read(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    out.mkdir(exist_ok=True)
    shutil.copy(ROOT / "web" / "index.html", out / "index.html")
    data = build(_read(collect.STATUS, {}), _read(monitor.ALERTS, []), cloud="github")
    (out / "status.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"사이트 생성: {out}")
