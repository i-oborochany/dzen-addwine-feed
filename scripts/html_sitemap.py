"""
Генерирует /sitemap-html/index.html — страницу-карту сайта для читателей и поисковика.
Помогает роботу обойти сайт целиком и распределить внутренний вес.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
HTML_SITEMAP_DIR = REPO_ROOT / "sitemap-html"
SITE_URL = "https://feed.addwine.ru"


def load_posts() -> list:
    if not POSTS_INDEX.exists():
        return []
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate() -> None:
    posts = load_posts()

    # Группируем по категориям
    from collections import defaultdict
    by_cat = defaultdict(list)
    for p in posts:
        cats = p.get("categories") or ["Прочее"]
        by_cat[cats[0]].append(p)

    # Импорт CATEGORIES_META для slug
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from category_renderer import CATEGORIES_META, render_category_page
        from html_renderer import (
            BASE_CSS, HEADER_HTML, FOOTER_HTML, LOGO_HEADER, LOGO_FOOTER,
            YANDEX_VERIFY_META, ANALYTICS_HEAD,
        )
    except Exception as e:
        print(f"⚠️  импорт: {e}")
        return

    # Рендер контента
    sections = ""
    for cat_name, cat_posts in sorted(by_cat.items()):
        cat_slug = CATEGORIES_META.get(cat_name, {}).get("slug", "")
        cat_link = f"/category/{cat_slug}/" if cat_slug else "#"
        cat_posts.sort(key=lambda p: p.get("published_at", ""), reverse=True)

        items = "".join(
            f'<li><a href="/posts/{_escape(p["slug"])}/">{_escape(p["title"])}</a></li>'
            for p in cat_posts
        )
        sections += f"""
        <section class="cat-block">
          <h2><a href="{cat_link}">{_escape(cat_name)}</a></h2>
          <ul>{items}</ul>
          <p class="cat-count">{len(cat_posts)} статей</p>
        </section>
"""

    header = HEADER_HTML.replace("__LOGO_HEADER__", LOGO_HEADER)
    footer = FOOTER_HTML.replace("__LOGO_FOOTER__", LOGO_FOOTER)

    extra_css = """
    .html-sitemap { max-width: 900px; margin: 30px auto; padding: 0 20px; }
    .html-sitemap h1 { font-size: 2.2rem; margin: 20px 0 12px; }
    .html-sitemap > p { color: var(--text-muted); margin-bottom: 32px; }
    .cat-block { margin-bottom: 36px; }
    .cat-block h2 { font-size: 1.4rem; margin-bottom: 12px; border-bottom: 2px solid var(--accent); padding-bottom: 6px; }
    .cat-block h2 a { color: var(--primary); text-decoration: none; }
    .cat-block h2 a:hover { text-decoration: underline; }
    .cat-block ul { list-style: none; padding: 0; margin: 0 0 8px; }
    .cat-block li { padding: 4px 0; border-bottom: 1px dotted var(--border); }
    .cat-block li a { color: var(--text); text-decoration: none; font-size: 15px; }
    .cat-block li a:hover { color: var(--primary); }
    .cat-count { font-size: 13px; color: var(--text-soft); }
    """

    total = sum(len(v) for v in by_cat.values())
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow, max-image-preview:large">
{YANDEX_VERIFY_META}
<title>Карта сайта — Журнал AddWine</title>
<meta name="description" content="Полная карта журнала AddWine: все статьи по категориям — вино, коктейли, крепкий алкоголь, пиво, российское виноделие, дайджесты.">
<link rel="canonical" href="{SITE_URL}/sitemap-html/">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Журнал AddWine">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}{extra_css}</style>
{ANALYTICS_HEAD}
</head>
<body>
{header}
<main>
  <div class="html-sitemap">
    <nav class="breadcrumb">
      <a href="https://addwine.ru">главная</a><span class="sep">/</span>
      <a href="/">блог</a><span class="sep">/</span>
      <span>карта сайта</span>
    </nav>
    <h1>Карта сайта</h1>
    <p>Все {total} статей журнала AddWine, разложенные по 14 рубрикам. Полезно если ищешь конкретную тему или хочешь исследовать блог целиком.</p>
    {sections}
  </div>
</main>
{footer}
</body>
</html>
"""
    HTML_SITEMAP_DIR.mkdir(parents=True, exist_ok=True)
    (HTML_SITEMAP_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"✅ /sitemap-html/index.html — {total} статей в {len(by_cat)} категориях")


if __name__ == "__main__":
    generate()
