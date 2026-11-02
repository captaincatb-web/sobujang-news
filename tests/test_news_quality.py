"""뉴스 중복·회사명 식별·AI 예산 배분 회귀 테스트 (외부 API 호출 없음)."""
import unittest
from datetime import datetime, timezone
from unittest import mock

from src.newsletter_collector import find_companies, build_alias_map, same_story
from src.newsletter_ai import _pick_targets, apply_ai_analysis


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


class AiReliabilityTests(unittest.TestCase):
    def test_unrelated_removed_but_indirect_business_risk_preserved(self):
        grouped = {
            "미래컴퍼니": [article("미래컴퍼니, 해외 로봇수술 교육 협력")],
            "코미코": [article("코미코, 공급망 차질로 생산 중단")],
        }
        classifications = {
            0: {"relevant": True, "semiconductor_relevance": "unrelated",
                "importance": 1, "category": "수주·협력"},
            1: {"relevant": True, "semiconductor_relevance": "indirect",
                "importance": 5, "category": "기타동향"},
        }
        with mock.patch("src.newsletter_ai._classify", return_value=classifications):
            stats = apply_ai_analysis(grouped, NOW, client=object())
        self.assertEqual(2, stats["analyzed"])
        self.assertEqual(1, stats["dropped"])
        self.assertEqual(0, len(grouped["미래컴퍼니"]))
        self.assertEqual(1, len(grouped["코미코"]))

    def test_failed_ai_batch_keeps_rules_and_tracks_unreviewed(self):
        grouped = {"코미코": [article("코미코 신규 반도체 장비 투자")]}
        with mock.patch("src.newsletter_ai._classify", side_effect=RuntimeError("test failure")):
            stats = apply_ai_analysis(grouped, NOW, client=object())
        self.assertEqual(1, stats["failed_batches"])
        self.assertEqual(1, stats["unreviewed"])
        self.assertEqual(1, len(grouped["코미코"]))




if __name__ == "__main__":
    unittest.main()
