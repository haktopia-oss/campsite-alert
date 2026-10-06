"""국립공원공단 예약시스템 야영장 — '야영장 예약 잔여 현황'(로그인 불필요).

북한산 사기막야영장 등. 날짜별 예약가능 영지 수가 id="RCCnt{MMDD}" 칸에 들어 있다.
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
    cells = re.findall(r'id="RCCnt(\d{2})(\d{2})"\s*>\s*(\d+)', html)
    if not cells:
        raise RuntimeError("잔여 현황 표를 찾지 못함")
    slots = []
    for mm, dd, n in cells:
        y = today.year + (1 if int(mm) < today.month else 0)  # 연말에 다음 해 1월로 넘어가는 경우
        d = date(y, int(mm), int(dd))
        if d < today or not wanted(d, "camp"):
            continue
        n = int(n)
        slots.append({"item": "all", "date": d.isoformat(), "stock": n, "remain": n, "open": True})
    return {"name": name, "url": PAGE,
            "items": [{"id": "all", "name": "야영지(전체)", "cat": "camp", "url": PAGE}],
            "slots": slots}
