from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT_DIR / "data" / "sent_history.json"

# 폭넓게 훑는 키워드 검색
KEYWORDS = [
    "반도체 중소기업",
    "반도체 중견기업",
    "반도체 소부장",
    "반도체 장비업체",
    "반도체 부품업체",
]

# 대표적인 반도체 중견/중소 상장사 (필요에 따라 자유롭게 추가/삭제하세요)
COMPANIES = [
    "한미반도체",
    "이오테크닉스",
    "원익IPS",
    "유진테크",
    "피에스케이",
    "하나마이크론",
    "네패스",
    "DB하이텍",
    "솔브레인",
    "티씨케이",
    "원익QnC",
    "동진쎄미켐",
    "심텍",
    "이수페타시스",
    "하나머티리얼즈",
    "넥스틴",
    "파크시스템스",
    "리노공업",
    "ISC",
    "유니테스트",
]

SEARCH_QUERIES = KEYWORDS + COMPANIES

MAX_ARTICLES_PER_RUN = 10
HISTORY_MAX_DAYS = 30
KST_OFFSET_HOURS = 9
