"""주간 수집 결과를 공개 가능한 집계 정보로 보관하고 품질 페이지를 생성한다.

원문 기사·API 키·개별 수집 URL은 상태 페이지/JSON에 기록하지 않는다.
"""
import json
from datetime import datetime
from html import escape
from pathlib import Path

from src.config import ROOT_DIR

HISTORY_PATH = ROOT_DIR / "data" / "news_collection_health.json"
PUBLIC_DIR = ROOT_DIR / "site"

SOURCE_LABELS = {
    "dart": "DART 공시",
    "google": "Google News",
    "google_en": "Google News 영문",
    "naver": "Naver 공식 API",
    "naver_web": "Naver 웹 검색",
    "rss": "국내 언론사 RSS",
    "rss_global": "해외 반도체 전문매체 RSS",
}


def _load_history(path: Path) -> dict:
    if not path.exists():
        return {}
    history = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(history, dict):
        raise ValueError("수집 상태 이력 JSON 형식이 올바르지 않습니다")
    return history


def _week_key(now: datetime) -> str:
    from src.site import week_key
    return week_key(now.date()).isoformat()


def _source_rows(entry: dict) -> str:
    totals = entry["collector"].get("sources_by_kind", {})
    raw = entry["collector"].get("raw_by_kind", {})
    kept = entry["collector"].get("kept_by_kind", {})
    failed = entry["collector"].get("failed_by_kind", {})
    rows = []
    for kind, n in totals.items():
        errors = failed.get(kind, 0)
        label = escape(SOURCE_LABELS.get(kind, kind))
        rows.append(
            "<tr><td>" + label + "</td><td>" + str(n) +
            "</td><td>" + str(raw.get(kind, 0)) +
            "</td><td>" + str(kept.get(kind, 0)) +
            "</td><td>" + str(errors) + "</td></tr>"
        )
    return "".join(rows)


def _fmt_rate(part: int, total: int) -> str:
    return f"{part / total * 100:.1f}%" if total else "—"


def render_page(entry: dict, previous: dict | None = None) -> str:
    """사이트 공통 레이아웃을 유지한 품질 현황 화면. 수치는 실제 실행 결과만 표시한다."""
    from src.site import _layout
    collector = entry["collector"]
    ai = entry["ai"]
    total = collector.get("sources_total", 0)
    failed = collector.get("sources_failed", 0)
    eligible, analyzed = ai.get("eligible", 0), ai.get("analyzed", 0)
    state = "일부 소스 실패" if failed or ai.get("failed_batches", 0) else "수집 완료"
    ai_state = "AI 미사용·미검토" if eligible and not analyzed else "AI 분석 실행" if analyzed else "검토 대상 없음"
    prev_text = ""
    if previous:
        p = previous.get("collector", {})
        prev_text = (
            f'<p class="sub">이전 주차 ({escape(previous.get("week", ""))}) · '
            f'채택 {p.get("articles_kept", 0):,}건 · 최근 기사 확인 기업 {p.get("companies_fresh", 0)}곳</p>'
        )
    failed_notes = collector.get("failure_examples", [])
    notes = "".join(
        f'<li>{escape(SOURCE_LABELS.get(kind, str(kind)))}: {escape(str(reason))}</li>'
        for kind, reason in failed_notes
    ) or "<li>기록된 수집 오류 없음</li>"
    main = f"""
<section class="hero">
  <p class="kicker">DATA QUALITY · {escape(entry["generated_at"])}</p>
  <h1>뉴스 수집 품질</h1>
  <p class="sub">{escape(state)} · 대상 {collector.get("companies_total", 0)}곳 · {escape(ai_state)}</p>
  {prev_text}
</section>
<section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:18px 0">
  <div class="quality-card"><small>수집 요청 성공률</small><strong>{_fmt_rate(total - failed, total)}</strong><span>정상 {total - failed:,} / 전체 {total:,}</span></div>
  <div class="quality-card"><small>수집 및 채택</small><strong>{collector.get("articles_kept", 0):,}건</strong><span>중복·필터 적용 후 회사별 기사</span></div>
  <div class="quality-card"><small>최근 7일 기사 확인 기업</small><strong>{collector.get("companies_fresh", 0):,}곳</strong><span>전체 {collector.get("companies_total", 0):,}곳</span></div>
  <div class="quality-card"><small>AI 검토율</small><strong>{_fmt_rate(analyzed, eligible)}</strong><span>검토 {analyzed:,} / 후보 {eligible:,}</span></div>
</section>
<section class="quality-section">
<h2>수집 소스별 결과</h2>
<p class="sub">수집 요청 수·원본 기사 수·중복/필터 후 채택 수·실패 요청 수. 채택 건수는 중복 귀속 전후 기준에 따라 합계와 다를 수 있습니다.</p>
<div style="overflow-x:auto"><table class="quality-table"><thead><tr><th>소스</th><th>요청</th><th>원본</th><th>채택</th><th>실패</th></tr></thead>
<tbody>{_source_rows(entry)}</tbody></table></div>
</section>
<section class="quality-section">
<h2>AI 처리 및 예외</h2>
<p>후보 {eligible:,}건 · 선택 {ai.get("selected", 0):,}건 · 검토 {analyzed:,}건 · 미검토 {ai.get("unreviewed", 0):,}건 · 제외 {ai.get("dropped", 0):,}건 · 실패 배치 {ai.get("failed_batches", 0):,}회</p>
<h3>실패 사유 예시 (종류별, 최대 10개)</h3><ul>{notes}</ul>
</section>
<p class="sub">기준: 실제 GitHub Actions 실행 결과 · 기사 적합률은 수동 정답 검수 없이는 산출하지 않음 · 데이터 갱신은 다음 주간 실행 시 반영</p>
<style>
.quality-card{{border:1px solid #e5e8eb;border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:8px}}
.quality-card small{{color:#6b7684;font-size:12px}}.quality-card strong{{font-size:25px;font-weight:750}}.quality-card span{{color:#6b7684;font-size:11px}}
.quality-section{{margin-top:26px}}.quality-section h2{{font-size:17px;margin-bottom:7px}}
.quality-section h3{{font-size:13px}}.quality-section p,.quality-section li{{font-size:12px;line-height:1.7}}
.quality-table{{width:100%;border-collapse:collapse;font-size:12px;text-align:right}}
.quality-table th,.quality-table td{{padding:10px;border-bottom:1px solid #e5e8eb}}
.quality-table th:first-child,.quality-table td:first-child{{text-align:left}}
</style>
"""
    return _layout(prefix="", title="수집 품질 · 소부장 주간 동향", main=main, nav='<a href="index.html">전체 주차</a>')


def record_health(now: datetime, collector: dict, ai: dict, *, history_path: Path | None = None, site_dir: Path | None = None) -> dict:
    """발행 성공 후 주간 이력을 저장하고 정적 페이지/JSON을 만든다. 이전 주 데이터는 보존한다."""
    history_path = history_path or HISTORY_PATH
    site_dir = site_dir or PUBLIC_DIR
    week = _week_key(now)
    history = _load_history(history_path)
    previous_keys = sorted(k for k in history if k < week)
    previous = history[previous_keys[-1]] if previous_keys else None
    entry = {
        "week": week,
        "generated_at": now.isoformat(timespec="seconds"),
        "collector": dict(collector),
        "ai": dict(ai),
    }
    html = render_page(entry, previous)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)
    # HTML까지 먼저 생성한 뒤 저장해 JSON 단독 생성 같은 부분 갱신을 피한다.
    history_path.write_text(json.dumps({**history, week: entry}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (site_dir / "collection-health.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    (site_dir / "quality.html").write_text(html, encoding="utf-8")
    return entry
