"""초안산캠핑장 — 노원구시설관리공단(문화인) '예약가능 자리조회' 달력 파싱.

로그인 없이 날짜·구역별 잔여 수를 준다. 인증서 체인이 불완전해 verify=False.
"""
import re
from datetime import date

import urllib3

from .common import is_weekend, session
from .xticket import _months

BASE = "https://nowonsc.moonhwain.kr:447"
MAIN = BASE + "/rsvc/rsv_srm.html?b_id=nowonsc"
CAL = BASE + "/rsvc/rsv_srmRsvCal.html"
_CELL = re.compile(r"srmRsvCalMap\('(\d{4}-\d\d-\d\d)','(\d+)'\);\"><span class=\"txt\">(.+?)\((\d+)\)</span>")


def _cat(zone: str) -> str:
    if "피크닉" in zone:
        return "bbq"      # 당일(미숙박)
    if "캐빈" in zone:
        return "glamp"    # 캐빈하우스
    return "camp"


def collect(months: int = 2) -> dict:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    today = date.today()
    s = session()
    s.verify = False
    s.get(MAIN, timeout=15)

    items, cells = {}, {}
    for ym in _months(today, months):
        html = s.get(CAL, params={"vwYm": ym, "s_idx": "", "stk_idx": ""},
                     headers={"Referer": MAIN}, timeout=15).text
        for ymd, idx, zone, n in _CELL.findall(html):  # 달력이 2개라 중복 → dict로 제거
            items[idx] = zone.strip()
            cells[(idx, ymd)] = int(n)

    slots = []
    for (idx, ymd), n in cells.items():
        d = date.fromisoformat(ymd)
        if d < today or not is_weekend(d):
            continue
        slots.append({"item": idx, "date": ymd, "stock": n, "remain": n, "open": True})
    return {"name": "초안산캠핑장", "url": MAIN,
            "items": [{"id": i, "name": z, "cat": _cat(z), "url": MAIN} for i, z in items.items()],
            "slots": slots}
