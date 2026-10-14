"""주차별 뉴스 홈페이지: 정적 뉴스 사이트 (KRDS 서식, GitHub Pages)

- site/index.html             7~10월 주차 목록 (월별 탭, 주요 소식 미리보기)
- site/news/YYYY-MM-DD.html  그 주(목요일 발행일 기준)의 뉴스레터 전체 + 회사 검색
- data/site_weeks.json       주차별 요약 (목록 페이지 재생성용)
배포는 .github/workflows/pages.yml 이 site/ 를 올린다.
"""
import json
from datetime import date, datetime, timedelta
from html import escape

from src.config import ROOT_DIR

SITE_DIR = ROOT_DIR / "site"
NEWS_DIR = SITE_DIR / "news"
META_PATH = ROOT_DIR / "data" / "site_weeks.json"
SITE_START = date(2026, 5, 7)  # 첫 주차: 5월 첫 목요일
REPO_URL = "https://github.com/captaincatb-web/sobujang-news"


def week_key(d: date) -> date:
    """발행일이 속한 주의 목요일 (월~수 수동 발행분도 그 주 목요일 페이지로 모은다)"""
    return d + timedelta(days=(3 - d.weekday()) % 7)


def all_week_keys(today: date) -> list:
    keys, d = [], SITE_START
    while d <= week_key(today):
        keys.append(d)
        d += timedelta(days=7)
    return keys


def _load_meta() -> dict:
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _layout(*, prefix: str, title: str, crumbs: str, main: str, script: str = "") -> str:
    """협력사 프로필 사이트와 같은 머리글·바닥글. prefix: 사이트 루트까지의 상대 경로('' 또는 '../')"""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | 소부장 주간 뉴스</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="{prefix}vendor/phosphor/style.css">
  <link rel="stylesheet" href="{prefix}styles.css">
  <link rel="stylesheet" href="{prefix}news.css">
</head>
<body>
  <a class="skip" href="#content">본문 바로가기</a>
  <header class="krds-header">
    <div class="inner head-inner">
      <ul class="utility" aria-label="관련 사이트">
        <li><a href="https://dart.fss.or.kr" target="_blank" rel="noopener">DART 전자공시<i class="ph ph-arrow-square-out" aria-hidden="true"></i></a></li>
        <li><a href="{REPO_URL}" target="_blank" rel="noopener">GitHub 저장소<i class="ph ph-arrow-square-out" aria-hidden="true"></i></a></li>
      </ul>
      <div class="branding">
        <a class="brand" href="{prefix or './'}"><span class="brand-mark" aria-hidden="true">소</span><span class="brand-name">소부장 주간 뉴스<small>반도체 협력사 동향</small></span></a>
      </div>
    </div>
    <nav class="gnb" aria-label="주 메뉴">
      <div class="inner"><ul>
        <li><a href="{prefix or './'}" aria-current="page">주간 뉴스</a></li>
      </ul></div>
    </nav>
  </header>
  <main id="content" class="inner">
    <nav class="breadcrumb" aria-label="현재 위치"><ol>
      <li><a href="{prefix or './'}"><i class="ph ph-house" aria-hidden="true"></i>홈</a></li>{crumbs}
    </ol></nav>
    {main}
  </main>
  <footer class="krds-footer">
    <div class="inner">
      <p class="f-logo"><span class="brand-mark" aria-hidden="true">소</span>소부장 주간 뉴스</p>
      <div class="f-info">
        <p><strong>매주 목요일 자동 갱신</strong> · 기사 제목과 원문 링크만 모아 보여 주는 자동 수집 페이지이며, 저작권은 각 언론사에 있습니다.</p>
      </div>
      <div class="f-btm"><p class="f-copy">© 2026 소부장 주간 뉴스</p></div>
    </div>
  </footer>
  {script}
</body>
</html>
"""


def publish_week(now: datetime, body_html: str, stats: dict, highlights: list) -> None:
    """한 주차 페이지를 쓰고 목록을 다시 만든다. highlights: [(회사, article)]"""
    key = week_key(now.date())
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    meta = _load_meta()
    meta[key.isoformat()] = {
        "fresh_news": stats["fresh_news"],
        "fresh_dart": stats["fresh_dart"],
        "fresh_companies": stats["fresh_companies"],
        "total": stats["total_companies"],
        "highlights": [{"company": c, "title": a["title"], "link": a["link"], "cat": a["cat2"]} for c, a in highlights[:3]],
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    keys = sorted(meta)
    i = keys.index(key.isoformat())
    prev_b = (
        f'<a class="btn btn-secondary btn-sm" href="{keys[i - 1]}.html"><i class="ph ph-caret-left" aria-hidden="true"></i>이전 주</a>'
        if i > 0 else ""
    )
    next_b = (
        f'<a class="btn btn-secondary btn-sm" href="{keys[i + 1]}.html">다음 주<i class="ph ph-caret-right" aria-hidden="true"></i></a>'
        if i + 1 < len(keys) else ""
    )
    start = key - timedelta(days=7)
    main = f"""
    <section class="page-head" aria-labelledby="title">
      <h1 id="title">{key:%Y.%m.%d}(목) 발행 · 주간 뉴스</h1>
      <p class="lead">{start.month}/{start.day} ~ {key.month}/{key.day} · 새 소식 <strong>{stats['fresh_news']}</strong>건
        (공시 {stats['fresh_dart']}건) · 소식 있는 회사 {stats['fresh_companies']}/{stats['total_companies']}곳</p>
    </section>
    <div class="news-bar">
      <div class="sch-input"><label class="sr-only" for="q">이 주 소식 검색</label>
        <input id="q" class="krds-input" type="search" placeholder="회사명·키워드 검색 (예: 심텍, 수주, 증설)" autocomplete="off">
        <i class="ph ph-magnifying-glass" aria-hidden="true"></i></div>
      <div class="news-pager"><a class="btn btn-tertiary btn-sm" href="../index.html">전체 주차</a>{prev_b}{next_b}</div>
    </div>
    <div class="news-body">{body_html}</div>"""
    script = (
        "<script>var q=document.getElementById('q');q.addEventListener('input',function(){var v=q.value.trim().toLowerCase();"
        "document.querySelectorAll('.news-body table tr').forEach(function(r){if(r.querySelector('th'))return;"
        "r.style.display=(!v||r.textContent.toLowerCase().indexOf(v)>-1)?'':'none';});});</script>"
    )
    crumbs = f'<li aria-current="page">{key:%m/%d} 주차</li>'
    (NEWS_DIR / f"{key}.html").write_text(
        _layout(prefix="../", title=f"주간 뉴스 {key:%m/%d}", crumbs=crumbs, main=main, script=script), encoding="utf-8"
    )
    build_index()


def build_index() -> None:
    meta = _load_meta()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "news.css").write_text(NEWS_CSS, encoding="utf-8")
    latest = max(meta) if meta else ""
    months = sorted({k[:7] for k in meta}, reverse=True)
    tabs = "".join(f'<button type="button" class="tab" data-m="{m}">{int(m[5:])}월</button>' for m in months)
    cards = []
    for k in sorted(meta, reverse=True):
        d, s = date.fromisoformat(k), meta[k]
        start = d - timedelta(days=7)
        hl = "".join(
            f'<li><span class="tag">{escape(h["cat"])}</span><b>{escape(h["company"])}</b> · '
            f'<a href="{escape(h["link"])}" target="_blank" rel="noopener">{escape(h["title"])}</a></li>'
            for h in s["highlights"]
        )
        badge = ' <span class="badge">최신</span>' if k == latest else ""
        cards.append(
            f'<article class="week-card{" is-latest" if k == latest else ""}" data-m="{k[:7]}">'
            f'<h2><a href="news/{k}.html">{d:%Y.%m.%d}(목) 발행 주</a>{badge}</h2>'
            f'<p class="meta">{start.month}/{start.day} ~ {d.month}/{d.day} · 새 소식 {s["fresh_news"]}건 '
            f'(공시 {s["fresh_dart"]}건) · 소식 있는 회사 {s["fresh_companies"]}/{s["total"]}곳</p><ul>{hl}</ul></article>'
        )
    main = f"""
    <section class="page-head" aria-labelledby="title">
      <h1 id="title">주간 뉴스</h1>
      <p class="lead">반도체 소부장 협력사 73곳의 뉴스·공시를 매주 목요일 모아 보여 줍니다. 5월부터 주차별로 볼 수 있습니다.</p>
    </section>
    <div class="tabs" role="group" aria-label="월 선택"><button type="button" class="tab" data-m="all">전체</button>{tabs}</div>
    {"".join(cards)}"""
    script = (
        "<script>var b=document.querySelectorAll('.tabs .tab'),c=document.querySelectorAll('.week-card');"
        "function show(m){b.forEach(function(x){x.classList.toggle('on',x.dataset.m===m)});"
        "c.forEach(function(x){x.style.display=(m==='all'||x.dataset.m===m)?'':'none'});}"
        "b.forEach(function(x){x.onclick=function(){show(x.dataset.m)}});show('all');</script>"
    )
    (SITE_DIR / "index.html").write_text(
        _layout(prefix="", title="주간 뉴스", crumbs='', main=main, script=script),
        encoding="utf-8",
    )


NEWS_CSS = """/* 주간 뉴스 페이지 추가 서식 (기본 색·글꼴은 styles.css 의 KRDS 값을 따른다) */
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
.tab{min-height:40px;padding:0 16px;border:1px solid var(--line-2);border-radius:999px;background:var(--surface);color:var(--text);font:inherit;cursor:pointer}
.tab.on{background:var(--selected);border-color:var(--selected);color:#fff;font-weight:700}
.week-card{border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:12px 0;background:var(--surface)}
.week-card.is-latest{border-color:var(--primary);border-width:2px}
.week-card h2{margin:0 0 4px;font-size:21px}.week-card h2 a{color:var(--text-strong);text-decoration:none}
.week-card h2 a:hover{text-decoration:underline}.week-card .meta{margin:0 0 8px;font-size:15px;color:var(--text-3)}
.week-card ul{margin:0;padding-left:20px;font-size:16px;line-height:1.7}.week-card .tag{font-size:12px;background:var(--subtle);padding:1px 6px;margin-right:6px;border-radius:4px}
.badge{font-size:12px;background:var(--primary);color:#fff;border-radius:999px;padding:2px 8px;vertical-align:middle}
.news-bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin:16px 0}
.news-bar .sch-input{flex:1;min-width:240px}.news-pager{display:flex;gap:8px}
.news-body{background:#fff;color:#191f28;border:1px solid var(--line);border-radius:12px;padding:16px;overflow-x:auto}
"""
