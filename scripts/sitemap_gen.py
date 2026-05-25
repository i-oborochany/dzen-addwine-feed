"""
Генерация sitemap.xml и robots.txt для feed.addwine.ru.
sitemap.xml перечисляет все статьи и главную, помогает Яндекс и Google индексировать.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_PATH = REPO_ROOT / "sitemap.xml"
ROBOTS_PATH = REPO_ROOT / "robots.txt"
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

SITE_URL = "https://feed.addwine.ru"


def _date_only(iso: str) -> str:
    try:
        return iso.split("T")[0]
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def generate_sitemap() -> None:
    """Создаёт sitemap.xml из posts_index.json."""
    posts = []
    if POSTS_INDEX.exists():
        try:
            posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
        except Exception:
            posts = []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # главная
    lines.append('  <url>')
    lines.append(f'    <loc>{SITE_URL}/</loc>')
    lines.append(f'    <lastmod>{today}</lastmod>')
    lines.append('    <changefreq>daily</changefreq>')
    lines.append('    <priority>1.0</priority>')
    lines.append('  </url>')

    # страницы статей
    for p in sorted(posts, key=lambda x: x.get("published_at", ""), reverse=True):
        slug = p.get("slug", "")
        if not slug:
            continue
        lastmod = _date_only(p.get("published_at", ""))
        lines.append('  <url>')
        lines.append(f'    <loc>{SITE_URL}/posts/{slug}/</loc>')
        lines.append(f'    <lastmod>{lastmod}</lastmod>')
        lines.append('    <changefreq>monthly</changefreq>')
        lines.append('    <priority>0.8</priority>')
        lines.append('  </url>')

    lines.append('</urlset>')
    SITEMAP_PATH.write_text("\n".join(lines), encoding="utf-8")


def generate_robots() -> None:
    """Создаёт robots.txt с указанием sitemap."""
    content = f"""User-agent: *
Allow: /

# Не индексируем технические файлы
Disallow: /posts/posts_index.json
Disallow: /posts/progress.json
Disallow: /posts/published.json

# Поисковые системы — добро пожаловать
User-agent: Yandex
Allow: /

User-agent: Googlebot
Allow: /

User-agent: YandexBot
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    ROBOTS_PATH.write_text(content, encoding="utf-8")


def generate_all() -> None:
    generate_sitemap()
    generate_robots()
