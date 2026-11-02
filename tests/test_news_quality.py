"""뉴스 중복·회사명 식별·AI 예산 배분 회귀 테스트 (외부 API 호출 없음)."""
import unittest
from datetime import datetime, timedelta, timezone

from src.newsletter_collector import find_companies, build_alias_map, same_story
from src.newsletter_ai import _pick_targets


NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


def article(title, *, when=NOW):
    return {
        "title": title, "pub_date": when, "source": "test",
        "cat2": "수주·협력", "cat3": "기업동향", "similar_articles": [],
        "link": "https://example.com/test"
    }


class EntityMatchingTests(unittest.TestCase):
    def test_ycchem_not_assigned_to_yc(self):
        matched = find_companies("와이씨켐, 반도체 소재 공급", build_alias_map())
        self.assertIn("와이씨켐", matched)
        self.assertNotIn("와이씨", matched)

    def test_yc_independent(self):
        self.assertIn("와이씨", find_companies("와이씨, 반도체 테스트 장비 공급", build_alias_map()))


class StoryClusteringTests(unittest.TestCase):
    def test_same_amount_alone_not_same_story(self):
        a = article("원익IPS 고객사 A에 반도체 장비 500억원 계약")
        b = article("원익IPS 고객사 B에 생산라인 장비 500억원 계약")
        self.assertFalse(same_story(a, b, "원익IPS"))

    def test_different_amounts_not_merged(self):
        a = article("피에스케이 반도체 장비 공급계약 150억원")
        b = article("피에스케이 반도체 장비 공급계약 350억원")
        self.assertFalse(same_story(a, b, "피에스케이"))


class FairAiBudgetTests(unittest.TestCase):
    def test_round_robin_includes_later_companies(self):
        grouped = {
            f"company_{i}": [article(f"company_{i} supplies a new product, event {j}") for j in range(6)]
            for i in range(70)
        }
        selected = _pick_targets(grouped, NOW)
        self.assertEqual(240, len(selected))
        self.assertIn("company_69", [company for company, _ in selected])


if __name__ == "__main__":
    unittest.main()
