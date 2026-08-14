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
# Полное хранилище всех статей (включая ещё не "выпущенные" в Дзен)
FEED_FULL_PATH = REPO_ROOT / "feed_full.json"

# Задержка публикации в Дзен: статья появляется в feed.xml только через N часов
# после публикации на поддомене. Так Яндекс считает первоисточником наш домен.
DZEN_DELAY_HOURS = 24

# Допустимые теги для Дзена в content:encoded
ALLOWED_TAGS = {
    "p", "a", "b", "i", "u", "s",
    "h1", "h2", "h3", "h4",
    "blockquote",
    "ul", "ol", "li",
    "img", "figure", "figcaption",
}

# Для тега <a> разрешаем атрибут href (теперь ссылки на addwine.ru разрешены)

TAG_REPLACEMENTS = {
    "strong": "b",
    "em": "i",
}


def remove_cta_blocks(html: str) -> str:
    """
    Удаляет только устаревший блок-заголовок 'AddWine рекомендует' (старый формат).
    Сами ссылки на addwine.ru и нативные упоминания ОСТАВЛЯЕМ — теперь они разрешены.
    """
    # Старый блок <h3>AddWine рекомендует</h3><p>...</p>
    html = re.sub(
        r'<h3>\s*AddWine\s*рекомендует\s*</h3>\s*<p>.*?</p>',
        '', html, flags=re.IGNORECASE | re.DOTALL
    )
    html = re.sub(
        r'<h3>[^<]*AddWine\s*рекоменд[^<]*</h3>\s*<p>.*?</p>',
        '', html, flags=re.IGNORECASE | re.DOTALL
    )
    return html


def add_figcaption(html: str) -> str:
    """
    Добавляет <figcaption> внутрь <figure>, если её нет.
    Берёт текст из alt атрибута img. Дзен рекомендует figure с figcaption.
    """
    def _fig_with_caption(m):
        inner = m.group(1)
        # уже есть figcaption?
        if 'figcaption' in inner.lower():
            return m.group(0)
        # берём alt из img
        alt_m = re.search(r'<img[^>]*alt="([^"]*)"', inner)
        alt = alt_m.group(1) if alt_m else ""
        if alt and alt not in ("обложка статьи", "иллюстрация: проблема", "иллюстрация: решение", "иллюстрация: финал"):
            return f'<figure>{inner}<figcaption>{alt}</figcaption></figure>'
        return f'<figure>{inner}</figure>'

    html = re.sub(r'<figure>(.*?)</figure>', _fig_with_caption, html, flags=re.IGNORECASE | re.DOTALL)
    return html


def sanitize_for_dzen(html: str) -> str:
    """
    Готовит HTML для content:encoded:
    - Удаляет CTA-блоки и ссылки на addwine.ru (требование Дзена)
    - Заменяет strong→b, em→i
    - Удаляет <br>, <div>, <span>, инлайн-стили
    - Оборачивает <img> в <figure> где нужно
    - Добавляет <figcaption> внутрь figure
    - Удаляет атрибут style, class и др. лишние атрибуты
    """
    if not html:
        return ""

    # 0. Убираем CTA-блоки и любые упоминания addwine.ru
    html = remove_cta_blocks(html)

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

    # 6. figcaption внутрь figure
    html = add_figcaption(html)

    # 7. Чистим лишние пробелы и переводы строк
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = html.strip()

    return html


def _parse_pubdate(s: str) -> datetime:
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return datetime.now(timezone.utc)


def read_feed() -> dict:
    """Читает полное хранилище статей. Возвращает {channel: {...}, items: [...]}.

    Приоритет: feed_full.json (полное хранилище, включая непроставленные в Дзен).
    Fallback: парсинг feed.xml (для обратной совместимости при первом запуске).
    """
    # 1. Полное хранилище
    if FEED_FULL_PATH.exists():
        try:
            import json as _json
            data = _json.loads(FEED_FULL_PATH.read_text(encoding="utf-8"))
            items = data.get("items", [])
            # pub_date хранится как RFC822-строка — оставляем как есть,
            # write_feed умеет работать со строками
            return {"channel": data.get("channel", {}), "items": items}
        except Exception as e:
            print(f"[feed_io] feed_full.json не читается ({e}), fallback на feed.xml")

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
    Сохраняет:
    1. feed_full.json — ПОЛНОЕ хранилище всех статей (для внутренних скриптов)
    2. feed.xml — фид для Дзена, куда попадают только статьи старше DZEN_DELAY_HOURS.
       Так поддомен становится первоисточником, а Дзен получает копию через сутки.

    Формат Дзена: https://dzen.ru/help/ru/website/rss-modify.html
    """
    import json as _json
    import os as _os

    # --- 1. Полное хранилище ---
    full_items = []
    for it in items:
        it2 = dict(it)
        pub = it2.get("pub_date")
        if isinstance(pub, datetime):
            it2["pub_date"] = format_datetime(pub)
        full_items.append(it2)
    FEED_FULL_PATH.write_text(
        _json.dumps({"channel": channel, "items": full_items}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # --- 2. Фильтр для Дзена: только статьи старше DZEN_DELAY_HOURS ---
    delay_h = float(_os.environ.get("DZEN_DELAY_HOURS", DZEN_DELAY_HOURS))
    now = datetime.now(timezone.utc)
    visible = []
    held = 0
    for it in full_items:
        try:
            dt = _parse_pubdate(it.get("pub_date", ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_h = (now - dt).total_seconds() / 3600
            if age_h >= delay_h:
                visible.append(it)
            else:
                held += 1
        except Exception:
            visible.append(it)
    if held:
        print(f"[feed_io] {held} стат. держим вне Дзен-фида (моложе {delay_h:.0f}ч) — выйдут при следующей пересборке")

    items = visible
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    # Полный набор namespace, как в примере Дзена
    lines.append(
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:media="http://search.yahoo.com/mrss/" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:georss="http://www.georss.org/georss">'
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
