import json
from datetime import datetime, timedelta, timezone

from src.config import HISTORY_MAX_DAYS, HISTORY_PATH, KST_OFFSET_HOURS

KST = timezone(timedelta(hours=KST_OFFSET_HOURS))


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {}
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2, sort_keys=True)


def prune(history: dict) -> dict:
    cutoff = datetime.now(KST) - timedelta(days=HISTORY_MAX_DAYS)
    kept = {}
    for link, sent_date in history.items():
        try:
            if datetime.strptime(sent_date, "%Y-%m-%d").replace(tzinfo=KST) >= cutoff:
                kept[link] = sent_date
        except ValueError:
            continue
    return kept
