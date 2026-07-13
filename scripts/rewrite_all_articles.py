"""
Полная переписка всех существующих статей под новую SEO-схему:
- 4800-5800 знаков
- FAQ секция в конце (для FAQPage schema)
- HowTo recipe блок для коктейлей
- ключи из Wordstat в title/H2/лиде
- расширенная схема + автолинковка entities

Работает батчами по 5 статей — чтобы не упереться в rate limit Claude.
"""
import json
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import seo_planner
import feed_io
import html_renderer

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

SKIP_KEYWORDS = ["дайджест", "самое интересное за нед", "события недели",
                 "главные статьи нед", "винный дайджест"]

REWRITE_SYSTEM = """Ты — SEO-редактор и главный автор винного журнала AddWine. Тебе дают старую статью (title, lead, body) + реальные ключи из Яндекс.Wordstat.

ЗАДАЧА: переписать статью под новые SEO-требования Яндекса.

ТРЕБОВАНИЯ:
1. Объём body: 4800–5800 знаков с пробелами.
2. Топ-1 ключ ОБЯЗАТЕЛЬНО в title (H1), первом предложении лида, первом абзаце статьи.
3. Топ-2, топ-3 ключей — в подзаголовках H2/H3 и первых 100 словах.
4. Long-tail ключи — в подзаголовках и тексте.
5. В КОНЦЕ статьи ОБЯЗАТЕЛЬНО добавь секцию FAQ:
   <h2>Частые вопросы</h2>
   <div class="faq">
     <h3>Вопрос 1?</h3>
     <p>Ответ 30-60 слов.</p>
     <h3>Вопрос 2?</h3>
     <p>Ответ.</p>
     <h3>Вопрос 3?</h3>
     <p>Ответ.</p>
     <h3>Вопрос 4?</h3>
     <p>Ответ.</p>
   </div>
6. ЕСЛИ тема — конкретный коктейль (Негрони, Мохито, Мартини, Маргарита, Олд Фэшн, Манхэттен, Дайкири и т.п.) — добавь после первого абзаца блок рецепта:
   <h2>Рецепт [название]</h2>
   <div class="recipe">
     <p><b>Ингредиенты:</b></p>
     <ul><li>...</li></ul>
     <p><b>Способ приготовления:</b></p>
     <ol><li>Шаг 1.</li><li>Шаг 2.</li></ol>
   </div>

СОХРАНИ первую <p>[[IMG_1]]</p> или <figure> с картинкой — она уже есть в теле, не выбрасывай.

Тон: экспертный, редакторский, для аудитории 30-55.

HTML-теги ТОЛЬКО: <p>, <h2>, <h3>, <h4>, <ul>, <ol>, <li>, <blockquote>, <b>, <i>, <a>, <figure>, <img>, <figcaption>, <div class="faq">, <div class="recipe">.

ФОРМАТ ОТВЕТА — строго JSON:
{
  "new_title": "<новый title 50-90 символов, включает топ-1 ключ>",
  "new_lead": "<новый лид 130-155 символов, включает топ-1 и топ-2 ключи>",
  "new_body": "<новое тело статьи в HTML — 4800-5800 знаков, с FAQ, картинкой, [возможно рецептом]>"
}
"""


def load_posts() -> list:
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def save_posts(posts: list) -> None:
    POSTS_INDEX.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def should_skip(post: dict) -> bool:
    title_low = post.get("title", "").lower()
    return any(k in title_low for k in SKIP_KEYWORDS)


def get_body_from_feed(feed_data: dict, slug: str) -> str:
    for item in feed_data.get("items", []):
        link = item.get("link") or item.get("guid") or ""
        if slug in link:
            return item.get("content_html", "")
    return ""


def preserve_first_image(new_body: str, old_body: str) -> str:
    """Если Claude выбросил <figure>/<img> — вставляем первую из старого body."""
    if "<img" in new_body:
        return new_body
    m = re.search(r'(<figure[^>]*>.*?</figure>|<p>\s*<img[^>]+/?>\s*</p>)', old_body, flags=re.S)
    if m:
        first_img = m.group(1)
        # Ставим после первого </p>
        return re.sub(r'(</p>)', r'\1\n' + first_img, new_body, count=1)
    return new_body


def rewrite_one(post: dict, feed_data: dict) -> bool:
    slug = post["slug"]
    title = post.get("title", "")
    lead = post.get("lead", "")

    print(f"\n▶ {slug}")
    print(f"  title: {title[:80]}")

    old_body = get_body_from_feed(feed_data, slug)
    if not old_body:
        print(f"  [!] body не найден в feed.xml, пропускаем")
        return False

    # SEO discovery через planner
    keywords = seo_planner.discover_keywords(title, lead=lead, limit=15)
    keywords_hint = seo_planner.format_seo_brief(keywords)
    if not keywords_hint:
        print(f"  [!] SEO-планер не дал ключей — пишем всё равно (усилим FAQ и структуру)")
        keywords_hint = "Ключей из Wordstat нет — просто напиши глубокую статью с FAQ."

    user_prompt = f"""СТАРАЯ СТАТЬЯ:

Title: {title}

Lead: {lead}

Body:
{old_body[:5000]}

---
{keywords_hint}

Переписывай в JSON согласно системному промпту."""

    try:
        result = claude_api.generate_json(REWRITE_SYSTEM, user_prompt, max_tokens=10000, temperature=0.4)
    except Exception as e:
        print(f"  [!] Claude упал: {e}")
        return False

    new_title = (result.get("new_title") or "").strip()
    new_lead = (result.get("new_lead") or "").strip()
    new_body = (result.get("new_body") or "").strip()

    if not new_title or not new_lead or not new_body:
        print(f"  [!] Claude вернул пустые поля")
        return False

    # длина проверка
    plain = re.sub(r'<[^>]+>', ' ', new_body)
    plain = re.sub(r'\s+', ' ', plain).strip()
    print(f"  ✅ title: {new_title[:70]}")
    print(f"  ✅ body: {len(plain)} знаков")
    if len(plain) < 3500:
        print(f"  ⚠️  body короткий")

    # сохраняем первую картинку если Claude забыл
    new_body = preserve_first_image(new_body, old_body)

    post["title"] = new_title
    post["lead"] = new_lead

    # Обновляем feed.xml для этого item
    for item in feed_data.get("items", []):
        link = item.get("link") or item.get("guid") or ""
        if slug in link:
            item["title"] = new_title
            item["description"] = new_lead
            item["content_html"] = new_body
            break

    return True


def main():
    posts = load_posts()
    feed_data = feed_io.read_feed()

    candidates = [p for p in posts if not should_skip(p)]
    print(f"Всего кандидатов на переписку: {len(candidates)}")

    updated = 0
    for i, post in enumerate(candidates, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(candidates)}]")
        try:
            if rewrite_one(post, feed_data):
                updated += 1
        except Exception as e:
            print(f"[!] упал: {e}")
            traceback.print_exc()
        time.sleep(0.5)  # rate limit safety

    save_posts(posts)
    print(f"\n✅ posts_index.json обновлён")
    feed_io.write_feed(feed_data["channel"], feed_data["items"])
    print(f"✅ feed.xml обновлён")

    print(f"\nПересобираем все HTML...")
    try:
        html_renderer.rebuild_from_feed("https://feed.addwine.ru")
        html_renderer.rebuild_index()
        print("✅ все HTML пересобраны")
    except Exception as e:
        print(f"[!] rebuild упал: {e}")
        traceback.print_exc()

    print(f"\n=== ИТОГО переписано {updated}/{len(candidates)} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
