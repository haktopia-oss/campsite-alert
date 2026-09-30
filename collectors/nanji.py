"""난지캠핑장 — 서울시 공공서비스예약 목록에서 존·월별 접수 상태 조회.

날짜별 달력 API는 봇차단(DynaPath)이 걸려 있어 사용하지 않는다.
"""
import re
from datetime import date

from bs4 import BeautifulSoup

from .common import categorize, session

BASE = "https://yeyak.seoul.go.kr"
LIST = BASE + "/web/search/selectPageListDetailSearchImg.do"
DETAIL = BASE + "/web/reservation/selectReservView.do?rsv_svc_id="

# 상태 → 예약 가능 여부
OPEN_STATES = {"접수중"}


def _parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.select("ul.img_board > li > a[onclick]"):
        m = re.search(r"fnDetailPage\('(S\d+)'", a["onclick"])
        if not m:
            continue
        title = a.get("title", "").strip()
        status_el = a.select_one(".bd_label[class*=status]")
        use = a.find("b", class_="date2")
        rows.append({
            "id": m.group(1),
            "title": title,
            "status": status_el.get_text(strip=True) if status_el else "",
            "use_period": use.next_sibling.strip() if use and use.next_sibling else "",
        })
    return rows


def collect(max_pages: int = 15) -> dict:
    s = session()
    zones, seen = [], set()
    for page in range(1, max_pages + 1):
        html = s.get(LIST, params={"code": "T500", "dCode": "T502",
                                   "currentPage": page}, timeout=15).text
        rows = _parse_page(html)
        if not rows:
            break
        new = [r for r in rows if r["id"] not in seen]
        if not new:  # 마지막 페이지 이후 같은 페이지가 반복되는 경우
            break
        for r in new:
            seen.add(r["id"])
            if "난지캠핑장" not in r["title"]:
                continue
            # "10월 일반캠핑존 B형(4인용, 자갈형) 26년 한강공원 난지캠핑장"
            m = re.match(r"(\d{1,2})월\s*(.+?)\s*\d{2}년\s*한강공원\s*난지캠핑장", r["title"])
            month = int(m.group(1)) if m else None
            zone = m.group(2).strip() if m else r["title"]
            zones.append({
                "id": r["id"], "month": month, "zone": zone,
                "cat": categorize(zone), "status": r["status"],
                "open": r["status"] in OPEN_STATES,
                "use_period": r["use_period"], "url": DETAIL + r["id"],
            })
    # 이용기간이 이미 끝난 달은 제외 ("2026.09.01 ~ 2026.09.30")
    today = date.today().strftime("%Y.%m.%d")
    zones = [z for z in zones
             if not (m := re.search(r"~\s*(\d{4}\.\d{2}\.\d{2})", z["use_period"]))
             or m.group(1) >= today]
    order = {"camp": 0, "glamp": 1, "bbq": 2}
    zones.sort(key=lambda z: (z["month"] or 0, order[z["cat"]], z["zone"]))
    return {"name": "난지캠핑장", "url": BASE, "zones": zones}
