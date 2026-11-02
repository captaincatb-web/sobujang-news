"""One-time or manual live RSS/Atom availability audit.

No API keys required. This probe does NOT mutate the public news site or archive.
Usage: python scripts/probe_news_sources.py --output /tmp/news_source_probe.json
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

from src.news_source_catalog import (
    COMPANY_OFFICIAL_RSS,
    GLOBAL_SEMICON_RSS,
    KOREAN_INDUSTRY_RSS,
)
from src.newsletter_collector import build_alias_map, find_companies

USER_AGENT = "Mozilla/5.0 (compatible; NewsFeedAudit/1.0)"
TIMEOUT = 16


# Alternative hostnames are diagnostics only; they are not automatically added
# to the public feed list without a successful parse.
ALTERNATIVE_IR = [
    ("Applied IR investor mirror", "https://investor.appliedmaterials.com/rss/news-releases.xml", "official", "어플라이드머티어리얼즈"),
    ("Applied IR investors mirror", "https://investors.appliedmaterials.com/rss/news-releases.xml", "official", "어플라이드머티어리얼즈"),
]


def catalog():
    return [(name, url, "domestic", "") for name, url in KOREAN_INDUSTRY_RSS] + [
        (name, url, "global", "") for name, url in GLOBAL_SEMICON_RSS
    ] + [(name, url, "official", company) for name, url, company in COMPANY_OFFICIAL_RSS]


def probe(item):
    name, url, kind, company = item
    record = {"name": name, "url": url, "kind": kind, "company": company,
              "status": "error", "http": None, "entries": 0, "match_count": 0, "examples": []}
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        record["http"] = response.status_code
        if not response.ok:
            record["reason"] = "HTTP " + str(response.status_code)
            return record
        parsed = feedparser.parse(response.content)
        record["entries"] = len(parsed.entries)
        if not parsed.entries:
            record["reason"] = "no RSS/Atom entries; response may be HTML or empty"
            return record
        aliases = build_alias_map()
        for entry in parsed.entries:
            title = entry.get("title", "")
            matches = find_companies(title, aliases)
            if matches:
                record["match_count"] += 1
                if len(record["examples"]) < 2:
                    record["examples"].append({"company": matches[:3], "title": title[:140]})
        record["status"] = "ok"
        record["format"] = parsed.version or "unknown"
        return record
    except requests.RequestException as exc:
        record["reason"] = type(exc).__name__
        return record
    except Exception as exc:
        record["reason"] = "probe_error:" + type(exc).__name__
        return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/news_source_probe.json")
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(probe, catalog()))
    successful = sum(r["status"] == "ok" for r in results)
    with ThreadPoolExecutor(max_workers=2) as executor:
        alternatives = list(executor.map(probe, ALTERNATIVE_IR))
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "sources_total": len(results), "sources_ok": successful,
              "sources_failed": len(results) - successful, "sources": results,
              "alternative_ir_candidates": alternatives}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print(f"[{r['status'].upper():5}] {r['kind']:8} {r['name'][:35]:35} HTTP={str(r['http']):4} "
              f"entries={r['entries']:3} matched={r['match_count']:2} "
              f"{r.get('reason','')}", flush=True)
        for example in r["examples"]:
            print(f"    MATCH: {example['company']}: {example['title']}")
    for candidate in alternatives:
        print(f"[ALTERNATIVE] {candidate['name']}: {candidate['status']} HTTP={candidate['http']} "
              f"entries={candidate['entries']} {candidate.get('reason', '')}")
    print(f"RESULT: {successful}/{len(results)} functioning RSS/Atom feeds. "
          f"Report saved to {dest}", flush=True)
    # This is a diagnostic job: source errors are reported, rather than hidden;
    # one unavailable provider does not break the whole regression workflow.


if __name__ == "__main__":
    main()
