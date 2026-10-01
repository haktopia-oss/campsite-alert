"""공통: HTTP 세션, 주말/공휴일 판정, 분류."""
from datetime import date, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

try:
    import holidays as _holidays
    _KR = _holidays.SouthKorea()
except ImportError:  # 없으면 토·일만으로 판정
    _KR = {}


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    # 접속 지연·끊김은 몇 번 더 시도 (2s, 4s, 8s 간격)
    retry = Retry(total=3, connect=3, read=2, backoff_factor=2,
                  status_forcelist=(502, 503, 504), allowed_methods=None)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def is_holiday(d: date) -> bool:
    return d in _KR


def holiday_name(d: date) -> str:
    # `in` 이 해당 연도 공휴일을 로드한다 (.get 만으로는 로드 안 됨)
    return _KR.get(d, "") if d in _KR else ""


def _off(d: date) -> bool:
    return d.weekday() >= 5 or is_holiday(d)


def is_weekend(d: date) -> bool:
    """토·일, 그리고 토·일과 이어진 공휴일(연휴)만. 평일 중간에 낀 공휴일은 제외."""
    if d.weekday() >= 5:
        return True
    if not is_holiday(d):
        return False
    # 쉬는 날이 끊기지 않고 이어지다 토·일에 닿으면 연휴
    for step in (1, -1):
        x = d + timedelta(days=step)
        while _off(x):
            if x.weekday() >= 5:
                return True
            x += timedelta(days=step)
    return False


def wanted(d: date, cat: str) -> bool:
    """알림·표시 대상 날짜인지.

    바베큐(당일): 토·일 + 주말과 이어진 공휴일.
    캠핑·글램핑(1박): 그날이 쉬는 날이고 '다음 날도 쉬는 날'인 밤만
      → 토요일 밤, 다음날(월)이 공휴일인 일요일 밤, 공휴일 금요일 밤 등.
    """
    if not is_weekend(d):
        return False
    return cat == "bbq" or _off(d + timedelta(days=1))


def categorize(name: str) -> str:
    """상품명 → camp / glamp / bbq."""
    if "글램핑" in name:
        return "glamp"
    if "바베큐" in name or "바비큐" in name or "캠프파이어" in name:
        return "bbq"
    return "camp"
