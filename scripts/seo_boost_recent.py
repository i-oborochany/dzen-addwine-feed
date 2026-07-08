"""
Точечный SEO-boost для последних N статей.
Обновляет ТОЛЬКО:
- title (H1) — с топ-1 ключом из Wordstat
- lead (meta description + первый абзац-превью на главной)
- alt-теги картинок обновляются автоматом при пересборке HTML (используют title+category)

НЕ трогает: body статьи, URL/slug, картинки, категории.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import wordstat_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

LIMIT_POSTS = 10  # сколько последних статей боост'нуть

# Пропускаем дайджесты и служебные типы
SKIP_KEYWORDS = ["дайджест", "самое интересное за нед", "события недели"]


SEO_SYSTEM = """Ты — SEO-редактор винного журнала AddWine. Тебе дают текущий заголовок и лид статьи + реальные ключевые слова из Яндекс.Wordstat с частотами.

ЗАДАЧА:
1. Переписать title (H1) — новый заголовок должен обязательно содержать топ-1 ключ (или его словоформу) в естественной, читаемой формулировке. НЕ кликбейт, НЕ капслок.
2. Переписать lead (короткое описание для meta description и превью на главной) — 100–155 символов. Обязательно содержит топ-1 ключ и стилистически похожую вариацию топ-2 ключа. Естественная формулировка, без буллетов.
3. Тон: экспертный, спокойный, редакторский. Без обещаний вроде «узнайте всё» и «читайте далее».

ФОРМАТ ОТВЕТА — строго JSON:
{
  "new_title": "<новый заголовок>",
  "new_lead": "<новый лид 100-155 символов>"
}
"""


def load_posts() -> list:
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def save_posts(posts: list) -> None:
    POSTS_INDEX.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def should_skip(post: dict) -> bool:
    title_low = post.get("title", "").lower()
    return any(k in title_low for k in SKIP_KEYWORDS)


def seo_boost_one(post: dict) -> bool:
    """
    Возвращает True если пост обновлён.
    """
    title = post.get("title", "")
    lead = post.get("lead", "")
    print(f"\n▶ «{title[:70]}»")

    keywords = wordstat_api.get_keywords(title, limit=15)
    if len(keywords) < 1:
        print(f"  [!] ключей вообще нет, пропускаем")
        return False

    print(f"  Топ ключей:")
    for kw in keywords[:5]:
        print(f"    - «{kw['phrase']}» ({kw['count']})")

    keys_block = "\n".join(f"  - «{kw['phrase']}» ({kw['count']} показов/мес)" for kw in keywords[:12])
    user = f"""ТЕКУЩИЙ ЗАГОЛОВОК: {title}

ТЕКУЩИЙ ЛИД: {lead}

РЕАЛЬНЫЕ КЛЮЧИ ИЗ WORDSTAT (от самых частотных):
{keys_block}

Верни строгий JSON с новыми title и lead согласно системному промпту."""

    try:
        result = claude_api.generate_json(SEO_SYSTEM, user, max_tokens=1500, temperature=0.3)
    except Exception as e:
        print(f"  [!] Claude упал: {e}")
        return False

    new_title = (result.get("new_title") or "").strip()
    new_lead = (result.get("new_lead") or "").strip()

    if not new_title or not new_lead:
        print(f"  [!] Claude не вернул полей")
        return False
    if len(new_lead) > 200:
        new_lead = new_lead[:180].rsplit(" ", 1)[0] + "…"

    print(f"  Новый title: {new_title}")
    print(f"  Новый lead ({len(new_lead)}): {new_lead}")

    post["title"] = new_title
    post["lead"] = new_lead
    return True


def main():
    posts = load_posts()
    print(f"Всего постов в индексе: {len(posts)}")

    # берём последние N (кроме дайджестов)
    candidates = [p for p in posts if not should_skip(p)][:LIMIT_POSTS]
    print(f"Кандидатов на boost: {len(candidates)}")

    changed = 0
    for post in candidates:
        if seo_boost_one(post):
            changed += 1

    print(f"\n=== ИТОГО обновлено: {changed}/{len(candidates)} ===")

    save_posts(posts)
    print("posts_index.json сохранён")

    # Обновляем feed.xml — там свои копии title и description
    print("\nОбновляем feed.xml...")
    try:
        import feed_io
        feed = feed_io.read_feed()
        # posts index уже отсортирован — берём title→slug map по URL /posts/<slug>/
        slug_to_new = {p["slug"]: p for p in posts}
        updated = 0
        for item in feed.get("items", []):
            link = item.get("link") or item.get("guid") or ""
            m = re.search(r"/posts/([^/]+)/?", link)
            if not m:
                continue
            slug = m.group(1)
            p = slug_to_new.get(slug)
            if p:
                item["title"] = p["title"]
                item["description"] = p["lead"]
                updated += 1
        feed_io.write_feed(feed["channel"], feed["items"])
        print(f"✅ feed.xml — обновлено {updated} items")
    except Exception as e:
        print(f"[!] feed.xml не обновился: {e}")

    # Пересобираем HTML этих статей + главную + категории
    print("\nПересобираем HTML...")
    try:
        import html_renderer
        # feed.xml даёт body_html — по нему rebuild_from_feed пересоберёт все страницы
        html_renderer.rebuild_from_feed("https://feed.addwine.ru")
        print("✅ Страницы статей пересобраны")
        html_renderer.rebuild_index()
        print("✅ Главная + категории + sitemap пересобраны")
    except Exception as e:
        print(f"[!] rebuild упал: {e}")
        import traceback
        traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
