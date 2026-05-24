"""
Сохранение картинок в images/, добавление <item> в feed.xml,
обновление posts/published.json.
"""
import json
import os
import re as _re_top
import re
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET


ALT_BY_INDEX = {1: "обложка", 2: "иллюстрация: проблема", 3: "иллюстрация: решение", 4: "иллюстрация: финал"}


def embed_images(html: str, image_urls: list, pages_base: str) -> str:
    """
    Подставляет картинки в плейсхолдеры [[IMG_1]]..[[IMG_4]] внутри html.
    Если плейсхолдеров нет (старый формат) — fallback: обложка сверху, остальные снизу.
    """
    if not image_urls:
        return html

    def _img_tag(i: int) -> str:
        url = image_urls[i - 1] if i - 1 < len(image_urls) else image_urls[-1]
        if not url.startswith("http"):
            url = f"{pages_base}/{url}"
        alt = ALT_BY_INDEX.get(i, f"иллюстрация {i}")
        return f'<p><img src="{url}" alt="{alt}"/></p>'

    has_any_placeholder = bool(_re_top.search(r"\[\[IMG_[1-4]\]\]", html))
    if has_any_placeholder:
        # заменяем [[IMG_N]] (с обёрткой <p>...</p> или без) на тег картинки
        result = html
        for i in range(1, 5):
            ph_in_p = _re_top.compile(rf"<p>\s*\[\[IMG_{i}\]\]\s*</p>")
            result = ph_in_p.sub(_img_tag(i), result)
            ph_bare = _re_top.compile(rf"\[\[IMG_{i}\]\]")
            result = ph_bare.sub(_img_tag(i), result)
        return result

    # fallback: старая логика — обложка сверху, остальные снизу
    main_url = image_urls[0] if image_urls[0].startswith("http") else f"{pages_base}/{image_urls[0]}"
    top = f'<p><img src="{main_url}" alt="обложка"/></p>'
    extras = "".join(
        f'<p><img src="{u if u.startswith("http") else pages_base + "/" + u}" alt="иллюстрация {i+2}"/></p>'
        for i, u in enumerate(image_urls[1:])
    )
    return f"{top}{html}{extras}"

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_PATH = REPO_ROOT / "feed.xml"
IMAGES_DIR = REPO_ROOT / "images"
POSTS_DIR = REPO_ROOT / "posts"
PUBLISHED_LOG = POSTS_DIR / "published.json"

NSMAP = {
    "yandex": "http://news.yandex.ru",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def load_published() -> set:
    if not PUBLISHED_LOG.exists():
        return set()
    try:
        data = json.loads(PUBLISHED_LOG.read_text(encoding="utf-8"))
        return set(data.get("urls", []))
    except Exception:
        return set()


def mark_published(url: str, title: str) -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    if PUBLISHED_LOG.exists():
        data = json.loads(PUBLISHED_LOG.read_text(encoding="utf-8"))
    else:
        data = {"posts": [], "urls": []}
    data["urls"] = list(set(data.get("urls", []) + [url]))
    data["posts"].insert(0, {
        "url": url,
        "title": title,
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    # храним только последние 500 записей
    data["posts"] = data["posts"][:500]
    PUBLISHED_LOG.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_images(images: list, slug: str) -> list:
    """
    Сохраняет 4 картинки в images/<YYYY-MM-DD>-<slug>/.
    Возвращает список публичных URL.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_name = f"{date_str}-{slug}"
    folder = IMAGES_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    urls = []
    for i, img_bytes in enumerate(images, 1):
        fname = f"cover-{i}.jpg"
        (folder / fname).write_bytes(img_bytes)
        urls.append(f"images/{folder_name}/{fname}")
    return urls


def slugify(text: str) -> str:
    text = text.lower()
    # транслитерация
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z",
        "и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
        "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch",
        "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    text = "".join(table.get(c, c) for c in text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:50] or "post"


def add_to_feed(article: dict, image_urls: list, source_url: str, config: dict) -> None:
    """
    Добавляет новый <item> в feed.xml.
    article: {title, lead, html}
    image_urls: список из 4 относительных путей; первый идёт в <enclosure>,
                остальные вшиваем как <img> в начало <yandex:full-text>.
    """
    pages_base = config["channel"]["pages_base_url"].rstrip("/")

    # читаем существующий feed
    if FEED_PATH.exists():
        # регистрируем namespaces чтобы при записи они сохранились
        for prefix, uri in NSMAP.items():
            ET.register_namespace(prefix, uri)
        tree = ET.parse(str(FEED_PATH))
        rss = tree.getroot()
        channel = rss.find("channel")
    else:
        for prefix, uri in NSMAP.items():
            ET.register_namespace(prefix, uri)
        rss = ET.Element("rss", attrib={"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = config["channel"]["title"]
        ET.SubElement(channel, "link").text = config["channel"]["link"]
        ET.SubElement(channel, "description").text = config["channel"]["description"]
        ET.SubElement(channel, "language").text = config["channel"]["language"]
        tree = ET.ElementTree(rss)

    # slug — из имени папки с картинками (формат: YYYY-MM-DD-<title-slug>)
    import re as _re
    m = _re.search(r"images/([^/]+)/", image_urls[0])
    slug = m.group(1) if m else f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"

    pub_date = datetime.now(timezone.utc)

    # формируем item для RSS
    item = ET.Element("item")
    ET.SubElement(item, "title").text = article["title"]
    permalink = f"{pages_base}/posts/{slug}/"
    ET.SubElement(item, "link").text = permalink
    ET.SubElement(item, "guid", attrib={"isPermaLink": "true"}).text = permalink
    ET.SubElement(item, "pubDate").text = format_datetime(pub_date)
    ET.SubElement(item, "description").text = article["lead"]

    # главная картинка через <enclosure>
    main_image_url = f"{pages_base}/{image_urls[0]}"
    ET.SubElement(item, "enclosure", attrib={
        "url": main_image_url,
        "type": "image/jpeg",
    })

    # подставляем картинки в плейсхолдеры [[IMG_N]]
    full_html = embed_images(article["html"], image_urls, pages_base)

    full_text = ET.SubElement(item, "{http://news.yandex.ru}full-text")
    full_text.text = full_html

    # вставляем item в начало списка
    first_item = channel.find("item")
    if first_item is not None:
        children = list(channel)
        idx = children.index(first_item)
        channel.insert(idx, item)
    else:
        channel.append(item)

    tree.write(str(FEED_PATH), encoding="utf-8", xml_declaration=True)

    # генерируем HTML-страницу статьи и обновляем главную
    try:
        import html_renderer
        article_for_html = {
            "title": article["title"],
            "lead": article["lead"],
            "html": full_html,  # с включёнными картинками
        }
        html_renderer.write_post(article_for_html, slug, image_urls, pub_date, pages_base)
        html_renderer.add_post(
            slug=slug,
            title=article["title"],
            lead=article["lead"],
            cover_url=main_image_url,
            published_at=pub_date.isoformat(),
        )
        html_renderer.rebuild_index()
    except Exception as e:
        print(f"[publisher] HTML-рендер упал (не критично): {e}")
