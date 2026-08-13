"""
Генерация статичных HTML-страниц для feed.addwine.ru.
Дизайн повторяет addwine.ru/articles: горизонтальные пилюли категорий, поиск, сетка карточек.
- posts/<slug>/index.html — страница статьи
- index.html — главная со списком статей + фильтр по категориям + поиск
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

# Аналитика на всех страницах
ANALYTICS_HEAD = """<!-- Yandex.Metrika -->
<script>
(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
m[i].l=1*new Date();
for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r){return;}}
k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
(window,document,'script','https://mc.yandex.ru/metrika/tag.js?id=109402027','ym');
ym(109402027,'init',{ssr:true,webvisor:true,clickmap:true,ecommerce:"dataLayer",accurateTrackBounce:true,trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/109402027" style="position:absolute;left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika -->
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-K1WDNQ5W20"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-K1WDNQ5W20');
</script>
<!-- /Google Analytics -->"""

# Inline SVG логотип addwine — тёмно-синий, жирный
# Лого как картинка — пользователь кладёт файл /logo.svg (или /logo.png) в корень репо
LOGO_HEADER = '<img class="addwine-logo" src="/logo.svg" alt="addwine" onerror="this.src=\'/logo.png\'">'
LOGO_FOOTER = '<img class="addwine-logo-footer" src="/logo.svg" alt="addwine" onerror="this.src=\'/logo.png\'">'

CATEGORIES = [
    "Вино, культура и личности",
    "Винные новости",
    "Вино и путешествия",
    "Российское виноделие",
    "Вино и еда",
    "Крепкий алкоголь",
    "Пиво и сидр",
    "Коктейли и безалкогольное",
    "Креплёные и десертные вина",
    "Технологии и инновации",
    "Вино и деньги",
    "Аксессуары для вина",
    "Дегустации и советы",
    "Дайджесты",
]


BASE_CSS = """
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
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
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
header.site { background: white; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; }
.header-wrap { max-width: 1280px; margin: 0 auto; padding: 18px 24px; display: flex; align-items: center; justify-content: space-between; gap: 32px; }
.brand { display: flex; align-items: center; gap: 14px; }
.brand .addwine-logo { height: 56px; width: auto; display: block; }
.footer-about .addwine-logo-footer { height: 48px; width: auto; display: block; }
@media (max-width: 560px) {
  .brand .addwine-logo { height: 42px; }
}
.brand .sub { font-size: 13px; color: var(--text-muted); letter-spacing: 0.02em; line-height: 1; }
.brand .sub::before { content: "/ "; color: var(--text-soft); margin-right: 4px; }
.header-nav { display: flex; align-items: center; gap: 26px; font-size: 14px; }
.header-nav a { color: var(--text); }
.header-nav a:hover { color: var(--primary); }
.header-nav .catalog-link { display: inline-flex; align-items: center; gap: 8px; background: var(--text); color: white; padding: 10px 18px; border-radius: 999px; font-weight: 500; }
.header-nav .catalog-link:hover { background: var(--primary); color: white; }
.header-nav .catalog-link::after { content: "→"; font-size: 14px; }
.header-icons { display: flex; align-items: center; gap: 16px; color: var(--text-muted); }
.header-icons a { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; }
.header-icons a:hover { color: var(--primary); }
.header-icons svg { width: 20px; height: 20px; }

/* Brand strip */
.brand-strip { background: var(--bg-alt); border-bottom: 1px solid var(--border); }
.brand-strip-wrap { max-width: 1280px; margin: 0 auto; padding: 12px 24px; display: flex; align-items: center; gap: 4px; overflow-x: auto; scrollbar-width: none; }
.brand-strip-wrap::-webkit-scrollbar { display: none; }
.brand-strip a { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 999px; font-size: 14px; color: var(--text-muted); white-space: nowrap; transition: background .15s, color .15s; }
.brand-strip a:hover { background: white; color: var(--text); box-shadow: 0 0 0 1px var(--border); }
.brand-strip a.brand-link { color: var(--text); font-weight: 500; }
.brand-strip a .ico { display: inline-block; width: 18px; height: 18px; flex-shrink: 0; opacity: 0.65; }
.brand-strip-sep { width: 1px; height: 20px; background: var(--border); margin: 0 8px; }

/* Main content */
main { max-width: 1280px; margin: 0 auto; padding: 48px 24px 80px; }

/* Blog page header */
.blog-head { margin-bottom: 28px; }
.blog-head h1 { font-size: clamp(34px, 4.5vw, 48px); font-weight: 800; line-height: 1.05; letter-spacing: -0.02em; color: var(--primary); }

/* Categories — horizontal text links */
.categories {
  display: flex; flex-wrap: wrap; gap: 28px 36px; margin: 24px 0 32px;
  padding-bottom: 0;
}
.cat-pill {
  background: none; border: none; padding: 0; cursor: pointer;
  font-family: inherit; font-size: 15px; font-weight: 500;
  color: var(--text-soft); transition: color .15s ease;
  user-select: none;
}
.cat-pill:hover { color: var(--text); }
.cat-pill.active { color: var(--primary); font-weight: 700; }

/* Search */
.search-box { position: relative; max-width: 720px; margin: 0 0 36px; }
.search-box input {
  width: 100%; padding: 14px 18px 14px 50px;
  border: 1px solid var(--border); border-radius: 999px;
  font-size: 15px; color: var(--text); background: white; outline: none;
  transition: border-color .15s, box-shadow .15s; font-family: inherit;
}
.search-box input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(0, 62, 107, 0.08); }
.search-box svg { position: absolute; left: 18px; top: 50%; transform: translateY(-50%); width: 18px; height: 18px; color: var(--text-soft); pointer-events: none; }

/* Articles grid — 4 cols on desktop */
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 36px 24px; }
.card { display: flex; flex-direction: column; }
.card a.cover {
  display: block; aspect-ratio: 16/11; overflow: hidden;
  border-radius: 10px; background: var(--bg-alt);
}
.card img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .35s ease; }
.card a.cover:hover img { transform: scale(1.03); }
.card .meta {
  display: flex; align-items: center; gap: 12px; margin: 14px 0 8px;
  font-size: 13px; color: var(--text-soft); flex-wrap: wrap;
}
.card .meta .date { color: var(--text-soft); }
.card .meta .cat { color: var(--text-muted); font-weight: 500; }
.card h2 {
  font-size: 17px; line-height: 1.3; font-weight: 700; letter-spacing: -0.005em;
}
.card h2 a { color: var(--text); }
.card h2 a:hover { color: var(--primary); }

.empty { grid-column: 1/-1; text-align: center; padding: 60px 0; color: var(--text-muted); font-size: 16px; }

/* Article page */
.post-wrap { max-width: 760px; margin: 0 auto; }
.breadcrumb { font-size: 13px; color: var(--text-muted); margin-bottom: 32px; }
.breadcrumb a { color: var(--text-muted); }
.breadcrumb a:hover { color: var(--primary); }
.breadcrumb .sep { margin: 0 8px; color: var(--text-soft); }
.post-header { margin-bottom: 28px; }
.post-header h1 { font-size: clamp(28px, 4vw, 44px); line-height: 1.1; font-weight: 800; letter-spacing: -0.02em; color: var(--primary); margin-bottom: 24px; }
.post-cover { margin: 0 0 28px; }
.post-cover img { width: 100%; border-radius: 10px; display: block; }
.post-meta-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 28px;
  padding-bottom: 20px; margin-bottom: 32px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}
.post-meta-bar .cat { color: var(--text-soft); font-weight: 500; }
.post-meta-bar .date { color: var(--text-soft); margin-left: auto; font-variant-numeric: tabular-nums; }
.post-header .lead { font-size: 18px; color: var(--text-muted); line-height: 1.5; }
.post-body { font-size: 17px; line-height: 1.75; color: #2a2a2a; }
.post-body p { margin-bottom: 20px; }
.post-body h2 { font-size: 26px; line-height: 1.25; font-weight: 700; letter-spacing: -0.015em; margin: 44px 0 18px; color: var(--text); }
.post-body h3 { font-size: 20px; line-height: 1.3; font-weight: 600; margin: 32px 0 14px; color: var(--text); }
.post-body ul, .post-body ol { margin: 20px 0 20px 26px; }
.post-body li { margin-bottom: 10px; }
.post-body img { width: 100%; height: auto; border-radius: 10px; margin: 32px 0; display: block; aspect-ratio: 3/2; object-fit: cover; }
.post-body blockquote { border-left: 3px solid var(--accent); padding: 6px 0 6px 22px; margin: 28px 0; color: var(--text); font-style: italic; font-size: 18px; }
.post-body a { color: var(--primary); border-bottom: 1px solid var(--primary); padding-bottom: 1px; }
.post-body a:hover { border-color: transparent; }
.post-body strong { font-weight: 600; }

/* Свежий абзац от актуализации */
.refresh-2026 {
  border-left: 3px solid var(--accent);
  padding: 12px 18px;
  background: #fefbf5;
  margin: 24px 0;
  border-radius: 4px;
  font-size: 16px;
  color: #3a3a3a;
}
.refresh-2026::before {
  content: "🔄 Обновлено:";
  display: block;
  font-size: 12px;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
  font-weight: 600;
}

/* FAQ секция */
.faq { margin: 32px 0; padding: 24px 28px; background: #fafaf7; border-radius: 12px; border: 1px solid var(--border); }
.faq h3 { font-size: 17px; font-weight: 600; margin: 20px 0 10px; color: var(--text); }
.faq h3:first-child { margin-top: 0; }
.faq p { margin: 0 0 16px; color: #3a3a3a; line-height: 1.6; }

/* Рецепт коктейля */
.recipe { margin: 32px 0; padding: 24px 28px; background: #f5f5f0; border-radius: 12px; border-left: 4px solid var(--accent); }
.recipe p b { font-size: 15px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--primary); }
.recipe ul, .recipe ol { margin: 12px 0 20px 22px; }
.recipe li { margin-bottom: 8px; font-size: 16px; }

/* Автолинки в статье */
.post-body a.autolink { color: var(--primary); border-bottom: 1px dotted var(--primary); text-decoration: none; }
.post-body a.autolink:hover { border-color: transparent; }

/* Похожие статьи */
.related { margin: 60px auto 40px; max-width: 1100px; padding: 0 8px; }
.related-title { font-size: 22px; font-weight: 700; margin-bottom: 24px; color: var(--text); border-top: 1px solid var(--border); padding-top: 40px; }
.related-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-bottom: 24px; }
.related-card { display: block; text-decoration: none; color: inherit; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); transition: transform 0.15s, box-shadow 0.15s; background: #fff; }
.related-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.06); }
.related-cover { aspect-ratio: 3/2; overflow: hidden; }
.related-cover img { width: 100%; height: 100%; object-fit: cover; display: block; margin: 0; border-radius: 0; }
.related-body { padding: 12px 14px 16px; }
.related-cat { display: inline-block; font-size: 11px; color: var(--text-soft); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
.related-body h4 { font-size: 15px; font-weight: 600; line-height: 1.35; color: var(--text); margin: 0; }
.related-all { display: inline-block; font-size: 14px; color: var(--primary); border-bottom: 1px solid var(--primary); padding-bottom: 1px; margin-top: 8px; }
.related-all:hover { border-color: transparent; }

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
.footer-bottom { border-top: 1px solid var(--border); padding-top: 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--text-muted); }

/* Mobile */
@media (max-width: 1100px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 900px) {
  .header-wrap { padding: 14px 16px; gap: 16px; }
  .header-nav { gap: 14px; }
  .brand .sub { display: none; }
  .grid { grid-template-columns: repeat(2, 1fr); gap: 28px 18px; }
  main { padding: 32px 16px 56px; }
  .footer-grid { grid-template-columns: 1fr 1fr; gap: 28px; }
  .categories { flex-direction: column; gap: 14px; margin: 18px 0 24px; }
}
@media (max-width: 560px) {
  .header-nav .catalog-link { display: none; }
  .grid { grid-template-columns: 1fr; gap: 24px; }
  .blog-head h1 { font-size: 30px; }
  .post-body { font-size: 16px; }
  .footer-grid { grid-template-columns: 1fr; }
}
"""


HEADER_HTML = """<header class="site">
  <div class="header-wrap">
    <a class="brand" href="https://addwine.ru">
      __LOGO_HEADER__
    </a>
    <nav class="header-nav">
      <a href="https://addwine.ru/catalogue" class="catalog-link">Каталог</a>
      <a href="/">Журнал</a>
      <a href="https://dzen.ru/addwine" target="_blank" rel="noopener">Дзен</a>
      <a href="https://addwine.ru/contacts">Контакты</a>
    </nav>
    <div class="header-icons">
      <a href="https://addwine.ru/user/notifications" aria-label="Уведомления">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
      </a>
      <a href="https://addwine.ru/favorites" aria-label="Избранное">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
      </a>
      <a href="https://addwine.ru/user" aria-label="Профиль">
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
    <a href="https://addwibe.ru/" target="_blank" rel="noopener" class="brand-link">
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 2v6c0 2 2 4 4 4s4-2 4-4V2H8z"/><path d="M12 12v8M9 22h6"/></svg>
      Дегустации с AddWibe
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
        <a href="https://addwine.ru" style="display:inline-block;margin-bottom:12px">__LOGO_FOOTER__</a>
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
      <span>® AddWine 2017-2026. Материалы для лиц старше 18 лет.</span>
      <span><a href="https://addwine.ru/privacy-policy">Политика конфиденциальности</a></span>
    </div>
  </div>
</footer>"""


def _ru_date(dt: datetime) -> str:
    """Формат DD.MM.YYYY как на addwine.ru/articles."""
    return f"{dt.day:02d}.{dt.month:02d}.{dt.year}"


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _seo_meta_description(lead: str, max_len: int = 155) -> str:
    """Обрезает lead до max_len символов для meta description."""
    if not lead:
        return ""
    if len(lead) <= max_len:
        return lead
    cut = lead[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


# Ключевые entities → страницы категорий для автолинковки
ENTITY_TO_CATEGORY_SLUG = {
    # Крепкий алкоголь
    "виски": "krepkiy-alkogol", "бурбон": "krepkiy-alkogol", "скотч": "krepkiy-alkogol",
    "сингл-молт": "krepkiy-alkogol", "сингл молт": "krepkiy-alkogol", "блендед": "krepkiy-alkogol",
    "коньяк": "krepkiy-alkogol", "арманьяк": "krepkiy-alkogol", "кальвадос": "krepkiy-alkogol",
    "текила": "krepkiy-alkogol", "мескаль": "krepkiy-alkogol",
    "джин": "krepkiy-alkogol",
    "граппа": "krepkiy-alkogol", "аквавит": "krepkiy-alkogol", "абсент": "krepkiy-alkogol",
    # Пиво
    "стаут": "pivo-i-sidr", "портер": "pivo-i-sidr", "ipa": "pivo-i-sidr",
    "лагер": "pivo-i-sidr", "пилснер": "pivo-i-sidr", "ламбик": "pivo-i-sidr",
    "витбир": "pivo-i-sidr", "сидр": "pivo-i-sidr",
    # Коктейли
    "негрони": "kokteyli-i-bezalkogolnoe", "мохито": "kokteyli-i-bezalkogolnoe",
    "мартини": "kokteyli-i-bezalkogolnoe", "маргарита": "kokteyli-i-bezalkogolnoe",
    "олд фэшн": "kokteyli-i-bezalkogolnoe", "манхэттен": "kokteyli-i-bezalkogolnoe",
    "дайкири": "kokteyli-i-bezalkogolnoe",
    # Креплёные
    "херес": "kreplenye-i-desertnye-vina", "портвейн": "kreplenye-i-desertnye-vina",
    "мадера": "kreplenye-i-desertnye-vina", "токай": "kreplenye-i-desertnye-vina",
    "сотерн": "kreplenye-i-desertnye-vina", "вермут": "kreplenye-i-desertnye-vina",
    # Российское виноделие
    "тамань": "rossiyskoe-vinodelie", "анапа": "rossiyskoe-vinodelie",
    "крым": "rossiyskoe-vinodelie", "кубань": "rossiyskoe-vinodelie",
    "краснодар": "rossiyskoe-vinodelie", "дагестан": "rossiyskoe-vinodelie",
    "абрау": "rossiyskoe-vinodelie", "лефкадия": "rossiyskoe-vinodelie",
    # Аксессуары
    "штопор": "aksessuary-dlya-vina", "декантер": "aksessuary-dlya-vina",
    "охладитель": "aksessuary-dlya-vina",
}


def _autolink_entities(body_html: str, current_slug: str) -> str:
    """
    Автоматически заменяет первое вхождение каждого entity на ссылку на страницу категории.
    Не трогает entity если оно уже внутри тега <a> или <h1>-<h6>.
    """
    linked = set()
    # Работаем только вне тегов
    parts = re.split(r'(<[^>]+>|<a\s[^>]*>.*?</a>|<h[1-6][^>]*>.*?</h[1-6]>)', body_html, flags=re.S)
    result = []
    for part in parts:
        if part.startswith("<") or not part.strip():
            result.append(part)
            continue
        for entity, cat_slug in sorted(ENTITY_TO_CATEGORY_SLUG.items(), key=lambda x: -len(x[0])):
            if entity in linked:
                continue
            if current_slug and cat_slug in current_slug:
                # не линкуем на собственную категорию
                linked.add(entity)
                continue
            # ищем entity с учётом падежных окончаний (первые 4+ символов)
            stem = entity[:max(4, len(entity) - 2)] if not (" " in entity or "-" in entity) else re.escape(entity)
            if " " in entity or "-" in entity:
                pat = rf"(?i)\b({re.escape(entity)})\b"
            else:
                pat = rf"(?i)\b({re.escape(stem)}\w*)\b"
            match = re.search(pat, part)
            if match:
                original = match.group(1)
                replacement = f'<a href="/category/{cat_slug}/" class="autolink">{original}</a>'
                part = part[:match.start()] + replacement + part[match.end():]
                linked.add(entity)
        result.append(part)
    return "".join(result)


def _extract_faq_pairs(body_html: str) -> list:
    """
    Ищет FAQ секцию в html: <div class="faq">...</div> с парами <h3>Q</h3><p>A</p>.
    Возвращает список dict {question, answer}.
    """
    m = re.search(r'<div\s+class="faq"[^>]*>(.*?)</div>', body_html, flags=re.S | re.I)
    if not m:
        return []
    inner = m.group(1)
    # находим пары h3+следующие p до следующего h3
    pairs = []
    chunks = re.split(r'<h3[^>]*>', inner)
    for chunk in chunks[1:]:
        end = chunk.find("</h3>")
        if end == -1:
            continue
        question = re.sub(r"<[^>]+>", "", chunk[:end]).strip()
        rest = chunk[end + 5:]
        # достаём все p до следующего h3 или конца
        answer_parts = re.findall(r"<p[^>]*>(.*?)</p>", rest, flags=re.S)
        answer = " ".join(re.sub(r"<[^>]+>", "", p).strip() for p in answer_parts)
        if question and answer:
            pairs.append({"question": question, "answer": answer})
    return pairs


def _extract_howto_recipe(body_html: str) -> dict:
    """
    Ищет секцию рецепта коктейля: <div class="recipe">...</div> с ingredients (ul) и steps (ol).
    Возвращает dict {name, ingredients: [...], steps: [...]} или {}.
    """
    m = re.search(r'<div\s+class="recipe"[^>]*>(.*?)</div>', body_html, flags=re.S | re.I)
    if not m:
        return {}
    inner = m.group(1)

    # ингредиенты — первый ul
    ul_m = re.search(r"<ul[^>]*>(.*?)</ul>", inner, flags=re.S)
    ingredients = []
    if ul_m:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", ul_m.group(1), flags=re.S):
            text = re.sub(r"<[^>]+>", "", li).strip()
            if text:
                ingredients.append(text)

    # шаги — ol
    ol_m = re.search(r"<ol[^>]*>(.*?)</ol>", inner, flags=re.S)
    steps = []
    if ol_m:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", ol_m.group(1), flags=re.S):
            text = re.sub(r"<[^>]+>", "", li).strip()
            if text:
                steps.append(text)

    if ingredients and steps:
        return {"ingredients": ingredients, "steps": steps}
    return {}


def _add_lazy_and_alt_to_imgs(body_html: str, title: str, category: str) -> str:
    """
    Постпроцессор HTML статьи:
    - добавляет loading="lazy", decoding="async" ко всем <img>
    - улучшает alt: шаблонные — заменяет на «{title} — {category}»
    - width/height у cover'ов чтобы не было CLS
    - оборачивает <img src="....jpg"> в <picture> с WebP-source (если ещё не обёрнуто)
    """
    lazy_alt = _escape(f"{title} — {category}") if category else _escape(title)

    def _repl_img(m):
        tag = m.group(0)
        # уже есть loading
        if "loading=" not in tag:
            tag = tag.replace("<img ", '<img loading="lazy" decoding="async" ', 1)
        # alt
        alt_match = re.search(r'alt="([^"]*)"', tag)
        if alt_match:
            cur = alt_match.group(1).lower()
            if (not cur.strip() or "обложка" in cur or "иллюстрац" in cur
                    or cur in ("cover", "image", "photo")):
                tag = re.sub(r'alt="[^"]*"', f'alt="{lazy_alt}"', tag)
        else:
            tag = tag.replace("<img ", f'<img alt="{lazy_alt}" ', 1)
        # width/height для cover'ов
        if "width=" not in tag and "cover-" in tag:
            tag = tag.replace("<img ", '<img width="1536" height="1024" ', 1)
        return tag

    body_html = re.sub(r'<img\b[^>]*>', _repl_img, body_html)

    # Оборачиваем cover-*.jpg в <picture> с WebP source
    def _wrap_picture(m):
        img_tag = m.group(0)
        src_m = re.search(r'src="([^"]+cover-\d+)\.jpg"', img_tag)
        if not src_m:
            return img_tag
        webp_src = f'{src_m.group(1)}.webp'
        return f'<picture><source type="image/webp" srcset="{webp_src}">{img_tag}</picture>'

    # только если ещё не внутри <picture>
    if "<picture>" not in body_html:
        body_html = re.sub(r'<img\b[^>]*src="[^"]+cover-\d+\.jpg"[^>]*>', _wrap_picture, body_html)

    return body_html


def _category_slug(cat_name: str) -> str:
    """slug категории для URL /category/<slug>/"""
    try:
        from category_renderer import CATEGORIES_META
        m = CATEGORIES_META.get(cat_name)
        if m:
            return m["slug"]
    except Exception:
        pass
    # fallback
    return re.sub(r"[^a-z0-9]+", "-", cat_name.lower().replace("ё", "e")).strip("-")


def _related_posts_html(current_slug: str, categories: list, limit: int = 4) -> str:
    """Возвращает HTML блока «Похожие статьи» из той же категории."""
    if not POSTS_INDEX.exists():
        return ""
    try:
        all_posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return ""
    main_cat = (categories or [None])[0]
    if not main_cat:
        return ""
    related = []
    for p in all_posts:
        if p.get("slug") == current_slug:
            continue
        if main_cat in (p.get("categories") or []):
            related.append(p)
        if len(related) >= limit:
            break
    if not related:
        return ""

    cards = ""
    for p in related:
        url = f"/posts/{p['slug']}/"
        cover = p.get("cover") or "/logo.png"
        cards += f"""
        <a class="related-card" href="{url}">
          <div class="related-cover"><img loading="lazy" decoding="async" width="1536" height="1024" src="{_escape(cover)}" alt="{_escape(p['title'])} — {_escape(main_cat)}"></div>
          <div class="related-body">
            <span class="related-cat">{_escape(main_cat)}</span>
            <h4>{_escape(p['title'])}</h4>
          </div>
        </a>
"""
    cat_slug = _category_slug(main_cat)
    all_link = f'<a class="related-all" href="/category/{cat_slug}/">Смотреть все статьи рубрики «{_escape(main_cat)}» →</a>'

    return f"""
    <section class="related">
      <h3 class="related-title">Похожие статьи</h3>
      <div class="related-grid">
        {cards}
      </div>
      {all_link}
    </section>
"""


def render_post_page(article: dict, slug: str, pub_date: datetime, categories: list = None) -> str:
    title = _escape(article["title"])
    lead = _escape(article["lead"])
    meta_desc = _escape(_seo_meta_description(article["lead"], 155))
    body_html = article["html"]
    cats = categories or []

    # старые <p><img alt="обложка"></p> уже не используются; на всякий случай
    body_html = re.sub(r'^\s*<p>\s*<img[^>]+alt="обложка"[^>]*/?>\s*</p>\s*', '', body_html, count=1)

    # постпроцессор картинок: lazy, alt, width/height
    body_html = _add_lazy_and_alt_to_imgs(body_html, article["title"], cats[0] if cats else "")

    # автолинковка entities → страницы категорий (первое вхождение)
    body_html = _autolink_entities(body_html, slug)

    # картинка для og:image — первое <img> в теле
    m = re.search(r'<img\s+[^>]*src="([^"]+)"', body_html)
    og_image = m.group(1) if m else "https://feed.addwine.ru/logo.png"
    canonical_url = f"https://feed.addwine.ru/posts/{slug}/"
    iso_date = pub_date.isoformat() if isinstance(pub_date, datetime) else str(pub_date)
    main_section = cats[0] if cats else "Журнал"

    cat_html = " · ".join(_escape(c) for c in cats[:2])
    breadcrumb_cat = _escape(cats[0]) if cats else "Статья"

    # word count для качественных сигналов
    plain_body = re.sub(r'<[^>]+>', ' ', body_html)
    plain_body = re.sub(r'\s+', ' ', plain_body).strip()
    word_count = len(plain_body.split())

    # JSON-LD: Article + BreadcrumbList для расширенных сниппетов
    import json as _json
    jsonld_article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "alternativeHeadline": article["lead"][:110],
        "image": {
            "@type": "ImageObject",
            "url": og_image,
            "width": 1536,
            "height": 1024,
        },
        "datePublished": iso_date,
        "dateModified": iso_date,
        "wordCount": word_count,
        "articleSection": main_section,
        "keywords": ", ".join(cats),
        "inLanguage": "ru-RU",
        "isFamilyFriendly": False,
        "isAccessibleForFree": True,
        "author": {
            "@type": "Person",
            "name": "Редакция AddWine",
            "url": "https://feed.addwine.ru/",
            "jobTitle": "Редактор винного журнала",
            "worksFor": {
                "@type": "Organization",
                "name": "AddWine",
                "url": "https://addwine.ru"
            },
            "sameAs": [
                "https://dzen.ru/addwine",
                "https://t.me/justaddwine"
            ]
        },
        "publisher": {
            "@type": "Organization",
            "name": "AddWine",
            "url": "https://addwine.ru",
            "logo": {
                "@type": "ImageObject",
                "url": "https://feed.addwine.ru/logo.png",
                "width": 300,
                "height": 60,
            },
            "sameAs": [
                "https://dzen.ru/addwine",
                "https://t.me/justaddwine",
                "https://addwine.ru",
            ]
        },
        "description": article["lead"],
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url
        }
    }
    jsonld_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": "https://addwine.ru/"},
            {"@type": "ListItem", "position": 2, "name": "Журнал", "item": "https://feed.addwine.ru/"},
            {"@type": "ListItem", "position": 3, "name": main_section, "item": canonical_url},
        ]
    }
    # Дополнительные JSON-LD блоки
    extra_jsonld_scripts = []

    # FAQPage
    faq_pairs = _extract_faq_pairs(body_html)
    if faq_pairs:
        faq_jsonld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": p["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": p["answer"]},
                } for p in faq_pairs
            ],
        }
        extra_jsonld_scripts.append(_json.dumps(faq_jsonld, ensure_ascii=False, indent=2))

    # HowTo (для коктейлей и рецептов)
    recipe = _extract_howto_recipe(body_html)
    if recipe:
        howto_jsonld = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": article["title"],
            "description": article["lead"],
            "image": og_image,
            "totalTime": "PT5M",
            "estimatedCost": {"@type": "MonetaryAmount", "currency": "RUB", "value": "500"},
            "supply": [{"@type": "HowToSupply", "name": ing} for ing in recipe["ingredients"]],
            "step": [
                {"@type": "HowToStep", "position": i + 1, "text": s, "name": f"Шаг {i+1}"}
                for i, s in enumerate(recipe["steps"])
            ],
        }
        extra_jsonld_scripts.append(_json.dumps(howto_jsonld, ensure_ascii=False, indent=2))

    jsonld_str = _json.dumps(jsonld_article, ensure_ascii=False, indent=2)
    jsonld_breadcrumb_str = _json.dumps(jsonld_breadcrumb, ensure_ascii=False, indent=2)
    extra_jsonld_str = "\n".join(f'<script type="application/ld+json">\n{s}\n</script>' for s in extra_jsonld_scripts)

    article_tags = "".join(f'<meta property="article:tag" content="{_escape(c)}">\n' for c in cats[:2])

    header = HEADER_HTML.replace("__LOGO_HEADER__", LOGO_HEADER)
    footer = FOOTER_HTML.replace("__LOGO_FOOTER__", LOGO_FOOTER)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
<meta name="referrer" content="no-referrer-when-downgrade">
<meta name="format-detection" content="telephone=no">
<meta name="theme-color" content="#003E6B">
{YANDEX_VERIFY_META}
<title>{title} — Журнал AddWine</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{canonical_url}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical_url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{lead}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1536">
<meta property="og:image:height" content="1024">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="Журнал AddWine">
<meta property="article:published_time" content="{iso_date}">
<meta property="article:modified_time" content="{iso_date}">
<meta property="article:author" content="AddWine">
<meta property="article:section" content="{_escape(main_section)}">
{article_tags}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{lead}">
<meta name="twitter:image" content="{og_image}">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Журнал AddWine">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}</style>
<script type="application/ld+json">
{jsonld_str}
</script>
<script type="application/ld+json">
{jsonld_breadcrumb_str}
</script>
{extra_jsonld_str}
{ANALYTICS_HEAD}
</head>
<body>
{header}
<main>
  <div class="post-wrap">
    <nav class="breadcrumb">
      <a href="https://addwine.ru">главная</a><span class="sep">/</span>
      <a href="/">блог</a><span class="sep">/</span>
      <span>{breadcrumb_cat.lower()}</span>
    </nav>
    <article>
      <header class="post-header">
        <h1>{title}</h1>
        <div class="post-meta-bar">
          <span class="cat">{cat_html or "Журнал AddWine"}</span>
          <span class="date">{_ru_date(pub_date)}</span>
        </div>
      </header>
      <div class="post-body">
{body_html}
      </div>
    </article>
{_related_posts_html(slug, cats, limit=4)}
  </div>
</main>
{footer}
</body>
</html>
"""


def render_index_page(posts_meta: list) -> str:
    posts_meta = sorted(posts_meta, key=lambda p: p.get("published_at", ""), reverse=True)
    # данные для JS — массив объектов
    js_data = json.dumps([{
        "slug": p["slug"],
        "title": p["title"],
        "lead": p.get("lead", ""),
        "cover": p["cover"],
        "date": p["published_at"],
        "cats": p.get("categories", []),
    } for p in posts_meta], ensure_ascii=False)

    # пилюли категорий — теперь ссылки на статические страницы /category/<slug>/
    cat_pills = '<a class="cat-pill active" href="/">Все статьи</a>'
    for cat in CATEGORIES:
        slug = _category_slug(cat)
        cat_pills += f'<a class="cat-pill" href="/category/{slug}/">{_escape(cat)}</a>'

    js_code = """
(function() {
  const posts = window.__POSTS__;
  const grid = document.getElementById('articles-grid');
  const pills = document.querySelectorAll('.cat-pill');
  const searchInput = document.getElementById('search-input');

  let activeCat = '';
  let searchQuery = '';

  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function fmtDate(iso) {
    try {
      const d = new Date(iso);
      return pad(d.getDate()) + '.' + pad(d.getMonth()+1) + '.' + d.getFullYear();
    } catch(e) { return ''; }
  }
  function escape(s) {
    return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function render() {
    const q = searchQuery.toLowerCase().trim();
    const filtered = posts.filter(p => {
      const catOk = !activeCat || (p.cats && p.cats.indexOf(activeCat) !== -1);
      const searchOk = !q || (p.title.toLowerCase().indexOf(q) !== -1 || (p.lead||'').toLowerCase().indexOf(q) !== -1);
      return catOk && searchOk;
    });
    if (filtered.length === 0) {
      grid.innerHTML = '<div class="empty">Нет статей по вашему запросу.</div>';
      return;
    }
    grid.innerHTML = filtered.map(p => {
      const cat = (p.cats && p.cats[0]) ? '<span class="cat">' + escape(p.cats[0]) + '</span>' : '';
      return '<article class="card">' +
        '<a class="cover" href="/posts/' + p.slug + '/"><img src="' + p.cover + '" alt="' + escape(p.title) + '" loading="lazy"></a>' +
        '<div class="meta"><span class="date">' + fmtDate(p.date) + '</span>' + cat + '</div>' +
        '<h2><a href="/posts/' + p.slug + '/">' + escape(p.title) + '</a></h2>' +
      '</article>';
    }).join('');
  }
  // пилюли теперь — обычные ссылки на /category/<slug>/, JS-фильтр по клику не нужен
  searchInput.addEventListener('input', function() {
    searchQuery = this.value;
    render();
  });
  render();
})();
"""

    header = HEADER_HTML.replace("__LOGO_HEADER__", LOGO_HEADER)
    footer = FOOTER_HTML.replace("__LOGO_FOOTER__", LOGO_FOOTER)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{YANDEX_VERIFY_META}
<title>Журнал AddWine — статьи о вине, виноделии и аксессуарах</title>
<meta name="description" content="Авторский журнал AddWine. Экспертные статьи о вине, виноделии, сомелье, бокалах, штопорах, декантерах и культуре потребления.">
<link rel="canonical" href="https://feed.addwine.ru/">
<meta property="og:type" content="website">
<meta property="og:url" content="https://feed.addwine.ru/">
<meta property="og:title" content="Журнал AddWine — о вине">
<meta property="og:description" content="Экспертные статьи о вине, виноделии и винной культуре.">
<meta property="og:image" content="https://feed.addwine.ru/logo.png">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="Журнал AddWine">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Журнал AddWine — о вине">
<meta name="twitter:description" content="Экспертные статьи о вине, виноделии и винной культуре.">
<meta name="twitter:image" content="https://feed.addwine.ru/logo.png">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Журнал AddWine">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}</style>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "AddWine",
  "url": "https://addwine.ru",
  "logo": {{
    "@type": "ImageObject",
    "url": "https://feed.addwine.ru/logo.png",
    "width": 300,
    "height": 60
  }},
  "description": "Крупнейший в России магазин винных аксессуаров: бокалы, штопоры, декантеры, охладители.",
  "telephone": "+7 495 297-27-97",
  "address": {{
    "@type": "PostalAddress",
    "addressCountry": "RU",
    "addressLocality": "Москва"
  }},
  "sameAs": [
    "https://dzen.ru/addwine",
    "https://t.me/justaddwine",
    "https://t.me/addwine_shop"
  ]
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Журнал AddWine",
  "alternateName": "AddWine Magazine",
  "url": "https://feed.addwine.ru/",
  "inLanguage": "ru-RU",
  "publisher": {{
    "@type": "Organization",
    "name": "AddWine",
    "url": "https://addwine.ru"
  }},
  "potentialAction": {{
    "@type": "SearchAction",
    "target": {{
      "@type": "EntryPoint",
      "urlTemplate": "https://feed.addwine.ru/?q={{search_term_string}}"
    }},
    "query-input": "required name=search_term_string"
  }}
}}
</script>
{ANALYTICS_HEAD}
</head>
<body>
{header}
<main>
  <section class="blog-head">
    <h1>Журнал</h1>
  </section>
  <nav class="categories">
    {cat_pills}
  </nav>
  <div class="search-box">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    <input type="text" id="search-input" placeholder="Поиск по блогу" autocomplete="off">
  </div>
  <section id="articles-grid" class="grid"></section>
</main>
{footer}
<script>
window.__POSTS__ = {js_data};
{js_code}
</script>
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


def add_post(slug: str, title: str, lead: str, cover_url: str, published_at: str, categories: list = None) -> None:
    posts = load_posts_index()
    posts = [p for p in posts if p.get("slug") != slug]
    posts.insert(0, {
        "slug": slug,
        "title": title,
        "lead": lead,
        "cover": cover_url,
        "published_at": published_at,
        "categories": (categories or [])[:2],
    })
    save_posts_index(posts)


def write_post(article: dict, slug: str, image_urls: list, pub_date: datetime, pages_base: str, categories: list = None) -> str:
    post_dir = POSTS_DIR / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    html = render_post_page(article, slug, pub_date, categories=categories)
    (post_dir / "index.html").write_text(html, encoding="utf-8")
    return f"{pages_base}/posts/{slug}/"


def rebuild_index() -> None:
    posts = load_posts_index()
    html = render_index_page(posts)
    INDEX_HTML.write_text(html, encoding="utf-8")
    # параллельно обновляем sitemap.xml, robots.txt и страницы категорий
    try:
        import sitemap_gen
        sitemap_gen.generate_all()
    except Exception as e:
        print(f"[html_renderer] sitemap не обновился: {e}")
    try:
        import category_renderer
        category_renderer.rebuild_all_categories()
    except Exception as e:
        print(f"[html_renderer] страницы категорий не пересобрались: {e}")
    try:
        import html_sitemap
        html_sitemap.generate()
    except Exception as e:
        print(f"[html_renderer] HTML-карта не создана: {e}")
    try:
        import llms_txt_gen
        llms_txt_gen.generate()
    except Exception as e:
        print(f"[html_renderer] llms.txt не создан: {e}")
    try:
        import indexnow_ping
        indexnow_ping.ensure_key_file()  # обеспечиваем наличие ключ-файла в корне
    except Exception as e:
        print(f"[html_renderer] IndexNow ключ не создан: {e}")


def rebuild_from_feed(pages_base: str) -> None:
    """Перечитывает feed.xml через feed_io и пересоздаёт страницы статей + главную."""
    import feed_io
    data = feed_io.read_feed()
    if not data["items"]:
        return

    # пользовательские категории берём из существующего posts_index.json
    existing_cats = {}
    for p in load_posts_index():
        existing_cats[p.get("slug")] = p.get("categories", [])

    # «дзен-зарезервированные» категории, которые НЕ показываем как пользовательские
    DZEN_RESERVED = {"format-article", "format-post", "comment-all", "comment-subscribers",
                     "comment-none", "index", "noindex", "native-draft"}

    posts = []
    for it in data["items"]:
        title = it["title"]
        lead = it["description"]
        cover_url = it["enclosure_url"]
        full_html = it["content_html"]
        pub_date = it["pub_date"] if isinstance(it["pub_date"], datetime) else datetime.now(timezone.utc)

        m = re.search(r"/images/([^/]+)/", cover_url)
        slug = m.group(1) if m else _slug_from_title(title, pub_date)

        cats = existing_cats.get(slug, [])

        article = {"title": title, "lead": lead, "html": full_html}
        post_dir = POSTS_DIR / slug
        post_dir.mkdir(parents=True, exist_ok=True)
        html = render_post_page(article, slug, pub_date, categories=cats)
        (post_dir / "index.html").write_text(html, encoding="utf-8")

        posts.append({
            "slug": slug,
            "title": title,
            "lead": lead,
            "cover": cover_url,
            "published_at": pub_date.isoformat(),
            "categories": cats[:2],
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
