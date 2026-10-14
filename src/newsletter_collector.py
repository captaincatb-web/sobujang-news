import html
import os
import re
from calendar import timegm
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from src.history import KST
from src.news_sources import fetch_naver_news, google_news_url
from src.newsletter_config import (
    COMPANY_ALIAS_RAW,
    DART_CORP_CODES,
    ENGLISH_SEARCH_TERMS,
    FRESH_DAYS,
    get_display_name,
    CATEGORY_WEIGHT,
    HARD_BLACK_TITLES,
    MAX_AGE_DAYS,
    MAX_FOREIGN_PER_COMPANY,
    MAX_STORED_PER_COMPANY,
    NEWS_CATEGORIES,
    OUTPUT_DIR,
    RSS_LIST,
    SIMILARITY_THRESHOLD,
    all_company_names,
)

REQUEST_TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0"}

PHOTO_CAPTION_RE = re.compile(r"[\(\[〈][^\)\]〉]*사진[^\)\]〉]*[\)\]〉]\s*$")
PHOTO_TAG_RE = re.compile(r"^\s*[\(\[〈]\s*포토\s*[\)\]〉]")

STOCK_NOISE_RE = re.compile(
    r"(특징주|테마주|수혜주|관련주|주도주|대장주|고래사냥|내일장|주식민원|투자전략|테마\s*상승|투자분석|주달|52주|신고가|신저가|외국인\s*대량|순매도|순매수|코스닥|코스피|급등|급락|상한가|하한가|증시일정|리포트|총정리|상승여력|목표가|올릴\s*종목|폭등|반도체주|장비주|동반\s*상승|동반\s*폭등|주목을|방긋|초고수|사고.*팔았다|질주|가격\s*부담|상쇄|자신감|헬로스톡|주목할\s*종목|싸다|증권|실적\s*감안|기대감도|차익실현|매수\s*추천|칩칩폭폭|딸깍|전량매도|전량매수|매수일지|투자일지|매매일기|매매복기|추천부터|손절|존버|물타기|줍줍|영끌|풀매수|풀매도|시선강탈|공략법|불타오르네|%\s*[↑↓]|장중|현재가|원선에서|만원대\s*(상승|하락)|%\s*(올라|뛰어|내려|빠져|하락에)|기술적\s*분석|지지선|저항선|움직였습니다|주식\s*\d선|기판주|소재주|부품주|장비주|강세|약세|최선호주|선호주|탑픽|애널리스트|투자\s*포인트|저평가|고평가|증시|투자\s*캘린더|프리뷰|체크포인트|월가|株|재주목|애프터마켓|프리마켓|상승폭|하락폭|장\s*마감|마감\s*시황|매수세|매도세|주요\s*공시|경제\s*일정|주간\s*일정|(?:상승|하락)\s*vi\b|\d+만\s*\d*\s*원(?:대|으로|에|선)|%\s*대\s*(?:상승|하락|강세|약세)|가격\s*내역|과거\s*데이터|tokenized|xstock|마감\s*분석|기업\s*주식\s*정보|원\s*마감(?!재))"
)
STOCK_BRACKET_RE = re.compile(r"\[.*(강세|약세|특징|종목|테마|토픽|시황|고래|주식|베스트).*\].*")
BROKER_RE = re.compile(
    r"(한국투자|nh투자|kb증권|삼성증권|미래에셋|대신증권|키움증권|신한투자|하나증권|메리츠증권|유안타|리서치센터|목표주가|투자의견|상승 마감|하락 마감|주가\s*전망|주가\s*추이|주가)"
)
ENGLISH_STOCK_RE = re.compile(
    r"(stock|shares|nasdaq|nyse|tse:|price target|buy rating|sell rating|hold rating|downgrade|upgrade|analyst|earnings per share|\beps\b|dividend|market cap|short interest|hedge fund|institutional invest|results beat|p/e ratio|valuation|trading at|52-week|moving average|zacks|motley fool|seeking alpha|why .* stock|should you buy|undervalued|overvalued|fair value|intrinsic value|narrative\?|investors|initiated at|initiates|reiterat|outperform|underperform|overweight|underweight|rating|margin trading|earnings preview|wall street|better buy|\bvs\.?\s|\betf\b|research reports?|market is going to|market size|cagr|(?:loses|gains|rises|falls|drops|jumps|climbs|slides)\s+\d+(?:\.\d+)?\s*(?:percent|%)|pre-?market|after-hours)"
)

# 회사별 오탐 필터 (제목을 소문자로 바꾼 뒤 검사)
FALSE_POSITIVE_PATTERNS = {
    "머크퍼포먼스머티리얼즈": r"제약|의약|신약|임상|바이오|치료제",
    "와이씨": r"예측|가상자산|블록체인|스타트업|달바|성과보수",
    "프로텍": r"코리아프로텍|화장품|뷰티|쿠션|선크림|케이스|보호필름|아이폰|갤럭시|프로텍트|protect|사이버작전|프로텍션|프로텍터|아세아프로텍|시큐어|코나아이|카드|버노바|아카데미|요하네스버그|남아공|수료",
    "AP시스템": r"중국|거버넌스\s*강화|esg\s*보고서|우드맥킨지|woodmac|태양광|인버터|solar|inverter",
    "유진테크": r"유진테크놀로지",
    "에스티아이": r"여론조사|지지|응답|복당|대통령|정당|찬성|반대|국힘|민주당|후보",
    "테스": r"테스터|미용|의료기기|강소기업|바이오|두산테스나|비공개|베타|스트레스|게임|nasa|나사|망원경|테스\W*형|필라테스|요가|골대체재|드퓨신테스|시지바이오|노보시스|테스토닉|사이테스|cites|야생동물|멸종위기|파충류|희귀동물|밀수|밀매|테스티파이|테스토스|테스코|t\.e\.s\.s|아크리테스|테스라|넥슨|마비노기|테스트|신테스|tplo|정형외과|동물병원|수의|cbt|obt|biff|영화|배우|감독|바르텔레미|드라마|테스나",
    "후성": r"후성유전|유전체|유전학|유전 편집|에피크리스퍼|심포지엄",
    "제이티": r"걸그룹|아이돌|데뷔|엔터|제이티\s*코리아|저축은행|캐피탈|jtbc|제이티비씨|jt방송|jt비씨|제이티시스템|제이티넷|제이티이엔지|제이티전자",
    "ASML": r"니콘|캐논|재도전장|도전장|장악한",
    "케이씨": r"kc\s*인증|kc\s*마크|[가-힣]케이씨|케이씨지|kcg|케이씨씨|kcc|케이씨에스|케이씨티|선박|방식|방오|조선|^pkc|\bpkc\b|케이씨피드|hkc|케이씨텍|제이케이씨",
    "디아이": r"어드밴텍|advantech|디아이에프엠|difm|디아이동일|디아이씨|adi|아나로그디바이스|sdi|배터리|holding|asml|디바인|divine|변동 원인|주식 마감|nvidia|슈퍼마이크로|3di|도쿄일렉트론|디아이랩|디아이파워|디아이건설|엑스디아이",
    "솔브레인": r"솔브레인홀딩스|홀딩스",
    "피에스케이": r"피에스케이홀딩스|홀딩스",
    "티에스이": r"엘디티",
    "디엔에프": r"서경디엔에프|서경dnf",
    "에바라": r"jitsugyo|에바라실업",
    "KLA": r"코소보|kosovo|해방군|liberation army|전쟁\s*범죄|헤이그",
}
FALSE_POSITIVE_RE = {k: re.compile(v) for k, v in FALSE_POSITIVE_PATTERNS.items()}

ASCII_ALIAS_RE = re.compile(r"^[a-z0-9.&\- ]+$")

# 회사와 무관한 스팸·채용 공고
GENERAL_NOISE_RE = re.compile(r"토토|카지노|바카라|슬롯|채용|인턴|신입|공채|경력직|뽑는다|일자리\s*박람회|취업\s*박람회|현장\s*면접")
# 투자의견·주가 분석 위주 매체 (언론사명 기준)
BLOCKED_SOURCE_RE = re.compile(
    r"seeking alpha|simply wall|marketbeat|zacks|tipranks|motley fool|benzinga|gurufocus|stocktitan|smartkarma|ad hoc news|tradingview|moomoo|coinmarketcap|openpr",
    re.I,
)
# 사진/이미지 페이지, 주가 분석 사이트
BLOCKED_LINK_RE = re.compile(r"view_photo|image_popup|/photo/|simplywall\.st|tradersunion\.com|tradingkey\.com|calgaryroughnecks\.com")


def build_alias_map() -> dict:
    return {alias.lower(): company for company, aliases in COMPANY_ALIAS_RAW.items() for alias in aliases}


def is_dart_link(link: str) -> bool:
    return bool(link) and "dart.fss.or.kr" in link


def get_clean_title(title: str, link: str) -> str:
    # DART 공시는 제목을 자르지 않음 (시장구분 괄호만 제거)
    if is_dart_link(link):
        return re.sub(r"^\((유가|코스닥|코넥스|기타)\)", "", title).strip()
    clean = title
    last_dash = clean.rfind(" - ")
    if last_dash != -1:
        clean = clean[:last_dash]
    first_bracket = clean.find(" < ")
    if first_bracket != -1:
        clean = clean[:first_bracket]
    # 인베스팅닷컴 재배포 기사의 "… By 알파경제 alphabiz" 꼬리말 (영문 "Driven By AI" 같은 표현은 건드리지 않음)
    clean = re.sub(r"\s+By\s+(?=[가-힣])[^…]{1,25}$", "", clean)
    return re.sub(r"\s*[|｜]\s*$", "", clean).strip()


def is_stock_or_analysis_news(clean_title: str) -> bool:
    t = clean_title.lower()
    if re.search(r"\d{6}", t):
        return True
    if re.search(r"[+\-]\d+\.?\d*\s*%", t):
        return True
    return bool(STOCK_NOISE_RE.search(t) or STOCK_BRACKET_RE.search(t) or BROKER_RE.search(t))


def is_english_stock_news(clean_title: str) -> bool:
    if len(re.findall(r"[가-힣]", clean_title)) > 3:
        return False  # 한글 위주 제목은 한글 필터가 처리
    # "Entegris (ENTG)" 처럼 티커를 괄호로 단 영문 제목은 대부분 주가·밸류에이션 기사
    if re.search(r"\((?:NASDAQ|NYSE)?:?\s?[A-Z]{2,5}\)|\([A-Z0-9]{2,6}\.[A-Z]{1,3}\)", clean_title):
        return True
    return bool(ENGLISH_STOCK_RE.search(clean_title.lower()))


# 제목에 옛 연도가 박힌 재게시 기사 (예: "[미리보는 EXPO 2012]"). "2020년 이후/대비" 같은 비교 표현은 제외
OLD_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)(?!\s*년\s*(?:이후|이래|대비|보다|만|부터|래))")
# 기사 주소에 박힌 작성일 (예: /2026/10/06/, 20261007155723)
URL_DATE_RE = re.compile(r"(?<!\d)(20\d{2})([/_-]?)(0[1-9]|1[0-2])\2(0[1-9]|[12]\d|3[01])")


def is_stale(clean_title: str, link: str, now: datetime) -> bool:
    """제목의 옛 연도나 주소의 작성일로 보아 수집 기간보다 한참 오래된 재게시 기사인지"""
    for year in OLD_YEAR_RE.findall(clean_title):
        if int(year) <= now.year - 5:
            return True
    if is_dart_link(link):
        return False
    m = URL_DATE_RE.search(link or "")
    if m:
        try:
            url_date = datetime(int(m.group(1)), int(m.group(3)), int(m.group(4)), tzinfo=timezone.utc)
        except ValueError:
            return False
        return url_date < now - timedelta(days=MAX_AGE_DAYS + 7)
    return False


def is_false_positive(clean_title: str, company: str) -> bool:
    t = clean_title.lower()
    # "‘제2 ASML’ 니어필드" 처럼 다른 회사를 빗댄 표현
    for alias in [company, *COMPANY_ALIAS_RAW.get(company, [])]:
        if re.search(r"제\s*2의?\s*[‘'\"]?\s*" + re.escape(alias.lower()), t):
            return True
    pattern = FALSE_POSITIVE_RE.get(company)
    return bool(pattern and pattern.search(t))


# "이완호 한국알박 팀장." 처럼 인물 사진 캡션이 제목으로 들어오는 경우
PERSON_CAPTION_RE = re.compile(r"^\S+\s+\S+\s+(팀장|대표|사장|부장|상무|전무|이사|교수|연구원|회장|본부장)\.?$")


# "OOO 대표(앞줄 왼쪽부터)와 ... 기념촬영 했다" 같은 단체사진 캡션
GROUP_CAPTION_RE = re.compile(r"기념촬영|앞줄|뒷줄|왼쪽부터|오른쪽부터|를 비롯해|하고 있다\.?$|(?:전시|공개|소개)된\s+\S+(?:\s+\S+){0,2}$")


def is_photo_caption(title: str) -> bool:
    return bool(
        PHOTO_CAPTION_RE.search(title) or PHOTO_TAG_RE.search(title) or PERSON_CAPTION_RE.search(title) or GROUP_CAPTION_RE.search(title)
    )


def find_companies(clean_title: str, alias_map: dict) -> list:
    lower = clean_title.lower()
    if "skc" in lower or "에스케이씨" in lower:
        return []
    if "와이씨켐" in lower or "ycchem" in lower or "yc chem" in lower:
        return []

    matched = {}
    for alias in sorted(alias_map, key=len, reverse=True):
        if ASCII_ALIAS_RE.match(alias):
            # 순수 영문/숫자 alias는 단어 경계 매칭 (예: "di"가 "nvidia"에 걸리는 오탐 차단)
            if re.search(r"(^|[^a-z0-9])" + re.escape(alias) + r"([^a-z0-9]|$)", lower):
                matched[alias_map[alias]] = True
        elif len(alias) <= 2:
            # '테스','후성' 같은 두 글자 이름은 '카르테스'처럼 다른 단어 안에 들어간 경우를 제외
            if re.search(r"(^|[^가-힣\-])" + re.escape(alias), lower):
                matched[alias_map[alias]] = True
        elif alias in lower:
            matched[alias_map[alias]] = True
    return list(matched)


def get_news_tag(clean_title: str, link: str) -> str:
    """기사·공시 분류. 공시는 보고서명으로 분류하고, 맞는 분류가 없으면 '공시'."""
    for tag, pattern in NEWS_CATEGORIES:
        if pattern.search(clean_title):
            return tag
    return "공시" if is_dart_link(link) else "기타동향"


_NON_WORD_RE = re.compile(r"[^A-Za-z0-9_가-힣]")


def normalize_title(title: str) -> str:
    return _NON_WORD_RE.sub("", title).lower()


def similarity(a: str, b: str, company_name: str = "") -> float:
    # company_name: 회사명 자체가 만드는 bigram이 유사도를 과대평가하는 문제 방지
    def clean(s: str) -> str:
        r = s.lower()
        r = re.sub(r"[0-9]+", "", r)
        r = re.sub(r"규모|억원|천만원|백만원|만원|원|대비|매출액|비중", "", r)
        r = re.sub(r"공급\s*계약|수주\s*공시|장비\s*계약|계약\s*체결|공급", "수주", r)
        r = re.sub(r"상장\s*임박|상장\s*초읽기|발판\s*마련|잰걸음|독자\s*생태계|구축|가속", "상장", r)
        r = re.sub(r"삼성전자[와에가]", "삼성전자", r)
        r = _NON_WORD_RE.sub("", r)
        if company_name:
            cn = _NON_WORD_RE.sub("", company_name.lower())
            if cn:
                r = r.replace(cn, "")
        return r

    na, nb = clean(a), clean(b)
    if not na or not nb:
        return 0
    if nb in na or na in nb:
        return 1

    def bigrams(s: str) -> set:
        return {s[i : i + 2] for i in range(len(s) - 1)}

    bg_a, bg_b = bigrams(na), bigrams(nb)
    if not bg_a or not bg_b:
        return 0
    return len(bg_a & bg_b) / min(len(bg_a), len(bg_b))


# 같은 소식 판별용 핵심 단어에서 뺄 흔한 단어 (회사명은 따로 뺀다)
STOP_TOKENS = set(
    "반도체 삼성 삼성전자 sk sk하이닉스 하이닉스 엔비디아 tsmc ai hbm d램 낸드 메모리 파운드리 장비 소재 부품 기판 기술 "
    "시장 투자 공급 공급계약 계약 체결 수주 확대 전망 규모 실적 매출 영업이익 국내 글로벌 세계 한국 미국 중국 일본 대만 "
    "올해 내년 분기 상반기 하반기 업계 기업 회사 사업 산업 신규 최대 단독 속보 종합 인터뷰 상장사 리뷰 주주 지분 보고 공시 "
    "보고서 주요사항보고서 결정 추진 강화 성공 개발 협력 the and for with of in on to a".split()
)
_PARTICLE_RE = re.compile(r"(으로|에서|에게|까지|부터|에도|이며|하고|과|와|은|는|이|가|을|를|의|에|도|로|만)$")


def key_tokens(title: str, company: str) -> set:
    """제목의 핵심 단어 (금액·고유명사 등). 조사·흔한 단어·회사명은 뺀다"""
    t = title.lower()
    # 금액 표기 통일: "72억9250만원" → "72.9억", "72.9억원" → "72.9억"
    t = re.sub(r"(\d+)억\s*(\d{1,4})만", lambda m: f"{int(m.group(1)) + int(m.group(2)) / 10000:.1f}억", t)
    t = re.sub(r"(\d)(조|억|만)\s*원", r"\1\2", t)
    t = re.sub(r"(\d)\.(\d)", r"\1_\2", t)  # 28.84% 같은 소수를 한 단어로
    t = re.sub(r"(\d)\s+(조|억|만|천|엔|원|%|달러|주|건|대|호기)", r"\1\2", t)  # "1조 원" → "1조원"
    t = re.sub(r"(\d[조억만천])\s+(엔|원|달러)", r"\1\2", t)  # "1조 엔" → "1조엔"
    names = set()
    for alias in [company, get_display_name(company), *COMPANY_ALIAS_RAW.get(company, [])]:
        names.update(w for w in re.findall(r"[a-z0-9가-힣]+", alias.lower()) if len(w) >= 2)
    tokens = set()
    for w in re.findall(r"[a-z0-9가-힣%_]+", t):
        if len(w) > 2:
            w = _PARTICLE_RE.sub("", w)
        if len(w) >= 2 and w not in STOP_TOKENS and not w.isdigit() and not any(n in w for n in names):
            tokens.add(w)
    return tokens


def same_story(a: dict, b: dict, company: str) -> bool:
    """글자 유사도가 높거나, 사흘 이내 기사끼리 핵심 단어가 2개 이상 겹치면 같은 소식"""
    if similarity(a["title"], b["title"], company) >= SIMILARITY_THRESHOLD:
        return True
    if abs((a["pub_date"] - b["pub_date"]).total_seconds()) > 3 * 86400:
        return False
    return len(key_tokens(a["title"], company) & key_tokens(b["title"], company)) >= 2


def format_date_string(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

# 소스 우선순위: 같은 기사가 여러 곳에서 오면 먼저 처리된 소스의 링크·제목을 남긴다
# (원문 링크·정확한 시각을 주는 소스 먼저, 네이버 검색 페이지는 긴 제목이 잘려 와서 마지막)
SOURCE_PRIORITY = {"dart": 0, "naver": 1, "rss": 2, "google": 3, "google_en": 4, "naver_web": 5}

# 네이버 API는 언론사명을 주지 않으므로 원문 도메인으로 표기
PRESS_BY_DOMAIN = {
    "etnews.com": "전자신문", "thelec.kr": "디일렉", "zdnet.co.kr": "지디넷코리아", "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제", "yna.co.kr": "연합뉴스", "newsis.com": "뉴시스", "news1.kr": "뉴스1",
    "edaily.co.kr": "이데일리", "mt.co.kr": "머니투데이", "sedaily.com": "서울경제", "fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제", "heraldcorp.com": "헤럴드경제", "chosun.com": "조선일보", "biz.chosun.com": "조선비즈",
    "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레", "khan.co.kr": "경향신문",
    "ddaily.co.kr": "디지털데일리", "dt.co.kr": "디지털타임스", "inews24.com": "아이뉴스24", "bloter.net": "블로터",
    "thebell.co.kr": "더벨", "dealsite.co.kr": "딜사이트", "newspim.com": "뉴스핌", "nocutnews.co.kr": "노컷뉴스",
    "ajunews.com": "아주경제", "etoday.co.kr": "이투데이", "businesspost.co.kr": "비즈니스포스트", "ebn.co.kr": "EBN",
    "kmib.co.kr": "국민일보", "seoul.co.kr": "서울신문", "munhwa.com": "문화일보", "dynews.co.kr": "동양일보",
    "datanews.co.kr": "데이터뉴스", "digitaltoday.co.kr": "디지털투데이", "kipost.net": "KIPOST", "g-enews.com": "글로벌이코노믹",
    "pinpointnews.co.kr": "핀포인트뉴스", "ceoeconomy.com": "CEO경제신문", "datatooza.com": "데이터투자", "job-post.co.kr": "잡포스트",
    "cbci.co.kr": "CBC뉴스", "alphabiz.co.kr": "알파경제", "viva100.com": "브릿지경제", "econovill.com": "이코노믹리뷰",
    "segye.com": "세계일보", "joseilbo.com": "조세일보", "wowtv.co.kr": "한국경제TV", "mbn.co.kr": "MBN", "ytn.co.kr": "YTN",
    "kukinews.com": "쿠키뉴스", "newsway.co.kr": "뉴스웨이", "sisajournal-e.com": "시사저널e", "the-pr.co.kr": "더피알",
}
DOMAIN_LIKE_RE = re.compile(r"^(?:www\.)?[\w-]+(?:\.[\w-]+)+$")


def normalize_press(name: str) -> str:
    """'www.edaily.co.kr'·'https://www.edaily.co.kr/' 처럼 주소로 들어온 언론사명을 '이데일리'로"""
    name = re.sub(r"^https?://|/+$", "", name or "")
    if name and DOMAIN_LIKE_RE.match(name):
        return _press_from_link("https://" + name)
    return name


def _press_from_link(link: str) -> str:
    host = re.sub(r"^https?://", "", link).split("/")[0].lower()
    host = re.sub(r"^(www|m|news|biz)\.", "", host) if host.count(".") > 1 else host
    for domain, name in PRESS_BY_DOMAIN.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "뉴스 출처"


def _search_terms(company: str) -> list:
    """회사별 검색어: 대표명 + 한글 별칭(영문 약어는 오탐이 많아 제외)"""
    terms = [company]
    for alias in COMPANY_ALIAS_RAW.get(company, []):
        if alias != company and re.search(r"[가-힣]", alias) and len(alias) >= 4 and alias not in company:
            terms.append(alias)
    return terms[:2]


def _range_url(query: str, start: datetime, end: datetime, lang: str = "ko") -> str:
    """과거 시점 수집용 구글뉴스 검색 (after:/before: 날짜 범위)"""
    q = f"{query} after:{start:%Y-%m-%d} before:{end:%Y-%m-%d}"
    hl = "hl=en-US&gl=US&ceid=US:en" if lang == "en" else "hl=ko&gl=KR&ceid=KR:ko"
    return f"https://news.google.com/rss/search?q={quote(q)}&{hl}"


def build_sources(asof: datetime | None = None) -> list:
    """수집 소스 목록 (company 가 있으면 해당 회사로 직접 귀속되는 DART 피드).
    asof 를 주면 그 시점까지의 과거 주차 수집용으로, 날짜 범위를 줄 수 있는 구글뉴스 검색만 쓴다."""
    if asof:
        sources = []
        start, end = asof - timedelta(days=MAX_AGE_DAYS), asof + timedelta(days=1)
        for company in all_company_names():
            q = " OR ".join(f'"{t}"' for t in _search_terms(company))
            sources.append({"kind": "google", "url": _range_url(q, start, end), "company": ""})
            if company in ENGLISH_SEARCH_TERMS:
                q_en = " OR ".join(f'"{t}"' for t in ENGLISH_SEARCH_TERMS[company])
                sources.append({"kind": "google_en", "url": _range_url(q_en, asof - timedelta(days=14), end, "en"), "company": ""})
        return sources
    sources = []
    for company, code in DART_CORP_CODES.items():
        if code:
            sources.append({"kind": "dart", "url": f"https://dart.fss.or.kr/api/companyRSS.xml?crpCd={code}", "company": company})
    for url in RSS_LIST:
        sources.append({"kind": "google" if "news.google.com" in url else "rss", "url": url, "company": ""})
    # 회사별 개별 검색: OR로 묶은 검색은 결과 100건 한도에 큰 회사 기사가 몰려 작은 회사가 누락됨
    for company in all_company_names():
        terms = _search_terms(company)
        q = " OR ".join(f'"{t}"' for t in terms)
        sources.append({"kind": "google", "url": google_news_url(q, MAX_AGE_DAYS), "company": ""})
        # 네이버 뉴스 제목검색: 구글 뉴스가 다루지 않는 국내 매체까지 (검색어 OR가 안 돼 별칭은 따로 검색)
        for term in terms:
            sources.append({"kind": "naver_web", "term": term, "company": ""})
        if company in ENGLISH_SEARCH_TERMS:
            q_en = " OR ".join(f'"{t}"' for t in ENGLISH_SEARCH_TERMS[company])
            sources.append({"kind": "google_en", "url": google_news_url(q_en, 14, lang="en"), "company": ""})
        if os.environ.get("NAVER_CLIENT_ID"):
            sources.append({"kind": "naver", "query": f'"{company}"', "company": ""})
    sources.sort(key=lambda s: SOURCE_PRIORITY[s["kind"]])
    return sources


def _fetch_feed(source: dict) -> list:
    """소스 1개 조회 → [{title, link, pub_date, source, (date_only, truncated, clean)}]"""
    kind = source["kind"]
    if kind == "naver":
        return _fetch_naver(source["query"])
    if kind == "naver_web":
        return fetch_naver_news(source["term"])
    url = source["url"]
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"[rss] {resp.status_code} {url}")
            return []
        entries = feedparser.parse(resp.content).entries
    except requests.RequestException as e:
        print(f"[rss] 조회 실패 {url}: {e}")
        return []
    items = []
    for entry in entries:
        link = entry.get("link")
        items.append(
            {"title": entry.get("title"), "link": link, "pub_date": _entry_pub_date(entry), "source": _entry_source(entry, link or "")}
        )
    return items


def _fetch_naver(query: str) -> list:
    headers = {
        "X-Naver-Client-Id": os.environ.get("NAVER_CLIENT_ID", ""),
        "X-Naver-Client-Secret": os.environ.get("NAVER_CLIENT_SECRET", ""),
    }
    try:
        resp = requests.get(NAVER_NEWS_URL, headers=headers, params={"query": query, "display": 30, "sort": "date"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        raw_items = resp.json().get("items", [])
    except (requests.RequestException, ValueError) as e:
        print(f"[naver] '{query}' 조회 실패: {e}")
        return []
    items = []
    for item in raw_items:
        link = item.get("originallink") or item.get("link")
        try:
            pub_date = parsedate_to_datetime(item["pubDate"])
        except (KeyError, TypeError, ValueError):
            continue
        title = html.unescape(re.sub(r"</?b>", "", item.get("title", "")))
        items.append({"title": title, "link": link, "pub_date": pub_date, "source": _press_from_link(link or "")})
    return items


def _entry_pub_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)


def _entry_source(entry, link: str) -> str:
    if is_dart_link(link):
        return "DART 전자공시"
    source = entry.get("source")
    if isinstance(source, dict) and source.get("title"):
        return normalize_press(source["title"])
    return _press_from_link(link) if "news.google.com" not in link else "뉴스 출처"


HANGUL_RE = re.compile(r"[가-힣]")


def _drop_reason(clean_title: str, link: str, src_name: str) -> str:
    """모든 기사·공시에 적용하는 제외 사유 ('' 이면 통과)"""
    if any(b in clean_title for b in HARD_BLACK_TITLES):
        return "차단 제목"
    if is_photo_caption(clean_title):
        return "사진 캡션"
    # 네이버 프리미엄콘텐츠(유료 구독형)·블로그 차단
    if re.search(r"contents\.premium\.naver\.com|blog\.naver\.com|tistory\.com|brunch\.co\.kr", link) or "네이버 블로그" in clean_title:
        return "블로그·유료"
    if re.search(r"티스토리|tistory|브런치", src_name, re.IGNORECASE):
        return "블로그·유료"
    if re.search(r"네이버\s*프리미엄|프리미엄콘텐츠|premium\s*contents", src_name, re.IGNORECASE):
        return "블로그·유료"
    return ""


def _news_drop_reason(clean_title: str, link: str, src_name: str) -> str:
    """회사별 공시 피드가 아닌 일반 기사에만 적용하는 제외 사유"""
    if is_stock_or_analysis_news(clean_title):
        return "주가·증시"
    if is_english_stock_news(clean_title):
        return "영문 주가"
    if GENERAL_NOISE_RE.search(clean_title):
        return "스팸·채용"
    if BLOCKED_LINK_RE.search(link) or BLOCKED_SOURCE_RE.search(src_name):
        return "차단 매체"
    return ""


def collect_articles(asof: datetime | None = None) -> dict:
    """DART + RSS + 구글뉴스 + 포털 뉴스검색 수집 → {회사명: [article, ...]} (회사별 최신순 상위 N건)"""
    alias_map = build_alias_map()
    sources = build_sources(asof)

    with ThreadPoolExecutor(max_workers=16) as pool:
        feeds = list(pool.map(_fetch_feed, sources))

    now = asof.astimezone(timezone.utc) if asof else datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    fresh_cutoff = now - timedelta(days=FRESH_DAYS)
    raw, kept, reasons = Counter(), Counter(), Counter()
    dropped = []  # 회사명이 든 최근 기사 중 걸러진 것 (필터 점검용)
    valid_articles = []
    seen_titles, seen_stale = set(), set()
    for source, items in zip(sources, feeds):
        kind, fixed_company = source["kind"], source["company"]
        raw[kind] += len(items)
        for item in items:
            title, link, pub_date = item["title"], item["link"], item["pub_date"]
            if not title or not link or not pub_date or pub_date < cutoff or pub_date > now:
                continue

            # 포털 검색 제목에는 '- 언론사' 꼬리가 없어 그대로 쓴다
            clean_title = title.strip() if item.get("clean") else get_clean_title(title, link)
            src_name = item["source"]
            # 같은 기사가 다른 소스/언론사로 들어와도 한 번만 (공백·기호 차이 무시, 잘린 제목은 앞부분 일치)
            norm = normalize_title(clean_title)
            if not norm or norm in seen_titles:
                continue
            if item.get("truncated") and any(t.startswith(norm) for t in seen_titles):
                continue
            if is_stale(clean_title, link, now):
                # 재게시된 옛 기사는 같은 제목의 최신 기사를 막지 않도록 따로 기억한다
                if norm in seen_stale:
                    continue
                seen_stale.add(norm)
                reason = "옛 기사"
            else:
                seen_titles.add(norm)
                reason = _drop_reason(clean_title, link, src_name)
            if not reason and fixed_company and re.search(r"\[첨부(추가|정정)\]", clean_title):
                reason = "첨부 정정 공시"  # 첨부서류만 추가·정정한 재제출 공시는 소식 가치가 없다
            if not reason and not fixed_company:
                reason = _news_drop_reason(clean_title, link, src_name)
            if reason:
                reasons[reason] += 1
                if not fixed_company and pub_date >= fresh_cutoff:
                    names = find_companies(clean_title, alias_map)
                    if names:
                        dropped.append((reason, ",".join(names), kind, src_name, clean_title))
                continue

            local = pub_date.astimezone(KST)
            base = {
                "title": clean_title,
                "link": link,
                "source": src_name,
                # 포털 검색의 'N일 전'처럼 날짜만 정확한 기사는 시각을 표시하지 않는다
                "date_str": local.strftime("%m-%d") if item.get("date_only") else format_date_string(pub_date),
                "pub_date": pub_date,
                "cat2": get_news_tag(clean_title, link),
                "via": kind,
                "truncated": item.get("truncated", False),
            }

            if fixed_company:
                # 회사별 DART 피드: 매칭/오탐필터 우회 → 해당 회사로 직접 귀속
                valid_articles.append(
                    {**base, "company": fixed_company, "cat3": "공시자료" if is_dart_link(link) else "기업동향"}
                )
                kept[kind] += 1
                continue

            names = find_companies(clean_title, alias_map)
            matched = [c for c in names if not is_false_positive(clean_title, c)]
            if names and not matched:
                reasons["동명이인·오탐"] += 1
                if pub_date >= fresh_cutoff:
                    dropped.append(("동명이인·오탐", ",".join(names), kind, src_name, clean_title))
            for company in matched:
                valid_articles.append({**base, "company": company, "cat3": "기업동향"})
            kept[kind] += bool(matched)

    by_company = {c: [] for c in all_company_names()}
    for article in valid_articles:
        by_company.setdefault(article["company"], []).append(article)

    for company, articles in by_company.items():
        seen_links = set()
        korean, foreign = [], []
        for a in sorted(articles, key=lambda x: x["pub_date"], reverse=True):
            if a["link"] in seen_links:
                continue
            seen_links.add(a["link"])
            (korean if HANGUL_RE.search(a["title"]) else foreign).append(a)
        kept_articles = korean[:MAX_STORED_PER_COMPANY] + foreign[:MAX_FOREIGN_PER_COMPANY]
        by_company[company] = sorted(kept_articles, key=lambda x: x["pub_date"], reverse=True)

    covered = sum(1 for a in by_company.values() if a)
    fresh_covered = sum(1 for arts in by_company.values() if any(a["pub_date"] >= fresh_cutoff for a in arts))
    print("소스별 원본 건수:", dict(raw))
    print("소스별 채택 건수:", dict(kept))
    print("제외 사유:", dict(reasons))
    print(f"수집 완료: {len(valid_articles)}건 / 기사 있는 회사 {covered}/{len(by_company)} (최근 {FRESH_DAYS}일 {fresh_covered}곳)")
    if not asof:
        _write_collect_report(raw, kept, reasons, dropped, by_company, fresh_cutoff)
    return by_company


def _write_collect_report(raw, kept, reasons, dropped, by_company, fresh_cutoff) -> None:
    """수집 점검용 보고서 → output/collect_report.txt (소스별 건수, 회사별 출처, 걸러진 최근 기사)"""
    lines = [
        "소스별 원본 건수: " + ", ".join(f"{k} {v}" for k, v in raw.most_common()),
        "소스별 채택 건수: " + ", ".join(f"{k} {v}" for k, v in kept.most_common()),
        "제외 사유: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()),
        "",
        f"[회사별 최근 {FRESH_DAYS}일 기사 수 · 처음 찾은 소스 기준]",
    ]
    for company, articles in by_company.items():
        fresh = Counter(a["via"] for a in articles if a["pub_date"] >= fresh_cutoff)
        lines.append(f"{company}: " + (", ".join(f"{k} {v}" for k, v in fresh.most_common()) or "-"))
    lines += ["", f"[걸러진 최근 {FRESH_DAYS}일 기사 중 회사명이 든 것] 사유 | 회사 | 소스 | 언론사 | 제목"]
    lines += [" | ".join(row) for row in sorted(dropped)[:800]]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "collect_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_similar(by_company: dict) -> dict:
    """회사별로 같은 사건을 다룬 기사·공시를 묶는다 (대표 기사 + similar_articles).
    대표뿐 아니라 이미 묶인 기사와도 비교해, 표현이 조금씩 다른 같은 소식이 따로 나오지 않게 한다."""
    grouped = {}
    for company, articles in by_company.items():
        clusters = []
        for article in articles:
            article = {**article, "similar_articles": []}
            for rep in clusters:
                members = [rep] + rep["similar_articles"]
                if any(same_story(article, m, company) for m in members):
                    rep["similar_articles"].append(article)
                    break
            else:
                clusters.append(article)
        grouped[company] = [_pick_headline(c) for c in clusters]
    return grouped


def _pick_headline(rep: dict) -> dict:
    """묶음의 대표 고르기: 공시와 기사가 묶이면 기사 제목, 잘린 제목(네이버 검색)이면 전체 제목이 있는 기사"""
    rep = _prefer_news_headline(rep)
    if not rep.get("truncated"):
        return rep
    full = next((s for s in rep["similar_articles"] if not s.get("truncated") and s["cat3"] != "공시자료"), None)
    if not full:
        return rep
    sims = [{**rep, "similar_articles": []}] + [s for s in rep["similar_articles"] if s is not full]
    sims.sort(key=lambda s: s["cat3"] != "공시자료")  # 묶인 공시는 계속 바로 아래(↳)에 둔다
    cat2 = rep["cat2"] if CATEGORY_WEIGHT.get(rep["cat2"], 1) > CATEGORY_WEIGHT.get(full["cat2"], 1) else full["cat2"]
    return {**full, "cat2": cat2, "similar_articles": sims}


def _prefer_news_headline(rep: dict) -> dict:
    """공시와 그 공시를 다룬 기사가 묶이면, 상대방·금액이 드러나는 기사 제목을 대표로 하고 공시는 바로 아래에 둔다"""
    if rep["cat3"] != "공시자료":
        return rep
    news = [s for s in rep["similar_articles"] if s["cat3"] != "공시자료"]
    if not news:
        return rep
    head = news[0]
    filing = {**rep, "similar_articles": []}
    others = [s for s in rep["similar_articles"] if s is not head]
    # 공시 보고서명으로 정한 분류가 더 정확하면(예: 기사 쪽이 '기타동향') 공시 분류를 따른다
    cat2 = rep["cat2"] if CATEGORY_WEIGHT.get(rep["cat2"], 1) > CATEGORY_WEIGHT.get(head["cat2"], 1) else head["cat2"]
    return {**head, "cat2": cat2, "similar_articles": [filing] + others}
