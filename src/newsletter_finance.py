import html as html_lib
import json
import math
from datetime import datetime

import requests

from src import stock_data
from src.history import KST
from src.newsletter_config import (
    CACHE_PATH,
    DART_CORP_CODES,
    FALLBACK_DEPTH,
    FOREIGN_TICKERS,
    STOCK_TICKERS,
)

REQUEST_TIMEOUT = 15
DART_ACCOUNT_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SMALL_GRAY = '<span style="color:#b0b8c1">'


# ------------------------------------------------------------
#  캐시 (GAS의 PropertiesService 대체: data/newsletter_cache.json)
# ------------------------------------------------------------
class Cache:
    def __init__(self):
        self.data = {}
        if CACHE_PATH.exists():
            try:
                self.data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


# ------------------------------------------------------------
#  분기 계산 (reprt_code: 11013=1Q, 11012=반기, 11014=3Q, 11011=사업보고서)
# ------------------------------------------------------------
def get_latest_quarter(now: datetime) -> dict:
    y, m = now.year, now.month
    latest = None
    for reprt, q, avail_month in (("11013", 1, 5), ("11012", 2, 8), ("11014", 3, 11), ("11011", 4, 99)):
        if avail_month <= m:
            latest = {"year": y, "reprt": reprt, "q": q}
    if not latest:
        latest = {"year": y - 1, "reprt": "11011", "q": 4} if m >= 4 else {"year": y - 1, "reprt": "11014", "q": 3}
    return latest


def get_prev_quarter(qtr: dict) -> dict:
    if qtr["q"] == 1:
        return {"year": qtr["year"] - 1, "reprt": "11011", "q": 4}
    reprt = {2: "11013", 3: "11012", 4: "11014"}[qtr["q"]]
    return {"year": qtr["year"], "reprt": reprt, "q": qtr["q"] - 1}


def get_yoy_quarter(qtr: dict) -> dict:
    return {"year": qtr["year"] - 1, "reprt": qtr["reprt"], "q": qtr["q"]}


# ------------------------------------------------------------
#  OpenDART 조회
# ------------------------------------------------------------
def fetch_latest_audit_report_rcp_no(corp_code: str, api_key: str, cache: Cache):
    """비상장 외감법인: 최근 2년 공시 중 '감사보고서' 최신 접수번호 (6개월 캐시)"""
    key = "AUDIT_" + corp_code
    cached = cache.get(key)
    now = datetime.now(KST)
    if cached:
        try:
            if (now - datetime.fromisoformat(cached["date"])).days < 180:
                return cached["rcp_no"]
        except (KeyError, ValueError, TypeError):
            pass

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": f"{now.year - 2}0101",
        "end_de": now.strftime("%Y%m%d"),
        "page_count": 100,
    }
    result = None
    try:
        res = requests.get(DART_LIST_URL, params=params, timeout=REQUEST_TIMEOUT).json()
        if res.get("status") == "000":
            audits = [r for r in res.get("list", []) if "감사보고서" in (r.get("report_nm") or "")]
            if audits:
                audits.sort(key=lambda r: r["rcept_dt"], reverse=True)
                result = audits[0]["rcept_no"]
    except (requests.RequestException, ValueError):
        return None

    cache.set(key, {"rcp_no": result, "date": now.isoformat()})
    return result


def fetch_account_one(corp_code: str, qtr: dict, api_key: str, cache: Cache, is_latest: bool = False):
    """단일회사 주요계정 → {div, rev, op, qtr} or None (확정 분기는 캐시)"""
    key = f"FIN_{qtr['year']}_{qtr['reprt']}_{corp_code}"
    cached = cache.get(key)
    if cached is not None:
        if cached == "NULL":
            return None
        return {**cached, "qtr": qtr}

    params = {"crtfc_key": api_key, "corp_code": corp_code, "bsns_year": qtr["year"], "reprt_code": qtr["reprt"]}
    result = None
    try:
        res = requests.get(DART_ACCOUNT_URL, params=params, timeout=REQUEST_TIMEOUT).json()
    except (requests.RequestException, ValueError):
        return None  # 네트워크 오류는 캐싱하지 않음

    if res.get("status") == "000" and res.get("list"):
        for div in ("OFS", "CFS"):  # 별도 우선, 없으면 연결
            rows = [r for r in res["list"] if r.get("fs_div") == div]
            rev = next((r for r in rows if r.get("account_nm") == "매출액"), None)
            op = next((r for r in rows if r.get("account_nm") == "영업이익"), None)
            if rev or op:
                slim = lambda r: {k: r.get(k) for k in ("thstrm_amount", "rcept_no")} if r else None
                result = {"div": "연결" if div == "CFS" else "별도", "rev": slim(rev), "op": slim(op)}
                break

    # 최신분기의 '데이터 없음'은 아직 미공시일 수 있어 캐싱하지 않음
    if result:
        cache.set(key, result)
        return {**result, "qtr": qtr}
    if not is_latest:
        cache.set(key, "NULL")
    return None


def fetch_account_with_fallback(corp_code: str, start_qtr: dict, api_key: str, cache: Cache):
    qtr = start_qtr
    for i in range(FALLBACK_DEPTH + 1):
        result = fetch_account_one(corp_code, qtr, api_key, cache, is_latest=(i == 0))
        if result:
            return result
        qtr = get_prev_quarter(qtr)
    return None


# ------------------------------------------------------------
#  숫자 포맷
# ------------------------------------------------------------
def js_round(x: float) -> int:
    return math.floor(x + 0.5)


def to_eok_won(row):
    if not row or not row.get("thstrm_amount"):
        return None
    try:
        n = float(str(row["thstrm_amount"]).replace(",", ""))
    except ValueError:
        return None
    return js_round(n / 100000000)


def pct_change(curr, prev):
    if curr is None or prev is None or prev == 0:
        return None
    return js_round(((curr - prev) / abs(prev)) * 1000) / 10


def _num(n) -> str:
    # 12.0 → "12", 12.5 → "12.5" (JS 숫자 출력과 동일하게)
    return str(int(n)) if float(n).is_integer() else str(n)


def format_pct(p) -> str:
    if p is None:
        return "-"
    return ("+" if p > 0 else "") + _num(p) + "%"


def op_comment(curr, prev, label: str) -> str:
    if curr is None or prev is None:
        return ""
    if prev < 0 <= curr:
        return label + " 흑자전환"
    if prev >= 0 > curr:
        return label + " 적자전환"
    if prev < 0 and curr < 0:
        return label + " 적자지속(" + format_pct(pct_change(curr, prev)) + ")"
    return label + " " + format_pct(pct_change(curr, prev))


def _fmt_amount(value: float, max_decimals: int) -> str:
    s = f"{value:,.{max_decimals}f}"
    if max_decimals:
        s = s.rstrip("0").rstrip(".")
    return s


# ------------------------------------------------------------
#  종가 셀
# ------------------------------------------------------------
def _currency(ticker: str) -> str:
    if ticker.endswith((".KS", ".KQ")):
        return "KRW"
    if ticker.endswith(".T"):
        return "JPY"
    return "USD"


def _quote_for(company: str):
    ticker = STOCK_TICKERS.get(company) or FOREIGN_TICKERS.get(company)
    if not ticker:
        return None, None
    if ticker not in _QUOTE_CACHE:
        _QUOTE_CACHE[ticker] = stock_data.get_quote(ticker)
    return ticker, _QUOTE_CACHE[ticker]


_QUOTE_CACHE = {}


def _pct_html(pct) -> str:
    if pct is None:
        return '<font color="#b0b8c1">-</font>'
    color = "#f04452" if pct > 0 else ("#3182f6" if pct < 0 else "#8b95a1")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "")
    return f'<font color="{color}">{arrow}{abs(pct):.1f}%</font>'


def build_price_short(company: str) -> str:
    """뉴스 없는 회사 요약줄용 1주 등락 (예: 1주 ▲3.6%)"""
    _, quote = _quote_for(company)
    if not quote or quote.get("week_change_pct") is None:
        return ""
    return f'<span style="font-size:11px;color:#8b95a1">1주 </span>{_pct_html(quote["week_change_pct"])}'


def build_price_cell(company: str) -> str:
    """회사 칸에 붙는 종가 + 전일·1주 등락률 (클릭 시 시세 페이지)"""
    domestic = STOCK_TICKERS.get(company)
    ticker, quote = _quote_for(company)
    if not quote:
        return '<span style="color:#b0b8c1;font-size:11px">비상장</span>'

    currency = _currency(ticker)
    price = _fmt_amount(quote["price"], 0 if currency == "KRW" else 2)
    price_text = price + "원" if currency == "KRW" else ("$" if currency == "USD" else "¥") + price
    if domestic:
        detail_url = "https://finance.naver.com/item/main.naver?code=" + domestic.split(".")[0]
    else:
        detail_url = "https://finance.yahoo.com/quote/" + ticker
    day = _pct_html(quote["change_pct"]) if quote.get("prev_close") else _pct_html(None)
    week = _pct_html(quote.get("week_change_pct"))
    # 좁은 화면에서도 "1주 ▼6.8%"가 중간에 끊기지 않도록 줄마다 nowrap
    nowrap = '<span style="white-space:nowrap"><font color="#8b95a1">'
    return (
        f'<div style="font-size:11px"><a href="{detail_url}" style="color:#191f28;text-decoration:none">{price_text}</a>'
        f"<br>{nowrap}1일</font> {day}</span><br>{nowrap}1주</font> {week}</span></div>"
    )


def weekly_movers(companies, top: int = 3) -> tuple:
    """1주 등락률 상위·하위 회사 → ([(회사, %)], [(회사, %)])"""
    changes = []
    for company in companies:
        _, quote = _quote_for(company)
        if quote and quote.get("week_change_pct") is not None:
            changes.append((company, quote["week_change_pct"]))
    changes.sort(key=lambda x: x[1], reverse=True)
    gainers = [c for c in changes if c[1] > 0][:top]
    losers = [c for c in reversed(changes) if c[1] < 0][:top]
    return gainers, losers


# ------------------------------------------------------------
#  Gemini AI 추정 분석 (분기 단위 캐시)
# ------------------------------------------------------------
def build_ai_analysis(company, rev, prev_rev, yoy_rev, op, prev_op, yoy_op, q_label, gemini_key, gemini_model, cache):
    if not gemini_key:
        return ""
    key = "AI_" + company + "_" + q_label.replace(" ", "")
    cached = cache.get(key)
    if cached:
        return cached

    rev_text = f"{rev:,}억원" if rev is not None else "데이터없음"
    op_text = f"{op:,}억원" if op is not None else "데이터없음"
    prompt = (
        f"다음은 반도체 소부장 기업 '{company}'의 {q_label} 실적이다.\n"
        f"매출액: {rev_text} (전분기 대비 {format_pct(pct_change(rev, prev_rev))}, 전년동기 대비 {format_pct(pct_change(rev, yoy_rev))})\n"
        f"영업이익: {op_text} (전분기 대비 {format_pct(pct_change(op, prev_op))}, 전년동기 대비 {format_pct(pct_change(op, yoy_op))})\n"
        "이 실적 변동의 가능한 원인을 반도체 산업 동향, 전방산업(메모리/파운드리) 업황, 계절성 등을 고려하여 한 문장(40자 이내)으로 간결하게 추정하라. "
        "확정적 표현(때문이다, ~했다) 대신 추정 표현(~로 추정, ~영향으로 보임)을 사용하라. 다른 설명 없이 문장만 출력하라."
    )
    try:
        res = requests.post(
            GEMINI_URL.format(model=gemini_model),
            params={"key": gemini_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        ).json()
        text = res["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return ""  # 실패는 캐싱하지 않고 다음 발송에서 재시도

    cache.set(key, text)
    return text


# ------------------------------------------------------------
#  재무 요약 셀
# ------------------------------------------------------------
def build_fin_summary(company, api_key, now, cache, gemini_key="", gemini_model=""):
    code = DART_CORP_CODES.get(company)
    if not code:
        ticker = FOREIGN_TICKERS.get(company)
        if ticker:
            url = f"https://finance.yahoo.com/quote/{ticker}/financials"
            return (
                f'<a href="{url}" style="color:#3182f6; text-decoration:none; font-size:11px;">재무정보 보기↗</a>'
                f"<br>{SMALL_GRAY}({ticker}, 해외상장)</span>"
            )
        return f"데이터없음<br>{SMALL_GRAY}(비상장)</span>"
    if not api_key:
        return '<span style="color:#b0b8c1">-</span>'

    latest = fetch_account_with_fallback(code, get_latest_quarter(now), api_key, cache)
    if not latest:
        # 사업보고서 미제출 비상장 외감법인 → 최근 감사보고서 링크
        rcp_no = fetch_latest_audit_report_rcp_no(code, api_key, cache)
        if rcp_no:
            return (
                f'<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}" '
                f'style="color:#3182f6; text-decoration:none; font-size:11px;">감사보고서 보기↗</a>'
                f"<br>{SMALL_GRAY}(사업보고서 미제출)</span>"
            )
        return f"데이터없음<br>{SMALL_GRAY}(사업보고서 미제출)</span>"

    qtr = latest["qtr"]
    prev = fetch_account_one(code, get_prev_quarter(qtr), api_key, cache)
    yoy = fetch_account_one(code, get_yoy_quarter(qtr), api_key, cache)

    rev, op = to_eok_won(latest["rev"]), to_eok_won(latest["op"])
    prev_rev = to_eok_won(prev["rev"]) if prev else None
    prev_op = to_eok_won(prev["op"]) if prev else None
    yoy_rev = to_eok_won(yoy["rev"]) if yoy else None
    yoy_op = to_eok_won(yoy["op"]) if yoy else None

    q_label = f"{qtr['year']}년 " + ("연간(사업보고서)" if qtr["q"] == 4 else f"{qtr['q']}Q")

    rcpt_no = (latest["rev"] or {}).get("rcept_no") or (latest["op"] or {}).get("rcept_no")
    q_label_html = (
        f'<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcpt_no}" style="color:#333d4b;text-decoration:none">{q_label} ↗</a>'
        if rcpt_no
        else q_label
    )

    html = '<div style="font-size:11px;line-height:1.5;text-align:left;">'
    html += f'<div style="font-weight:bold;color:#333d4b;margin-bottom:2px;">{q_label_html} ({latest["div"]})</div>'
    html += "<div>매출 " + (f"{rev:,}억" if rev is not None else "-") + "</div>"
    html += f'<div style="color:#8b95a1;">QoQ {format_pct(pct_change(rev, prev_rev))} · YoY {format_pct(pct_change(rev, yoy_rev))}</div>'
    html += '<div style="margin-top:3px">영업이익 ' + (f"{op:,}억" if op is not None else "-") + "</div>"
    op_qoq = op_comment(op, prev_op, "QoQ") or "QoQ -"
    op_yoy = op_comment(op, yoy_op, "YoY") or "YoY -"
    html += f'<div style="color:#8b95a1;">{op_qoq} · {op_yoy}</div>'

    ai = build_ai_analysis(company, rev, prev_rev, yoy_rev, op, prev_op, yoy_op, q_label, gemini_key, gemini_model, cache)
    if ai:
        html += (
            '<div style="margin-top:4px;padding-top:4px;border-top:1px dashed #d1d6db;color:#6b7684;font-size:10px;font-style:italic;">'
            f'💡 {html_lib.escape(ai)} <span style="color:#b0b8c1;">(AI 추정)</span></div>'
        )
    return html + "</div>"
