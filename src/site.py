"""주차별 뉴스 홈페이지 (정적 사이트, GitHub Pages용 site/). 디자인 기준은 DESIGN.md.

- site/index.html           주차 목록 (월별 구간, 주요 소식 미리보기)
- site/news/YYYY-MM-DD.html 그 주(목요일 발행일 기준) 뉴스레터 전체 + 회사 검색
- data/site_weeks.json      주차별 요약 (목록 재생성용)
- data/weeks/YYYY-MM-DD.html 뉴스레터 본문 원본 (디자인을 바꿔도 모든 주차를 다시 만들 수 있게 보관)
배포는 .github/workflows/pages.yml 이 site/ 를 올린다.
"""
import json
import re
from datetime import date, datetime, timedelta
from html import escape

from src.config import ROOT_DIR

SITE_DIR = ROOT_DIR / "site"
NEWS_DIR = SITE_DIR / "news"
WEEKS_DIR = ROOT_DIR / "data" / "weeks"
META_PATH = ROOT_DIR / "data" / "site_weeks.json"
SITE_START = date(2026, 1, 1)  # 첫 주차: 1월 첫 목요일
REPO_URL = "https://github.com/captaincatb-web/sobujang-news"
WEEKDAY = "월화수목금토일"

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]\\s*")
# 뉴스레터 본문 맨 위의 제목·발행 정보 (페이지 머리말과 겹치므로 사이트에서는 뺀다)
INNER_HEAD_RE = re.compile(r'<h2 style="margin:0 0 4px">.*?</h2>\s*<div style="font-size:12px;[^>]*>.*?</div>', re.S)


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


LEGEND_RE = re.compile(r"제목 색:.*?지분 = ", re.S)


# 이미 저장된 주차 본문에 들어 있는 '오탐 제외 사례'와 5그룹 '뉴스 미확인' 목록은 페이지에서 뺀다
FP_BLOCK_RE = re.compile(r'<div style="margin:18px 0 6px"><b style="font-size:13px">🚫 오탐 제외 사례.*?(?=<div style="font-size:11px;color:#8b95a1;margin-top:14px)', re.S)
QUIET_BLOCK_RE = re.compile(r'<div style="color:#6b7684;line-height:1.8;font-size:11px;margin-bottom:8px">📭 <b>최근 7일 뉴스 미확인.*?</div>', re.S)


OLD_EXTRA_RE = re.compile(r'<div style="font-size:12px;color:#6b7684;margin:-6px 0 12px">5그룹 .*?</div>', re.S)
CHIP_RE = re.compile(r'(<a [^>]*>)([^<]*)(</a>) <b style="color:#3182f6">([^<]*)</b>')
GROUP_H3_RE = re.compile(r"<h3([^>]*)>(.*?)</h3>", re.S)


def _group_nav(body: str) -> list:
    """본문의 그룹 제목 → [(앵커 id, '1그룹')]"""
    return [(f"g{i}", re.sub(r"<[^>]+>|\s*\(.*", "", t).strip()) for i, (_, t) in enumerate(GROUP_H3_RE.findall(body), 1)]


def _clean_body(body: str) -> str:
    body = QUIET_BLOCK_RE.sub("", FP_BLOCK_RE.sub("", body))
    body = OLD_EXTRA_RE.sub("", body)
    # 제목에 이미 든 금액을 뒤에 한 번 더 붙인 칩은 뺀다
    body = CHIP_RE.sub(lambda m: m.group(0) if m.group(4).strip() not in m.group(2) else m.group(1) + m.group(2) + m.group(3), body)
    # 그룹 제목은 h2로 (h1 다음에 h3가 오면 제목 단계가 건너뛴다) + 이동용 앵커
    counter = iter(range(1, 99))
    body = GROUP_H3_RE.sub(lambda m: f'<h2 id="g{next(counter)}"{m.group(1)}>{m.group(2)}</h2>', body)
    body = EMOJI_RE.sub("", INNER_HEAD_RE.sub("", body, count=1))
    # 제목 색 안내를 이 사이트의 색(구리·검정·회색)에 맞게 바꾼다
    return LEGEND_RE.sub("제목 색: 구리색 24시간 이내 · 검정 최근 7일 · 회색 지난 소식(8~30일) · 지분 = ", body)


def _layout(*, prefix: str, title: str, main: str, script: str = "", nav: str = "") -> str:
    """머리말·바닥글. prefix: 사이트 루트까지의 상대 경로('' 또는 '../')"""
    home = prefix or "./"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(title)}</title>
  <link rel="icon" href="data:,">
  <link rel="preload" href="{prefix}vendor/pretendard/PretendardVariable.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{prefix}news.css">
</head>
<body>
  <a class="skip" href="#content">본문 바로가기</a>
  <header class="mast">
    <div class="wrap mast-row">
      <a class="mast-name" href="{home}">소부장 주간 동향</a>
      <nav class="mast-nav" aria-label="바로가기">{nav}<a href="{prefix}dashboard.html">올해 대시보드</a></nav>
    </div>
  </header>
  <main id="content" class="wrap">
    {main}
  </main>
  <footer class="foot">
    <div class="wrap">
      <p>기사 제목과 원문 링크만 모아 보여 주는 자동 수집 페이지입니다. 기사의 저작권은 각 언론사에 있습니다.</p>
      <p>매주 목요일 갱신 · <a href="#content">↑ 맨 위로</a></p>
    </div>
  </footer>
  {script}
</body>
</html>
"""


def publish_week(now: datetime, body_html: str, stats: dict, highlights: list) -> None:
    """한 주차를 저장하고 페이지·목록을 다시 만든다. highlights: [(회사, article)]"""
    key = week_key(now.date())
    WEEKS_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    (WEEKS_DIR / f"{key}.html").write_text(body_html, encoding="utf-8")
    meta = _load_meta()
    meta[key.isoformat()] = {
        "fresh_news": stats["fresh_news"],
        "fresh_dart": stats["fresh_dart"],
        "fresh_companies": stats["fresh_companies"],
        "total": stats["total_companies"],
        "extra_companies": (stats.get("extra") or {}).get("fresh_companies"),
        "extra_total": (stats.get("extra") or {}).get("total_companies"),
        "highlights": [{"company": c, "title": a["title"], "link": a["link"], "cat": a["cat2"]} for c, a in highlights[:3]],
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    rebuild_all()


def rebuild_all() -> None:
    """보관된 본문과 요약으로 모든 주차 페이지·목록·서식 파일을 다시 만든다 (디자인을 바꿨을 때도 쓴다)"""
    meta = _load_meta()
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "news.css").write_text(NEWS_CSS, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    keys = sorted(meta)
    for i, k in enumerate(keys):
        raw = WEEKS_DIR / f"{k}.html"
        if raw.exists():
            _write_week_page(k, meta[k], raw.read_text(encoding="utf-8"), keys[i - 1] if i else None, keys[i + 1] if i + 1 < len(keys) else None)
    _write_index(meta)
    from src import dashboard  # site ↔ dashboard 순환 import를 피해 여기서 불러온다

    dashboard.build(_layout)


def _write_week_page(k: str, s: dict, body_html: str, prev_k, next_k) -> None:
    d = date.fromisoformat(k)
    start = d - timedelta(days=7)
    pager = (
        (f'<a href="{prev_k}.html" rel="prev">← 이전 주</a>' if prev_k else '<span>← 이전 주</span>')
        + (f'<a href="{next_k}.html" rel="next">다음 주 →</a>' if next_k else '<span>다음 주 →</span>')
    )
    cleaned = _clean_body(body_html)
    nav_items = _group_nav(body_html)
    jump = "".join(f'<a href="#{i}">{escape(t)}</a>' for i, t in nav_items)
    is_latest = next_k is None
    title_txt = "이번 주 소식" if is_latest else f"{start.month}/{start.day}~{d.month}/{d.day} 소식"
    extra = ""
    if s.get("extra_total"):
        extra = f' · 5그룹 {s["extra_total"]}곳 중 {s.get("extra_companies") or 0}곳 소식 확인'
    main = f"""
    <section class="hero">
      <p class="kicker">{d.year}년 {d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 발행 · {start.month}/{start.day} ~ {d.month}/{d.day}</p>
      <h1>{title_txt} <em>{s['fresh_news']}</em>건</h1>
      <p class="sub">1~4그룹 {s['total']}곳 기준 · 공시 {s['fresh_dart']}건 포함 · 소식이 있는 회사 {s['fresh_companies']}곳{extra}</p>
    </section>
    <div class="tools">
      <label class="search"><span class="sr">이 주 소식 검색</span>
        <input id="q" type="search" placeholder="회사명·키워드로 찾기  (예: 심텍, 수주, 증설)" autocomplete="off"></label>
      <nav class="pager" aria-label="주차 이동">{pager}</nav>
      <button type="button" id="wbtn" class="wbtn" aria-pressed="false">★ 관심 회사만 <span id="wn">0</span></button>
      <nav class="jump" aria-label="그룹 이동"><span>바로가기</span>{jump}</nav>
    </div>
    <p class="none" id="none" role="status" aria-live="polite" hidden></p>
    <div class="news-body">{cleaned}</div>"""
    script = """<script>
var q=document.getElementById('q'),n=document.getElementById('none'),body=document.querySelector('.news-body'),wbtn=document.getElementById('wbtn'),wn=document.getElementById('wn');
var W=[],watchOnly=false;try{W=JSON.parse(localStorage.getItem('watch')||'[]')}catch(e){}
function save(){try{localStorage.setItem('watch',JSON.stringify(W))}catch(e){}}
function dataRows(){return Array.prototype.filter.call(body.querySelectorAll('table tr'),function(r){return !r.querySelector('th')&&!r.querySelector('td[colspan]')});}
// 회사 이름 옆에 관심 표시(★) 버튼: 이 브라우저에만 저장된다
dataRows().forEach(function(r){var b=r.querySelector('td b');if(!b)return;var name=b.textContent.trim();r.setAttribute('data-co',name);
  var btn=document.createElement('button');btn.type='button';btn.className='star';
  function paint(){var on=W.indexOf(name)>-1;btn.textContent=on?'\u2605':'\u2606';btn.setAttribute('aria-pressed',on?'true':'false');btn.setAttribute('aria-label',name+(on?' \uad00\uc2ec \ud68c\uc0ac \ud574\uc81c':' \uad00\uc2ec \ud68c\uc0ac\ub85c \ucd94\uac00'));}
  btn.onclick=function(){var i=W.indexOf(name);if(i>-1)W.splice(i,1);else W.push(name);save();document.querySelectorAll('.star').forEach(function(x){x.onpaint&&x.onpaint()});paint();wn.textContent=W.length;run();};
  btn.onpaint=paint;paint();b.parentNode.insertBefore(btn,b);});
wn.textContent=W.length;
wbtn.addEventListener('click',function(){watchOnly=!watchOnly;wbtn.setAttribute('aria-pressed',watchOnly?'true':'false');run();});
function run(){
  var v=q.value.trim().toLowerCase(),c=0;
  body.querySelectorAll('table tr').forEach(function(r){if(r.querySelector('th'))return;
    var q1=!v||r.textContent.toLowerCase().indexOf(v)>-1,w1=!watchOnly||(r.getAttribute('data-co')&&W.indexOf(r.getAttribute('data-co'))>-1);
    var ok=q1&&w1;r.style.display=ok?'':'none';if(ok&&!r.querySelector('td[colspan]'))c++;});
  var filtering=!!v||watchOnly;
  // 결과가 없는 그룹은 제목·표 머리까지 숨기고, 걸러 보는 중에는 요약 블록도 접는다
  body.querySelectorAll('h2').forEach(function(h){var t=h.nextElementSibling;while(t&&t.tagName!=='TABLE'&&t.tagName!=='H2')t=t.nextElementSibling;
    var show=!filtering||(t&&t.tagName==='TABLE'&&Array.prototype.some.call(t.querySelectorAll('tr'),function(r){return !r.querySelector('th')&&r.style.display!=='none'}));
    h.style.display=show?'':'none';if(t&&t.tagName==='TABLE')t.style.display=show?'':'none';});
  Array.prototype.forEach.call(body.children,function(el){if(el.tagName!=='H2'&&el.tagName!=='TABLE'&&!el.matches('div[style*="font-size:11px"]'))el.style.display=filtering?'none':'';});
  n.hidden=!filtering;
  var label=(v?'\u201c'+q.value.trim()+'\u201d ':'')+(watchOnly?'(\uad00\uc2ec \ud68c\uc0ac) ':'');
  n.textContent=filtering?(c?label+c+'\uacf3\uc5d0\uc11c \ucc3e\uc558\uc2b5\ub2c8\ub2e4.':(watchOnly&&!v&&!W.length?'\ud68c\uc0ac \uc774\ub984 \uc606\uc758 \u2606\ub97c \ub20c\ub7ec \uad00\uc2ec \ud68c\uc0ac\ub97c \ucd94\uac00\ud558\uc138\uc694.':label+'\uc774 \uc8fc\ucc28\uc5d0 \uc5c6\uc2b5\ub2c8\ub2e4. \ub2e4\ub978 \uc8fc\ucc28\ub3c4 \ucc3e\uc544\ubcf4\uc138\uc694.')):'';
  try{history.replaceState(null,'',v?'#q='+encodeURIComponent(q.value.trim()):location.pathname)}catch(e){}
}
q.addEventListener('input',run);
q.addEventListener('keydown',function(e){if(e.key==='Escape'){q.value='';run();}});
var m=location.hash.match(/^#q=(.*)$/);if(m){q.value=decodeURIComponent(m[1]);run();}
</script>"""
    (NEWS_DIR / f"{k}.html").write_text(
        _layout(prefix="../", title=f"{d:%m/%d} 주간 동향 · 소부장 주간 동향", main=main, script=script, nav='<a href="../index.html">전체 주차</a>'),
        encoding="utf-8",
    )


def _write_index(meta: dict) -> None:
    keys = sorted(meta, reverse=True)
    if not keys:
        return
    latest = keys[0]
    ls = meta[latest]
    ld = date.fromisoformat(latest)

    def heads(s, n=3):
        return "".join(
            f'<li><span class="cat">{escape(h["cat"])}</span><b>{escape(h["company"])}</b> '
            f'<a href="{escape(h["link"])}" target="_blank" rel="noopener">{escape(h["title"])}</a></li>'
            for h in s["highlights"][:n]
        )

    feature = f"""
    <section class="feature" aria-labelledby="latest">
      <p class="kicker">최신 · {ld.year}.{ld.month:02d}.{ld.day:02d}({WEEKDAY[ld.weekday()]}) 발행</p>
      <h1 id="latest"><a href="news/{latest}.html">이번 주 소식 <em>{ls['fresh_news']}</em>건</a></h1>
      <p class="sub">1~4그룹 {ls['total']}곳 기준 · 공시 {ls['fresh_dart']}건 포함 · 소식이 있는 회사 {ls['fresh_companies']}곳</p>
      <ul class="heads">{heads(ls)}</ul>
      <p><a class="go" href="news/{latest}.html">이 주 전체 보기 →</a></p>
    </section>"""

    months = sorted({k[:7] for k in keys}, reverse=True)
    groups = []
    for m in months:
        rows = []
        for k in [k for k in keys if k[:7] == m and k != latest]:
            d, s = date.fromisoformat(k), meta[k]
            rows.append(
                f'<li class="row"><a class="date" href="news/{k}.html"><span class="d">{d.month}.{d.day:02d}</span>'
                f'<span class="w">{WEEKDAY[d.weekday()]}</span></a>'
                f'<ul class="heads">{heads(s, 2)}</ul>'
                f'<p class="count"><b>{s["fresh_news"]}</b>건<br><span>{s["fresh_companies"]}/{s["total"]}곳</span></p></li>'
            )
        if rows:
            groups.append(f'<section class="month" id="m{m}"><h2>{int(m[5:])}월</h2><ol class="rows">{"".join(rows)}</ol></section>')
    toc = "".join(f'<a href="#m{m}">{int(m[5:])}월</a>' for m in months)
    main = f"""{feature}
    <nav class="toc" aria-label="월 바로가기"><span>지난 주차</span>{toc}</nav>
    {"".join(groups)}"""
    (SITE_DIR / "index.html").write_text(_layout(prefix="", title="소부장 주간 동향", main=main), encoding="utf-8")


NEWS_CSS = """/* 디자인 기준: DESIGN.md */
@font-face{font-family:"Pretendard Variable";font-weight:45 920;font-display:swap;src:local("Pretendard Variable"),url("vendor/pretendard/PretendardVariable.woff2") format("woff2-variations")}
:root{--paper:#f6f4ee;--ink:#17191c;--sub:#5d6168;--dim:#6b6f76;--rule:#d8d3c6;--cu:#a8480f;--up:#d0342c;--down:#2a62c4}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.6 "Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;font-variant-numeric:tabular-nums;word-break:keep-all}
a{color:inherit;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:#b8b2a2}
a:hover{text-decoration-color:var(--cu);color:var(--cu)}
a:focus-visible,input:focus-visible{outline:2px solid var(--cu);outline-offset:2px}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
.sr,.skip:not(:focus){position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip:focus{position:fixed;top:8px;left:8px;background:var(--ink);color:#fff;padding:8px 12px;z-index:9}
/* 마스트헤드 */
.mast{border-top:4px solid var(--ink);border-bottom:1px solid var(--ink)}
.mast-row{display:flex;justify-content:space-between;align-items:baseline;gap:16px;padding-top:14px;padding-bottom:12px}
.mast-name{font-size:20px;font-weight:800;letter-spacing:-.02em;text-decoration:none}
.mast-nav{display:flex;gap:18px;font-size:14px}
.mast-nav a{display:inline-block;padding:10px 0;text-decoration:none;color:var(--sub)}.mast-nav a:hover{color:var(--cu)}
/* 머리말 */
.kicker{margin:36px 0 8px;font-size:14px;font-weight:600;color:var(--cu);letter-spacing:.01em}
h1{margin:0;font-size:clamp(34px,6vw,56px);line-height:1.12;font-weight:800;letter-spacing:-.035em}
h1 em{font-style:normal;color:var(--cu)}
h1 a{text-decoration:none}h1 a:hover{color:inherit}
.sub{margin:12px 0 0;font-size:17px;color:var(--sub)}
/* 최신 주차 */
.feature{padding-bottom:28px;border-bottom:2px solid var(--ink)}
.heads{list-style:none;margin:22px 0 0;padding:0}
.heads li{display:flex;gap:10px;align-items:baseline;padding:9px 0;border-top:1px solid var(--rule);font-size:17px}
.heads li:first-child{border-top:0}
.feature .heads li{font-size:19px}
.cat{flex:none;min-width:4.6em;font-size:12px;font-weight:600;color:var(--sub);letter-spacing:.02em}
.heads b{flex:none;font-weight:800}
.go{display:inline-block;margin-top:14px;font-weight:600;color:var(--cu);text-decoration:none;border-bottom:2px solid var(--cu)}
.go:hover{color:var(--ink);border-color:var(--ink)}
/* 지난 주차 */
.toc{display:flex;gap:6px 18px;flex-wrap:wrap;align-items:baseline;margin:26px 0 0;padding:10px 0;border-bottom:1px solid var(--rule);font-size:15px}
.toc span{font-size:13px;color:var(--sub);margin-right:6px}
.toc a{display:inline-block;padding:10px 4px;text-decoration:none;font-weight:600}
.month{margin-top:30px}
.month h2{margin:0;padding-bottom:8px;border-bottom:2px solid var(--ink);font-size:22px;font-weight:800;letter-spacing:-.02em}
.rows{list-style:none;margin:0;padding:0}
.row{position:relative;display:grid;grid-template-columns:84px 1fr 92px;gap:0 18px;padding:14px 0;border-bottom:1px solid var(--rule);align-items:start}
.date{text-decoration:none;display:flex;flex-direction:column;line-height:1.1}
.date .d{font-size:26px;font-weight:800;letter-spacing:-.03em}
.date .w{font-size:12px;color:var(--sub);margin-top:4px}
.date:hover .d{color:var(--cu)}
.date::after{content:"";position:absolute;inset:0}
.row .heads a{position:relative;z-index:1}
.row .heads{margin:0}
.row .heads li{padding:3px 0;border:0;font-size:16px}
.count{margin:0;text-align:right;font-size:14px;color:var(--sub);line-height:1.35}
.count b{font-size:24px;font-weight:800;color:var(--ink);letter-spacing:-.02em}
.count span{font-size:12px}
/* 주차 페이지 */
.hero{padding-bottom:6px}
.tools{position:sticky;top:0;z-index:5;background:var(--paper);display:flex;flex-wrap:wrap;gap:6px 20px;justify-content:space-between;align-items:center;margin:22px 0 4px;padding:10px 0 6px;border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.jump{flex:1 0 100%;display:flex;flex-wrap:wrap;gap:0 4px;align-items:center;font-size:14px;font-weight:600}
.jump span{font-size:12px;font-weight:400;color:var(--sub);margin-right:8px}
.jump a{display:inline-block;padding:10px 8px;text-decoration:none}.jump a:hover{color:var(--cu)}
.search{flex:1 1 280px;max-width:440px}
.search input{width:100%;height:44px;padding:0 12px;border:1px solid #9b9686;border-radius:0;background:#fff;font:inherit;font-size:16px;color:var(--ink)}
.pager{display:flex;gap:18px;font-size:14px;font-weight:600}
.pager a,.pager span{display:inline-block;padding:11px 0}.pager a{text-decoration:none}.pager a:hover{color:var(--cu)}.pager span{color:var(--dim)}
.none{margin:14px 0;color:var(--sub)}
.wbtn{height:44px;padding:0 14px;border:1px solid #9b9686;background:#fff;color:var(--ink);font:inherit;font-size:14px;font-weight:600;cursor:pointer}
.wbtn[aria-pressed="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
.star{border:0;background:transparent;color:var(--cu);font-size:18px;line-height:1;padding:6px 6px 6px 0;margin:-6px 0;cursor:pointer;vertical-align:middle;min-width:28px;min-height:36px}
.star:focus-visible,.wbtn:focus-visible{outline:2px solid var(--cu);outline-offset:2px}
html{scroll-padding-top:120px}
/* 본문(뉴스레터 HTML 재서식: 인라인 서식을 이 사이트 기준으로 덮어쓴다) */
.news-body{margin-top:8px;font-size:15px;max-width:none!important}
.news-body *{font-family:inherit!important}
.news-body div[style*="max-width:1000px"]{max-width:none!important}
.news-body div[style*="border-radius:8px"]{border:0!important;border-top:2px solid var(--ink)!important;border-radius:0!important;background:transparent!important;padding:14px 0 6px!important;margin:18px 0 6px!important}
.news-body div[style*="font-weight:bold"]{font-size:14px!important;color:var(--cu);letter-spacing:.02em}
.news-body h2{border:0!important;border-top:2px solid var(--ink)!important;padding:12px 0 0!important;margin:34px 0 4px!important;font-size:21px!important;font-weight:800!important;letter-spacing:-.02em}
.news-body table{border:0!important;border-collapse:collapse!important;width:100%;margin-bottom:8px!important}
.news-body th,.news-body td{border:0!important;border-top:1px solid var(--rule)!important;padding:12px 10px 12px 0!important;vertical-align:top;background:transparent!important}
.news-body tr{background:transparent!important}
.news-body th{font-size:12px!important;font-weight:600!important;color:var(--sub);text-align:left!important;letter-spacing:.02em;border-top:1px solid var(--ink)!important;padding:8px 10px 8px 0!important}
.news-body td{line-height:1.7}
.news-body td:first-child{width:19%;min-width:110px}
.news-body td b{font-weight:700}
.news-body td[colspan]{color:var(--sub)!important}
.news-body a[style*="#f04452"]{color:var(--cu)!important}
.news-body a[style*="#3182f6"]{color:var(--ink)!important}
.news-body a[style*="#8b95a1"]{color:var(--dim)!important}
.news-body a{text-decoration:underline!important;text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:#c9c3b4}
.news-body span[style*="background:#f2f4f6"]{background:transparent!important;color:var(--sub)!important;padding:0!important;margin-right:4px;font-size:11px!important;font-weight:600;letter-spacing:.02em;border-left:2px solid #9b9686;padding-left:6px!important}
.news-body span[style*="background:#e8f3ff"]{background:transparent!important;border:0!important;color:var(--sub)!important;font-weight:600;padding:0!important;border-left:2px solid var(--ink)!important;padding-left:6px!important}
.news-body [style*="color:#8b95a1"],.news-body [style*="color:#6b7684"],.news-body [style*="color:#b0b8c1"]{color:var(--sub)!important}
.news-body font[color="#8b95a1"]{color:var(--sub)!important}
.news-body font[color="#4e5968"]{color:var(--sub)!important}
.news-body [style*="font-size:10px"],.news-body [style*="font-size:11px"],.news-body font[size="1"]{font-size:12px!important}
.news-body font[color="#f04452"],.news-body span[style*="color:#f04452"]{color:var(--up)!important}
.news-body font[color="#3182f6"],.news-body span[style*="color:#3182f6"]{color:var(--down)!important}
.news-body b[style*="color:#f04452"],.news-body b[style*="color:#3182f6"]{color:var(--ink)!important}
.news-body div[style*="margin:0 0 7px"] span[style*="font-size:12px"]{white-space:nowrap}
/* 1~4그룹 회사 칸: 종가·등락을 한 줄로 이어 쓰고, 관련기사 줄은 접는다 */
.news-body td:first-child div[style*="font-size"] br{display:none}
.news-body td:first-child div[style*="font-size"] span{margin-left:6px}
.news-body td:first-child a{display:inline-block;padding:4px 0}
.news-body span:has(>a[style*="color:#6b7684"]){display:none}
.news-body td a{padding:2px 0}
/* 대시보드 */
.dash-filters{position:sticky;top:0;z-index:5;background:var(--paper);display:flex;flex-wrap:wrap;gap:10px 12px;align-items:center;margin:22px 0 0;padding:10px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.dash-filters select{height:44px;padding:0 10px;border:1px solid #9b9686;border-radius:0;background:#fff;font:inherit;font-size:15px;color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0;min-height:4px}
.chip{border:1px solid var(--ink);background:var(--ink);color:#fff;font:inherit;font-size:14px;padding:6px 10px;cursor:pointer}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin:22px 0 0;border-top:2px solid var(--ink);border-bottom:1px solid var(--rule)}
.kpi{padding:14px 16px 14px 0;display:flex;flex-direction:column;gap:2px}
.kpi+.kpi{padding-left:16px;border-left:1px solid var(--rule)}
.kpi-l{font-size:13px;color:var(--sub)}
.kpi b{font-size:34px;font-weight:800;letter-spacing:-.03em;line-height:1.1}
.kpi-wide b{font-size:24px;line-height:1.35}
.kpi-u{font-size:13px;color:var(--sub)}
.panel{margin-top:34px}
.panel h2{margin:0;padding-bottom:8px;border-bottom:2px solid var(--ink);font-size:20px;font-weight:800;letter-spacing:-.02em}
.panel-sub{font-size:13px;font-weight:400;color:var(--sub);letter-spacing:0;margin:8px 0 0}
.panel-row{display:grid;grid-template-columns:1fr 1fr;gap:0 36px}
.chart{margin-top:12px;width:100%;overflow:hidden}
.chart svg{display:block}
.chart .grid{stroke:var(--rule);stroke-width:1}
.chart .ax{font-size:12px;fill:var(--sub)}
.chart .bar{fill:var(--cu)}
.chart .bar.on{fill:var(--ink)}
.chart .hit{cursor:pointer}.chart .hit:hover .bar{fill:#7f350b}
.hbars{margin-top:8px}
.hb{display:grid;grid-template-columns:minmax(84px,30%) 1fr 44px;gap:10px;align-items:center;width:100%;min-height:36px;padding:4px 0;border:0;border-bottom:1px solid var(--rule);background:transparent;font:inherit;font-size:15px;color:var(--ink);text-align:left;cursor:pointer}
.hb:hover .hb-b{background:#7f350b}
.hb.on{font-weight:700}.hb.on .hb-b{background:var(--ink)}
.hb-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-t{height:10px;background:transparent}
.hb-b{display:block;height:10px;background:var(--cu);border-radius:0 4px 4px 0;min-width:2px}
.hb-v{text-align:right;font-weight:600}
.hb:focus-visible,.chip:focus-visible,.dash-filters select:focus-visible{outline:2px solid var(--cu);outline-offset:2px}
.list{width:100%;border-collapse:collapse;margin-top:6px;font-size:15px}
.list th{text-align:left;font-size:12px;font-weight:600;color:var(--sub);padding:8px 10px 8px 0;border-bottom:1px solid var(--ink)}
.list td{padding:10px 10px 10px 0;border-bottom:1px solid var(--rule);vertical-align:top;line-height:1.55}
.list .nw{white-space:nowrap}.list .cat,.list .src{font-size:13px;color:var(--sub)}
.tip{position:fixed;z-index:20;pointer-events:none;background:var(--ink);color:#fff;font-size:13px;line-height:1.45;padding:6px 9px}
/* 바닥글 */
.foot{margin-top:56px;border-top:1px solid var(--ink);padding:18px 0 40px;font-size:13px;color:var(--sub)}
.foot p{margin:0 0 4px}
/* 모바일 */
@media (max-width:640px){
  body{font-size:16px}
  .wrap{padding:0 16px}
  .kicker{margin-top:26px}
  .row{grid-template-columns:62px 1fr;gap:0 12px}
  .count{grid-column:2;text-align:left;margin-top:6px;display:flex;gap:6px;align-items:baseline}
  .count br{display:none}
  .date .d{font-size:22px}
  .heads li{flex-wrap:wrap;gap:2px 8px;font-size:16px}
  .cat{min-width:0}
  .news-body td:first-child{width:27%;min-width:84px}
  .news-body th,.news-body td{padding:10px 8px 10px 0!important}
  .pager{width:100%;justify-content:space-between}
  .kpis{grid-template-columns:1fr 1fr}
  .kpi:nth-child(3){padding-left:0;border-left:0}
  .kpi:nth-child(n+3){border-top:1px solid var(--rule)}
  .panel-row{grid-template-columns:1fr}
  .list th:nth-child(5),.list td:nth-child(5),.list th:nth-child(3),.list td:nth-child(3){display:none}
  .dash-filters select{flex:1 1 40%}
  .list{table-layout:fixed}
  .list td{overflow-wrap:anywhere}
  .list th:nth-child(1),.list td:nth-child(1){width:46px}
  .list th:nth-child(2),.list td:nth-child(2){width:30%;white-space:normal}
  .news-body td:nth-child(3){max-width:92px;overflow-wrap:anywhere}
  .news-body td:nth-child(4){max-width:64px;overflow-wrap:anywhere}
  .news-body th:nth-child(n+3){width:auto!important}
}
"""
