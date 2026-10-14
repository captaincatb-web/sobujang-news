"""API 키 없이 쓰는 추가 뉴스 검색: 네이버 뉴스 제목검색 결과 페이지

네이버 뉴스는 구글 뉴스가 잘 다루지 않는 국내 매체(전문지·지역지·인터넷 매체)까지 찾아 준다.
공식 API가 아니어서 짧은 간격으로 몰아 요청하면 403으로 막히므로 1초 간격으로 한 건씩 요청하고,
막히면 그 주 수집에서는 더 요청하지 않는다(다른 소스로 계속 동작하고 로그로만 알린다).
"""
import html
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

KST = timezone(timedelta(hours=9))
REQUEST_TIMEOUT = 20
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 모바일 검색이 한 페이지에 15건(PC는 10건)을 준다. 모바일이 막히면 PC로 넘어간다.
NAVER_HOSTS = [
    ("https://m.search.naver.com/search.naver", "m_news"),
    ("https://search.naver.com/search.naver", "news"),
]
NAVER_INTERVAL = 1.0  # 초. 73개사를 0.8~1초 간격으로 PC·모바일 각각 조회해도 차단되지 않았다

TAG_RE = re.compile(r"<[^>]+>")
RELATIVE_TIME_RE = re.compile(r"^(\d+)\s*(분|시간|일|주)\s*전$")
ABSOLUTE_DATE_RE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})\.?$")
TIME_LABEL_RE = re.compile(r">\s*(\d+\s*(?:분|시간|일|주)\s*전|\d{4}\.\d{1,2}\.\d{1,2}\.?)\s*<")
TIME_UNITS = {"분": "minutes", "시간": "hours", "일": "days", "주": "weeks"}

# 기사 1건은 언론사명(.prof) → 시각 → 제목(PC .tit / 모바일 .title) 순으로 나온다
NAVER_TITLE_RE = re.compile(r'href="([^"]+)"[^>]*data-heatmap-target="\.tit(?:le)?"[^>]*>(.*?)</a>', re.S)
NAVER_PRESS_RE = re.compile(r"^[^>]*>\s*<span[^>]*>([^<]+)</span>")


def _text(fragment: str) -> str:
    return html.unescape(TAG_RE.sub("", fragment)).strip()


def parse_time_label(label: str, now: datetime):
    """'10분 전'·'3일 전'·'2026.09.14.' → (UTC 시각, 날짜만 정확한지)"""
    label = label.strip()
    m = RELATIVE_TIME_RE.match(label)
    if m:
        unit = m.group(2)
        return now - timedelta(**{TIME_UNITS[unit]: int(m.group(1))}), unit in ("일", "주")
    m = ABSOLUTE_DATE_RE.match(label)
    if m:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d, 12, tzinfo=KST).astimezone(timezone.utc), True
    return None, False


def parse_naver_news(page: str, now: datetime) -> list:
    items = []
    for chunk in page.split('data-heatmap-target=".prof"')[1:]:
        title_m = NAVER_TITLE_RE.search(chunk)
        press_m = NAVER_PRESS_RE.search(chunk)
        time_m = TIME_LABEL_RE.search(chunk)
        if not (title_m and press_m and time_m):
            continue  # 언론사 로고 칸 등 기사 본문이 없는 조각
        pub_date, date_only = parse_time_label(time_m.group(1), now)
        if not pub_date:
            continue
        press = _text(press_m.group(1))
        title = _text(title_m.group(2)).replace("새 창 열림", "").strip()
        title = re.sub(r"\s+-\s+" + re.escape(press) + r"$|\s*[|｜]\s*$", "", title)  # 제목 끝의 '- 언론사', '|'
        # 네이버는 긴 제목을 '...'으로 잘라 보낸다 → 다른 소스의 전체 제목이 있으면 그쪽을 대표로 쓴다
        truncated = title.endswith("...")
        if truncated:
            title = title[:-3].rstrip() + "…"
        items.append(
            {
                "title": title,
                "link": html.unescape(title_m.group(1)),
                "pub_date": pub_date,
                "source": press,
                "date_only": date_only,
                "truncated": truncated,
                "clean": True,
            }
        )
    return items


class _Pacer:
    """여러 스레드에서 불러도 요청 사이 간격을 지키고, 403/429를 받은 호스트는 더 쓰지 않는다"""

    def __init__(self, interval: float):
        self.interval = interval
        self.lock = threading.Lock()
        self.last = 0.0
        self.blocked = set()

    def wait(self) -> None:
        with self.lock:
            delay = self.last + self.interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


_naver_pacer = _Pacer(NAVER_INTERVAL)


def fetch_naver_news(term: str, now: datetime | None = None) -> list:
    """네이버 뉴스 제목검색 (최신순): 회사명이 제목에 든 최근 기사 15건"""
    now = now or datetime.now(timezone.utc)
    for url, where in NAVER_HOSTS:
        if url in _naver_pacer.blocked:
            continue
        _naver_pacer.wait()
        params = {"where": where, "query": f'"{term}"', "sort": "1", "field": "1"}
        try:
            resp = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            print(f"[naver_web] '{term}' 조회 실패: {e}")
            return []
        if resp.status_code in (403, 429):
            _naver_pacer.blocked.add(url)
            print(f"[naver_web] {url} 차단({resp.status_code}) → 이번 수집에서는 이 주소를 더 쓰지 않음")
            continue
        if resp.status_code != 200:
            print(f"[naver_web] '{term}' 응답 {resp.status_code}")
            return []
        return parse_naver_news(resp.text, now)
    return []


def google_news_url(query: str, days: int, lang: str = "ko") -> str:
    if lang == "en":
        return f"https://news.google.com/rss/search?q={quote(query)}+when:{days}d&hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote(query)}+when:{days}d&hl=ko&gl=KR&ceid=KR:ko"
