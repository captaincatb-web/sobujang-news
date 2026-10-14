import argparse
import os
import sys
from datetime import datetime

from src import email_sender, gnews_decoder, site
from src.history import KST
from src.newsletter_collector import BLOCKED_LINK_RE, collect_articles, group_similar, is_stale
from src.newsletter_config import OUTPUT_DIR, RECIPIENT_EMAIL_DEFAULT, TARGET_GROUPS, all_company_names
from src.newsletter_finance import Cache, build_fin_summary, build_price_cell, build_price_short, weekly_movers
from src.newsletter_html import build_newsletter_html
from src.newsletter_rank import FRESH_DAYS, age_days, candidate_articles, is_routine, pick_highlights, select_company


def build_subject(now: datetime) -> str:
    return f"📬 [뉴스레터] 핵심 소부장 파트너사 주간 동향 ({now.month}/{now.day})"


def main() -> None:
    parser = argparse.ArgumentParser(description="소부장 파트너사 동향 뉴스레터")
    parser.add_argument("--dry-run", action="store_true", help="메일을 보내지 않고 output/ 에 HTML만 저장")
    args = parser.parse_args()

    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    if not args.dry_run and not (smtp_user and smtp_password):
        print("필수 환경 변수가 없습니다: SMTP_USER, SMTP_PASSWORD (또는 --dry-run 사용)")
        sys.exit(1)

    dart_key = os.environ.get("OPENDART_KEY", "")
    gemini_key = os.environ.get("GEMINI_KEY", "")
    gemini_model = os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"
    recipient = os.environ.get("RECIPIENT_EMAIL") or RECIPIENT_EMAIL_DEFAULT

    now = datetime.now(KST)
    grouped = group_similar(collect_articles())
    resolve_links(grouped, now)
    selections = {company: select_company(articles, now) for company, articles in grouped.items()}
    highlights = pick_highlights(selections, now)

    cache = Cache()
    companies = all_company_names()
    fin_cells, price_cells, price_short = {}, {}, {}
    for company in companies:
        fin_cells[company] = build_fin_summary(company, dart_key, now, cache, gemini_key, gemini_model)
        price_cells[company] = build_price_cell(company)
        price_short[company] = build_price_short(company)
    cache.save()

    html_body = build_newsletter_html(
        now=now,
        groups=TARGET_GROUPS,
        selections=selections,
        highlights=highlights,
        movers=weekly_movers(companies),
        stats=build_stats(grouped, now, len(companies)),
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
    site.publish_week(now, html_body, build_stats(grouped, now, len(companies)), highlights)

    if args.dry_run:
        return
    email_sender.send_html(
        os.environ.get("SMTP_HOST") or "smtp.gmail.com",
        int(os.environ.get("SMTP_PORT") or 465),
        smtp_user,
        smtp_password,
        recipient,
        subject,
        html_body,
    )
    print(f"메일 발송 완료 → {recipient}")


def build_stats(grouped: dict, now: datetime, total_companies: int) -> dict:
    fresh = {c: [a for a in arts if age_days(now, a) <= FRESH_DAYS] for c, arts in grouped.items()}
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
    targets = [a for articles in grouped.values() for a in candidate_articles(articles, now)]
    mapping = gnews_decoder.decode_all(a["link"] for a in targets)
    for a in targets:
        a["link"] = mapping.get(a["link"], a["link"])

    def is_bad(a: dict) -> bool:
        return bool(BLOCKED_LINK_RE.search(a["link"])) or is_stale(a["title"], a["link"], now)

    for company, articles in grouped.items():
        kept = []
        for a in articles:
            if is_bad(a):
                continue
            a["similar_articles"] = [s for s in a["similar_articles"] if not is_bad(s)]
            kept.append(a)
        grouped[company] = kept


if __name__ == "__main__":
    main()
