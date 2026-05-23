"""
Журнал прогресса (posts/progress.json):
- cycle_position: 1..5 (после 5 сбрасывается в 1)
- content_plan_index: индекс следующей строки контент-плана (0-based)
- history: история последних публикаций
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = REPO_ROOT / "posts" / "progress.json"
CONTENT_PLAN_PATH = REPO_ROOT / "content_plan.json"


def load_progress() -> dict:
    if not PROGRESS_PATH.exists():
        return {
            "cycle_position": 1,
            "content_plan_index": 0,
            "history": [],
        }
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def save_progress(data: dict) -> None:
    PROGRESS_PATH.parent.mkdir(exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_content_plan() -> list:
    return json.loads(CONTENT_PLAN_PATH.read_text(encoding="utf-8"))["items"]


def recent_titles(progress: dict, days: int = 60) -> list:
    """Заголовки за последние N дней — для дедупликации тем."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for entry in progress.get("history", []):
        try:
            ts = datetime.fromisoformat(entry["date"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                out.append(entry.get("title", ""))
        except Exception:
            continue
    return out


def append_history(progress: dict, title: str, cycle_pos: int, topic_type: str, source_url: str = "") -> None:
    progress.setdefault("history", []).insert(0, {
        "date": datetime.now(timezone.utc).isoformat(),
        "cycle_position": cycle_pos,
        "topic_type": topic_type,  # "trend" или "content_plan"
        "title": title,
        "source_url": source_url,
    })
    # ограничиваем 500 записей
    progress["history"] = progress["history"][:500]


def advance_cycle(progress: dict, topic_type: str) -> None:
    """Двигаем счётчики после успешной публикации."""
    pos = progress.get("cycle_position", 1)
    progress["cycle_position"] = (pos % 5) + 1
    if topic_type == "content_plan":
        progress["content_plan_index"] = progress.get("content_plan_index", 0) + 1
