"""
Агент актуализации: статьи старше N дней получают свежий абзац,
синонимизированный title/lead, обновлённый dateModified. Улучшает SEO —
Яндекс/Google любят регулярно обновляемые страницы.

Запускается раз в неделю через workflow. Обрабатывает до BATCH статей за прогон,
чтобы не тратить весь API-баланс за раз.
"""
import json
import re
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import feed_io
import html_renderer

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

MIN_AGE_DAYS = 90     # Актуализируем статьи старше 90 дней
BATCH = 5             # До 5 статей за прогон
SKIP_KEYWORDS = ["дайджест", "самое интересное", "события недели"]


REFRESH_SYSTEM = """Ты — SEO-редактор винного журнала AddWine. Тебе дают статью, которая была опубликована 3+ месяцев назад. Задача — освежить её так, чтобы Яндекс и Google засчитали обновление, а читатель получил свежую информацию.

СТРОГО:
1. Синонимизируй title и lead — смысл сохрани, формулировку измени. Ключевое слово оставь, но переставь или замени вариацией.
2. Добавь ОДИН свежий абзац в 2-3 предложения (60-100 слов) — актуальное наблюдение, уточнение, новый нюанс по теме. Не выдумывай факты — если точных данных нет, дай общее полезное дополнение.
3. Новый абзац оберни в <p class="refresh-2026">...</p> — чтобы было видно где вставка.
4. Не переписывай статью, не меняй структуру, slug, категории, картинки.

ФОРМАТ ОТВЕТА — строго JSON:
{
  "new_title": "<обновлённый title 50-90 символов>",
  "new_lead": "<обновлённый лид 130-155 символов>",
  "fresh_paragraph": "<p class=\\"refresh-2026\\">Новый абзац...</p>"
}
"""


def load_posts():
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def save_posts(posts):
    POSTS_INDEX.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def should_skip(post):
    tl = post.get("title", "").lower()
    return any(k in tl for k in SKIP_KEYWORDS)


def old_enough(post, min_days):
    date_str = post.get("published_at", "")
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days >= min_days
    except Exception:
        return False


def insert_paragraph(body_html: str, fresh_p: str) -> str:
    """Вставляет свежий абзац после первого </p> или после первого <figure>."""
    # Если уже есть refresh-2026 в этой статье — заменяем на новый
    if 'class="refresh-2026"' in body_html:
        return re.sub(r'<p\s+class="refresh-2026"[^>]*>.*?</p>', fresh_p, body_html, flags=re.S)
    # Вставляем после первого figure если есть
    m = re.search(r'</figure>', body_html)
    if m:
        return body_html[:m.end()] + "\n" + fresh_p + body_html[m.end():]
    # Иначе после первого закрывающего </p>
    m = re.search(r'</p>', body_html)
    if m:
        return body_html[:m.end()] + "\n" + fresh_p + body_html[m.end():]
    return fresh_p + body_html


def refresh_one(post, feed_data) -> bool:
    slug = post["slug"]
    title = post.get("title", "")
    lead = post.get("lead", "")

    print(f"\n▶ {slug}")
    print(f"  title: {title[:70]}")

    # Найдём body в feed.xml
    body = ""
    feed_item = None
    for item in feed_data.get("items", []):
        link = item.get("link") or item.get("guid") or ""
        if slug in link:
            body = item.get("content_html", "")
            feed_item = item
            break
    if not body:
        print(f"  [!] body в feed.xml не найден")
        return False

    user = f"""СТАРЫЙ TITLE: {title}

СТАРЫЙ LEAD: {lead}

СТАРЫЙ BODY (первые 3000 символов):
{body[:3000]}

Освежи по правилам системного промпта. Ответ — JSON."""

    try:
        result = claude_api.generate_json(REFRESH_SYSTEM, user, max_tokens=1500, temperature=0.4)
    except Exception as e:
        print(f"  [!] Claude упал: {e}")
        return False

    new_title = (result.get("new_title") or "").strip()
    new_lead = (result.get("new_lead") or "").strip()
    fresh_p = (result.get("fresh_paragraph") or "").strip()

    if not new_title or not new_lead or not fresh_p:
        print(f"  [!] Claude не вернул нужных полей")
        return False

    print(f"  ✅ title: {new_title[:70]}")
    print(f"  ✅ +абзац: {fresh_p[:80]}")

    # Обновляем posts_index.json
    post["title"] = new_title
    post["lead"] = new_lead

    # Обновляем feed.xml item
    if feed_item:
        feed_item["title"] = new_title
        feed_item["description"] = new_lead
        feed_item["content_html"] = insert_paragraph(body, fresh_p)
        # обновляем pub_date, но осторожно — многие RSS-читалки ре-показывают статью
        # оставим pub_date, но JSON-LD в html renderer использует dateModified = now
    return True


def main():
    posts = load_posts()
    feed_data = feed_io.read_feed()

    # Кандидаты: не дайджесты + старше MIN_AGE_DAYS + сортировка от самых старых
    candidates = [p for p in posts if not should_skip(p) and old_enough(p, MIN_AGE_DAYS)]
    candidates.sort(key=lambda p: p.get("published_at", ""))

    print(f"Всего статей старше {MIN_AGE_DAYS} дней: {len(candidates)}")
    print(f"Обрабатываем первые {BATCH}")

    updated = 0
    for post in candidates[:BATCH]:
        try:
            if refresh_one(post, feed_data):
                updated += 1
        except Exception as e:
            print(f"[!] fatal: {e}")
            traceback.print_exc()

    save_posts(posts)
    feed_io.write_feed(feed_data["channel"], feed_data["items"])
    print(f"\n✅ posts_index.json + feed.xml сохранены")

    print("\nПересобираем HTML...")
    try:
        html_renderer.rebuild_from_feed("https://feed.addwine.ru")
        html_renderer.rebuild_index()
        print("✅ страницы + главная + категории")
    except Exception as e:
        print(f"[!] rebuild: {e}")

    # IndexNow пинг для обновлённых URL
    try:
        import indexnow_ping
        refreshed_urls = [f"https://feed.addwine.ru/posts/{p['slug']}/"
                          for p in candidates[:BATCH]]
        indexnow_ping.ping_urls(refreshed_urls)
    except Exception as e:
        print(f"[!] IndexNow: {e}")

    print(f"\n=== ИТОГО актуализировано {updated}/{min(BATCH, len(candidates))} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
