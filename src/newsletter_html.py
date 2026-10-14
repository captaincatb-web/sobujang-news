from datetime import datetime, timedelta
from html import escape

from src.newsletter_config import FRESH_DAYS, get_display_name
from src.newsletter_rank import age_days

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


def _article(article: dict, now: datetime, show_sim: bool = True) -> str:
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


def _header(now: datetime, stats: dict) -> str:
    start = now - timedelta(days=FRESH_DAYS)
    return (
        f'<h2 style="margin:0 0 4px">📬 소부장 파트너사 주간 동향</h2>'
        f'<div style="font-size:12px;color:#6b7684;margin-bottom:12px">'
        f'{now.year}.{now.month:02d}.{now.day:02d}({WEEKDAYS[now.weekday()]}) 발행 · '
        f"수집 기간 {start.month}/{start.day} ~ {now.month}/{now.day} · "
        f'이번 주 새 소식 <b>{stats["fresh_news"]}건</b> (공시 {stats["fresh_dart"]}건) · '
        f'소식 있는 회사 {stats["fresh_companies"]}/{stats["total_companies"]}곳</div>'
    )


def _highlights(highlights: list) -> str:
    if not highlights:
        return ""
    rows = []
    for company, a in highlights:
        rows.append(
            f'<div style="margin:0 0 7px">{_badge(a)} <b>{get_display_name(company)}</b> · '
            f'<a href="{escape(a["link"])}" style="color:#191f28;text-decoration:none">{escape(a["title"])}</a> '
            f'<span style="{META}">{_meta(a)}</span></div>'
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


def build_newsletter_html(
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
) -> str:
    cols = 3 if show_fin else 2
    out = ['<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1000px;color:#191f28">']
    out.append(_header(now, stats))
    out.append(_highlights(highlights))
    out.append(_movers(*movers))
    out.append(
        f'<div style="{META};margin-bottom:4px">제목 색: <b style="color:#f04452">빨강</b> 24시간 이내 · '
        '<b style="color:#3182f6">파랑</b> 최근 7일 · <b style="color:#8b95a1">회색</b> 지난 소식(8~30일) · <span style="white-space:nowrap">📄지분 = 지분·소유 변동 공시 건수</span></div>'
    )

    for group in groups:
        out.append(
            f'<h3 style="margin:22px 0 8px;font-size:15px;border-left:4px solid #3182f6;padding-left:8px">{group["group_name"]}</h3>'
        )
        out.append(TABLE)
        out.append(
            '<tr bgcolor="#f2f4f6" style="color:#4e5968"><th width="19%" style="white-space:nowrap">회사·주가</th>'
            + ('<th width="16%">최근분기 재무</th>' if show_fin else "")
            + "<th>이번 주 소식</th></tr>"
        )

        older_rows, quiet = [], []
        alt = False
        for company in group["companies"]:
            sel = selections.get(company) or {"shown": [], "routine": [], "older": None}
            lead_fin = f'<td valign="top" style="font-size:11px">{fin_cells[company]}</td>' if show_fin else ""
            if sel["shown"]:
                alt = not alt
                bg = "#f8f9fa" if alt else "#ffffff"
                news = "".join(_article(a, now) for a in sel["shown"]) + _routine_line(sel["routine"])
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
    out.append("</div>")
    return "".join(out)
