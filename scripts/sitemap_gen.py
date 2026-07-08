"""
Генерация sitemap-index + sub-sitemaps + robots.txt для feed.addwine.ru.

Структура:
- /sitemap.xml — sitemap index (ссылается на два ниже)
- /sitemap-posts.xml — все статьи
- /sitemap-categories.xml — 14 страниц категорий + главная
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_INDEX = REPO_ROOT / "sitemap.xml"
SITEMAP_POSTS = REPO_ROOT / "sitemap-posts.xml"
SITEMAP_CATEGORIES = REPO_ROOT / "sitemap-categories.xml"
ROBOTS_PATH = REPO_ROOT / "robots.txt"
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

SITE_URL = "https://feed.addwine.ru"


def _date_only(iso: str) -> str:
    try:
        return iso.split("T")[0]
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_posts() -> list:
    if not POSTS_INDEX.exists():
        return []
    try:
        return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return []


def _load_categories() -> dict:
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from category_renderer import CATEGORIES_META
        return CATEGORIES_META
    except Exception:
        return {}


def generate_sitemap_posts() -> None:
    posts = _load_posts()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in sorted(posts, key=lambda x: x.get("published_at", ""), reverse=True):
        slug = p.get("slug", "")
        if not slug:
            continue
        lastmod = _date_only(p.get("published_at", ""))
        lines.extend([
            '  <url>',
            f'    <loc>{SITE_URL}/posts/{slug}/</loc>',
            f'    <lastmod>{lastmod}</lastmod>',
            '    <changefreq>monthly</changefreq>',
            '    <priority>0.8</priority>',
            '  </url>',
        ])
    lines.append('</urlset>')
    SITEMAP_POSTS.write_text("\n".join(lines), encoding="utf-8")


def generate_sitemap_categories() -> None:
    cats = _load_categories()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    # главная
    lines.extend([
        '  <url>',
        f'    <loc>{SITE_URL}/</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>1.0</priority>',
        '  </url>',
    ])

    # страницы категорий
    for cat_name, meta in cats.items():
        lines.extend([
            '  <url>',
            f'    <loc>{SITE_URL}/category/{meta["slug"]}/</loc>',
            f'    <lastmod>{today}</lastmod>',
            '    <changefreq>weekly</changefreq>',
            '    <priority>0.7</priority>',
            '  </url>',
        ])

    lines.append('</urlset>')
    SITEMAP_CATEGORIES.write_text("\n".join(lines), encoding="utf-8")


def generate_sitemap_index() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             '  <sitemap>',
             f'    <loc>{SITE_URL}/sitemap-posts.xml</loc>',
             f'    <lastmod>{today}</lastmod>',
             '  </sitemap>',
             '  <sitemap>',
             f'    <loc>{SITE_URL}/sitemap-categories.xml</loc>',
             f'    <lastmod>{today}</lastmod>',
             '  </sitemap>',
             '</sitemapindex>']
    SITEMAP_INDEX.write_text("\n".join(lines), encoding="utf-8")


def generate_robots() -> None:
    content = """User-agent: *
Allow: /

# Не индексируем технические файлы
Disallow: /posts/posts_index.json
Disallow: /posts/progress.json
Disallow: /posts/published.json

User-agent: Yandex
Allow: /

User-agent: Googlebot
Allow: /

User-agent: YandexBot
Allow: /

Sitemap: https://feed.addwine.ru/sitemap.xml
"""
    ROBOTS_PATH.write_text(content, encoding="utf-8")


def generate_all() -> None:
    generate_sitemap_posts()
    generate_sitemap_categories()
    generate_sitemap_index()
    generate_robots()


if __name__ == "__main__":
    generate_all()
    print("✅ sitemap.xml (index)")
    print("✅ sitemap-posts.xml")
    print("✅ sitemap-categories.xml")
    print("✅ robots.txt")
