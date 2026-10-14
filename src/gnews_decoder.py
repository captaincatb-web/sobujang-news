import json
import re
from concurrent.futures import ThreadPoolExecutor

import requests

# 구글뉴스 RSS 링크(news.google.com/rss/articles/CBMi...)를 원문 기사 주소로 변환한다.
# 원문 링크가 더 짧고(메일 용량 절감), 리디렉션 없이 바로 열린다. 실패하면 원래 링크를 그대로 쓴다.
ID_RE = re.compile(r"news\.google\.com/(?:rss/)?articles/([^?/]+)")
BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 10


def decode_one(url: str) -> str:
    m = ID_RE.search(url)
    if not m:
        return url
    gid = m.group(1)
    try:
        page = requests.get(f"https://news.google.com/rss/articles/{gid}", headers=HEADERS, timeout=TIMEOUT).text
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not sg or not ts:
            return url
        inner = (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
            f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{gid}",{ts.group(1)},"{sg.group(1)}"]'
        )
        resp = requests.post(
            BATCH_URL,
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])},
            timeout=TIMEOUT,
        )
        body = json.loads(resp.text.split("\n\n")[1])
        decoded = json.loads(body[0][2])[1]
        return decoded if isinstance(decoded, str) and decoded.startswith("http") else url
    except (requests.RequestException, ValueError, IndexError, TypeError, KeyError):
        return url


def decode_all(urls) -> dict:
    """{구글 링크: 원문 링크} (변환 실패 시 원래 링크)"""
    targets = sorted({u for u in urls if ID_RE.search(u or "")})
    if not targets:
        return {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        decoded = dict(zip(targets, pool.map(decode_one, targets)))
    ok = sum(1 for k, v in decoded.items() if k != v)
    print(f"구글뉴스 링크 원문 변환: {ok}/{len(targets)}")
    return decoded
