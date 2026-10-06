"""네이버예약 캠핑장 — 공개 API에서 상품(사이트)별·날짜별 잔여 조회.

중랑가족캠핑장, 북한산 진관글램핑장, 북한산 둘레캠프 등.
"""
import re
from datetime import date, datetime, timedelta

from .common import categorize, session, wanted

API = "https://api.booking.naver.com/v3.0/businesses/{}"
BOOK_URL = "https://m.booking.naver.com/booking/5/bizes/{}"  # 업종 번호가 달라도 네이버가 맞는 곳으로 넘겨줌


def _clean_name(name: str) -> str:
    # "[9월,10월] 2-1 오토캠핑사이트/데크" → "2-1 오토캠핑사이트/데크"
    return re.sub(r"^\[[^\]]*월\]\s*", "", name).strip()


def _window_end(item: dict, today: date) -> date:
    """예약 가능한 마지막 날짜 (RI01 = 오늘로부터 N일 이내)."""
    days = item.get("bookingAvailableEndValue")
    if item.get("bookingAvailableCode") == "RI01" and isinstance(days, int):
        return today + timedelta(days=days)
    return today + timedelta(days=60)


def collect(name: str, business_id: int, today: date | None = None, horizon_days: int = 45) -> dict:
    today = today or date.today()
    api, book = API.format(business_id), BOOK_URL.format(business_id)
    s = session()
    items = s.get(f"{api}/biz-items", params={"lang": "ko"}, timeout=15).json()
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"상품 목록을 못 받음: {str(items)[:80]}")

    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=horizon_days, hours=23, minutes=59, seconds=59)

    out_items, slots = [], []
    for it in items:
        if not it.get("isImp") or it.get("isClosedBooking"):
            continue
        iid = it["bizItemId"]
        cat = categorize(it["name"])
        item_name = _clean_name(it["name"])
        win_end = _window_end(it, today)
        paused = bool((it.get("bookableSettingJson") or {}).get("isPaused"))
        out_items.append({"id": iid, "name": item_name, "cat": cat,
                          "url": f"{book}/items/{iid}"})

        sched = s.get(f"{api}/biz-items/{iid}/daily-schedules", timeout=15, params={
            "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        }).json()
        if not isinstance(sched, dict):
            continue
        for ymd, v in sched.items():
            d = date.fromisoformat(ymd)
            if not wanted(d, cat) or not v.get("isBusinessDay") or not v.get("isSaleDay"):
                continue
            stock = v.get("stock") or 0
            if stock <= 0:
                continue
            remain = max(stock - (v.get("bookingCount") or 0), 0)
            slots.append({
                "item": iid, "date": ymd, "stock": stock, "remain": remain,
                "open": (d <= win_end) and not paused,  # 예약창 열린 날짜인지
            })

    return {"name": name, "url": book,
            "items": out_items, "slots": slots}
