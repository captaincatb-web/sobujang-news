import re
from datetime import datetime, timedelta
from html import escape

from src.newsletter_config import FRESH_DAYS, get_display_name
from src.newsletter_rank import age_days, score

# 메일 클라이언트가 <style> 블록을 무시하는 경우가 있어 인라인으로 작성하되, 한 통에 담을 수 있도록
# 표는 '회사 · 주가 | 소식' 2칸으로 단순화했다 (모바일에서도 제목이 한 줄에 더 많이 보인다).
WEEKDAYS = "월화수목금토일"
TABLE = (
    '<table border="1" cellspacing="0" cellpadding="7" width="100%" '
    'style="border-collapse:collapse;border-color:#e5e8eb;font-size:13px;margin-bottom:16px">'
)
BADGE = "font-size:10px;padding:1px 4px;white-space:nowrap"
META = "font-size:11px;color:#8b95a1"


def _title_color(age: float) -> str:
    return "#f04452" if age <= 1 else ("#3182f6" if age <= FRESH_DAYS else "#8b95a1")


def _badge(article: dict) -> str:
    if article["cat3"] == "공시자료":
        label = "공시" if article["cat2"] == "공시" else f"공시·{article['cat2']}"
        return f'<span style="{BADGE};background:#e8f3ff;color:#3182f6;border:1px solid #3182f6">{label}</span>'
    return f'<span style="{BADGE};background:#f2f4f6;color:#4e5968">{article["cat2"]}</span>'


def _meta(article: dict) -> str:
    sims = article["similar_articles"]
    more = f" 외 {len(sims)}건" if sims else ""
    return f'{escape(article["source"])}{more} · {article["date_str"]}'


def _article(article: dict, now: datetime, show_sim: bool = True, ref: bool = False) -> str:
    if ref:  # 위 '이번 주 주요 소식'에 이미 실린 기사는 같은 내용을 다시 풀어 쓰지 않는다
        short = article["title"] if len(article["title"]) <= 30 else article["title"][:28].rstrip() + "…"
        return f'<div style="margin:2px 0 7px">{_badge(article)} <span style="{META}">↑ 주요 소식에 게재 · {escape(short)}</span></div>'
    age = age_days(now, article)
    out = (
        f'<div style="margin:2px 0 7px">{_badge(article)} '
        f'<a href="{escape(article["link"])}" style="color:{_title_color(age)};text-decoration:none">'
        f'<b>{escape(article["title"])}</b></a><br><span style="{META}">{_meta(article)}</span>'
    )
    # 다른 매체·공시가 같은 소식을 어떻게 다뤘는지 한 줄 (같은 매체의 재송고는 생략, 긴 제목은 줄임)
    sim = next((s for s in article["similar_articles"] if s["source"] != article["source"]), None) if show_sim else None
    if sim:
        title = sim["title"] if len(sim["title"]) <= 42 else sim["title"][:40].rstrip() + "…"
        out += (
            f'<br><span style="{META}">↳ <a href="{escape(sim["link"])}" style="color:#6b7684;text-decoration:none">'
            f"{escape(title)}</a> · {escape(sim['source'])}</span>"
        )
    return out + "</div>"


def _routine_line(routine: list) -> str:
    """메일 칸을 차지하지 않도록 지분·소유 공시는 건수만 한 줄로"""
    if not routine:
        return ""
    newest = routine[0]
    return (
        f'<div style="{META}">📄 지분·소유 변동 {len(routine)}건 · '
        f'<a href="{escape(newest["link"])}" style="color:#8b95a1">{escape(newest["title"][:30])}</a></div>'
    )


def _routine_mark(routine: list) -> str:
    """새 소식 없음 목록에 붙는 지분·소유 공시 표시 (최신 공시로 연결)"""
    if not routine:
        return ""
    return f' <a href="{escape(routine[0]["link"])}" style="color:#8b95a1;font-size:11px">📄지분 {len(routine)}</a>'


def _name_html(company: str) -> str:
    disp = get_display_name(company)
    return f"<b>{company}</b>" if disp == company else f'<b title="{company}">{disp}</b>'


SITE_URL = "https://captaincatb-web.github.io/sobujang-news/"
AMOUNT_RE = re.compile(r"\d[\d,.]*\s*(?:조|억)?\s*(?:\d[\d,.]*\s*만)?\s*(?:원|달러|엔|위안)|\d[\d,.]*\s*(?:%|호기|대|건)")


def _delta(cur: int, prev) -> str:
    if prev is None or cur == prev:
        return ""
    color, arrow = ("#f04452", "▲") if cur > prev else ("#3182f6", "▼")
    return f' <span style="color:{color}">{arrow}{abs(cur - prev)}</span>'


def _header(now: datetime, stats: dict) -> str:
    start = now - timedelta(days=FRESH_DAYS)
    prev = stats.get("prev") or {}
    vs = ' <span style="color:#8b95a1">(지난주 대비)</span>' if prev else ""
    return (
        f'<h2 style="margin:0 0 4px">📬 소부장 파트너사 주간 동향</h2>'
        f'<div style="font-size:12px;color:#6b7684;margin-bottom:12px">'
        f'{now.year}.{now.month:02d}.{now.day:02d}({WEEKDAYS[now.weekday()]}) 발행 · '
        f"수집 기간 {start.month}/{start.day} ~ {now.month}/{now.day} · "
        f'1~4그룹 이번 주 새 소식 <b>{stats["fresh_news"]}건</b>{_delta(stats["fresh_news"], prev.get("fresh_news"))} '
        f'(공시 {stats["fresh_dart"]}건) · '
        f'소식 있는 회사 {stats["fresh_companies"]}/{stats["total_companies"]}곳'
        f'{_delta(stats["fresh_companies"], prev.get("fresh_companies"))}'
        f'{vs}'
        f' · <a href="{SITE_URL}" style="color:#3182f6">전체 주차 보기</a></div>'
        + _extra_line(stats)
    )


BIG_AMOUNT_RE = re.compile(r"\d[\d,.]*\s*(?:조|억)(?:\s*\d[\d,.]*\s*만)?\s*(?:원|달러|엔)?")
VERB_RULES = (("투자협약", "투자협약"), ("협약", "협약"), ("MOU", "MOU"), ("계약", "계약"), ("인수", "인수"), ("투자", "투자"), ("수주", "수주"), ("증설", "증설"), ("공급", "공급"))


def headline_phrase(company: str, article: dict) -> str:
    """'대덕전자 6150억 투자'처럼 제목에 실제로 있는 금액·행위만으로 만든 짧은 문구 (금액이 없으면 빈 문자열).
    분류가 아닌 제목 속 낱말을 써서 사실과 다른 표현이 들어가지 않게 한다."""
    m = BIG_AMOUNT_RE.search(article["title"])
    if not m:
        return ""
    amount = re.sub(r"(?<=[억조])원$", "", re.sub(r"\s+", "", m.group(0)))  # '6150억원'→'6150억', '56억7566만원'은 그대로
    verb = next((v for key, v in VERB_RULES if key in article["title"]), "")
    return " ".join(x for x in (get_display_name(company), amount, verb) if x)


def lead_phrases(highlights: list, n: int = 3) -> list:
    out, seen = [], set()
    for company, a in highlights:
        phrase = headline_phrase(company, a)
        if phrase and phrase not in seen:
            seen.add(phrase)
            out.append(phrase)
        if len(out) >= n:
            break
    return out


def _lead_line(highlights: list) -> str:
    phrases = lead_phrases(highlights)
    if not phrases:
        return ""
    return (
        '<div style="margin:0 0 6px;font-size:14px"><b>이번 주 핵심</b> · '
        + " · ".join(escape(p) for p in phrases)
        + f' <span style="{META}">(아래 주요 소식 참고)</span></div>'
        f'<div style="margin:0 0 12px;font-size:13px">👉 <a href="{SITE_URL}" style="color:#3182f6"><b>전체 주차·검색 보기</b></a>'
        f' <span style="{META}">내 거래처를 이름으로 바로 찾을 수 있습니다</span></div>'
    )


def _check_items(selections: dict, now: datetime, limit: int = 8) -> list:
    """이번 주 새 공시(지분·소유 변동 제외) → 확인이 필요한 항목"""
    seen, items = set(), []
    for company, sel in selections.items():
        for a in sel["shown"] + [m for x in sel["shown"] for m in x["similar_articles"]]:
            if a["cat3"] != "공시자료" or a["cat2"] == "지분변동" or age_days(now, a) > FRESH_DAYS or a["link"] in seen:
                continue
            seen.add(a["link"])
            items.append((a["pub_date"], company, a))
    items.sort(key=lambda x: x[0], reverse=True)
    return items[:limit], max(len(items) - limit, 0)


def _checklist(selections: dict, now: datetime, movers: tuple) -> str:
    """'먼저 확인할 것': 새 공시와 1주 주가 변동을 맨 위에 모은다 (사실만, 원인·전망은 쓰지 않는다)"""
    items, more = _check_items(selections, now)
    gainers, losers = movers
    if not items and not gainers and not losers:
        return ""
    rows = []
    for _, company, a in items:
        title = a["title"].split(" - ", 1)[1] if " - " in a["title"] else a["title"]
        note = " · 정정 내용은 공시 원문 확인" if "정정" in a["title"] else (" · 기준일은 공시 원문 확인" if "기준일" in a["title"] else "")
        rows.append(
            f'<div style="margin:0 0 4px">{_badge(a)} <b>{get_display_name(company)}</b> · '
            f'<a href="{escape(a["link"])}" style="color:#191f28;text-decoration:none">{escape(title)}</a> '
            f'<span style="{META}">DART · {a["date_str"]}{note}</span></div>'
        )
    if more:
        rows.append(f'<div style="{META}">그 밖의 공시 {more}건은 웹페이지에서 확인하세요.</div>')
    body = "".join(rows)
    if body:
        body = f'<div style="{META};margin:0 0 4px">공시 (이번 주)</div>' + body
    return (
        '<div style="border:1px solid #f0b9bd;border-radius:8px;padding:12px 14px;margin:0 0 12px;background:#fffafa">'
        '<div style="font-weight:bold;font-size:14px;margin-bottom:8px">📌 먼저 확인할 것</div>'
        + body
        + (f'<div style="{META};margin:8px 0 4px">1주 주가 변동 (사실만 표기, 원인은 원문 확인 필요)</div>' + _movers(gainers, losers) if gainers or losers else "")
        + "</div>"
    )


def _highlights(highlights: list) -> str:
    if not highlights:
        return ""
    rows = []
    for company, a in highlights:
        title = a["title"] if len(a["title"]) <= 42 else a["title"][:40].rstrip() + "…"
        amount = AMOUNT_RE.search(a["title"])
        chip = (
            f' <b style="color:#3182f6">{escape(amount.group(0).strip())}</b>'
            if amount and amount.group(0).strip() not in title
            else ""
        )
        rows.append(
            f'<div style="margin:0 0 7px">{_badge(a)} <b>{get_display_name(company)}</b> · '
            f'<a href="{escape(a["link"])}" title="{escape(a["title"])}" style="color:#191f28;text-decoration:none">{escape(title)}</a>'
            f'{chip} <span style="{META}">{_meta(a)}</span></div>'
        )
    return (
        '<div style="border:1px solid #d1d6db;border-radius:8px;padding:12px 14px;margin:0 0 12px;background:#fbfcfd">'
        '<div style="font-weight:bold;font-size:14px;margin-bottom:8px">⭐ 이번 주 주요 소식</div>' + "".join(rows) + "</div>"
    )


def _movers(gainers: list, losers: list) -> str:
    if not gainers and not losers:
        return ""

    def fmt(items, color, arrow):
        return " · ".join(
            f'<span style="white-space:nowrap">{get_display_name(c)} <span style="color:{color}">{arrow}{abs(p):.1f}%</span></span>'
            for c, p in items
        ) or "-"

    nowrap = 'style="white-space:nowrap"'
    return (
        '<div style="font-size:12px;margin:0 0 6px">'
        f'<b {nowrap}>📈 1주 상승</b> {fmt(gainers, "#f04452", "▲")} &nbsp;&nbsp; '
        f'<b {nowrap}>📉 1주 하락</b> {fmt(losers, "#3182f6", "▼")}</div>'
    )


def _extra_line(stats: dict) -> str:
    extra = stats.get("extra")
    if not extra:
        return ""
    return (
        f'<div style="font-size:12px;color:#6b7684;margin:-6px 0 12px">5그룹 {extra["total_companies"]}개사 · '
        f'소식 있는 회사 <b>{extra["fresh_companies"]}곳</b> (뉴스 전용, 재무·주가 제외)</div>'
    )


COMPACT_TABLE = (
    '<table border="1" cellspacing="0" cellpadding="6" width="100%" '
    'style="border-collapse:collapse;border-color:#e5e8eb;font-size:12px;margin-bottom:12px">'
)


def _compact_group(group: dict, selections: dict, now: datetime, title_len: int = 56, max_rows: int = 999) -> str:
    """추가 그룹: 최근 7일 뉴스가 확인된 회사만 '회사 | 헤드라인 | 언론사·날짜 | 분류' 한 줄씩, 나머지는 이름만"""
    rows, scored = [], []
    for company in group["companies"]:
        shown = (selections.get(company) or {"shown": []})["shown"]
        if not shown:
            continue
        a = shown[0]
        more = f" 외 {len(shown) - 1 + len(a['similar_articles'])}건" if len(shown) > 1 or a["similar_articles"] else ""
        # 한 통(Gmail 100KB 한도)에 담기 위해 행 마크업을 최소화한다 (스타일 대신 속성·font 태그)
        title = a["title"] if len(a["title"]) <= title_len else a["title"][: title_len - 2].rstrip() + "…"
        scored.append((score(a, now), get_display_name(company), a["pub_date"]))
        rows.append(
            f'<tr valign="top"><td><b>{get_display_name(company)}</b></td>'
            f'<td><a href="{escape(a["link"])}" style="color:{_title_color(age_days(now, a))};text-decoration:none">{escape(title)}</a></td>'
            f'<td><font color="#8b95a1" size="1">{escape(a["source"])}{more}<br>{a["date_str"]}</font></td>'
            f'<td><font color="#4e5968" size="1">{a["cat2"]}</font></td></tr>'
        )
    order = sorted(range(len(rows)), key=lambda i: scored[i][2], reverse=True)  # 최신 소식이 위로
    rows, scored = [rows[i] for i in order], [scored[i] for i in order]
    out = [f'<h3 style="margin:22px 0 8px;font-size:15px;border-left:4px solid #8b95a1;padding-left:8px">{group["group_name"]}</h3>']
    out.append(f'<div style="{META};margin:-4px 0 6px">소식이 확인된 {len(rows)}곳 · 최신 소식순</div>')
    overflow = []
    if len(rows) > max_rows:  # 한도 초과: 점수가 높은 회사의 행만 남기고 나머지는 이름만
        keep = set(sorted(range(len(rows)), key=lambda i: scored[i][0], reverse=True)[:max_rows])
        overflow = [scored[i][1] for i in range(len(rows)) if i not in keep]
        rows = [r for i, r in enumerate(rows) if i in keep]
    if rows:
        out.append(COMPACT_TABLE)
        out.append(
            '<tr bgcolor="#f2f4f6" style="color:#4e5968"><th width="15%">회사</th><th>헤드라인</th>'
            '<th width="17%">언론사·날짜</th><th width="9%">분류</th></tr>' + "".join(rows) + "</table>"
        )
    if overflow:
        out.append(
            f'<div style="color:#6b7684;line-height:1.8;font-size:11px;margin-bottom:6px">📰 <b>그 외 소식 있는 회사 ({len(overflow)}곳, 지면 제한으로 제목 생략)</b> · '
            + " · ".join(overflow) + "</div>"
        )
    return "".join(out)


def _notes(now: datetime) -> str:
    start = now - timedelta(days=FRESH_DAYS)
    return (
        f'<div style="{META};margin-top:14px;line-height:1.6;border-top:1px solid #e5e8eb;padding-top:8px">'
        f"비고 · 수집 기간 {start.month}/{start.day}~{now.month}/{now.day}(최근 7일). "
        "제외 규칙: 주가 등락 나열·목표주가/투자의견 단신, 동명 기업·인물·일반명사 오탐, 제목에 회사명이 없는 기사, 채용·스팸. "
        "이름이 흔해 오탐이 잦은 회사와 기존 1~4그룹과 중복된 회사는 5그룹에서 제외했습니다.</div>"
    )


def _build_html(
    *,
    now: datetime,
    groups: list,
    selections: dict,
    highlights: list,
    movers: tuple,
    stats: dict,
    fin_cells: dict,
    price_cells: dict,
    price_short: dict,
    show_fin: bool,
    compact_len: int = 56,
    max_rows: int = 999,
) -> str:
    cols = 3 if show_fin else 2
    hl_links = {a["link"] for _, a in highlights}
    out = ['<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1000px;color:#191f28">']
    out.append(_header(now, stats))
    out.append(_lead_line(highlights))
    out.append(_checklist(selections, now, movers))
    out.append(_highlights(highlights))
    out.append(
        f'<div style="{META};margin-bottom:4px">제목 색: <b style="color:#f04452">빨강</b> 24시간 이내 · '
        '<b style="color:#3182f6">파랑</b> 최근 7일 · <b style="color:#8b95a1">회색</b> 지난 소식(8~30일) · <span style="white-space:nowrap">📄지분 = 지분·소유 변동 공시 건수</span></div>'
    )

    for group in groups:
        if group.get("compact"):
            out.append(_compact_group(group, selections, now, compact_len, max_rows))
            continue
        def top_score(c):  # 새 소식이 있는 회사부터, 가장 중요한 기사 점수가 높은 순 (없는 회사는 원래 순서 유지)
            shown = (selections.get(c) or {"shown": []})["shown"]
            return -score(shown[0], now) if shown else 99

        ordered = sorted(group["companies"], key=top_score)
        n_news = sum(1 for c in ordered if (selections.get(c) or {"shown": []})["shown"])
        out.append(
            f'<h3 style="margin:22px 0 8px;font-size:15px;border-left:4px solid #3182f6;padding-left:8px">{group["group_name"]}</h3>'
        )
        out.append(f'<div style="{META};margin:-4px 0 6px">새 소식 {n_news}곳 · 중요도순</div>')
        out.append(TABLE)
        out.append(
            '<tr bgcolor="#f2f4f6" style="color:#4e5968"><th width="19%" style="white-space:nowrap">회사·주가</th>'
            + ('<th width="16%">최근분기 재무</th>' if show_fin else "")
            + "<th>이번 주 소식</th></tr>"
        )

        older_rows, quiet = [], []
        alt = False
        for company in ordered:
            sel = selections.get(company) or {"shown": [], "routine": [], "older": None}
            lead_fin = f'<td valign="top" style="font-size:11px">{fin_cells[company]}</td>' if show_fin else ""
            if sel["shown"]:
                alt = not alt
                bg = "#f8f9fa" if alt else "#ffffff"
                news = "".join(_article(a, now, ref=a["link"] in hl_links) for a in sel["shown"]) + _routine_line(sel["routine"])
                out.append(
                    f'<tr bgcolor="{bg}"><td valign="top" style="color:#333d4b;word-break:keep-all">{_name_html(company)}<br>{price_cells[company]}</td>'
                    f'{lead_fin}<td valign="top">{news}</td></tr>'
                )
            elif sel["older"]:
                older_rows.append(
                    f'<tr><td valign="top" style="color:#6b7684;word-break:keep-all">{_name_html(company)}<br>{price_cells[company]}</td>'
                    f'{lead_fin}<td valign="top">{_article(sel["older"], now, show_sim=False)}{_routine_line(sel["routine"])}</td></tr>'
                )
            else:
                item = f"{_name_html(company)} {price_short[company]}{_routine_mark(sel['routine'])}".strip()
                quiet.append(f'<span style="white-space:nowrap">{item}</span>')

        if older_rows:
            out.append(
                f'<tr><td colspan="{cols}" bgcolor="#fafafa" style="{META}"><b>지난 소식</b> · '
                "이번 주 새 소식이 없는 회사의 최근 기사 (8~30일 전)</td></tr>"
            )
            out.extend(older_rows)
        if quiet:
            out.append(
                f'<tr><td colspan="{cols}" style="color:#6b7684;line-height:1.8;font-size:12px">'
                f'📭 <b>새 소식 없음 ({len(quiet)}곳)</b> · ' + " · ".join(quiet) + "</td></tr>"
            )
        out.append("</table>")
    out.append(_notes(now))
    out.append("</div>")
    return "".join(out)


GMAIL_CLIP_BYTES = 98 * 1024  # Gmail은 약 102KB를 넘는 본문을 잘라 보여 준다


def build_newsletter_html(**kwargs) -> str:
    """추가 그룹의 헤드라인 길이를 줄여가며 Gmail 한도 안에 맞춘다 (끝까지 넘으면 그대로 반환, 호출 쪽에서 경고)"""
    html = ""
    for compact_len, max_rows in ((56, 999), (44, 999), (34, 999), (34, 90), (34, 60), (34, 40), (34, 25), (34, 12)):
        html = _build_html(**kwargs, compact_len=compact_len, max_rows=max_rows)
        if len(html.encode()) <= GMAIL_CLIP_BYTES:
            break
    return html
