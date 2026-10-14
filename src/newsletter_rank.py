from datetime import datetime

from src.newsletter_collector import HANGUL_RE, normalize_title
from src.newsletter_config import (
    CATEGORY_WEIGHT,
    FIXED_COMPANY_LIMIT,
    FRESH_DAYS,
    HIGHLIGHT_COUNT,
    HIGHLIGHT_MIN_WEIGHT,
    ROUTINE_CATEGORY,
)


def age_days(now: datetime, article: dict) -> float:
    return (now - article["pub_date"]).total_seconds() / 86400


def is_routine(article: dict) -> bool:
    """정기 소유보고·국민연금 지분 변동처럼 매주 반복되는 소식"""
    return article["cat2"] == ROUTINE_CATEGORY


def score(article: dict, now: datetime) -> float:
    """중요도 = 분류 가중치 + 최신성 + 여러 매체가 다룬 정도"""
    age = age_days(now, article)
    recency = 2 if age <= 1 else 1.5 if age <= 3 else 1 if age <= FRESH_DAYS else 0
    coverage = min(len(article["similar_articles"]), 3) * 0.7
    # 같은 소식에 공시가 함께 묶여 있으면(회사가 공식 확인한 사안) 가산점
    filed = 1 if article["cat3"] != "공시자료" and any(m["cat3"] == "공시자료" for m in article["similar_articles"]) else 0
    # 영문 기사(해외 기업)는 국문 기사가 없을 때 보완용
    foreign = 0 if HANGUL_RE.search(article["title"]) else -2
    return CATEGORY_WEIGHT.get(article["cat2"], 1) + recency + coverage + filed + foreign


def select_company(articles: list, now: datetime) -> dict:
    """회사 1곳에서 메일에 보일 기사를 고른다.

    - shown: 최근 7일 기사 중 중요도 순 최대 2건 (지분변동 같은 반복성 소식은 제외)
    - routine: 최근 7일 지분변동 소식 (본문 칸을 쓰지 않고 건수만 표시)
    - older: 최근 7일 소식이 없을 때 보여줄 8~30일 전 최신 기사 1건
    """
    fresh = [a for a in articles if age_days(now, a) <= FRESH_DAYS]
    main = sorted((a for a in fresh if not is_routine(a)), key=lambda a: score(a, now), reverse=True)
    routine = [a for a in fresh if is_routine(a)]
    shown = main[:FIXED_COMPANY_LIMIT]

    older = None
    if not shown:
        older = next((a for a in articles if age_days(now, a) > FRESH_DAYS and not is_routine(a)), None)
    return {"shown": shown, "routine": routine, "older": older}


def pick_highlights(selections: dict, now: datetime, count: int = HIGHLIGHT_COUNT) -> list:
    """전체 회사에서 '이번 주 주요 소식'을 고른다 → [(회사명, article)]"""
    candidates = []
    for company, sel in selections.items():
        for a in sel["shown"]:
            if CATEGORY_WEIGHT.get(a["cat2"], 1) >= HIGHLIGHT_MIN_WEIGHT:
                candidates.append((score(a, now), company, a))
    candidates.sort(key=lambda x: x[0], reverse=True)

    picked, seen = [], set()
    for _, company, a in candidates:
        key = normalize_title(a["title"])
        if key in seen or a["link"] in seen:
            continue  # 여러 회사에 함께 걸린 같은 기사는 한 번만
        seen.update((key, a["link"]))
        picked.append((company, a))
        if len(picked) >= count:
            break
    return picked


def candidate_articles(articles: list, now: datetime) -> list:
    """원문 링크 변환·검증 대상: 메일에 오를 가능성이 있는 기사와 그 유사기사"""
    fresh = [a for a in articles if age_days(now, a) <= FRESH_DAYS]
    main = sorted((a for a in fresh if not is_routine(a)), key=lambda a: score(a, now), reverse=True)
    routine = [a for a in fresh if is_routine(a)]
    older = [a for a in articles if age_days(now, a) > FRESH_DAYS and not is_routine(a)]
    picked = main[: FIXED_COMPANY_LIMIT + 2] + routine[:2] + older[:2]
    return picked + [s for a in picked for s in a["similar_articles"][:1]]
