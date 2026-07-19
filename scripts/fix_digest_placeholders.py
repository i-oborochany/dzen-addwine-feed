"""
Пересобирает старые дайджесты — заменяет оставшиеся [[IMG_N]] в feed.xml
на реальные <figure><img> из соответствующей папки images/<slug>/.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io
import html_renderer

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"


def main():
    print("Читаю feed.xml...")
    feed = feed_io.read_feed()

    fixed_count = 0
    for item in feed.get("items", []):
        title = item.get("title", "")
        if not any(kw in title.lower() for kw in ["дайджест", "самое интересное", "события недели"]):
            continue

        html = item.get("content_html", "")
        if "[[IMG_" not in html:
            continue

        # определяем slug
        link = item.get("link", "")
        m = re.search(r"/posts/([^/]+)/?", link)
        if not m:
            continue
        slug = m.group(1)
        folder = IMAGES_DIR / slug
        if not folder.exists():
            print(f"⚠️  папка не найдена: {slug}")
            continue

        # собираем список URL картинок
        covers = sorted(folder.glob("cover-*.jpg"))
        image_urls = [f"images/{slug}/{c.name}" for c in covers]
        if not image_urls:
            print(f"⚠️  нет cover-*.jpg в {slug}")
            continue

        print(f"\n▶ {slug}")
        print(f"  картинок в папке: {len(image_urls)}")

        # заменяем плейсхолдеры (используем логику publisher.embed_images)
        import publisher
        new_html = publisher.embed_images(html, image_urls, "https://feed.addwine.ru")

        item["content_html"] = new_html
        fixed_count += 1
        remaining = re.findall(r"\[\[IMG_\d+\]\]", new_html)
        print(f"  ✅ обновлено. Оставшихся плейсхолдеров: {len(remaining)}")

    print(f"\n✅ обновлено дайджестов в feed.xml: {fixed_count}")

    print("\nСохраняем feed.xml...")
    feed_io.write_feed(feed["channel"], feed["items"])

    print("\nПересобираем HTML-страницы всех дайджестов...")
    html_renderer.rebuild_from_feed("https://feed.addwine.ru")
    print("✅ страницы дайджестов пересобраны")

    html_renderer.rebuild_index()
    print("✅ главная + категории пересобраны")

    return 0


if __name__ == "__main__":
    sys.exit(main())
