# 소부장 주간 뉴스

반도체 소부장 협력사 73곳의 뉴스·공시를 매주 목요일 모아 보여 주는 정적 사이트입니다. 7월부터 주차별로 볼 수 있습니다.

- 수집·정리: `src/` (구글뉴스·네이버 뉴스 검색·DART 공시 RSS, 오탐 필터, 중복 묶기, 중요도 선정)
- 사이트: `site/` (주차 목록 `index.html`, 주차별 `news/YYYY-MM-DD.html`), GitHub Pages로 배포
- 매주 목요일 05:30(KST) `weekly-news-site.yml`이 이번 주 페이지를 만들고, 06:30 `pages.yml`이 배포합니다.
- 지난 주차 소급: `site_request.txt`를 고쳐 push하면 `site-backfill.yml`이 7월부터 다시 만듭니다 (구글뉴스 검색 기준, 공시·주가 제외).

## 처음 한 번 설정
1. Settings → Pages → Source를 **GitHub Actions**로 바꿉니다.
2. (선택) Settings → Secrets → Actions에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `OPENDART_KEY` 등록 — 없어도 동작합니다.
