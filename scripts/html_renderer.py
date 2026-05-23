"""
Генерация статичных HTML-страниц для feed.addwine.ru:
- posts/<slug>/index.html — страница статьи
- index.html — главная со списком статей
- posts/index.json — метаданные всех статей (для генерации главной)
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "posts"
INDEX_HTML = REPO_ROOT / "index.html"
POSTS_INDEX = POSTS_DIR / "posts_index.json"
FEED_PATH = REPO_ROOT / "feed.xml"

YANDEX_VERIFY_META = '<meta name="yandex-verification" content="d5940a0d077e7558" />'

BASE_CSS = """
:root {
  --primary: #003E6B;
  --primary-dark: #002a4a;
  --accent: #EFD79A;
  --accent-soft: #f7e8c5;
  --bg: #faf7f2;
  --text: #1a1a1a;
  --muted: #6b6b6b;
  --border: #e8e2d6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", Helvetica, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--primary); text-decoration: none; transition: color .15s; }
a:hover { color: var(--accent); }

header.site {
  background: var(--primary);
  color: var(--accent);
  padding: 28px 24px;
  border-bottom: 4px solid var(--accent);
}
header.site .wrap {
  max-width: 1080px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap;
}
header.site .brand a {
  color: var(--accent); font-weight: 700; font-size: 22px; letter-spacing: -0.01em;
}
header.site .brand .tag {
  display: block; font-size: 13px; font-weight: 400; opacity: 0.75; margin-top: 2px;
}
header.site nav a {
  color: var(--accent); margin-left: 18px; font-size: 14px; opacity: 0.85;
}
header.site nav a:hover { opacity: 1; }

main { max-width: 1080px; margin: 0 auto; padding: 48px 24px 80px; }

.hero {
  text-align: center; margin-bottom: 56px; padding: 24px;
}
.hero h1 {
  font-size: clamp(28px, 4vw, 44px); font-weight: 700; color: var(--primary);
  letter-spacing: -0.02em; margin-bottom: 14px;
}
.hero p { font-size: 18px; color: var(--muted); max-width: 640px; margin: 0 auto; }

.grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 28px;
}
.card {
  background: white; border-radius: 14px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 4px 24px rgba(0,62,107,.05);
  display: flex; flex-direction: column;
  transition: transform .2s, box-shadow .2s;
}
.card:hover { transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,.06), 0 12px 32px rgba(0,62,107,.08); }
.card a.cover { display: block; aspect-ratio: 16/9; overflow: hidden; background: var(--accent-soft); }
.card img { width: 100%; height: 100%; object-fit: cover; display: block; }
.card .body { padding: 20px 22px 24px; flex: 1; display: flex; flex-direction: column; }
.card .date { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
.card h2 { font-size: 19px; line-height: 1.35; margin-bottom: 10px; font-weight: 600; }
.card h2 a { color: var(--primary); }
.card p.lead { color: var(--muted); font-size: 15px; flex: 1; }
.card .read { margin-top: 14px; color: var(--primary); font-weight: 600; font-size: 14px; }

article.post { background: white; padding: 48px clamp(20px, 5vw, 64px); border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 4px 24px rgba(0,62,107,.05); }
article.post .meta { color: var(--muted); font-size: 14px; margin-bottom: 14px; }
article.post h1 {
  font-size: clamp(26px, 3.5vw, 38px); line-height: 1.2; color: var(--primary);
  letter-spacing: -0.02em; margin-bottom: 18px; font-weight: 700;
}
article.post .lead {
  font-size: 19px; color: #333; margin-bottom: 36px; line-height: 1.5;
  border-left: 4px solid var(--accent); padding-left: 18px;
}
article.post .body { font-size: 17px; line-height: 1.75; color: #2a2a2a; }
article.post .body h2 {
  font-size: 24px; margin: 40px 0 16px; color: var(--primary); font-weight: 700;
}
article.post .body h3 {
  font-size: 19px; margin: 28px 0 12px; color: var(--primary-dark); font-weight: 600;
}
article.post .body p { margin-bottom: 18px; }
article.post .body ul, article.post .body ol { margin: 18px 0 18px 28px; }
article.post .body li { margin-bottom: 8px; }
article.post .body img {
  width: 100%; border-radius: 10px; margin: 28px 0; display: block;
}
article.post .body blockquote {
  border-left: 4px solid var(--accent); padding: 12px 20px; margin: 24px 0;
  background: var(--accent-soft); color: var(--primary-dark); font-style: italic;
}
article.post .body a { color: var(--primary); border-bottom: 1px solid var(--accent); }

footer.site {
  background: var(--primary); color: var(--accent); padding: 36px 24px; margin-top: 80px;
  text-align: center; font-size: 14px; opacity: 0.95;
}
footer.site a { color: var(--accent); border-bottom: 1px solid rgba(239,215,154,.4); }

.back { display: inline-block; margin-bottom: 24px; color: var(--primary); font-size: 14px; font-weight: 600; }
.back::before { content: "← "; }

@media (max-width: 640px) {
  header.site .wrap { flex-direction: column; align-items: flex-start; }
  header.site nav { width: 100%; }
  header.site nav a { margin: 0 18px 0 0; }
  main { padding: 32px 16px 56px; }
  .hero { margin-bottom: 32px; padding: 0; }
  .grid { grid-template-columns: 1fr; gap: 20px; }
  article.post { padding: 28px 20px; }
}
"""

HEADER_HTML = """<header class="site">
  <div class="wrap">
    <div class="brand"><a href="/">AddWine</a><span class="tag">журнал о вине, виноделии и культуре</span></div>
    <nav>
      <a href="/">Главная</a>
      <a href="https://dzen.ru/addwine" target="_blank" rel="noopener">Дзен</a>
      <a href="https://addwine.ru" target="_blank" rel="noopener">Магазин</a>
      <a href="/feed.xml">RSS</a>
    </nav>
  </div>
</header>"""

FOOTER_HTML = """<footer class="site">
  <p>AddWine — авторский журнал о вине. Материалы для лиц старше 18 лет.</p>
  <p style="margin-top:8px"><a href="https://addwine.ru">addwine.ru</a> · <a href="https://dzen.ru/addwine">dzen.ru/addwine</a></p>
</footer>"""


def _ru_date(dt: datetime) -> str:
    months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}"


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_post_page(article: dict, slug: str, cover_url: str, pub_date: datetime) -> str:
    """HTML страницы статьи."""
    title = _escape(article["title"])
    lead = _escape(article["lead"])
    body_html = article["html"]  # доверяем своему контенту

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{YANDEX_VERIFY_META}
<title>{title} — AddWine</title>
<meta name="description" content="{lead}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{lead}">
<meta property="og:image" content="{cover_url}">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="AddWine RSS">
<style>{BASE_CSS}</style>
</head>
<body>
{HEADER_HTML}
<main>
  <a class="back" href="/">К списку статей</a>
  <article class="post">
    <div class="meta">{_ru_date(pub_date)}</div>
    <h1>{title}</h1>
    <p class="lead">{lead}</p>
    <div class="body">
{body_html}
    </div>
  </article>
</main>
{FOOTER_HTML}
</body>
</html>
"""


def render_index_page(posts_meta: list) -> str:
    """HTML главной страницы со списком статей."""
    posts_meta = sorted(posts_meta, key=lambda p: p.get("published_at", ""), reverse=True)[:30]

    cards = ""
    for p in posts_meta:
        try:
            pub = datetime.fromisoformat(p["published_at"])
        except Exception:
            pub = datetime.now(timezone.utc)
        cards += f"""    <article class="card">
      <a class="cover" href="/posts/{p['slug']}/"><img src="{p['cover']}" alt="{_escape(p['title'])}" loading="lazy"></a>
      <div class="body">
        <div class="date">{_ru_date(pub)}</div>
        <h2><a href="/posts/{p['slug']}/">{_escape(p['title'])}</a></h2>
        <p class="lead">{_escape(p.get('lead', ''))}</p>
        <span class="read">Читать →</span>
      </div>
    </article>
"""

    if not cards:
        cards = '<p style="grid-column:1/-1;text-align:center;color:var(--muted)">Скоро здесь появятся статьи.</p>'

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{YANDEX_VERIFY_META}
<title>AddWine — журнал о вине</title>
<meta name="description" content="Авторский журнал о вине, виноделии и винной культуре. Экспертные статьи от сомелье.">
<meta property="og:type" content="website">
<meta property="og:title" content="AddWine — журнал о вине">
<meta property="og:description" content="Экспертные статьи о вине, виноделии и винной культуре.">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="AddWine RSS">
<style>{BASE_CSS}</style>
</head>
<body>
{HEADER_HTML}
<main>
  <section class="hero">
    <h1>AddWine — журнал о вине</h1>
    <p>Экспертные статьи о вине, виноделии, сомелье и культуре потребления. Каждый день — новая публикация.</p>
  </section>
  <section class="grid">
{cards}  </section>
</main>
{FOOTER_HTML}
</body>
</html>
"""


def load_posts_index() -> list:
    if POSTS_INDEX.exists():
        return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    return []


def save_posts_index(posts: list) -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    POSTS_INDEX.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def add_post(slug: str, title: str, lead: str, cover_url: str, published_at: str) -> None:
    """Добавляет статью в posts_index.json (дедуп по slug)."""
    posts = load_posts_index()
    posts = [p for p in posts if p.get("slug") != slug]
    posts.insert(0, {
        "slug": slug,
        "title": title,
        "lead": lead,
        "cover": cover_url,
        "published_at": published_at,
    })
    save_posts_index(posts)


def write_post(article: dict, slug: str, image_urls: list, pub_date: datetime, pages_base: str) -> str:
    """
    Создаёт posts/<slug>/index.html.
    Возвращает permalink (URL вида https://feed.addwine.ru/posts/<slug>/).
    """
    post_dir = POSTS_DIR / slug
    post_dir.mkdir(parents=True, exist_ok=True)

    cover_url = f"{pages_base}/{image_urls[0]}"
    html = render_post_page(article, slug, cover_url, pub_date)
    (post_dir / "index.html").write_text(html, encoding="utf-8")
    return f"{pages_base}/posts/{slug}/"


def rebuild_index() -> None:
    """Перегенерирует index.html из posts_index.json."""
    posts = load_posts_index()
    html = render_index_page(posts)
    INDEX_HTML.write_text(html, encoding="utf-8")


def rebuild_from_feed(pages_base: str) -> None:
    """
    Одноразовая миграция: читает feed.xml, генерит страницы для всех существующих статей,
    обновляет posts_index.json и index.html.
    """
    if not FEED_PATH.exists():
        return

    NS = {"yandex": "http://news.yandex.ru"}
    tree = ET.parse(str(FEED_PATH))
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        return

    posts = []
    for item in channel.findall("item"):
        title_el = item.find("title")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        enc_el = item.find("enclosure")
        ft_el = item.find("yandex:full-text", NS)

        title = title_el.text if title_el is not None else "Без названия"
        lead = desc_el.text if desc_el is not None else ""
        cover_url = enc_el.get("url") if enc_el is not None else ""
        full_html = ft_el.text if ft_el is not None else ""

        # парсим pubDate
        try:
            from email.utils import parsedate_to_datetime
            pub_date = parsedate_to_datetime(pubdate_el.text) if pubdate_el is not None else datetime.now(timezone.utc)
        except Exception:
            pub_date = datetime.now(timezone.utc)

        # slug — из cover URL (там путь вида images/<slug>/cover-1.jpg)
        m = re.search(r"/images/([^/]+)/", cover_url)
        slug = m.group(1) if m else _slug_from_title(title, pub_date)

        # пишем страницу
        article = {"title": title, "lead": lead, "html": full_html}
        write_post(article, slug, [f"images/{slug}/cover-1.jpg"], pub_date, pages_base)

        posts.append({
            "slug": slug,
            "title": title,
            "lead": lead,
            "cover": cover_url,
            "published_at": pub_date.isoformat(),
        })

    save_posts_index(posts)
    rebuild_index()


def _slug_from_title(title: str, dt: datetime) -> str:
    table = {
        "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z",
        "и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r",
        "с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch",
        "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
    }
    text = "".join(table.get(c, c) for c in title.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:50] or "post"
    return f"{dt.strftime('%Y-%m-%d')}-{text}"
