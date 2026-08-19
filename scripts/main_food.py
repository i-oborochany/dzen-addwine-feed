"""
Точка входа для публикации статьи «Вино и еда».
Запускается через workflow food.yml по нечётным дням месяца.
"""
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import food_writer
import openai_api
import publisher
import progress as progress_mod
import addwine_linker
import seo_planner

INTERVAL_HOURS = 40  # минимум 40 часов между двумя food-публикациями


def can_publish_today(progress: dict) -> bool:
    last = progress.get("last_food_post")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        hours_passed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        return hours_passed >= INTERVAL_HOURS
    except Exception:
        return True


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    progress = progress_mod.load_progress()

    if not can_publish_today(progress) and not os.environ.get("FORCE_PUBLISH"):
        last = progress.get("last_food_post", "?")
        print(f"⚠️  Последняя food-статья была {last}, ещё не прошло {INTERVAL_HOURS} часов. Пропускаем.")
        return 0

    food_titles = []
    for h in progress.get("history", []):
        if h.get("topic_type") == "food":
            food_titles.append(h.get("title", ""))

    print("=" * 60)
    print(f"ВИНО И ЕДА — публикация {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Уже опубликовано food-статей: {len(food_titles)}")

    print("\n[1/4] Выбираем тему (с семантическим дедупом на 90 дней)")
    topic = food_writer.pick_topic(food_titles, history=progress.get("history", []))
    print(f"  → {topic}")

    print("\n[1.5/4] SEO-планирование: Claude → фразы → Wordstat → топ ключей")
    keywords = seo_planner.discover_keywords(topic, lead="", limit=15)
    keywords_hint = seo_planner.format_seo_brief(keywords)

    print("\n[2/4] Claude пишет гастрономическую статью ПОД эти ключи")
    article = food_writer.write_food_article(topic, food_titles, keywords_hint=keywords_hint)
    print(f"  заголовок: {article['title_chosen']}")
    print(f"  категории: {article['categories']}")
    print(f"  ссылка на кухню: {article['_kitchen_category']['title']} → {article['_kitchen_category']['url']}")
    print(f"  длина html: {len(article['html'])} символов")

    article["title"] = article["title_chosen"]

    print("\n[2.5/4] Дополнительная нативная вставка ссылки на addwine.ru")
    try:
        links = addwine_linker.fetch_links()
        result = addwine_linker.inject_link(article["html"], links)
        if result.get("link_inserted"):
            article["html"] = result["html"]
            print(f"  ✅ вставлена: {result.get('selected_title')}")
        else:
            print("  ⚠️  addwine_linker пропущен (уже есть ссылка на кухню в тексте)")
    except Exception as e:
        print(f"  [!] не критично: {e}")

    print("\n[3/4] Генерим 1 фото через gpt-image-1 (medium)")
    images = []
    for i, prompt in enumerate(article["image_prompts"][:1], 1):
        print(f"  фото {i}/1 ...")
        try:
            import image_style
            prompt = image_style.enrich(prompt, article.get("title", "") or article.get("title_chosen", ""))
            img = openai_api.generate_image(prompt)
            images.append(img)
            print(f"     ok, {len(img)} байт")
        except Exception as e:
            print(f"     [!] {e}")
            raise

    print("\n[4/4] Сохраняем картинки + добавляем в feed.xml")
    slug = publisher.slugify(article["title"])
    image_urls = publisher.save_images(images, slug)
    for u in image_urls:
        print(f"  -> {u}")

    publisher.add_to_feed(article, image_urls, article["_kitchen_category"]["url"], config)

    progress_mod.append_history(progress, article["title"], progress.get("cycle_position", 1), "food", article["_kitchen_category"]["url"])
    progress["last_food_post"] = datetime.now(timezone.utc).isoformat()
    progress_mod.save_progress(progress)

    print(f"\n  progress.json обновлён, last_food_post = {progress['last_food_post'][:19]}")
    print("=" * 60)
    print("SUCCESS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)
