"""
Чтение/запись feed.xml в формате Дзена.
Используем ручную сборку XML — это даёт полный контроль над CDATA и порядком элементов.

Формат Дзена (https://dzen.ru/help/ru/website/rss-modify.html):
- content:encoded с CDATA
- Картинки в <figure> или <img>
- Допустимые теги: p, a, b, i, u, s, h1-h4, blockquote, ul/li, ol/li
- <category>format-article</category>, <category>comment-all</category>, <category>index</category>
- enclosure для обложки
"""
import re
from email.utils import format_datetime, parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_PATH = REPO_ROOT / "feed.xml"

# Допустимые теги для Дзена в content:encoded
ALLOWED_TAGS = {
    "p", "a", "b", "i", "u", "s",
    "h1", "h2", "h3", "h4",
    "blockquote",
    "ul", "ol", "li",
    "img", "figure", "figcaption",
}

TAG_REPLACEMENTS = {
    "strong": "b",
    "em": "i",
}


def sanitize_for_dzen(html: str) -> str:
    """
    Готовит HTML для content:encoded:
    - Заменяет strong→b, em→i
    - Удаляет <br>, <div>, <span>, инлайн-стили
    - Оборачивает <img> в <figure> где нужно
    - Удаляет атрибут style, class и др. лишние атрибуты
    """
    if not html:
        return ""

    # 1. Замена тегов: strong → b, em → i
    for old, new in TAG_REPLACEMENTS.items():
        html = re.sub(rf"<\s*{old}\s*>", f"<{new}>", html, flags=re.IGNORECASE)
        html = re.sub(rf"<\s*/\s*{old}\s*>", f"</{new}>", html, flags=re.IGNORECASE)

    # 2. Удалить <br>, <br/>, <br />
    html = re.sub(r"<\s*br\s*/?\s*>", "", html, flags=re.IGNORECASE)

    # 3. Удалить пустые <span> и <div> (оставив содержимое)
    html = re.sub(r"<\s*(span|div)[^>]*>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<\s*/\s*(span|div)\s*>", "", html, flags=re.IGNORECASE)

    # 4. Убрать атрибут style, class, id (кроме href, src, alt)
    def clean_attrs(m):
        tag = m.group(1).lower()
        attrs = m.group(2)
        # сохраняем только href, src, alt
        kept = []
        for a in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', attrs):
            name = a.group(1).lower()
            val = a.group(2)
            if name in ("href", "src", "alt"):
                kept.append(f'{name}="{val}"')
        kept_str = " " + " ".join(kept) if kept else ""
        if tag == "img":
            return f"<img{kept_str}/>"
        return f"<{tag}{kept_str}>"

    html = re.sub(r"<(\w+)([^>]*)>", clean_attrs, html)

    # 5. Картинки: <p><img.../></p> → <figure><img.../></figure>
    html = re.sub(
        r"<p>\s*<img([^>]*?)/?>\s*</p>",
        r"<figure><img\1/></figure>",
        html, flags=re.IGNORECASE
    )

    # 6. Чистим лишние пробелы и переводы строк
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = html.strip()

    return html


def _parse_pubdate(s: str) -> datetime:
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return datetime.now(timezone.utc)


def read_feed() -> dict:
    """Читает feed.xml. Возвращает {channel: {...}, items: [...]}.
    Совместим с обоими форматами: старым (yandex:full-text) и новым (content:encoded).
    """
    if not FEED_PATH.exists():
        return {"channel": {}, "items": []}

    NS = {
        "yandex": "http://news.yandex.ru",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "media": "http://search.yahoo.com/mrss/",
    }
    tree = ET.parse(str(FEED_PATH))
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        return {"channel": {}, "items": []}

    channel_meta = {
        "title": channel.findtext("title", ""),
        "link": channel.findtext("link", ""),
        "description": channel.findtext("description", ""),
        "language": channel.findtext("language", "ru"),
    }

    items = []
    for item in channel.findall("item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        guid = item.findtext("guid", link)
        pubdate = item.findtext("pubDate", "")
        description = item.findtext("description", "")

        enc = item.find("enclosure")
        enclosure_url = enc.get("url") if enc is not None else ""
        enclosure_type = enc.get("type", "image/jpeg") if enc is not None else "image/jpeg"

        # читаем контент: сначала yandex:full-text (старый), иначе content:encoded
        content = ""
        yandex_ft = item.find("yandex:full-text", NS)
        if yandex_ft is not None and yandex_ft.text:
            content = yandex_ft.text
        else:
            content_enc = item.find("content:encoded", NS)
            if content_enc is not None and content_enc.text:
                content = content_enc.text

        items.append({
            "title": title,
            "link": link,
            "guid": guid,
            "pub_date": _parse_pubdate(pubdate) if pubdate else datetime.now(timezone.utc),
            "description": description,
            "enclosure_url": enclosure_url,
            "enclosure_type": enclosure_type,
            "content_html": content,
        })

    return {"channel": channel_meta, "items": items}


def _esc(s: str) -> str:
    """Экранирование для XML-атрибутов и текста (без HTML внутри CDATA)."""
    if s is None:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def write_feed(channel: dict, items: list) -> None:
    """
    Сохраняет feed.xml в формате Дзена.
    Полностью соответствует примеру из https://dzen.ru/help/ru/website/rss-modify.html:
    - xmlns:content, xmlns:dc, xmlns:media, xmlns:atom
    - content:encoded с CDATA
    - figure/img внутри content
    - media:rating
    - одна category (format-article)
    """
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:media="http://search.yahoo.com/mrss/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">'
    )
    lines.append('  <channel>')
    lines.append(f'    <title>{_esc(channel.get("title", ""))}</title>')
    lines.append(f'    <link>{_esc(channel.get("link", ""))}</link>')
    lines.append(f'    <description>{_esc(channel.get("description", ""))}</description>')
    lines.append(f'    <language>{_esc(channel.get("language", "ru"))}</language>')
    lines.append('    <atom:link href="https://feed.addwine.ru/feed.xml" rel="self" type="application/rss+xml" />')

    for it in items:
        clean_html = sanitize_for_dzen(it.get("content_html", ""))
        pub = it.get("pub_date") or datetime.now(timezone.utc)
        if isinstance(pub, str):
            pub_str = pub
        else:
            pub_str = format_datetime(pub)

        lines.append('    <item>')
        lines.append(f'      <title>{_esc(it.get("title", ""))}</title>')
        lines.append(f'      <link>{_esc(it.get("link", ""))}</link>')
        lines.append(f'      <guid isPermaLink="true">{_esc(it.get("guid", it.get("link", "")))}</guid>')
        lines.append(f'      <pubDate>{_esc(pub_str)}</pubDate>')
        lines.append(f'      <description>{_esc(it.get("description", ""))}</description>')
        # ровно одна категория — тип публикации (Дзен в примере показывает только одну)
        lines.append('      <category>format-article</category>')
        # маркировка возрастного контента — обязательное поле из примера Дзена
        lines.append('      <media:rating scheme="urn:simple">nonadult</media:rating>')
        # обложка
        enc_url = it.get("enclosure_url", "")
        if enc_url:
            lines.append(f'      <enclosure url="{_esc(enc_url)}" type="{_esc(it.get("enclosure_type", "image/jpeg"))}" />')
        # полный текст с CDATA
        lines.append('      <content:encoded><![CDATA[')
        lines.append(clean_html)
        lines.append('      ]]></content:encoded>')
        lines.append('    </item>')

    lines.append('  </channel>')
    lines.append('</rss>')

    FEED_PATH.write_text("\n".join(lines), encoding="utf-8")
