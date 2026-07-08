"""
Генератор статических страниц категорий.
Для каждой рубрики создаёт /category/<slug>/index.html с:
- Уникальным title и meta description с ключами
- Расширенным H1 + вводным абзацем
- Списком статей категории
- BreadcrumbList JSON-LD и CollectionPage JSON-LD
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
CATEGORY_DIR = REPO_ROOT / "category"


# slug + описания + SEO-подсказки для каждой рубрики
CATEGORIES_META = {
    "Вино, культура и личности": {
        "slug": "vino-kultura-i-lichnosti",
        "meta_desc": "Люди, истории и культурный код винной индустрии: биографии виноделов, сомелье и звёзд, связанных с вином.",
        "h1": "Вино, культура и личности",
        "intro": "Раздел о тех, кто формирует винную культуру: биографии великих виноделов, интервью с сомелье, звёзды винной сцены и их выбор.",
    },
    "Винные новости": {
        "slug": "vinnye-novosti",
        "meta_desc": "Актуальные винные новости: рейтинги, международные премии, тренды рынка, знаковые события мирового виноделия.",
        "h1": "Винные новости",
        "intro": "Оперативные новости мирового и российского виноделия: премии Wine Spectator, Decanter, рейтинги ресторанов, тренды рынка.",
    },
    "Вино и путешествия": {
        "slug": "vino-i-puteshestviya",
        "meta_desc": "Винные путешествия: маршруты по регионам, гид по дегустационным залам, отели с винной картой, лучшие туры.",
        "h1": "Вино и путешествия",
        "intro": "Гид по винным маршрутам мира и России: Тоскана, Бордо, Долина Луары, Крым, Кубань — что попробовать, где остановиться.",
    },
    "Российское виноделие": {
        "slug": "rossiyskoe-vinodelie",
        "meta_desc": "Всё о российском виноделии: терруары Кубани и Крыма, автохтонные сорта, известные хозяйства и молодые виноделы.",
        "h1": "Российское виноделие",
        "intro": "Российское виноделие переживает ренессанс. Раздел посвящён терруарам Тамани, Крыма, Долины Дона и Кавказа, автохтонным сортам и лучшим хозяйствам страны.",
    },
    "Вино и еда": {
        "slug": "vino-i-eda",
        "meta_desc": "Гид по сочетаниям вина и еды: что пить с красным мясом, рыбой, сырами, азиатской кухней, десертами.",
        "h1": "Вино и еда",
        "intro": "Правила и тонкости сочетания вина с едой: гид по стейкам и красному, гастрономия сыров и рыбы, азиатская кухня и десерты — с конкретными сортами и температурами подачи.",
    },
    "Крепкий алкоголь": {
        "slug": "krepkiy-alkogol",
        "meta_desc": "Виски, коньяк, ром, текила, джин: производство, стили, как правильно пить и с чем — экспертные гиды.",
        "h1": "Крепкий алкоголь",
        "intro": "Всё о крепких напитках: скотч и бурбон, коньяк и арманьяк, ром Карибов, текила и мескаль, джин и водка. Стили, производство, правила подачи и гастрономические пары.",
    },
    "Пиво и сидр": {
        "slug": "pivo-i-sidr",
        "meta_desc": "Пиво и сидр: стили, производство, бокалы, температуры подачи, гастрономические пары. Крафт и мировая классика.",
        "h1": "Пиво и сидр",
        "intro": "Гид по стилям пива и сидра: IPA, стауты, ламбики, пилснер, крафт и классика. Как варят, из чего пить и с чем сочетать.",
    },
    "Коктейли и безалкогольное": {
        "slug": "kokteyli-i-bezalkogolnoe",
        "meta_desc": "Классические коктейли с рецептами: Негрони, Мартини, Мохито. Гид по барной культуре, воде и безалкогольным напиткам.",
        "h1": "Коктейли и безалкогольное",
        "intro": "Классические коктейли IBA с полными рецептами: Негрони, Олд Фэшн, Манхэттен, Мартини. Плюс — минеральные воды, тоники и безалкогольные аперитивы новой волны.",
    },
    "Креплёные и десертные вина": {
        "slug": "kreplenye-i-desertnye-vina",
        "meta_desc": "Херес, портвейн, мадера, токай, сотерн, вермуты: стили, производство, правила подачи, гастрономические пары.",
        "h1": "Креплёные и десертные вина",
        "intro": "Недооценённый премиум-сегмент: херес во всех стилях от Fino до Pedro Ximénez, портвейн Ruby и Vintage, мадера, токай, сотерн, вермуты — с правилами подачи и парами.",
    },
    "Технологии и инновации": {
        "slug": "tekhnologii-i-innovatsii",
        "meta_desc": "Технологии в виноделии: биодинамика, дроны, спутниковый мониторинг, автохтонные сорта, AI в дегустации.",
        "h1": "Технологии и инновации",
        "intro": "Наука и технологии в виноделии: биодинамика, точное земледелие, инновации на винодельнях, спутниковые данные, AI в оценке качества.",
    },
    "Вино и деньги": {
        "slug": "vino-i-dengi",
        "meta_desc": "Экономика вина: инвестиции, аукционы, топ дорогих бутылок, рыночные тренды, коллекционирование.",
        "h1": "Вино и деньги",
        "intro": "Деловая сторона вина: аукционы Sotheby's и Christie's, инвестиции в винтажи, коллекционные бренды и рыночные тренды.",
    },
    "Аксессуары для вина": {
        "slug": "aksessuary-dlya-vina",
        "meta_desc": "Гид по винным аксессуарам: бокалы, штопоры, декантеры, охладители, пробки. Как выбрать для дома и ресторана.",
        "h1": "Аксессуары для вина",
        "intro": "Всё о винных аксессуарах: бокалы Sydonios и Riedel, штопоры L'Atelier du Vin, декантеры, охладители и системы хранения. Что выбрать для дома и ресторана.",
    },
    "Дегустации и советы": {
        "slug": "degustatsii-i-sovety",
        "meta_desc": "Гиды по дегустации: как правильно пробовать вино, оценивать аромат и вкус, читать этикетку, хранить открытые бутылки.",
        "h1": "Дегустации и советы",
        "intro": "Практические гиды по дегустации: как оценивать вино по 5 шагам, читать этикетку, определять срок жизни бутылки, вести домашние дегустации.",
    },
    "Дайджесты": {
        "slug": "daydzhesty",
        "meta_desc": "Еженедельные дайджесты Журнала AddWine: самое интересное за неделю — статьи по вину, гастрономии и барной культуре.",
        "h1": "Дайджесты",
        "intro": "Еженедельные подборки самого интересного из Журнала AddWine: главные статьи о вине, крепком алкоголе, гастрономии и барной культуре недели.",
    },
}


def load_posts() -> list:
    if not POSTS_INDEX.exists():
        return []
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def render_category_page(cat_name: str, meta: dict, posts_in_cat: list) -> str:
    """
    Возвращает HTML страницы категории.
    """
    from html_renderer import (
        _escape, BASE_CSS, HEADER_HTML, FOOTER_HTML, LOGO_HEADER, LOGO_FOOTER,
        YANDEX_VERIFY_META, ANALYTICS_HEAD, _ru_date,
    )

    slug = meta["slug"]
    canonical = f"https://feed.addwine.ru/category/{slug}/"
    title_seo = f"{meta['h1']} — статьи Журнала AddWine"
    desc = meta["meta_desc"]

    # Список статей
    posts_html = ""
    for p in posts_in_cat[:60]:  # до 60 последних
        post_url = f"/posts/{p['slug']}/"
        cover = p.get("cover") or "/logo.png"
        cats_line = " · ".join(_escape(c) for c in p.get("categories", [])[:2]) or _escape(cat_name)
        try:
            dt = datetime.fromisoformat(p["published_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date_line = _ru_date(dt)
        except Exception:
            date_line = ""
        posts_html += f"""
        <a class="cat-card" href="{post_url}">
          <div class="cat-card-cover">
            <img loading="lazy" decoding="async" width="1536" height="1024" src="{_escape(cover)}" alt="{_escape(p['title'])} — {_escape(cat_name)}">
          </div>
          <div class="cat-card-body">
            <div class="cat-card-meta"><span>{cats_line}</span> · <span>{date_line}</span></div>
            <h3>{_escape(p['title'])}</h3>
            <p>{_escape(p.get('lead', '')[:200])}</p>
          </div>
        </a>
"""

    if not posts_in_cat:
        posts_html = '<p class="empty">В этой рубрике пока нет статей. Скоро появятся!</p>'

    # JSON-LD CollectionPage + BreadcrumbList
    jsonld_collection = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": meta["h1"],
        "description": meta["meta_desc"],
        "url": canonical,
        "isPartOf": {"@type": "WebSite", "name": "Журнал AddWine", "url": "https://feed.addwine.ru/"},
        "numberOfItems": len(posts_in_cat),
    }
    jsonld_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": "https://addwine.ru/"},
            {"@type": "ListItem", "position": 2, "name": "Журнал", "item": "https://feed.addwine.ru/"},
            {"@type": "ListItem", "position": 3, "name": meta["h1"], "item": canonical},
        ]
    }
    jsonld_str = json.dumps(jsonld_collection, ensure_ascii=False, indent=2)
    jsonld_bc = json.dumps(jsonld_breadcrumb, ensure_ascii=False, indent=2)

    header = HEADER_HTML.replace("__LOGO_HEADER__", LOGO_HEADER)
    footer = FOOTER_HTML.replace("__LOGO_FOOTER__", LOGO_FOOTER)

    extra_css = """
    .cat-hero { max-width: 800px; margin: 30px auto 40px; padding: 0 20px; }
    .cat-hero h1 { font-size: 2.4rem; margin: 20px 0 12px; }
    .cat-hero p { color: var(--muted); font-size: 1.1rem; line-height: 1.6; }
    .cat-grid { max-width: 1200px; margin: 0 auto 60px; padding: 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
    .cat-card { display: block; text-decoration: none; color: inherit; background: var(--card); border-radius: 12px; overflow: hidden; transition: transform 0.15s; border: 1px solid var(--border); }
    .cat-card:hover { transform: translateY(-2px); }
    .cat-card-cover img { width: 100%; height: 200px; object-fit: cover; display: block; }
    .cat-card-body { padding: 16px 18px 20px; }
    .cat-card-meta { font-size: 0.82rem; color: var(--muted); margin-bottom: 6px; }
    .cat-card-body h3 { font-size: 1.1rem; margin: 8px 0 8px; line-height: 1.3; }
    .cat-card-body p { font-size: 0.9rem; color: var(--muted); line-height: 1.5; margin: 0; }
    .empty { text-align: center; color: var(--muted); padding: 40px; grid-column: 1/-1; }
    """

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{YANDEX_VERIFY_META}
<title>{_escape(title_seo)}</title>
<meta name="description" content="{_escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{_escape(meta['h1'])} — Журнал AddWine">
<meta property="og:description" content="{_escape(desc)}">
<meta property="og:site_name" content="Журнал AddWine">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Журнал AddWine">
<link rel="icon" href="https://addwine.ru/favicon.ico">
<style>{BASE_CSS}{extra_css}</style>
<script type="application/ld+json">
{jsonld_str}
</script>
<script type="application/ld+json">
{jsonld_bc}
</script>
{ANALYTICS_HEAD}
</head>
<body>
{header}
<main>
  <div class="cat-hero">
    <nav class="breadcrumb">
      <a href="https://addwine.ru">главная</a><span class="sep">/</span>
      <a href="/">блог</a><span class="sep">/</span>
      <span>{_escape(meta['h1'].lower())}</span>
    </nav>
    <h1>{_escape(meta['h1'])}</h1>
    <p>{_escape(meta['intro'])}</p>
  </div>
  <div class="cat-grid">
    {posts_html}
  </div>
</main>
{footer}
</body>
</html>
"""


def rebuild_all_categories() -> None:
    """Пересобирает все страницы категорий."""
    posts = load_posts()
    CATEGORY_DIR.mkdir(exist_ok=True)

    for cat_name, meta in CATEGORIES_META.items():
        posts_in_cat = [p for p in posts if cat_name in (p.get("categories") or [])]
        posts_in_cat.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        html = render_category_page(cat_name, meta, posts_in_cat)
        out_dir = CATEGORY_DIR / meta["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  ✅ /category/{meta['slug']}/ — {len(posts_in_cat)} статей")


if __name__ == "__main__":
    rebuild_all_categories()
