"""
Одноразовый скрипт восстановления фида.

Проблема: с 14.08 по 19.08 воркфлоу не коммитили feed_full.json, из-за чего
новые статьи навсегда выпадали из feed.xml (фильтр 24ч отсеивал их на каждом ране).
Статьи существуют как HTML в posts/<slug>/ и в posts_index.json, но не в фиде.

Что делает:
1. Читает текущий фид (read_feed — fallback на feed.xml)
2. Находит статьи из posts_index.json которых нет в фиде
3. Для каждой достаёт body из posts/<slug>/index.html (div.post-body)
4. Собирает item и вставляет в правильное место по дате
5. write_feed → создаёт feed_full.json + отфильтрованный feed.xml
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feed_io

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
POSTS_DIR = REPO_ROOT / "posts"
SITE = "https://feed.addwine.ru"


def extract_body(slug: str) -> str:
    """Достаёт содержимое div.post-body из HTML-страницы статьи."""
    page = POSTS_DIR / slug / "index.html"
    if not page.exists():
        return ""
    html = page.read_text(encoding="utf-8")
    m = re.search(r'<div class="post-body">\s*(.*?)\s*</div>\s*<div class="post-signature">', html, flags=re.S)
    if not m:
        # без подписи (старый формат) — до закрытия article
        m = re.search(r'<div class="post-body">\s*(.*?)\s*</div>\s*</article>', html, flags=re.S)
    if not m:
        return ""
    body = m.group(1)
    # Разворачиваем <picture> в простой <img> (Дзен не понимает picture/source)
    body = re.sub(
        r'<picture>.*?<img([^>]*)>.*?</picture>',
        r'<img\1>',
        body, flags=re.S,
    )
    return body


def main():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    feed = feed_io.read_feed()
    items = feed["items"]

    existing_slugs = set()
    for it in items:
        m = re.search(r"/posts/([^/]+)/?", it.get("link", "") or it.get("guid", ""))
        if m:
            existing_slugs.add(m.group(1))

    print(f"В фиде: {len(items)} статей, в индексе: {len(posts)}")

    restored = 0
    for p in posts:
        slug = p.get("slug", "")
        if not slug or slug in existing_slugs:
            continue
        body = extract_body(slug)
        if not body:
            print(f"  [!] body не найден для {slug} — пропуск")
            continue

        pub_at = p.get("published_at", "")
        try:
            dt = datetime.fromisoformat(pub_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)

        cover = p.get("cover", "")
        if cover and not cover.startswith("http"):
            cover = f"{SITE}/{cover.lstrip('/')}"

        permalink = f"{SITE}/posts/{slug}/"
        item = {
            "title": p.get("title", ""),
            "link": permalink,
            "guid": permalink,
            "pub_date": dt,
            "description": p.get("lead", ""),
            "enclosure_url": cover,
            "enclosure_type": "image/jpeg",
            "content_html": body,
        }
        items.append(item)
        restored += 1
        print(f"  ✅ восстановлена: {pub_at[:10]}  {p.get('title','')[:60]}")

    if not restored:
        print("Нечего восстанавливать — фид полный")
        # Всё равно пересохраняем чтобы создать feed_full.json
        feed_io.write_feed(feed["channel"], items)
        return 0

    # Сортируем по дате, новые сверху
    def _key(it):
        pd = it.get("pub_date")
        if isinstance(pd, datetime):
            return pd.isoformat()
        try:
            return feed_io._parse_pubdate(str(pd)).isoformat()
        except Exception:
            return ""
    items.sort(key=_key, reverse=True)

    feed_io.write_feed(feed["channel"], items)
    print(f"\n=== Восстановлено {restored} статей. feed_full.json создан, feed.xml пересобран ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
