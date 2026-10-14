"""7월부터 지난 주차 페이지를 소급 생성 (구글뉴스 날짜 범위 검색만 사용, 공시·주가 제외)
사용: python -m src.site_backfill [--only 2026-09-10]"""
import argparse
from datetime import datetime, time, timezone

from src import site
from src.history import KST
from src.newsletter import build_stats, resolve_links
from src.newsletter_collector import collect_articles, group_similar
from src.newsletter_config import TARGET_GROUPS, all_company_names
from src.newsletter_html import build_newsletter_html
from src.newsletter_rank import pick_highlights, select_company


def build_week(key) -> None:
    now = datetime.combine(key, time(6, 0), tzinfo=KST)
    grouped = group_similar(collect_articles(asof=now))
    resolve_links(grouped, now)
    selections = {c: select_company(a, now) for c, a in grouped.items()}
    highlights = pick_highlights(selections, now)
    companies = all_company_names()
    stats = build_stats(grouped, now, len(companies))
    html = build_newsletter_html(
        now=now, groups=TARGET_GROUPS, selections=selections, highlights=highlights, movers=([], []), stats=stats,
        fin_cells={}, price_cells={c: "" for c in companies}, price_short={c: "" for c in companies}, show_fin=False,
    )
    site.publish_week(now, html, stats, highlights)
    print(f"[백필] {key} 완료: 새 소식 {stats['fresh_news']}건, 회사 {stats['fresh_companies']}곳")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="이 목요일(YYYY-MM-DD) 한 주만")
    args = ap.parse_args()
    today = datetime.now(KST).date()
    keys = site.all_week_keys(today)[:-1]  # 이번 주는 정기 뉴스레터 빌드가 만든다
    if args.only:
        keys = [k for k in keys if k.isoformat() == args.only]
    for key in keys:
        if not args.only and (site.NEWS_DIR / f"{key}.html").exists():
            continue  # 이미 만든 주차는 건너뛴다 (--only 로 지정하면 다시 만든다)
        build_week(key)


if __name__ == "__main__":
    main()
