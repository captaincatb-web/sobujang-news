"""수집 헬스·소스 추가·공시 보존 회귀 테스트 (네트워크 호출 없음)."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from src import newsletter_collector
from src.collection_quality import record_health
from src.news_source_catalog import ADDITIONAL_RSS_URLS, GLOBAL_RSS_URLS, COMPANY_OFFICIAL_RSS


def feed_item(url, now, title="단일판매ㆍ공급계약체결"):
    return {"title": title, "link": url, "pub_date": now - timedelta(minutes=5), "source": "DART"}


def source(company, receipt):
    return {
        "kind": "dart",
        "company": company,
        "url": "https://example.com/feed/" + receipt,
        "receipt": receipt,
    }


class CollectorHealthTests(unittest.TestCase):
    def test_preserves_identical_dart_titles_and_separate_receipts(self):
        now = datetime.now(timezone.utc)
        sources = [source("코미코", "20261102900001"), source("코미코", "20261102900002"), source("피에스케이", "20261102900003")]
        def mock_fetch(s):
            return [feed_item("https://dart.fss.or.kr/api/link.jsp?rcpNo=" + s["receipt"], now)]
        with mock.patch.object(newsletter_collector, "build_sources", return_value=sources), \
             mock.patch.object(newsletter_collector, "_fetch_feed", side_effect=mock_fetch), \
             mock.patch.object(newsletter_collector, "_write_collect_report"):
            result = newsletter_collector.collect_articles()
        self.assertEqual(2, len(result["코미코"]))
        self.assertEqual(1, len(result["피에스케이"]))
        self.assertEqual(0, newsletter_collector.LAST_COLLECTION_REPORT["sources_failed"])
        self.assertIn("additional_sources", newsletter_collector.LAST_COLLECTION_REPORT)

    def test_rss_headers_are_host_specific(self):
        browser = newsletter_collector.rss_request_headers("https://semiwiki.com/feed/")
        basic = newsletter_collector.rss_request_headers("https://www.hankyung.com/feed/all-news")
        self.assertNotEqual(browser["User-Agent"], basic["User-Agent"])
        self.assertIn("Chrome/", browser["User-Agent"])
        self.assertEqual("Mozilla/5.0", basic["User-Agent"])

    def test_zero_results_stop_publication(self):
        sources = [source("코미코", "20261102900001")]
        with mock.patch.object(newsletter_collector, "build_sources", return_value=sources), \
             mock.patch.object(newsletter_collector, "_fetch_feed", return_value=[]), \
             mock.patch.object(newsletter_collector, "_write_collect_report"):
            with self.assertRaisesRegex(RuntimeError, "0건"):
                newsletter_collector.collect_articles()

    def test_new_sources_are_unique_and_included(self):
        self.assertEqual(9, len(ADDITIONAL_RSS_URLS))
        self.assertEqual(9, len(set(ADDITIONAL_RSS_URLS)))
        sources = newsletter_collector.build_sources()
        urls = {x.get("url") for x in sources}
        for u in ADDITIONAL_RSS_URLS:
            self.assertIn(u, urls)
        self.assertTrue(any(s.get("kind") == "rss_global" for s in sources if s.get("url") in GLOBAL_RSS_URLS))
        self.assertEqual(2, len(COMPANY_OFFICIAL_RSS))
        for _name, url, company in COMPANY_OFFICIAL_RSS:
            self.assertIn({"kind": "press", "url": url, "company": company},
                          [s for s in sources if s.get("kind") == "press"])


class HealthPageTests(unittest.TestCase):
    def sample(self):
        collector = {
            "sources_total": 11, "sources_failed": 2,
            "sources_by_kind": {"rss": 7, "rss_global": 4},
            "failed_by_kind": {"rss": 1, "rss_global": 1},
            "failure_examples": [("rss", "HTTP 503")],
            "raw_by_kind": {"rss": 30, "rss_global": 12},
            "kept_by_kind": {"rss": 5, "rss_global": 2},
            "articles_kept": 7, "companies_total": 322, "companies_fresh": 3,
        }
        ai = {"eligible": 12, "selected": 10, "analyzed": 8, "unreviewed": 4, "dropped": 2, "failed_batches": 1}
        return collector, ai

    def test_generated_files_and_previous_week_preserved(self):
        collector, ai = self.sample()
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            history = p / "data" / "history.json"
            site = p / "site"
            first = datetime(2026, 10, 29, 5, 30, tzinfo=timezone(timedelta(hours=9)))
            second = first + timedelta(days=7)
            record_health(first, collector, ai, history_path=history, site_dir=site)
            record_health(second, collector, ai, history_path=history, site_dir=site)
            saved = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(2, len(saved))
            html = (site / "quality.html").read_text(encoding="utf-8")
            self.assertIn("수집 품질", html)
            self.assertIn("81.8%", html)  # (11 - 2) / 11 * 100
            self.assertIn("해외 반도체 전문매체 RSS", html)
            self.assertIn("66.7%", html)  # 8 / 12 * 100
            published = json.loads((site / "collection-health.json").read_text(encoding="utf-8"))
            self.assertEqual(322, published["collector"]["companies_total"])

    def test_status_does_not_claim_ai_success_if_unreviewed(self):
        collector, ai = self.sample()
        ai.update({"analyzed": 0, "unreviewed": 12, "failed_batches": 0})
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            record_health(datetime(2026, 11, 5, tzinfo=timezone.utc), collector, ai, history_path=p / "data.json", site_dir=p / "site")
            self.assertIn("AI 미사용·미검토", (p / "site" / "quality.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
