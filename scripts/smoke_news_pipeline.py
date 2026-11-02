"""Live but non-destructive end-to-end sample of ONLY the currently active additional RSS sources.

No API keys; no page publication. This checks whether RSS entries survive the
actual company matcher, exclusion logic, grouping and article selection.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from src import newsletter_collector as collector
from src.news_source_catalog import ADDITIONAL_RSS_URLS, COMPANY_OFFICIAL_RSS, GLOBAL_RSS_URLS
from src.newsletter_rank import select_company


def main():
    sources = [
        {"kind": "rss_global" if url in GLOBAL_RSS_URLS else "rss", "url": url, "company": ""}
        for url in ADDITIONAL_RSS_URLS
    ] + [{"kind": "press", "url": url, "company": co} for _, url, co in COMPANY_OFFICIAL_RSS]
    # Mocks only source SELECTION: all 12 RSS feeds are truly fetched over HTTP.
    with mock.patch.object(collector, "build_sources", return_value=sources):
        by_company = collector.collect_articles()
    grouped = collector.group_similar(by_company)
    now = datetime.now(timezone.utc)
    rows = []
    for company, articles in grouped.items():
        sel = select_company(articles, now)
        for article in sel["shown"]:
            rows.append({"company": company, "title": article["title"][:160],
                         "source": article["source"], "category": article["cat2"],
                         "url": article["link"][:300]})
    report = {"status": collector.LAST_COLLECTION_REPORT, "selected_news_count": len(rows),
              "selected_sample": rows[:30]}
    out = Path("output/source_pipeline_smoke.json")
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = collector.LAST_COLLECTION_REPORT
    print(f"LIVE_PIPELINE: {metrics['sources_total']} source requests / "
          f"{metrics['sources_failed']} failed / {metrics['articles_kept']} company-article matches / "
          f"{metrics['companies_fresh']} companies with recent news / "
          f"{len(rows)} selected headlines")
    print("SELECTED_HEADLINES:")
    for row in rows[:24]:
        print(f"  {row['company']} | {row['category']} | {row['title']}")
    print(f"REPORT: {out}")


if __name__ == "__main__":
    main()
