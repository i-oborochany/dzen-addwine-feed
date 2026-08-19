"""
Сохранение картинок в images/, добавление <item> в feed.xml (в формате Дзена),
обновление posts/published.json.
"""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import feed_io


ALT_BY_INDEX = {1: "обложка статьи", 2: "иллюстрация: проблема", 3: "иллюстрация: решение"}


def embed_images(html: str, image_urls: list, pages_base: str) -> str:
    """
    Подставляет картинки в плейсхолдеры [[IMG_N]] внутри html (N от 1 до 12).
    Используется как для статей с 3 картинками, так и для дайджестов с 5-7.
    """
    if not image_urls:
        return html

    def _figure(i: int) -> str:
        url = image_urls[i - 1] if i - 1 < len(image_urls) else image_urls[-1]
        if not url.startswith("http"):
            url = f"{pages_base}/{url}"
        alt = ALT_BY_INDEX.get(i, f"иллюстрация {i}")
        return f'<figure><img src="{url}" alt="{alt}"/></figure>'

    has_any = bool(re.search(r"\[\[IMG_\d+\]\]", html))
    if has_any:
        result = html
        # поддерживаем до 50 картинок — хватит для дайджестов с большим количеством статей
        for i in range(1, 51):
            result = re.sub(rf"<p>\s*\[\[IMG_{i}\]\]\s*</p>", _figure(i), result)
            result = re.sub(rf"\[\[IMG_{i}\]\]", _figure(i), result)
        # оставшиеся [[IMG_N]] (если Claude поставил > 50) заменим на последнюю картинку
        result = re.sub(r"<p>\s*\[\[IMG_\d+\]\]\s*</p>", _figure(len(image_urls)), result)
        result = re.sub(r"\[\[IMG_\d+\]\]", _figure(len(image_urls)), result)
        return result

    # fallback — одна обложка сверху
    return _figure(1) + html


REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_PATH = REPO_ROOT / "feed.xml"
IMAGES_DIR = REPO_ROOT / "images"
POSTS_DIR = REPO_ROOT / "posts"
PUBLISHED_LOG = POSTS_DIR / "published.json"


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
    data["posts"] = data["posts"][:500]
    PUBLISHED_LOG.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_images(images: list, slug: str) -> list:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_name = f"{date_str}-{slug}"
    folder = IMAGES_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    urls = []
    for i, img_bytes in enumerate(images, 1):
        fname = f"cover-{i}.jpg"
        (folder / fname).write_bytes(img_bytes)
        # WebP версия — сильно легче, ускоряет Core Web Vitals
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            webp_path = folder / f"cover-{i}.webp"
            im.save(webp_path, "WEBP", quality=82, method=6)
        except Exception as e:
            print(f"[publisher] WebP не создался (не критично): {e}")
        urls.append(f"images/{folder_name}/{fname}")
    return urls


def slugify(text: str, max_len: int = 75) -> str:
    """Транслит + обрез по границе слова (не посреди слова)."""
    text = text.lower()
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z",
        "и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
        "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch",
        "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    text = "".join(table.get(c, c) for c in text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) <= max_len:
        return text or "post"
    # обрезаем по границе слова
    cut = text[:max_len].rsplit("-", 1)[0]
    return cut or text[:max_len] or "post"


def add_to_feed(article: dict, image_urls: list, source_url: str, config: dict) -> None:
    """
    Добавляет новый <item> в feed.xml в формате Дзена.
    article: {title, lead, html}
    """
    pages_base = config["channel"]["pages_base_url"].rstrip("/")

    # slug
    m = re.search(r"images/([^/]+)/", image_urls[0])
    slug = m.group(1) if m else f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
    pub_date = datetime.now(timezone.utc)
    permalink = f"{pages_base}/posts/{slug}/"
    main_image_url = f"{pages_base}/{image_urls[0]}" if not image_urls[0].startswith("http") else image_urls[0]

    # подставляем картинки в плейсхолдеры
    full_html = embed_images(article["html"], image_urls, pages_base)

    # читаем существующий feed
    feed_data = feed_io.read_feed()
    if not feed_data["channel"]:
        feed_data["channel"] = {
            "title": config["channel"]["title"],
            "link": config["channel"]["link"],
            "description": config["channel"]["description"],
            "language": config["channel"]["language"],
        }

    # новый item
    new_item = {
        "title": article["title"],
        "link": permalink,
        "guid": permalink,
        "pub_date": pub_date,
        "description": article["lead"],
        "enclosure_url": main_image_url,
        "enclosure_type": "image/jpeg",
        "content_html": full_html,
    }

    # вставляем в начало списка
    feed_data["items"].insert(0, new_item)

    # сохраняем
    feed_io.write_feed(feed_data["channel"], feed_data["items"])

    # IndexNow НЕ пингуем здесь: страница появится на Pages только после git push.
    # Пинг делает отдельный шаг воркфлоу (scripts/ping_recent.py) после деплоя,
    # иначе Яндекс приходит раньше деплоя и получает 404.
    print(f"[publisher] IndexNow-пинг отложен до пост-деплой шага: {permalink}")

    # генерируем HTML-страницу статьи и обновляем главную
    try:
        import html_renderer
        article_for_html = {
            "title": article["title"],
            "lead": article["lead"],
            "html": full_html,
        }
        html_renderer.write_post(article_for_html, slug, image_urls, pub_date, pages_base, categories=article.get("categories", []))
        html_renderer.add_post(
            slug=slug,
            title=article["title"],
            lead=article["lead"],
            cover_url=main_image_url,
            published_at=pub_date.isoformat(),
            categories=article.get("categories", []),
        )
        html_renderer.rebuild_index()
    except Exception as e:
        print(f"[publisher] HTML-рендер упал (не критично): {e}")
