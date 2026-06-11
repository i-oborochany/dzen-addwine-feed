"""Перегенерирует последнюю статью-дайджест с обновлённым embed_images."""
import sys, re
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io, publisher, html_renderer, sitemap_gen

PAGES_BASE = "https://feed.addwine.ru"

data = feed_io.read_feed()
items = data["items"]
print(f"Всего items: {len(items)}")

# находим дайджест (по title содержит "событи" "недел" или "дайджест")
for it in items:
    title = it.get("title", "").lower()
    if any(k in title for k in ("событи", "дайджест", "недел")):
        slug_m = re.search(r"/images/([^/]+)/", it.get("enclosure_url", ""))
        slug = slug_m.group(1) if slug_m else None
        if not slug:
            continue
        # собираем все cover-N.jpg для этой папки
        folder = Path("../images") / slug
        if not folder.exists():
            print(f"Папка не найдена: {folder}")
            continue
        covers = sorted([p.name for p in folder.iterdir() if p.name.startswith("cover-") and p.suffix == ".jpg"],
                        key=lambda x: int(re.search(r"cover-(\d+)", x).group(1)))
        image_urls = [f"images/{slug}/{c}" for c in covers]
        print(f"Дайджест: {it['title'][:60]}")
        print(f"  slug: {slug}, картинок: {len(image_urls)}")

        # вытаскиваем исходный HTML без figure (только текст и плейсхолдеры)
        # сначала удалим уже подставленные figure теги  
        clean = re.sub(r'<figure>\s*<img[^>]*/?\s*>\s*(?:<figcaption>[^<]*</figcaption>)?\s*</figure>', "", it["content_html"])
        # ищем плейсхолдеры — если их там нет, нужно вставить картинки по порядку перед каждым h3
        if "[[IMG_" not in clean:
            # вставляем перед каждым h3 в порядке
            counter = [0]
            def _replace_h3(m):
                counter[0] += 1
                return f"<p>[[IMG_{counter[0]}]]</p>\n{m.group(0)}"
            clean = re.sub(r"<h3[^>]*>.*?</h3>", _replace_h3, clean, flags=re.DOTALL)
        # подставляем картинки
        new_html = publisher.embed_images(clean, image_urls, PAGES_BASE)
        it["content_html"] = new_html
        break

feed_io.write_feed(data["channel"], items)
print("feed.xml сохранён")

html_renderer.rebuild_from_feed(PAGES_BASE)
sitemap_gen.generate_all()
print("страницы и sitemap обновлены")
