"""xticket(camp.xticket.kr) 캠핑장 — 날짜별 잔여 수(전체 사이트 합계).

우이동가족캠핑장(강북구), 앵봉산가족캠핑장(은평구) 등.
풀 브라우저 UA + Referer + Origin 이 없으면 빈 응답 `{}` 이 온다.
"""
from datetime import date

from .common import session, wanted

BASE = "https://camp.xticket.kr"


def _months(today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def collect(name: str, shop_encode: str, months: int = 2) -> dict:
    today = date.today()
    main = f"{BASE}/web/main?shopEncode={shop_encode}"
    hdr = {"X-Requested-With": "XMLHttpRequest", "Referer": main, "Origin": BASE}
    s = session()
    s.get(main, timeout=15)
    s.post(f"{BASE}/Web/Book/GetShopInformation.json",
           data={"shop_encode": shop_encode}, headers=hdr, timeout=15)

    slots = []
    for ym in _months(today, months):
        r = s.post(f"{BASE}/Web/Book/GetBookPlayDate.json",
                   data={"play_month": ym}, headers=hdr, timeout=15).json()
        if r.get("error") or r.get("error1"):
            raise RuntimeError((r.get("error") or r.get("error1")).get("message"))
        for x in (r.get("data") or {}).get("bookPlayDateList") or []:
            pd = x.get("play_date") or ""
            if len(pd) != 8:
                continue
            d = date(int(pd[:4]), int(pd[4:6]), int(pd[6:]))
            if d < today or not wanted(d, "camp"):
                continue
            remain = int(x.get("book_remain_count") or 0)
            slots.append({"item": "all", "date": d.isoformat(), "stock": remain,
                          "remain": remain,
                          "open": x.get("advance_yn") != "1"})  # 1 = 우선예약 기간
    return {"name": name, "url": main,
            "items": [{"id": "all", "name": "캠핑 사이트(전체)", "cat": "camp", "url": main}],
            "slots": slots}
