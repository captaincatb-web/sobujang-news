import argparse
import json
import os
from datetime import datetime, timedelta

from src import gnews_decoder, site
from src.config import ROOT_DIR
from src.history import KST
from src.newsletter_ai import apply_ai_analysis
from src.newsletter_collector import BLOCKED_LINK_RE, FALSE_POSITIVE_CASES, collect_articles, group_similar, is_stale
from src.newsletter_config import LEGACY_COMPANIES, OUTPUT_DIR, TARGET_GROUPS, all_company_names
from src.newsletter_finance import Cache, build_fin_summary, build_price_cell, build_price_short, weekly_movers
from src.newsletter_html import build_newsletter_html
from src.newsletter_rank import FRESH_DAYS, age_days, candidate_articles, is_routine, pick_highlights, select_company


def build_subject(now: datetime) -> str:
    return f"📬 [뉴스레터] 핵심 소부장 파트너사 주간 동향 ({now.month}/{now.day})"


def main() -> None:
    parser = argparse.ArgumentParser(description="소부장 파트너사 동향 뉴스레터 (HTML 생성 전용, 메일은 보내지 않음)")
    parser.add_argument("--dry-run", action="store_true", help="이전 버전과의 호환용 (항상 HTML만 저장)")
    parser.parse_args()

    dart_key = os.environ.get("OPENDART_KEY", "")
    gemini_key = os.environ.get("GEMINI_KEY", "")
    gemini_model = os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"

    now = datetime.now(KST)
    grouped = group_similar(collect_articles())
    resolve_links(grouped, now)
    apply_ai_analysis(grouped, now)
    selections = {company: select_company(articles, now) for company, articles in grouped.items()}
    highlights = pick_highlights(selections, now)

    cache = Cache()
    companies = LEGACY_COMPANIES  # 재무·주가는 기존 73개사만 (5그룹은 뉴스 전용)
    fin_cells, price_cells, price_short = {}, {}, {}
    for company in companies:
        fin_cells[company] = build_fin_summary(company, dart_key, now, cache, gemini_key, gemini_model)
        price_cells[company] = build_price_cell(company)
        price_short[company] = build_price_short(company)
    cache.save()

    stats = build_stats(grouped, now, len(companies), companies)
    extra_names = [c for c in all_company_names() if c not in set(companies)]
    stats["extra"] = build_stats(grouped, now, len(extra_names), extra_names)
    stats["fp_cases"] = list(dict.fromkeys(FALSE_POSITIVE_CASES))
    stats["prev"] = load_prev_stats(now)
    save_stats(now, stats)
    html_body = build_newsletter_html(
        now=now,
        groups=TARGET_GROUPS,
        selections=selections,
        highlights=highlights,
        movers=weekly_movers(companies),
        stats=stats,
        fin_cells=fin_cells,
        price_cells=price_cells,
        price_short=price_short,
        show_fin=bool(dart_key),
    )
    subject = build_subject(now)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "newsletter.html"
    out_path.write_text(html_body, encoding="utf-8")
    (OUTPUT_DIR / "subject.txt").write_text(subject, encoding="utf-8")
    print(f"HTML 저장: {out_path} ({len(html_body.encode()) // 1024}KB) / 제목: {subject}")
    site.publish_week(now, html_body, stats, highlights)
    if len(html_body.encode()) > 100 * 1024:
        print("[경고] HTML이 100KB를 넘습니다 (메일로 보낼 경우 Gmail이 본문 끝을 자릅니다).")


HISTORY_PATH = ROOT_DIR / "data" / "newsletter_history.json"


def _week_key(now: datetime) -> str:
    """발행일이 속한 주의 목요일 (월~수에 미리 돌려도 같은 주로 묶는다)"""
    return (now.date() + timedelta(days=(3 - now.weekday()) % 7)).isoformat()


def load_prev_stats(now: datetime):
    """지난 주 수치 (비교용). 이력이 없으면 None"""
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    earlier = [k for k in history if k < _week_key(now)]
    return history[max(earlier)] if earlier else None


def save_stats(now: datetime, stats: dict) -> None:
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        history = {}
    history[_week_key(now)] = {k: stats[k] for k in ("fresh_news", "fresh_dart", "fresh_companies")}
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def build_stats(grouped: dict, now: datetime, total_companies: int, names=None) -> dict:
    fresh = {c: [a for a in arts if age_days(now, a) <= FRESH_DAYS] for c, arts in grouped.items() if names is None or c in names}
    return {
        "fresh_news": sum(1 for arts in fresh.values() for a in arts if a["cat3"] != "공시자료" and not is_routine(a)),
        # 공시는 관련 기사와 한 묶음이 된 경우(유사기사 쪽)도 센다
        "fresh_dart": sum(
            1 for arts in fresh.values() for a in arts for m in [a] + a["similar_articles"] if m["cat3"] == "공시자료"
        ),
        "fresh_companies": sum(1 for arts in fresh.values() if any(not is_routine(a) for a in arts)),
        "total_companies": total_companies,
    }


def resolve_links(grouped: dict, now: datetime) -> None:
    """메일에 오를 수 있는 기사만 구글뉴스 링크를 원문 링크로 바꾸고,
    원문 주소가 드러난 뒤에야 알 수 있는 사진 페이지·주가 사이트·재게시 옛 기사를 제거한다"""
    compact = {c for g in TARGET_GROUPS if g.get("compact") for c in g["companies"]}
    targets = [a for company, articles in grouped.items() for a in candidate_articles(articles, now, company in compact)]
    mapping = gnews_decoder.decode_all(a["link"] for a in targets)
    for a in targets:
        a["link"] = mapping.get(a["link"], a["link"])

    unresolved = {k for k, v in mapping.items() if k == v}  # 원문 주소로 바꾸지 못한 구글 링크

    def is_bad(a: dict) -> bool:
        return a["link"] in unresolved or bool(BLOCKED_LINK_RE.search(a["link"])) or is_stale(a["title"], a["link"], now)

    for company, articles in grouped.items():
        kept = []
        for a in articles:
            if is_bad(a):
                continue
            a["similar_articles"] = [
                s for s in a["similar_articles"] if not is_bad(s) and "news.google.com/rss/articles" not in s["link"]
            ]
            kept.append(a)
        grouped[company] = kept


if __name__ == "__main__":
    main()
