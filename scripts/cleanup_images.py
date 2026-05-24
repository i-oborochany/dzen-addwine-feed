"""
Одноразовый cleanup: удаляет 2-3-4 картинки из всех статей.
- Удаляет <img src=".../cover-2.jpg"> (и cover-3, cover-4) из HTML
- Удаляет плейсхолдеры [[IMG_2]], [[IMG_3]], [[IMG_4]]
- Удаляет файлы cover-2.jpg, cover-3.jpg, cover-4.jpg с диска
- Сохраняет feed.xml
- Перегенерирует страницы статей и главную
"""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publisher
import html_renderer

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_PATH = REPO_ROOT / "feed.xml"
IMAGES_DIR = REPO_ROOT / "images"

NS = {"yandex": "http://news.yandex.ru"}
PAGES_BASE = "https://feed.addwine.ru"


def clean_html(html: str) -> str:
    """Убирает упоминания cover-2/3/4 и плейсхолдеры IMG_2/3/4 из html."""
    # <p>...<img src="...cover-N.jpg"...></p>
    html = re.sub(
        r'<p>\s*<img[^>]*src="[^"]*cover-[2-4]\.jpg[^"]*"[^>]*/?>\s*</p>',
        '', html, flags=re.IGNORECASE
    )
    # одинокие img
    html = re.sub(
        r'<img[^>]*src="[^"]*cover-[2-4]\.jpg[^"]*"[^>]*/?>',
        '', html, flags=re.IGNORECASE
    )
    # плейсхолдеры
    html = re.sub(r'<p>\s*\[\[IMG_[2-4]\]\]\s*</p>', '', html)
    html = re.sub(r'\[\[IMG_[2-4]\]\]', '', html)
    # убираем подряд идущие пустые строки
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html


def cleanup():
    if not FEED_PATH.exists():
        print("feed.xml не найден")
        return 1

    for prefix, uri in publisher.NSMAP.items():
        ET.register_namespace(prefix, uri)
    tree = ET.parse(str(FEED_PATH))
    root = tree.getroot()
    channel = root.find("channel")
    items = channel.findall("item")
    print(f"Найдено статей: {len(items)}")

    for idx, item in enumerate(items, 1):
        title = item.findtext("title", default="").strip()
        ft_el = item.find("yandex:full-text", NS)
        if ft_el is None or not ft_el.text:
            continue

        old_html = ft_el.text
        new_html = clean_html(old_html)
        if new_html != old_html:
            ft_el.text = new_html
            print(f"  [{idx}/{len(items)}] {title[:60]} — html почищен ({len(old_html) - len(new_html)} симв.)")
        else:
            print(f"  [{idx}/{len(items)}] {title[:60]} — нечего чистить")

    tree.write(str(FEED_PATH), encoding="utf-8", xml_declaration=True)
    print("\nfeed.xml сохранён")

    # удаляем файлы cover-2/3/4 в каждой папке images/<slug>
    if IMAGES_DIR.exists():
        deleted = 0
        for folder in IMAGES_DIR.iterdir():
            if not folder.is_dir():
                continue
            for n in (2, 3, 4):
                f = folder / f"cover-{n}.jpg"
                if f.exists():
                    f.unlink()
                    deleted += 1
        print(f"Удалено лишних картинок с диска: {deleted}")

    # перегенерируем
    print("\nПерегенерируем страницы и главную ...")
    html_renderer.rebuild_from_feed(PAGES_BASE)
    print("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(cleanup())
