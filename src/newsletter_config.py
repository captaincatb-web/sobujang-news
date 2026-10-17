import re

from src.config import ROOT_DIR
from src.newsletter_extra_groups import EXTRA_AMBIGUOUS, EXTRA_DUP_OF, EXTRA_RAW

# ============================================================
#  [뉴스레터 2호] 1~4그룹 소부장 파트너사 동향 (Google Apps Script 버전 이식)
# ============================================================

RECIPIENT_EMAIL_DEFAULT = "devla@naver.com"
FIXED_COMPANY_LIMIT = 2
SIMILARITY_THRESHOLD = 0.30
MAX_STORED_PER_COMPANY = 30
MAX_FOREIGN_PER_COMPANY = 5  # 영문 기사는 양이 많아 국문 기사를 밀어내지 않도록 따로 상한을 둔다
MAX_SIM = 1  # 기사당 표시할 유사기사 최대 건수
MAX_AGE_DAYS = 30  # 이보다 오래된 기사는 제외
FALLBACK_DEPTH = 4  # 최신 분기 조회 실패 시 과거로 최대 몇 단계까지 더 시도할지

# 해외 기업 영문 검색어 (구글 뉴스 영문판). 국문 기사가 없을 때 보완용이라 순위에서는 국문 기사보다 뒤로 간다
ENGLISH_SEARCH_TERMS = {
    "ASML": ["ASML"],
    "어플라이드머티어리얼즈": ["Applied Materials"],
    "램리서치": ["Lam Research"],
    "도쿄일렉트론": ["Tokyo Electron"],
    "KLA": ["KLA Corp", "KLA Corporation"],
    "에바라": ["Ebara"],
    "인테그리스": ["Entegris"],
    "이비덴": ["Ibiden"],
    "레이저텍": ["Lasertec"],
}

CACHE_PATH = ROOT_DIR / "data" / "newsletter_cache.json"
OUTPUT_DIR = ROOT_DIR / "output"

RSS_LIST = [
    "https://rss.etnews.com/Section902.xml",
    "http://www.thelec.kr/rss/allArticle.xml",
    "https://feeds.feedburner.com/zdkorea",
    # 전자신문 소부장 전용 섹션
    "http://rss.etnews.com/06064.xml",  # 전자 > 소재
    "http://rss.etnews.com/06062.xml",  # 전자 > 부품
    "http://rss.etnews.com/06061.xml",  # 전자 > 장비
    # 반도체·전자 전문지와 경제지 산업면 (최신 50건 안팎만 주므로 포털 검색의 보조)
    "https://www.kipost.net/rss/allArticle.xml",
    "https://www.epnc.co.kr/rss/allArticle.xml",
    "https://www.mk.co.kr/rss/50100032/",
    "https://www.ebn.co.kr/rss/allArticle.xml",
    "https://news.google.com/rss/search?q=(반도체+기술개발+OR+신제품+OR+양산+OR+국산화+OR+공급계약+OR+수주+OR+투자+OR+증설)+when:14d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(반도체+사업재편+OR+합병+OR+인수+OR+거버넌스+OR+ESG)+when:14d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(AP시스템+OR+국제엘렉트릭+OR+글로벌스탠다드테크놀로지+OR+버슘머트리얼즈+OR+신성이엔지+OR+에드워드코리아+OR+에스티아이)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(에이에스엠케이+OR+엘오티베큠+OR+원익IPS+OR+유니셈+OR+유진테크+OR+케이씨+OR+테스+OR+테키스트+OR+피에스케이+OR+한국알박+OR+한양이엔지)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(금강쿼츠+OR+뉴파워프라즈마+OR+디아이+OR+새솔다이아몬드공업+OR+신한다이아몬드공업+OR+싸이노스+OR+아드반테스트코리아+OR+엠이케이+OR+영신쿼츠+OR+예스티)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(와이씨+OR+원익큐엔씨+OR+이오테크닉스+OR+제이티+OR+코리아인스트루먼트+OR+코미코+OR+코세스+OR+티에스이+OR+프로텍+OR+피엠티+OR+하나머티리얼즈)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(대덕전자+OR+동우화인켐+OR+동진쎄미켐+OR+동진세미켐+OR+디엔에프+OR+린데코리아+OR+머크퍼포먼스머티리얼즈+OR+삼영순화+OR+솔브레인+OR+신성전자정밀+OR+심텍+OR+아데카코리아)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(에어프로덕츠코리아+OR+에프에스티+OR+엔씨케이+OR+엠이엠씨코리아+OR+엠케이전자+OR+원익머트리얼즈+OR+이엔에프테크놀로지+OR+케이씨텍+OR+코스탯아이앤씨)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(티엘비+OR+티오케이첨단재료+OR+한솔케미칼+OR+해성디에스+OR+후성)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=(ASML+OR+어플라이드머티어리얼즈+OR+램리서치+OR+도쿄일렉트론+OR+KLA+OR+에바라+OR+인테그리스+OR+이비덴+OR+레이저텍)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    # 충북/충청 지역 소부장 기업 보도 보강
    "https://news.google.com/rss/search?q=site:dynews.co.kr+(반도체+OR+소부장+OR+글로벌기업+OR+충북기업)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=site:dynews.co.kr+(심텍+OR+하나머티리얼즈+OR+솔브레인+OR+티엘비+OR+이엔에프테크놀로지+OR+후성)+when:30d&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=Ebara+(semiconductor+OR+CMP+OR+pump)+when:30d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Entegris+(semiconductor+OR+materials)+when:30d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Lasertec+(semiconductor+OR+EUV+OR+mask)+when:30d&hl=en-US&gl=US&ceid=US:en",
]

# 회사별 DART 고유번호 (CORPCODE.xml 대조 완료, 64개사)
DART_CORP_CODES = {
    # 1그룹
    "AP시스템": "01203808",
    "국제엘렉트릭코리아": "00218052",
    "글로벌스탠다드테크놀로지": "00540863",
    "버슘머트리얼즈한양기공": "00162285",
    "신성이엔지": "00136271",
    "에드워드코리아": "00203874",
    "에스티아이": "00298340",
    "에이에스엠케이": "00361637",
    "엘오티베큠": "00484682",
    "원익IPS": "01135941",
    "유니셈": "00260569",
    "유진테크": "00531014",
    "케이씨": "00209780",
    "테스": "00524421",
    "테키스트": "00625401",
    "피에스케이": "01365825",
    "한국알박": "00361646",
    "한양이엔지": "00216762",
    # 2그룹
    "금강쿼츠": "00321578",
    "뉴파워프라즈마": "00521390",
    "디아이": "00118275",
    "새솔다이아몬드공업": "00486653",
    "신한다이아몬드공업": "00137447",
    "싸이노스": "00597454",
    "아드반테스트코리아": "00260426",
    "엠이케이": "00892304",
    "영신쿼츠": "00140894",
    "예스티": "00530556",
    "와이씨": "01109539",
    "원익큐엔씨": "00468374",
    "이오테크닉스": "00246417",
    "제이티": "00365457",
    "코리아인스트루먼트": "00410623",
    "코미코": "00997812",
    "코세스": "00365934",
    "티에스이": "00372226",
    "프로텍": "00325112",
    "피엠티": "00654175",
    "하나머티리얼즈": "00660750",
    # 3그룹
    "대덕전자": "01478712",
    "동우화인켐": "00178897",
    "동진쎄미켐": "00118804",
    "디엔에프": "00569691",
    "린데코리아": "00144261",
    "머크퍼포먼스머티리얼즈": "00453965",
    "삼영순화": "00180740",
    "솔브레인": "01489648",
    "신성전자정밀": "00210360",
    "심텍": "01095722",
    "아데카코리아": "00203111",
    "에어프로덕츠코리아": "01177381",
    "에프에스티": "00223434",
    "엔씨케이": "00423210",
    "엠이엠씨코리아": "00155221",
    "엠케이전자": "00121686",
    "원익머트리얼즈": "00623661",
    "이엔에프테크놀로지": "00530185",
    "케이씨텍": "01261893",
    "코스탯아이앤씨": "00184773",
    "티엘비": "00920379",
    "티오케이첨단재료": "00965187",
    "한솔케미칼": "00140955",
    "해성디에스": "01032413",
    "후성": "00595191",
}

TARGET_GROUPS = [
    {"group_id": 1, "group_name": "1그룹 (장비/설비/인프라)", "companies": ["AP시스템", "국제엘렉트릭코리아", "글로벌스탠다드테크놀로지", "버슘머트리얼즈한양기공", "신성이엔지", "에드워드코리아", "에스티아이", "에이에스엠케이", "엘오티베큠", "원익IPS", "유니셈", "유진테크", "케이씨", "테스", "테키스트", "피에스케이", "한국알박", "한양이엔지"]},
    {"group_id": 2, "group_name": "2그룹 (부품/테스트/소모품)", "companies": ["금강쿼츠", "뉴파워프라즈마", "디아이", "새솔다이아몬드공업", "신한다이아몬드공업", "싸이노스", "아드반테스트코리아", "엠이케이", "영신쿼츠", "예스티", "와이씨", "원익큐엔씨", "이오테크닉스", "제이티", "코리아인스트루먼트", "코미코", "코세스", "티에스이", "프로텍", "피엠티", "하나머티리얼즈"]},
    {"group_id": 3, "group_name": "3그룹 (소재/기판/화학)", "companies": ["대덕전자", "동우화인켐", "동진쎄미켐", "디엔에프", "린데코리아", "머크퍼포먼스머티리얼즈", "삼영순화", "솔브레인", "신성전자정밀", "심텍", "아데카코리아", "에어프로덕츠코리아", "에프에스티", "엔씨케이", "엠이엠씨코리아", "엠케이전자", "원익머트리얼즈", "이엔에프테크놀로지", "케이씨텍", "코스탯아이앤씨", "티엘비", "티오케이첨단재료", "한솔케미칼", "해성디에스", "후성"]},
    {"group_id": 4, "group_name": "4그룹 (글로벌 핵심 장비/소재)", "companies": ["ASML", "어플라이드머티어리얼즈", "램리서치", "도쿄일렉트론", "KLA", "에바라", "인테그리스", "이비덴", "레이저텍"]},
]

# 표시용 회사명 약칭 (표 셀 줄바꿈 방지). 내부 키는 풀네임 그대로 사용.
COMPANY_DISPLAY_NAME = {
    "국제엘렉트릭코리아": "국제엘렉트릭",
    "글로벌스탠다드테크놀로지": "GST",
    "버슘머트리얼즈한양기공": "버슘머트리얼즈",
    "새솔다이아몬드공업": "새솔다이아몬드",
    "신한다이아몬드공업": "신한다이아몬드",
    "아드반테스트코리아": "아드반테스트",
    "코리아인스트루먼트": "코리아인스트루먼트",
    "머크퍼포먼스머티리얼즈": "머크퍼포먼스",
    "에어프로덕츠코리아": "에어프로덕츠",
    "이엔에프테크놀로지": "이엔에프테크",
    "코스탯아이앤씨": "코스탯",
    "티오케이첨단재료": "TOK첨단재료",
    "어플라이드머티어리얼즈": "어플라이드",
    "도쿄일렉트론": "TEL",
}

HARD_BLACK_TITLES = ["김보라 시장, 첨단 반도체 소부장 기업 ㈜이오테크닉스 방문"]

# 기사·공시 분류 (위에서부터 먼저 맞는 것). DART 공시 제목(보고서명)에도 같은 규칙을 쓴다.
NEWS_CATEGORIES = [
    ("사업재편", re.compile(r"인수|합병|분사|매각|사업\s*재편|구조\s*조정|M&A|지분\s*(양도|양수|인수|매각)|영업\s*양[수도]|물적\s*분할|타법인|출자|최대\s*주주.{0,20}변경|acqui|merger|divest", re.I)),
    ("지분변동", re.compile(r"대량\s*보유|소유\s*상황|소유\s*주식|보유\s*비율|지분율|지분\s*[\d.]+\s*%|최대\s*주주\s*등\s*소유")),
    ("수주·협력", re.compile(r"공급\s*계약|수주|납품|단일\s*판매|계약\s*체결|출하|공급\s*확대|억\S*\s.{0,30}공급|MOU|협약|협력|제휴|파트너십|contract|order|partnership", re.I)),
    ("자금조달", re.compile(r"유상\s*증자|무상\s*증자|전환\s*사채|교환\s*사채|신주\s*인수권|전환\s*청구|교환\s*청구|자기\s*주식|자사주|\bCB\b|\bBW\b|신주|주식\s*소각|배당|외자\s*유치")),
    ("실적", re.compile(r"실적|매출|영업\s*이익|영업익|순이익|이익|흑자|적자|수익성|영업\s*현금|잉여\s*현금|가이던스|어닝|분기\s*보고서|반기\s*보고서|사업\s*보고서|감사\s*보고서|손익\s*구조|기업\s*설명회|\bIR\b|results|revenue|earnings|quarter", re.I)),
    ("투자·증설", re.compile(r"투자|증설|공장|CAPEX|생산|거점|착공|준공|캐파|신규\s*시설|유형\s*자산|invest|expan|plant|facility|fab\b", re.I)),
    ("분쟁·소송", re.compile(r"소송|분쟁|특허\s*침해|제소|판결|패소|승소|lawsuit|litigation", re.I)),
    ("기술·제품", re.compile(r"기술\s*개발|신기술|세계\s*최초|국산화|특허|양산|신제품|출시|개발|R&D|연구|공개|선보|전시|참가|박람회|솔루션|플랫폼|launch|unveil|develop", re.I)),
    ("경영·인사", re.compile(r"대표\s*이사|CEO|이사회|사외\s*이사|경영진|지배\s*구조|주주\s*총회|취임|선임|인사|임원")),
    ("시장·전망", re.compile(r"전망|수요|시장|성장|전략|업황|호황|가격|인상|인하|점유율")),
    ("행사·방문", re.compile(r"박람회|세미나|포럼|컨퍼런스|간담회|방문|개막|전시회|SEDEX|워크숍|설명회\s*개최|페스티벌")),
    ("ESG·사회", re.compile(r"기탁|나눔|취약계층|전달식|맞손|탄소\s*중립|ESG|RE100|친환경|재활용|자원\s*순환|사회\s*공헌|수상|봉사|기부|후원|어워즈|컴플라이언스|가족")),
]

# 기사 중요도 가중치 (순위·주요 소식 선정용). 지분변동은 정기 소유보고·국민연금 지분 변동 같은 반복성 소식이라 뒤로 미룬다.
CATEGORY_WEIGHT = {
    "수주·협력": 5, "사업재편": 5, "실적": 4, "투자·증설": 4, "기술·제품": 4,
    "자금조달": 3, "분쟁·소송": 3, "경영·인사": 2, "시장·전망": 2, "공시": 2,
    "ESG·사회": 1, "행사·방문": 1, "기타동향": 1, "지분변동": -3,
}
# 비중이 낮은 분류는 회사당 1건만 보여 준다 (중요 소식이 있으면 그 자리를 양보)
LOW_VALUE_CATEGORIES = {"기타동향", "행사·방문", "ESG·사회"}
# 분석·전망성 기사 표현 (소식이라기보다 의견이라 순위를 낮춘다)
OPINION_RE = re.compile(r"주목|관건|가능성|기대감|전망이다|수혜|전략|분석|리포트|칼럼|인터뷰")
ROUTINE_CATEGORY = "지분변동"
HIGHLIGHT_MIN_WEIGHT = 4  # 이 이상인 분류만 '이번 주 주요 소식' 후보
HIGHLIGHT_COUNT = 6
FRESH_DAYS = 7  # 주간 발송: 최근 7일을 '이번 주 소식'으로 보고, 그 이전은 '지난 소식'으로 분리

COMPANY_ALIAS_RAW = {
    "AP시스템": ["AP시스템", "AP Systems"], "국제엘렉트릭코리아": ["국제엘렉트릭코리아", "국제엘렉트릭"], "글로벌스탠다드테크놀로지": ["글로벌스탠다드테크놀로지", "GST"],
    "버슘머트리얼즈한양기공": ["버슘머트리얼즈한양기공", "버슘머트리얼즈", "한양기공", "Versum"], "신성이엔지": ["신성이엔지"], "에드워드코리아": ["에드워드코리아", "Edwards Korea"],
    "에스티아이": ["에스티아이"], "에이에스엠케이": ["에이에스엠케이", "ASMK", "ASM코리아", "ASM in Korea", "ASM Korea"], "엘오티베큠": ["엘오티베큠", "LOT Vacuum"],
    "원익IPS": ["원익IPS", "원익아이피에스"], "유니셈": ["유니셈", "Unisem"], "유진테크": ["유진테크"], "케이씨": ["케이씨", "KC"], "테스": ["테스", "TESR"],
    "테키스트": ["테키스트", "Techist"], "피에스케이": ["피에스케이", "PSK"], "한국알박": ["한국알박", "ULVAC Korea"], "한양이엔지": ["한양이엔지", "Hanyang ENG"],
    "금강쿼츠": ["금강쿼츠"], "뉴파워프라즈마": ["뉴파워프라즈마"], "디아이": ["디아이", "DI"], "새솔다이아몬드공업": ["새솔다이아몬드공업", "새솔다이아몬드"],
    "신한다이아몬드공업": ["신한다이아몬드공업", "신한다이아몬드"], "싸이노스": ["싸이노스", "Cyanos"], "아드반테스트코리아": ["아드반테스트코리아", "아드반테스트", "Advantest"],
    "엠이케이": ["엠이케이", "MEK"], "영신쿼츠": ["영신쿼츠"], "예스티": ["예스티", "YEST"], "와이씨": ["와이씨", "YC", "와이아이케이"],
    "원익큐엔씨": ["원익큐엔씨", "원익QnC"], "이오테크닉스": ["이오테크닉스"], "제이티": ["제이티", "JT"], "코리아인스트루먼트": ["코리아인스트루먼트", "Korea Instrument"],
    "코미코": ["코미코", "KoMiCo"], "코세스": ["코세스", "KOSES"], "티에스이": ["티에스이", "TSE"], "프로텍": ["프로텍", "Protec"], "피엠티": ["피엠티", "PMT"],
    "하나머티리얼즈": ["하나머티리얼즈"], "대덕전자": ["대덕전자"], "동우화인켐": ["동우화인켐"], "동진쎄미켐": ["동진쎄미켐", "동진세미켐"], "디엔에프": ["디엔에프"],
    "린데코리아": ["린데코리아", "Linde Korea"], "머크퍼포먼스머티리얼즈": ["머크퍼포먼스머티리얼즈", "머크 퍼포먼스", "Merck"], "삼영순화": ["삼영순화"],
    "솔브레인": ["솔브레인", "Soulbrain"], "신성전자정밀": ["신성전자정밀"], "심텍": ["심텍", "Simtech"], "아데카코리아": ["아데카코리아", "ADEKA Korea"],
    "에어프로덕츠코리아": ["에어프로덕츠코리아", "Air Products"], "에프에스티": ["에프에스티", "FST"], "엔씨케이": ["엔씨케이", "NCK"], "엠이엠씨코리아": ["엠이엠씨코리아", "MEMC"],
    "엠케이전자": ["엠케이전자", "MK전자"], "원익머트리얼즈": ["원익머트리얼즈"], "이엔에프테크놀로지": ["이엔에프테크놀로지"], "케이씨텍": ["케이씨텍", "KC Tech"],
    "코스탯아이앤씨": ["코스탯아이앤씨", "코스탯"], "티엘비": ["티엘비"], "티오케이첨단재료": ["티오케이첨단재료", "TOK첨단재료"], "한솔케미칼": ["한솔케미칼"],
    "해성디에스": ["해성디에스", "해성DS"], "후성": ["후성", "Foosung"],
    "ASML": ["ASML", "에이에스엠엘"], "어플라이드머티어리얼즈": ["어플라이드머티어리얼즈", "어플라이드 머티어리얼즈", "AMAT", "Applied Materials"],
    "램리서치": ["램리서치", "Lam Research"], "도쿄일렉트론": ["도쿄일렉트론", "TEL", "Tokyo Electron"], "KLA": ["KLA", "케이엘에이"],
    "에바라": ["에바라", "Ebara", "에바라제작소", "에바라 제작소", "에바라펌프", "에바라정밀"], "인테그리스": ["인테그리스", "엔테그리스", "Entegris"], "이비덴": ["이비덴", "Ibiden"], "레이저텍": ["레이저텍", "레이저테크", "Lasertec"],
}

EXTRA_GROUP_NAMES = {"A": "A그룹", "B": "B그룹", "C": "C그룹", "D": "D그룹", "E": "E그룹"}


def _name_key(name: str) -> str:
    """'코리아'·'한국' 표기 차이를 무시한 비교용 키 (어플라이드머티어리얼즈코리아 = 어플라이드머티어리얼즈)"""
    return name.lower().replace("코리아", "").replace("한국", "").replace(" ", "")


def build_extra_groups():
    """추가 A~E그룹 구성 → (groups, 제외 내역). 기존 73개사와 중복되거나 이름이 모호한 회사는 뺀다."""
    existing = {}
    for company in [c for g in TARGET_GROUPS for c in g["companies"]]:
        for alias in [company, *COMPANY_ALIAS_RAW.get(company, [])]:
            existing[_name_key(alias)] = company
    groups, skipped = [], {"기존 중복": [], "이름 모호": []}
    seen = set()
    for n, (letter, raw) in enumerate(EXTRA_RAW.items(), start=5):
        companies = []
        for name in (x.strip() for x in raw.split(",")):
            key = _name_key(name)
            if name in EXTRA_DUP_OF or key in existing or key in seen:
                skipped["기존 중복"].append(name)
            elif name in EXTRA_AMBIGUOUS or len(name) <= 2:
                skipped["이름 모호"].append(name)
            else:
                seen.add(key)
                companies.append(name)
        groups.append({"group_id": n, "group_name": f"{EXTRA_GROUP_NAMES[letter]} (추가 {len(companies)}개사)", "companies": companies, "compact": True})
    return groups, skipped


EXTRA_GROUPS, EXTRA_SKIPPED = build_extra_groups()
for _g in EXTRA_GROUPS:
    for _c in _g["companies"]:
        COMPANY_ALIAS_RAW.setdefault(_c, [_c])
TARGET_GROUPS = TARGET_GROUPS + EXTRA_GROUPS
LEGACY_COMPANIES = [c for g in TARGET_GROUPS if not g.get("compact") for c in g["companies"]]

# 4그룹 해외 9개사 티커 (DART 데이터 없음)
FOREIGN_TICKERS = {
    "ASML": "ASML",
    "어플라이드머티어리얼즈": "AMAT",
    "램리서치": "LRCX",
    "도쿄일렉트론": "8035.T",
    "KLA": "KLAC",
    "에바라": "6361.T",
    "인테그리스": "ENTG",
    "이비덴": "4062.T",
    "레이저텍": "6920.T",
}

# 국내 상장 39개사 야후 파이낸스 티커 (.KS=유가증권, .KQ=코스닥)
STOCK_TICKERS = {
    "AP시스템": "265520.KQ", "글로벌스탠다드테크놀로지": "083450.KQ", "신성이엔지": "011930.KS",
    "에스티아이": "039440.KQ", "엘오티베큠": "083310.KQ", "원익IPS": "240810.KQ", "유니셈": "036200.KQ",
    "유진테크": "084370.KQ", "케이씨": "029460.KS", "테스": "095610.KQ", "피에스케이": "319660.KQ", "한양이엔지": "045100.KQ",
    "뉴파워프라즈마": "144960.KQ", "디아이": "003160.KS", "예스티": "122640.KQ", "와이씨": "232140.KQ",
    "원익큐엔씨": "074600.KQ", "이오테크닉스": "039030.KQ", "제이티": "089790.KQ", "코미코": "183300.KQ",
    "코세스": "089890.KQ", "티에스이": "131290.KQ", "프로텍": "053610.KQ", "피엠티": "147760.KQ", "하나머티리얼즈": "166090.KQ",
    "대덕전자": "353200.KS", "동진쎄미켐": "005290.KQ", "디엔에프": "092070.KQ", "솔브레인": "357780.KQ",
    "심텍": "222800.KQ", "에프에스티": "036810.KQ", "엠케이전자": "033160.KQ", "원익머트리얼즈": "104830.KQ",
    "이엔에프테크놀로지": "102710.KQ", "케이씨텍": "281820.KS", "티엘비": "356860.KQ", "한솔케미칼": "014680.KS",
    "해성디에스": "195870.KS", "후성": "093370.KS",
}


def get_display_name(company: str) -> str:
    return COMPANY_DISPLAY_NAME.get(company, company)


def all_company_names() -> list:
    return [c for g in TARGET_GROUPS for c in g["companies"]]
