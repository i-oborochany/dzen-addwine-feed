"""
Чистый фикс: находит дайджест в feed.xml, ПОЛНОСТЬЮ удаляет все figure
и плейсхолдеры [[IMG_N]], затем расставляет картинки перед каждым <h3>.
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io
import publisher
import html_renderer
import sitemap_gen

PAGES_BASE = "https://feed.addwine.ru"
REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"


def main():
    data = feed_io.read_feed()
    items = data["items"]

    for it in items:
        title = it.get("title", "")
        title_low = title.lower()
        if not any(k in title_low for k in ("событи", "дайджест", "недел")):
            continue

        # выделяем slug
        m = re.search(r"/images/([^/]+)/", it.get("enclosure_url", ""))
        slug = m.group(1) if m else None
        if not slug:
            continue

        folder = IMAGES_DIR / slug
        if not folder.exists():
            print(f"Папка не найдена: {folder}")
            continue

        # все cover-N.jpg, отсортированы по номеру
        covers = sorted(
            [p.name for p in folder.iterdir() if p.name.startswith("cover-") and p.suffix == ".jpg"],
            key=lambda x: int(re.search(r"cover-(\d+)", x).group(1)),
        )
        image_urls = [f"images/{slug}/{c}" for c in covers]
        print(f"Дайджест: {title[:70]}")
        print(f"  slug: {slug}")
        print(f"  картинок в папке: {len(image_urls)}")

        html = it["content_html"]

        # 1. удаляем ВСЕ figure с img
        html = re.sub(
            r"<figure[^>]*>\s*<img[^>]*/?>\s*(?:<figcaption[^>]*>.*?</figcaption>)?\s*</figure>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # 2. удаляем все оставшиеся плейсхолдеры [[IMG_N]] (и их обёртки <p>)
        html = re.sub(r"<p>\s*\[\[IMG_\d+\]\]\s*</p>", "", html)
        html = re.sub(r"\[\[IMG_\d+\]\]", "", html)
        # 3. удаляем лишние пустые параграфы
        html = re.sub(r"<p>\s*</p>", "", html)
        html = re.sub(r"\n{3,}", "\n\n", html)

        # 4. перед каждым <h3> вставляем плейсхолдер по порядку
        counter = [0]
        def _ins(m):
            counter[0] += 1
            return f"<p>[[IMG_{counter[0]}]]</p>\n{m.group(0)}"
        html = re.sub(r"<h3[^>]*>.*?</h3>", _ins, html, flags=re.DOTALL)
        print(f"  плейсхолдеров вставлено перед <h3>: {counter[0]}")

        # 5. вызываем embed_images — он подставит реальные пути
        new_html = publisher.embed_images(html, image_urls, PAGES_BASE)

        # проверка: остались ли необработанные плейсхолдеры
        leftover = re.findall(r"\[\[IMG_\d+\]\]", new_html)
        print(f"  необработанных плейсхолдеров: {len(leftover)}")
        # проверка: сколько figure в финальном HTML
        n_fig = new_html.count("<figure>")
        print(f"  figure в финальном HTML: {n_fig}")

        it["content_html"] = new_html
        break

    feed_io.write_feed(data["channel"], items)
    print("\nfeed.xml сохранён")

    html_renderer.rebuild_from_feed(PAGES_BASE)
    sitemap_gen.generate_all()
    print("страницы и sitemap обновлены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
