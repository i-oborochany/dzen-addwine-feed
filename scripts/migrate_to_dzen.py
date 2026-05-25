"""
Одноразовый скрипт: конвертирует существующий feed.xml в формат Дзена.
- Парсит yandex:full-text
- Очищает HTML (figure/img, b/i, без div/span/br)
- Сохраняет через feed_io.write_feed (content:encoded + CDATA)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io
import html_renderer


def migrate():
    data = feed_io.read_feed()
    items = data["items"]
    channel = data["channel"]

    if not channel.get("title"):
        channel = {
            "title": "Журнал AddWine",
            "link": "https://dzen.ru/addwine",
            "description": "Новости и материалы о вине, виноделии и винной культуре",
            "language": "ru",
        }

    print(f"Найдено статей: {len(items)}")
    for it in items:
        print(f"  - {it['title'][:80]}")

    feed_io.write_feed(channel, items)
    print(f"\nfeed.xml сохранён в формате Дзена ({len(items)} статей)")

    # заодно пересоберём HTML-страницы и главную
    print("\nПерегенерируем страницы и главную ...")
    html_renderer.rebuild_from_feed("https://feed.addwine.ru")
    print("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
