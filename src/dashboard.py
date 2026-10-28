"""올해 기사 대시보드: 보관된 주차 본문(data/weeks/*.html)에서 기사를 모아 site/dashboard.html 을 만든다.

- 같은 기사가 여러 주차에 걸쳐 실려도(지난 소식 등) 한 번만 센다 (링크, 없으면 회사+제목 기준)
- 과거 주차에 섞여 있던 시황 기사·동명 오탐은 지금의 필터를 다시 적용해 뺀다
- 차트와 목록은 페이지 안의 데이터로 브라우저에서 그린다 (회사·분류·주차를 누르면 서로 걸러 보기)
"""
import html as H
import json
import re
from datetime import date

from src.config import ROOT_DIR
from src.newsletter_collector import (
    BLOCKED_LINK_RE,
    is_english_stock_news,
    is_false_positive,
    is_stock_or_analysis_news,
    normalize_title,
)
from src.newsletter_config import COMPANY_DISPLAY_NAME, TARGET_GROUPS

WEEKS_DIR = ROOT_DIR / "data" / "weeks"
SITE_DIR = ROOT_DIR / "site"

ARTICLE_RE = re.compile(r'<div style="margin:2px 0 7px">(.*?)</div>', re.S)
BADGE_RE = re.compile(r'<span style="font-size:10px[^>]*>([^<]+)</span>')
LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>(?:<b>)?(.*?)(?:</b>)?</a>', re.S)
META_RE = re.compile(r'<span style="font-size:11px;color:#8b95a1">([^<]*)</span>')
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
NAME_RE = re.compile(r"<td[^>]*>\s*<b[^>]*>(.*?)</b>", re.S)
GROUP_SPLIT_RE = re.compile(r"(?=<h3)")
FONT_RE = re.compile(r"<font[^>]*>(.*?)</font>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"(\d{2})-(\d{2})")
MORE_RE = re.compile(r"\s*외\s*\d+건\s*$")

GROUP_LABELS = [re.sub(r"\s*\(.*", "", g["group_name"]) for g in TARGET_GROUPS]


def _text(fragment: str) -> str:
    return H.unescape(TAG_RE.sub("", fragment)).strip()


def _company_index() -> dict:
    """표시 이름(약칭 포함) → (회사 풀네임, 그룹 번호)"""
    index = {}
    for gi, g in enumerate(TARGET_GROUPS):
        for c in g["companies"]:
            index[c] = (c, gi)
            index[COMPANY_DISPLAY_NAME.get(c, c)] = (c, gi)
    return index


def _article_date(mmdd: str, week: date):
    m = DATE_RE.search(mmdd or "")
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = week.year - 1 if month > week.month + 1 else week.year  # 1월 주차에 실린 12월 기사
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _keep(title: str, link: str, company: str) -> bool:
    if BLOCKED_LINK_RE.search(link):  # 원문 변환 전의 구글뉴스 링크도 기사로 연결되므로 남긴다
        return False
    if is_stock_or_analysis_news(title) or is_english_stock_news(title):
        return False
    return not is_false_positive(title, company)


def collect(year: int) -> list:
    """올해 기사 목록 → [{d, co, g, cat, t, u, s, w}] (최신순)"""
    index = _company_index()
    seen, rows = set(), []
    for path in sorted(WEEKS_DIR.glob("*.html")):
        week = date.fromisoformat(path.stem)
        body = path.read_text(encoding="utf-8")
        for block in GROUP_SPLIT_RE.split(body)[1:]:
            for row in ROW_RE.findall(block):
                if "<th" in row or "colspan" in row:
                    continue
                name_m = NAME_RE.search(row)
                if not name_m or _text(name_m.group(1)) not in index:
                    continue
                company, gi = index[_text(name_m.group(1))]
                items = []
                for art in ARTICLE_RE.findall(row):  # 1~4그룹: 기사 블록
                    link_m, badge_m, meta_m = LINK_RE.search(art), BADGE_RE.search(art), META_RE.search(art)
                    if not link_m or not meta_m:
                        continue  # '주요 소식에 게재' 참조 줄 등
                    source, _, when = meta_m.group(1).rpartition(" · ")
                    items.append((link_m.group(1), _text(link_m.group(2)), _text(badge_m.group(1)) if badge_m else "기타동향", source, when))
                if not items and "<font" in row:  # 5그룹: 회사 | 헤드라인 | 언론사·날짜 | 분류
                    link_m, fonts = LINK_RE.search(row), FONT_RE.findall(row)
                    if link_m and len(fonts) >= 2:
                        source, _, when = fonts[0].partition("<br>")
                        items.append((link_m.group(1), _text(link_m.group(2)), _text(fonts[1]), _text(source), _text(when)))
                for link, title, cat, source, when in items:
                    link = H.unescape(link)
                    d = _article_date(when, week)
                    if not d or d.year != year or not _keep(title, link, company):
                        continue
                    key = (company, normalize_title(title))
                    if link in seen or key in seen:
                        continue
                    seen.update((link, key))
                    rows.append(
                        {
                            "d": d.isoformat(),
                            "co": company,
                            "g": gi,
                            "cat": re.sub(r"^공시·?", "", cat) or "공시",
                            "dart": cat.startswith("공시"),
                            "t": title,
                            "u": link,
                            "s": MORE_RE.sub("", _text(source)),
                            "w": week.isoformat(),
                        }
                    )
    rows.sort(key=lambda r: (r["d"], r["w"]), reverse=True)
    return rows


def build(layout, year: int | None = None) -> None:
    """layout: site._layout (순환 import를 피하려고 인자로 받는다)"""
    weeks = sorted(p.stem for p in WEEKS_DIR.glob("*.html"))
    if not weeks:
        return
    year = year or date.fromisoformat(weeks[-1]).year
    rows = collect(year)
    data = json.dumps(
        {"rows": rows, "groups": GROUP_LABELS, "weeks": [w for w in weeks if w.startswith(str(year))], "total": sum(len(g["companies"]) for g in TARGET_GROUPS)},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    first = rows[-1]["d"] if rows else f"{year}-01-01"
    last = rows[0]["d"] if rows else weeks[-1]
    main = f"""
    <section class="hero">
      <p class="kicker">{year}년 누적 · {int(first[5:7])}/{int(first[8:])} ~ {int(last[5:7])}/{int(last[8:])}</p>
      <h1>올해 소식 <em id="k-total">{len(rows)}</em>건</h1>
      <p class="sub">매주 실린 기사를 한곳에 모았습니다. 같은 기사는 한 번만 세고, 시황·동명 오탐은 뺐습니다.</p>
    </section>
    <div class="dash-filters" role="search">
      <label class="search"><span class="sr">기사 검색</span><input id="f-q" type="search" placeholder="회사명·키워드로 찾기" autocomplete="off"></label>
      <label><span class="sr">그룹</span><select id="f-g"><option value="">전체 그룹</option></select></label>
      <label><span class="sr">분류</span><select id="f-cat"><option value="">전체 분류</option></select></label>
      <label><span class="sr">월</span><select id="f-m"><option value="">전체 월</option></select></label>
      <button type="button" id="f-reset" class="wbtn">초기화</button>
    </div>
    <p class="chips" id="chips" aria-live="polite"></p>
    <section class="kpis" aria-label="요약">
      <div class="kpi"><span class="kpi-l">기사</span><b id="k-n">0</b><span class="kpi-u">건</span></div>
      <div class="kpi"><span class="kpi-l">소식이 있었던 회사</span><b id="k-co">0</b><span class="kpi-u" id="k-co-u">곳</span></div>
      <div class="kpi"><span class="kpi-l">주 평균</span><b id="k-avg">0</b><span class="kpi-u">건 / 주</span></div>
      <div class="kpi kpi-wide"><span class="kpi-l">가장 많이 다뤄진 회사</span><b id="k-top">-</b><span class="kpi-u" id="k-top-n"></span></div>
    </section>
    <section class="panel">
      <h2>주차별 기사 수</h2>
      <p class="panel-sub">막대를 누르면 그 주차 기사만 봅니다.</p>
      <div class="chart" id="c-week" role="img" aria-label="주차별 기사 수 막대 그래프"></div>
    </section>
    <div class="panel-row">
      <section class="panel">
        <h2>분류별</h2>
        <div class="hbars" id="c-cat"></div>
      </section>
      <section class="panel">
        <h2>그룹별</h2>
        <div class="hbars" id="c-grp"></div>
      </section>
    </div>
    <section class="panel">
      <h2>기사가 많은 회사 <span class="panel-sub" id="top-n"></span></h2>
      <div class="hbars hbars-co" id="c-co"></div>
    </section>
    <section class="panel">
      <h2>전체 기사 <span class="panel-sub" id="list-n"></span></h2>
      <table class="list"><thead><tr><th scope="col">날짜</th><th scope="col">회사</th><th scope="col">분류</th><th scope="col">제목</th><th scope="col">언론사</th></tr></thead><tbody id="list"></tbody></table>
      <p><button type="button" id="more" class="wbtn" hidden>더 보기</button></p>
    </section>
    <div class="tip" id="tip" role="tooltip" hidden></div>"""
    script = "<script>var DATA=" + data + ";</script>\n<script>" + DASH_JS + "</script>"
    (SITE_DIR / "dashboard.html").write_text(
        layout(prefix="", title=f"{year}년 기사 대시보드 · 소부장 주간 동향", main=main, script=script, nav='<a href="index.html">전체 주차</a>'),
        encoding="utf-8",
    )


DASH_JS = r"""
(function(){
var R=DATA.rows,G=DATA.groups,f={q:'',g:'',cat:'',m:'',co:'',w:''},shown=100;
var $=function(id){return document.getElementById(id)};
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function count(list,key){var m={};list.forEach(function(r){var k=key(r);m[k]=(m[k]||0)+1});return m}
// 선택지
G.forEach(function(g,i){$('f-g').insertAdjacentHTML('beforeend','<option value="'+i+'">'+esc(g)+'</option>')});
Object.entries(count(R,function(r){return r.cat})).sort(function(a,b){return b[1]-a[1]}).forEach(function(e){$('f-cat').insertAdjacentHTML('beforeend','<option>'+esc(e[0])+'</option>')});
Object.keys(count(R,function(r){return r.d.slice(0,7)})).sort().reverse().forEach(function(m){$('f-m').insertAdjacentHTML('beforeend','<option value="'+m+'">'+(+m.slice(5))+'월</option>')});
function pass(r,skip){
  if(f.q){var v=f.q.toLowerCase();if((r.t+' '+r.co+' '+r.s).toLowerCase().indexOf(v)<0)return false}
  if(f.g!==''&&skip!=='g'&&String(r.g)!==f.g)return false;
  if(f.cat&&skip!=='cat'&&r.cat!==f.cat)return false;
  if(f.m&&r.d.slice(0,7)!==f.m)return false;
  if(f.co&&skip!=='co'&&r.co!==f.co)return false;
  if(f.w&&skip!=='w'&&r.w!==f.w)return false;
  return true}
// 툴팁
var tip=$('tip');
function showTip(e,html){tip.innerHTML=html;tip.hidden=false;var x=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-8),y=e.clientY-tip.offsetHeight-12;tip.style.left=x+'px';tip.style.top=(y<8?e.clientY+18:y)+'px'}
function hideTip(){tip.hidden=true}
function weekLabel(w){var d=new Date(w+'T00:00:00'),s=new Date(d-7*864e5);return (s.getMonth()+1)+'/'+s.getDate()+'~'+(d.getMonth()+1)+'/'+d.getDate()}
// 주차별 세로 막대 (한 계열이라 범례 없음, 선택한 주차만 잉크색)
function weekChart(list){
  var m=count(list,function(r){return r.w}),W=DATA.weeks,max=Math.max.apply(null,W.map(function(w){return m[w]||0}).concat([1]));
  var el=$('c-week'),wd=el.clientWidth||900,h=180,pad=28,bw=(wd-pad)/W.length,gap=Math.max(2,bw*.28);
  var ticks=[0,Math.ceil(max/2),max],svg='<svg width="'+wd+'" height="'+(h+24)+'" viewBox="0 0 '+wd+' '+(h+24)+'">';
  ticks.forEach(function(t){var y=h-(t/max)*(h-10);svg+='<line x1="'+pad+'" x2="'+wd+'" y1="'+y+'" y2="'+y+'" class="grid"/><text x="'+(pad-6)+'" y="'+(y+4)+'" class="ax" text-anchor="end">'+t+'</text>'});
  W.forEach(function(w,i){var v=m[w]||0,bh=v?Math.max(2,(v/max)*(h-10)):0,x=pad+i*bw+gap/2,y=h-bh,bwid=bw-gap,r=Math.min(4,bwid/2,bh);
    var cls=f.w===w?'bar on':'bar';
    var path=bh?'M'+x+','+h+'V'+(y+r)+'Q'+x+','+y+' '+(x+r)+','+y+'H'+(x+bwid-r)+'Q'+(x+bwid)+','+y+' '+(x+bwid)+','+(y+r)+'V'+h+'Z':'';
    svg+='<g class="hit" data-w="'+w+'" data-v="'+v+'"><rect x="'+(pad+i*bw)+'" y="0" width="'+bw+'" height="'+h+'" fill="transparent"/>'+(path?'<path d="'+path+'" class="'+cls+'"/>':'')+'</g>';
    var d=new Date(w+'T00:00:00');if(d.getDate()<=7)svg+='<text x="'+(pad+i*bw+bw/2)+'" y="'+(h+18)+'" class="ax" text-anchor="middle">'+(d.getMonth()+1)+'월</text>'});
  el.innerHTML=svg+'</svg>';
  el.querySelectorAll('.hit').forEach(function(g){
    g.addEventListener('mousemove',function(e){showTip(e,'<b>'+weekLabel(g.dataset.w)+'</b> 주<br>'+g.dataset.v+'건')});
    g.addEventListener('mouseleave',hideTip);
    g.addEventListener('click',function(){f.w=f.w===g.dataset.w?'':g.dataset.w;shown=100;render()})});
}
// 가로 막대 (값은 잉크색 글자, 막대는 한 색)
function hbars(id,entries,key,label,limit){
  var el=$(id),max=Math.max.apply(null,entries.map(function(e){return e[1]}).concat([1])),out='';
  entries.slice(0,limit||99).forEach(function(e){var on=f[key]===String(e[0]);
    out+='<button type="button" class="hb'+(on?' on':'')+'" data-k="'+esc(e[0])+'" aria-pressed="'+on+'"><span class="hb-l">'+esc(label(e[0]))+'</span><span class="hb-t"><span class="hb-b" style="width:'+(e[1]/max*100).toFixed(1)+'%"></span></span><span class="hb-v">'+e[1]+'</span></button>'});
  el.innerHTML=out||'<p class="panel-sub">해당하는 기사가 없습니다.</p>';
  el.querySelectorAll('.hb').forEach(function(b){b.addEventListener('click',function(){f[key]=f[key]===b.dataset.k?'':b.dataset.k;if(key==='g')$('f-g').value=f.g;if(key==='cat')$('f-cat').value=f.cat;shown=100;render()})});
}
function sorted(m){return Object.entries(m).sort(function(a,b){return b[1]-a[1]||(a[0]<b[0]?-1:1)})}
function render(){
  var list=R.filter(function(r){return pass(r)});
  $('k-n').textContent=list.length.toLocaleString();
  var cos=count(list,function(r){return r.co}),top=sorted(cos)[0];
  $('k-co').textContent=Object.keys(cos).length;$('k-co-u').textContent='곳 / '+DATA.total+'곳';
  var nw=Object.keys(count(list,function(r){return r.w})).length;$('k-avg').textContent=nw?Math.round(list.length/(f.w?1:DATA.weeks.length)):0;
  $('k-top').textContent=top?top[0]:'-';$('k-top-n').textContent=top?top[1]+'건':'';
  weekChart(R.filter(function(r){return pass(r,'w')}));
  hbars('c-cat',sorted(count(R.filter(function(r){return pass(r,'cat')}),function(r){return r.cat})),'cat',function(k){return k});
  hbars('c-grp',sorted(count(R.filter(function(r){return pass(r,'g')}),function(r){return r.g})),'g',function(k){return G[k]});
  var coE=sorted(count(R.filter(function(r){return pass(r,'co')}),function(r){return r.co}));
  $('top-n').textContent='상위 '+Math.min(20,coE.length)+'곳 · 누르면 그 회사 기사만';
  hbars('c-co',coE,'co',function(k){return k},20);
  // 선택 상태
  var chips=[];if(f.co)chips.push(['co',f.co]);if(f.w)chips.push(['w',weekLabel(f.w)+' 주']);
  $('chips').innerHTML=chips.map(function(c){return '<button type="button" class="chip" data-k="'+c[0]+'">'+esc(c[1])+' ✕</button>'}).join('');
  $('chips').querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){f[b.dataset.k]='';render()})});
  // 목록
  $('list-n').textContent=list.length.toLocaleString()+'건 · 최신순';
  $('list').innerHTML=list.slice(0,shown).map(function(r){return '<tr><td class="nw">'+r.d.slice(5).replace('-','.')+'</td><td class="nw"><b>'+esc(r.co)+'</b></td><td class="nw cat">'+esc(r.cat)+(r.dart?' · 공시':'')+'</td><td><a href="'+esc(r.u)+'" target="_blank" rel="noopener">'+esc(r.t)+'</a></td><td class="src">'+esc(r.s)+'</td></tr>'}).join('')||'<tr><td colspan="5" class="panel-sub">조건에 맞는 기사가 없습니다.</td></tr>';
  $('more').hidden=list.length<=shown;
}
$('f-q').addEventListener('input',function(){f.q=this.value.trim();shown=100;render()});
$('f-g').addEventListener('change',function(){f.g=this.value;shown=100;render()});
$('f-cat').addEventListener('change',function(){f.cat=this.value;shown=100;render()});
$('f-m').addEventListener('change',function(){f.m=this.value;shown=100;render()});
$('f-reset').addEventListener('click',function(){f={q:'',g:'',cat:'',m:'',co:'',w:''};['f-q','f-g','f-cat','f-m'].forEach(function(i){$(i).value=''});shown=100;render()});
$('more').addEventListener('click',function(){shown+=200;render()});
var rt;addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){weekChart(R.filter(function(r){return pass(r,'w')}))},150)});
render();
})();
"""
