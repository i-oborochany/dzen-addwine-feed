"""
Релизер Дзен-фида. Запускается по крону каждые 3 часа.

Пересобирает feed.xml из feed_full.json: статьи, которым исполнилось 24 часа,
попадают в фид (и значит в Дзен) без ожидания следующей публикации.

Без этого статья ждала не 24ч, а «24ч + до следующей публикации» (до 2 суток).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io


def main():
    data = feed_io.read_feed()
    if not data.get("items"):
        print("[feed_release] хранилище пустое — нечего выпускать")
        return 0
    before = feed_io.FEED_PATH.read_text(encoding="utf-8") if feed_io.FEED_PATH.exists() else ""
    feed_io.write_feed(data["channel"], data["items"])
    after = feed_io.FEED_PATH.read_text(encoding="utf-8")
    if before == after:
        print("[feed_release] изменений нет (новых «созревших» статей не появилось)")
    else:
        print("[feed_release] ✅ feed.xml обновлён — созревшие статьи выпущены в Дзен")
    return 0


if __name__ == "__main__":
    sys.exit(main())
