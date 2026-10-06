"""국립공원공단 예약시스템 야영장 — '야영장 예약 잔여 현황'(로그인 불필요).

북한산 사기막야영장 등. 영지마다 날짜별 아이콘이 있다:
  <i title="A01 : 2026-10-24" class="icon-reservation ...">  ← 예약가능 (icon-waiting=대기, icon-none-reservation=만료, icon-end=불가)
날짜별로 icon-reservation 개수를 센다. (위쪽 '예약가능 시설수' RCCnt 칸은 실제와 무관하게 0이라 쓰면 안 됨)
응답이 수 MB짜리 HTML이라 필요한 부분만 정규식으로 뽑는다.
"""
import re
from datetime import date

from .common import session, wanted

BASE = "https://res.knps.or.kr"
PAGE = BASE + "/reservation/searchSimpleCampReservation.do"


def collect(name: str, dept_id: str, dept_name: str, park: str) -> dict:
    today = date.today()
    s = session()
    s.get(PAGE, timeout=20)
    html = s.post(BASE + "/reservation/campsiteList.do", timeout=40,
                  headers={"X-Requested-With": "XMLHttpRequest", "Referer": PAGE},
                  data={"dept_id": dept_id, "dept_name": dept_name, "parent_dept_name": park,
                        "prd_ctg_id": "", "isGreenpoint": "N"}).text
    icons = re.findall(r'<i\s+title="[^"]*?:\s*(\d{4}-\d\d-\d\d)"\s+class="(icon-[a-z-]+)', html)
    if not icons:
        raise RuntimeError("영지 아이콘 형식이 바뀜 (예약 현황을 못 찾음)")
    free, days = {}, set()
    for ymd, cls in icons:
        days.add(ymd)
        if cls == "icon-reservation":
            free[ymd] = free.get(ymd, 0) + 1
    slots = []
    for ymd in sorted(days):
        d = date.fromisoformat(ymd)
        if d < today or not wanted(d, "camp"):
            continue
        n = free.get(ymd, 0)
        slots.append({"item": "all", "date": ymd, "stock": n, "remain": n, "open": True})
    return {"name": name, "url": PAGE,
            "items": [{"id": "all", "name": "야영지(전체)", "cat": "camp", "url": PAGE}],
            "slots": slots}
