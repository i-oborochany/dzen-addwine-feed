"""
Автоматический дожим статей на позициях 4-15 в Яндексе/Google.
Логика: находим страницы близкие к топ-3, для каждой Claude усиливает
недостающее (глубина, конкретика, таблицы, FAQ, свежий блок).

BATCH — сколько статей за прогон. Обычно 3-5 чтобы не тратить весь баланс.
"""
import json
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import feed_io
import html_renderer
import topvisor_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"

BATCH = 3  # До 3 статей за прогон
MIN_POS = 4
MAX_POS = 15


BOOST_SYSTEM = """Ты — SEO-редактор винного журнала AddWine. Тебе дают статью, которая почти пробилась в топ-3 Яндекса/Google по ключевым запросам. Задача — усилить статью так чтобы она войти в топ-3.

СТРАТЕГИЯ ДОЖИМА:
1. По каждому ключу проверь: правильно ли выделен в title, есть ли в первом абзаце и h2. Если нет — добавь.
2. Добавь блоки которых часто нет у конкурентов из топа: конкретная таблица сравнения, пронумерованный чек-лист, реальные цифры и имена, короткий FAQ (если ещё нет), 2-3 экспертных наблюдения.
3. Не переписывай статью с нуля. Только добавь недостающее и усиль слабое.
4. Общий объём должен вырасти на 20-40% (было 4800-5800 → станет 5800-7500).

ОСОБО:
- НЕ трогай <picture>, <figure>, <img>, HowTo-рецепты, FAQ-блоки — оставь как есть.
- Новые вставки помечай классом refresh-boost: <div class="refresh-boost">...</div>
- Если в статье уже есть refresh-boost блок — обнови/расширь его, не создавай второй.

ФОРМАТ ОТВЕТА — строго JSON:
{
  "new_title": "<title, если требует правки, иначе оригинальный>",
  "new_lead": "<lead, если требует правки, иначе оригинальный>",
  "new_body": "<полный body с добавленными блоками refresh-boost>"
}
"""


def load_posts():
    return json.loads(POSTS_INDEX.read_text(encoding="utf-8"))


def save_posts(posts):
    POSTS_INDEX.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def find_post_by_url(posts, url) -> dict:
    """Ищет статью в posts_index по URL."""
    m = re.search(r"/posts/([^/]+)/?", url)
    if not m:
        return None
    slug = m.group(1)
    for p in posts:
        if p.get("slug") == slug:
            return p
    return None


def boost_one(post, keywords, feed_data) -> bool:
    slug = post["slug"]
    title = post.get("title", "")
    lead = post.get("lead", "")

    print(f"\n▶ {slug}")
    print(f"  title: {title[:70]}")
    print(f"  ключи для дожима:")
    for k in keywords[:5]:
        print(f"    {k['se']:6}  #{k['pos']:3}  «{k['kw']}»")

    # Ищем body в feed
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

    keys_block = "\n".join(f"- «{k['kw']}» ({k['se']}, позиция {k['pos']})"
                          for k in keywords[:10])
    user = f"""СТАТЬЯ:

TITLE: {title}

LEAD: {lead}

BODY:
{body[:6000]}

КЛЮЧИ на позициях 4-15 (нужно дожать до топ-3):
{keys_block}

Усиль по правилам системного промпта. Ответ — JSON."""

    try:
        result = claude_api.generate_json(BOOST_SYSTEM, user, max_tokens=12000, temperature=0.3)
    except Exception as e:
        print(f"  [!] Claude упал: {e}")
        return False

    new_title = (result.get("new_title") or title).strip()
    new_lead = (result.get("new_lead") or lead).strip()
    new_body = (result.get("new_body") or "").strip()

    if not new_body:
        print(f"  [!] Claude не вернул body")
        return False

    old_len = len(re.sub(r'<[^>]+>', ' ', body))
    new_len = len(re.sub(r'<[^>]+>', ' ', new_body))
    print(f"  ✅ body: {old_len} → {new_len} знаков (+{new_len - old_len})")

    post["title"] = new_title
    post["lead"] = new_lead

    if feed_item:
        feed_item["title"] = new_title
        feed_item["description"] = new_lead
        feed_item["content_html"] = new_body
    return True


def main():
    candidates = topvisor_api.find_boost_candidates(min_pos=MIN_POS, max_pos=MAX_POS)
    if not candidates:
        print(f"✅ Кандидатов на дожим (позиции {MIN_POS}-{MAX_POS}) нет")
        return 0

    # Сортируем по средней позиции — чем ниже, тем важнее дожать
    for c in candidates:
        c["avg_pos"] = sum(k["pos"] for k in c["keywords"]) / len(c["keywords"])
    candidates.sort(key=lambda c: c["avg_pos"])

    print(f"Кандидатов на дожим: {len(candidates)}")
    print(f"Обрабатываем первые {BATCH} (самые близкие к топ-3)\n")

    posts = load_posts()
    feed_data = feed_io.read_feed()

    updated = 0
    boosted_urls = []
    for c in candidates[:BATCH]:
        post = find_post_by_url(posts, c["url"])
        if not post:
            print(f"  ⚠️  post не найден: {c['url']}")
            continue
        try:
            if boost_one(post, c["keywords"], feed_data):
                updated += 1
                boosted_urls.append(c["url"])
        except Exception as e:
            print(f"  [!] {e}")
            traceback.print_exc()

    save_posts(posts)
    feed_io.write_feed(feed_data["channel"], feed_data["items"])

    print("\nПересобираем HTML...")
    try:
        html_renderer.rebuild_from_feed("https://feed.addwine.ru")
        html_renderer.rebuild_index()
        print("✅ HTML пересобран")
    except Exception as e:
        print(f"[!] rebuild: {e}")

    # IndexNow пинг
    if boosted_urls:
        try:
            import indexnow_ping
            indexnow_ping.ping_urls(boosted_urls)
        except Exception as e:
            print(f"[!] IndexNow: {e}")

    print(f"\n=== ИТОГО дожато {updated}/{min(BATCH, len(candidates))} статей ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
