"""추가 뉴스 RSS/Atom 목록.

기존 포털/공시 검색의 보조 소스. 기사 제목에 등록 기업이 확인된 항목만
기존 회사별 필터·중복 제거·AI 검증을 거친다. 유료 기사 본문은 수집하지 않는다.

URL 참고:
- 국내 RSS: 한국경제, 조선비즈, 연합뉴스, 파이낸셜뉴스, 아시아경제
- 해외 RSS: Semiconductor Engineering, EE Times, SemiWiki, SemiAnalysis
RSS 제공·접속 정책은 변경될 수 있어 실행 시 상태를 별도로 기록한다.
"""

KOREAN_INDUSTRY_RSS = [
    ("한국경제", "https://www.hankyung.com/feed/all-news"),
    ("조선비즈", "https://biz.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("연합뉴스 경제", "https://www.yna.co.kr/rss/economy.xml"),
    ("파이낸셜뉴스", "https://www.fnnews.com/rss/r20/fn_realnews_all.xml"),
    ("아시아경제", "https://www.asiae.co.kr/rss/all.htm"),
]

GLOBAL_SEMICON_RSS = [
    ("Semiconductor Engineering", "https://semiengineering.com/feed/"),
    ("EE Times", "https://www.eetimes.com/feed/"),
    ("SemiWiki", "https://semiwiki.com/feed/"),
    ("SemiAnalysis", "https://newsletter.semianalysis.com/feed"),
]

# 가동 결과를 확인한 뒤 변경할 수 있도록 출처명·URL을 함께 관리.
ADDITIONAL_RSS_URLS = [url for _name, url in KOREAN_INDUSTRY_RSS + GLOBAL_SEMICON_RSS]
GLOBAL_RSS_URLS = frozenset(url for _name, url in GLOBAL_SEMICON_RSS)
