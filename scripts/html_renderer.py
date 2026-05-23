"""
Генерация статичных HTML-страниц для feed.addwine.ru.
Дизайн повторяет основной сайт addwine.ru: та же шапка, навигация, футер.
- posts/<slug>/index.html — страница статьи
- index.html — главная со списком статей
- posts/posts_index.json — метаданные всех статей
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
@font-face {
  font-family: 'Inter';
  src: url('https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfMZg.woff2') format('woff2');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
:root {
  --bg: #ffffff;
  --bg-alt: #fafaf7;
  --text: #1a1a1a;
  --text-muted: #6b6b6b;
  --text-soft: #999999;
  --border: #ececec;
  --border-soft: #f5f5f5;
  --primary: #003E6B;
  --primary-dark: #002a4a;
  --accent: #b48b3d;
  --accent-soft: #f5efe2;
  --topbar: #1a1a1a;
  --topbar-text: #f5f5f5;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif;
  font-size: 16px; line-height: 1.55; color: var(--text); background: var(--bg);
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
a { color: inherit; text-decoration: none; transition: color .15s ease, opacity .15s ease; }

/* Topbar */
.topbar {
  background: var(--topbar); color: var(--topbar-text);
  padding: 9px 24px; font-size: 13px; text-align: center; letter-spacing: 0.01em;
}
.topbar a { color: var(--topbar-text); border-bottom: 1px solid rgba(255,255,255,.3); padding-bottom: 1px; }
.topbar a:hover { border-color: rgba(255,255,255,.7); }

/* Main header */
header.site {
  background: white; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 100;
}
.header-wrap {
  max-width: 1280px; margin: 0 auto; padding: 18px 24px;
  display: flex; align-items: center; justify-content: space-between; gap: 32px;
}
.brand {
  display: flex; align-items: baseline; gap: 14px;
}
.brand .logo {
  font-size: 24px; font-weight: 700; letter-spacing: -0.02em; color: var(--text);
}
.brand .sub {
  font-size: 13px; color: var(--text-muted); letter-spacing: 0.02em;
}
.brand .sub::before { content: "/ "; color: var(--text-soft); margin-right: 4px; }

.header-nav { display: flex; align-items: center; gap: 26px; font-size: 14px; }
.header-nav a { color: var(--text); }
.header-nav a:hover { color: var(--primary); }
.header-nav .catalog-link {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--text); color: white; padding: 10px 18px; border-radius: 999px;
  font-weight: 500;
}
.header-nav .catalog-link:hover { background: var(--primary); color: white; }
.header-nav .catalog-link::after { content: "→"; font-size: 14px; }

.header-icons { display: flex; align-items: center; gap: 16px; color: var(--text-muted); }
.header-icons a { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; }
.header-icons a:hover { color: var(--primary); }
.header-icons svg { width: 20px; height: 20px; }

/* Brand strip */
.brand-strip { background: var(--bg-alt); border-bottom: 1px solid var(--border); }
.brand-strip-wrap {
  max-width: 1280px; margin: 0 auto; padding: 12px 24px;
  display: flex; align-items: center; gap: 4px; overflow-x: auto;
  scrollbar-width: none;
}
.brand-strip-wrap::-webkit-scrollbar { display: none; }
.brand-strip a {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 999px;
  font-size: 14px; color: var(--text-muted); white-space: nowrap;
  transition: background .15s, color .15s;
}
.brand-strip a:hover { background: white; color: var(--text); box-shadow: 0 0 0 1px var(--border); }
.brand-strip a.brand-link { color: var(--text); font-weight: 500; }
.brand-strip a .ico {
  display: inline-block; width: 18px; height: 18px; flex-shrink: 0;
  opacity: 0.65;
}
.brand-strip-sep {
  width: 1px; height: 20px; background: var(--border); margin: 0 8px;
}

/* Main content */
main { max-width: 1280px; margin: 0 auto; padding: 56px 24px 80px; }

/* Hero (главная) */
.hero { margin-bottom: 56px; max-width: 720px; }
.hero h1 {
  font-size: clamp(34px, 5vw, 54px); font-weight: 700; line-height: 1.05;
  letter-spacing: -0.025em; color: var(--text); margin-bottom: 18px;
}
.hero p { font-size: 18px; color: var(--text-muted); line-height: 1.5; max-width: 540px; }

/* Articles grid */
.grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px 24px;
}
.card { display: flex; flex-direction: column; }
.card a.cover {
  display: block; aspect-ratio: 16/10; overflow: hidden; border-radius: 8px;
  background: var(--bg-alt);
}
.card img {
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform .4s ease;
}
.card a.cover:hover img { transform: scale(1.03); }
.card .meta { display: flex; align-items: center; gap: 10px; margin: 14px 0 8px; font-size: 13px; color: var(--text-soft); }
.card .meta .tag { background: var(--accent-soft); color: var(--accent); padding: 3px 9px; border-radius: 999px; font-weight: 500; font-size: 12px; }
.card h2 { font-size: 19px; line-height: 1.3; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 8px; }
.card h2 a { color: var(--text); }
.card h2 a:hover { color: var(--primary); }
.card p.lead { color: var(--text-muted); font-size: 14px; line-height: 1.5; }

/* Featured article (первая большая карточка) */
.featured { grid-column: span 3; display: grid; grid-template-columns: 1.2fr 1fr; gap: 40px; align-items: center; margin-bottom: 8px; }
.featured a.cover { aspect-ratio: 16/10; }
.featured .body { padding: 0 12px; }
.featured h2 { font-size: clamp(24px, 2.6vw, 34px); line-height: 1.15; margin-bottom: 16px; }
.featured p.lead { font-size: 16px; margin-bottom: 18px; }
.featured .read-more { display: inline-flex; align-items: center; gap: 8px; color: var(--primary); font-weight: 600; font-size: 14px; }
.featured .read-more::after { content: "→"; transition: transform .15s; }
.featured .read-more:hover::after { transform: translateX(4px); }

/* Article page */
.post-wrap { max-width: 760px; margin: 0 auto; }
.breadcrumb { font-size: 13px; color: var(--text-muted); margin-bottom: 32px; }
.breadcrumb a { color: var(--text-muted); border-bottom: 1px solid transparent; }
.breadcrumb a:hover { color: var(--primary); }
.breadcrumb .sep { margin: 0 8px; color: var(--text-soft); }

.post-header { margin-bottom: 36px; }
.post-header .meta { font-size: 13px; color: var(--text-soft); margin-bottom: 14px; display: flex; gap: 10px; align-items: center; }
.post-header .meta .tag { background: var(--accent-soft); color: var(--accent); padding: 3px 9px; border-radius: 999px; font-weight: 500; font-size: 12px; }
.post-header h1 {
  font-size: clamp(28px, 4vw, 42px); line-height: 1.15; font-weight: 700;
  letter-spacing: -0.02em; color: var(--text); margin-bottom: 18px;
}
.post-header .lead {
  font-size: 19px; color: var(--text-muted); line-height: 1.5;
}
.post-cover { margin: 0 0 40px; }
.post-cover img { width: 100%; border-radius: 10px; display: block; }

.post-body { font-size: 17px; line-height: 1.75; color: #2a2a2a; }
.post-body p { margin-bottom: 20px; }
.post-body h2 { font-size: 26px; line-height: 1.25; font-weight: 700; letter-spacing: -0.015em; margin: 44px 0 18px; color: var(--text); }
.post-body h3 { font-size: 20px; line-height: 1.3; font-weight: 600; margin: 32px 0 14px; color: var(--text); }
.post-body ul, .post-body ol { margin: 20px 0 20px 26px; }
.post-body li { margin-bottom: 10px; }
.post-body img { width: 100%; border-radius: 10px; margin: 32px 0; display: block; }
.post-body blockquote {
  border-left: 3px solid var(--accent); padding: 6px 0 6px 22px;
  margin: 28px 0; color: var(--text); font-style: italic; font-size: 18px;
}
.post-body a { color: var(--primary); border-bottom: 1px solid var(--primary); padding-bottom: 1px; }
.post-body a:hover { border-color: transparent; }
.post-body strong { font-weight: 600; }

/* Footer */
footer.site { background: var(--bg-alt); border-top: 1px solid var(--border); margin-top: 80px; padding: 56px 24px 32px; }
.footer-wrap { max-width: 1280px; margin: 0 auto; }
.footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 40px; margin-bottom: 40px; }
.footer-col h4 { font-size: 13px; font-weight: 600; color: var(--text-soft); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }
.footer-col ul { list-style: none; }
.footer-col li { margin-bottom: 10px; font-size: 14px; }
.footer-col a { color: var(--text); }
.footer-col a:hover { color: var(--primary); }
.footer-about { font-size: 14px; color: var(--text-muted); line-height: 1.55; max-width: 320px; }
.footer-about .logo { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 12px; display: block; letter-spacing: -0.02em; }
.footer-bottom {
  border-top: 1px solid var(--border); padding-top: 24px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;
  font-size: 13px; color: var(--text-muted);
}

/* Mobile */
@media (max-width: 900px) {
  .header-wrap { padding: 14px 16px; gap: 16px; }
  .header-nav { gap: 14px; }
  .brand .sub { display: none; }
  .grid { grid-template-columns: repeat(2, 1fr); gap: 24px 18px; }
  .featured { grid-column: span 2; grid-template-columns: 1fr; gap: 18px; }
  main { padding: 36px 16px 56px; }
  .footer-grid { grid-template-columns: 1fr 1fr; gap: 28px; }
}
@media (max-width: 560px) {
  .header-nav .catalog-link { display: none; }
  .grid { grid-template-columns: 1fr; }
  .featured { grid-column: span 1; }
  .hero h1 { font-size: 32px; }
  .post-body { font-size: 16px; }
  .footer-grid { grid-template-columns: 1fr; }
}
"""

HEADER_HTML = """<div class="topbar">
  <a href="https://addwine.ru/catalogue?have_express_delivery=true">Экспресс-доставка по Москве — получите заказ уже через 2–3 часа</a>
</div>
<header class="site">
  <div class="header-wrap">
    <a class="brand" href="https://addwine.ru">
      <span class="logo">addwine</span>
      <span class="sub">журнал о вине</span>
    </a>
    <nav class="header-nav">
      <a href="https://addwine.ru/catalogue" class="catalog-link">Каталог</a>
      <a href="/" class="active">Журнал</a>
      <a href="https://dzen.ru/addwine" target="_blank" rel="noopener">Дзен</a>
      <a href="https://addwine.ru/contacts">Контакты</a>
    </nav>
    <div class="header-icons">
      <a href="https://addwine.ru/user/notifications" title="Уведомления" aria-label="Уведомления">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
      </a>
      <a href="https://addwine.ru/favorites" title="Избранное" aria-label="Избранное">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
      </a>
      <a href="https://addwine.ru/user" title="Профиль" aria-label="Профиль">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </a>
    </div>
  </div>
</header>
<div class="brand-strip">
  <div class="brand-strip-wrap">
    <a href="https://add-event.ru/" target="_blank" rel="noopener" class="brand-link">
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
      Аренда с AddEvent
    </a>
    <a href="https://sellers.addwine.ru/" target="_blank" rel="noopener" class="brand-link">
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>
      Дистрибьюция с AddSeller
    </a>
    <a href="https://addcellar.ru/" target="_blank" rel="noopener" class="brand-link">
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 9l9-6 9 6v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>
      Мебель с AddCellar
    </a>
    <span class="brand-strip-sep"></span>
    <a href="https://addwine.ru/catalogue/category/podacha/bokaly-dlya-vina">Бокалы</a>
    <a href="https://addwine.ru/catalogue/category/servirovka/shtopory">Штопоры</a>
    <a href="https://addwine.ru/catalogue/category/podacha/dekantery">Декантеры</a>
    <a href="https://addwine.ru/catalogue/category/izuchenie">Подарки</a>
  </div>
</div>"""

FOOTER_HTML = """<footer class="site">
  <div class="footer-wrap">
    <div class="footer-grid">
      <div class="footer-col footer-about">
        <a class="logo" href="https://addwine.ru">addwine</a>
        <p>Журнал о вине, виноделии и винной культуре от команды AddWine — крупнейшего в России магазина аксессуаров для вина.</p>
      </div>
      <div class="footer-col">
        <h4>Каталог</h4>
        <ul>
          <li><a href="https://addwine.ru/catalogue/category/hranenie">Хранение вина</a></li>
          <li><a href="https://addwine.ru/catalogue/category/servirovka">Сервировка</a></li>
          <li><a href="https://addwine.ru/catalogue/category/podacha">Дегустация</a></li>
          <li><a href="https://addwine.ru/catalogue/category/izuchenie">Винные подарки</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Журнал</h4>
        <ul>
          <li><a href="/">Все статьи</a></li>
          <li><a href="/feed.xml">RSS-лента</a></li>
          <li><a href="https://dzen.ru/addwine" target="_blank">Канал на Дзене</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Компания</h4>
        <ul>
          <li><a href="https://addwine.ru/about">О компании</a></li>
          <li><a href="https://addwine.ru/contacts">Контакты</a></li>
          <li><a href="https://addwine.ru/delivery-info">Доставка и оплата</a></li>
          <li><a href="https://t.me/justaddwine" target="_blank">Telegram</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© AddWine 2017–2026. Материалы для лиц старше 18 лет.</span>
      <span><a href="https://addwine.ru/privacy-policy">Политика конфиденциальности</a></span>
    </div>
  </div>
</footer>"""


def _ru_date(dt: datetime) -> str:
    months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}"


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_post_page(article: dict, slug: str, cover_url: str, pub_date: datetime) -> str:
    title = _escape(article["title"])
    lead = _escape(article["lead"])
    body_html = article["html"]

    # удаляем первую <p><img ...></p> из тела — она нам не нужна, обложка отдельно
    body_html_clean = re.sub(r'^\s*<p>\s*<img[^>]+alt="обложка"[^>]*/?>\s*</p>\s*', '', body_html, count=1)

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
<meta property="og:site_name" content="AddWine">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="AddWine Журнал">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}</style>
</head>
<body>
{HEADER_HTML}
<main>
  <div class="post-wrap">
    <nav class="breadcrumb">
      <a href="https://addwine.ru">addwine</a><span class="sep">/</span>
      <a href="/">Журнал</a><span class="sep">/</span>
      <span>Статья</span>
    </nav>
    <article>
      <header class="post-header">
        <div class="meta">
          <span class="tag">Журнал AddWine</span>
          <span>{_ru_date(pub_date)}</span>
        </div>
        <h1>{title}</h1>
        <p class="lead">{lead}</p>
      </header>
      <div class="post-cover">
        <img src="{cover_url}" alt="{title}">
      </div>
      <div class="post-body">
{body_html_clean}
      </div>
    </article>
  </div>
</main>
{FOOTER_HTML}
</body>
</html>
"""


def render_index_page(posts_meta: list) -> str:
    posts_meta = sorted(posts_meta, key=lambda p: p.get("published_at", ""), reverse=True)[:30]

    cards_html = ""
    for i, p in enumerate(posts_meta):
        try:
            pub = datetime.fromisoformat(p["published_at"])
        except Exception:
            pub = datetime.now(timezone.utc)
        if i == 0:
            cards_html += f"""    <article class="card featured">
      <a class="cover" href="/posts/{p['slug']}/"><img src="{p['cover']}" alt="{_escape(p['title'])}" loading="eager"></a>
      <div class="body">
        <div class="meta">
          <span class="tag">Главная статья</span>
          <span>{_ru_date(pub)}</span>
        </div>
        <h2><a href="/posts/{p['slug']}/">{_escape(p['title'])}</a></h2>
        <p class="lead">{_escape(p.get('lead', ''))}</p>
        <a class="read-more" href="/posts/{p['slug']}/">Читать</a>
      </div>
    </article>
"""
        else:
            cards_html += f"""    <article class="card">
      <a class="cover" href="/posts/{p['slug']}/"><img src="{p['cover']}" alt="{_escape(p['title'])}" loading="lazy"></a>
      <div class="meta">
        <span class="tag">Статья</span>
        <span>{_ru_date(pub)}</span>
      </div>
      <h2><a href="/posts/{p['slug']}/">{_escape(p['title'])}</a></h2>
      <p class="lead">{_escape(p.get('lead', '')[:150])}{'...' if len(p.get('lead', '')) > 150 else ''}</p>
    </article>
"""

    if not cards_html:
        cards_html = '<p style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px 0">Скоро здесь появятся статьи.</p>'

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{YANDEX_VERIFY_META}
<title>Журнал AddWine — о вине, виноделии и винной культуре</title>
<meta name="description" content="Авторский журнал AddWine. Экспертные статьи о вине, виноделии, сомелье, аксессуарах и культуре потребления.">
<meta property="og:type" content="website">
<meta property="og:title" content="Журнал AddWine — о вине">
<meta property="og:description" content="Экспертные статьи о вине, виноделии и винной культуре.">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="AddWine">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="AddWine Журнал">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}</style>
</head>
<body>
{HEADER_HTML}
<main>
  <section class="hero">
    <h1>Журнал о вине</h1>
    <p>Экспертные статьи о вине, виноделии, сомелье и аксессуарах от команды AddWine. Новые материалы каждый день.</p>
  </section>
  <section class="grid">
{cards_html}  </section>
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
    post_dir = POSTS_DIR / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    cover_url = f"{pages_base}/{image_urls[0]}" if not image_urls[0].startswith("http") else image_urls[0]
    html = render_post_page(article, slug, cover_url, pub_date)
    (post_dir / "index.html").write_text(html, encoding="utf-8")
    return f"{pages_base}/posts/{slug}/"


def rebuild_index() -> None:
    posts = load_posts_index()
    html = render_index_page(posts)
    INDEX_HTML.write_text(html, encoding="utf-8")


def rebuild_from_feed(pages_base: str) -> None:
    """Одноразовая миграция: читает feed.xml, генерит страницы и главную."""
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

        try:
            from email.utils import parsedate_to_datetime
            pub_date = parsedate_to_datetime(pubdate_el.text) if pubdate_el is not None else datetime.now(timezone.utc)
        except Exception:
            pub_date = datetime.now(timezone.utc)

        m = re.search(r"/images/([^/]+)/", cover_url)
        slug = m.group(1) if m else _slug_from_title(title, pub_date)

        article = {"title": title, "lead": lead, "html": full_html}
        # пишем напрямую — image_urls здесь не нужны, обложка уже в cover_url
        post_dir = POSTS_DIR / slug
        post_dir.mkdir(parents=True, exist_ok=True)
        html = render_post_page(article, slug, cover_url, pub_date)
        (post_dir / "index.html").write_text(html, encoding="utf-8")

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
