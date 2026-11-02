# 소부장 주간 뉴스

반도체 소부장 협력사 73곳의 뉴스·공시를 매주 목요일 모아 보여 주는 정적 사이트입니다. 1월부터 주차별로 볼 수 있습니다.

- 수집·정리: `src/` (구글뉴스·네이버 뉴스 검색·DART 공시 RSS, 오탐 필터, 중복 묶기, 중요도 선정)
- 사이트: `site/` (주차 목록 `index.html`, 주차별 `news/YYYY-MM-DD.html`), GitHub Pages로 배포
- 매주 목요일 05:30(KST) `weekly-news-site.yml`이 이번 주 페이지를 만들고, 06:30 `pages.yml`이 배포합니다.

## 처음 한 번 설정
1. Settings → Pages → Source를 **GitHub Actions**로 바꿉니다.
2. (선택) Settings → Secrets → Actions에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `OPENDART_KEY` 등록 — 없어도 동작합니다.

## 수집 소스 확대 및 품질 모니터링

기존 Google News 검색·Naver 뉴스·DART·기존 전문매체 RSS는 유지하면서
`src/news_source_catalog.py`에 보조 RSS 12개를 추가했습니다.

- 국내 5개: 한국경제, 조선비즈, 연합뉴스(경제), 파이낸셜뉴스, 아시아경제
- 해외 반도체 전문매체 4개: Semiconductor Engineering, EE Times, SemiWiki, SemiAnalysis
- 공식 발표/IR 3개: Applied Materials, Lam Research, 삼성 반도체 뉴스룸

새로운 소스는 등록 기업의 뉴스만 대상으로 하며 기존 중복/품질 필터를 통과해야 화면에 표시됩니다.
공식 IR 피드는 확정된 회사에 직접 귀속하고, 일반 언론사 RSS는 기업명 매칭을 우선합니다.
실제 외부 피드의 가용성은 주간 실행 결과를 통해 확인하며, 실패한 소스는 별도 집계합니다.

정상 수집 이후 `site/quality.html` (메뉴: **수집 품질**)에서 수집 성공률, 출처별 기사 수,
최근 기사 확인 기업 수, AI 분석/미검토 수 등을 확인할 수 있습니다.
`data/news_collection_health.json`은 주간 상태 이력을 보관합니다.
이 수치들은 기사 정답 검수에 근거한 정확도/재현율이 아니며, 기사 적합률은 별도 검수가 필요합니다.

품질 확인용 CI: `python -m unittest discover -s tests -p "test_*.py" -v`.
아직 첫 주간 실행 결과가 없다면 품질 페이지는 **집계 준비 중**으로 표시합니다.
