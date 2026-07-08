"""
Единая точка входа для всех 4 «extra»-рубрик.
Читает env RUBRIC (spirits/beer/water/fortified) и запускает соответствующий поток.
"""
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extras_writer
import openai_api
import publisher
import progress as progress_mod
import wordstat_api

INTERVAL_HOURS = 88  # минимум ~3.7 дня между статьями одной рубрики


def can_publish_now(progress: dict, progress_key: str) -> bool:
    last = progress.get(progress_key)
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
    rubric = os.environ.get("RUBRIC", "").strip().lower()
    if rubric not in ("spirits", "beer", "water", "fortified"):
        print(f"⚠️  Неизвестная рубрика: '{rubric}'. Должно быть: spirits/beer/water/fortified")
        return 1

    cfg = extras_writer.load_config(rubric)
    print("=" * 60)
    print(f"РУБРИКА: {cfg['rubric_name']} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    site_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    progress = progress_mod.load_progress()

    if not can_publish_now(progress, cfg["progress_key"]) and not os.environ.get("FORCE_PUBLISH"):
        last = progress.get(cfg["progress_key"], "?")
        print(f"⚠️  Последняя статья была {last}, ещё не прошло {INTERVAL_HOURS} часов. Пропускаем.")
        return 0

    # история этой рубрики
    used_titles = [h.get("title", "") for h in progress.get("history", []) if h.get("topic_type") == rubric]
    print(f"Уже опубликовано в рубрике: {len(used_titles)}")

    print("\n[1/4] Выбираем тему")
    topic = extras_writer.pick_topic(cfg, used_titles)
    print(f"  → {topic}")

    print("\n[1.5/4] Yandex Wordstat — подбор SEO-ключей")
    keywords = wordstat_api.get_keywords(topic, limit=15)
    keywords_hint = wordstat_api.format_for_prompt(keywords)

    print("\n[2/4] Claude пишет статью")
    try:
        article = extras_writer.write_article(rubric, topic, used_titles, keywords_hint=keywords_hint)
    except Exception as e:
        print(f"  [!!] Claude/парсинг упал: {type(e).__name__}: {e}")
        raise
    print(f"  заголовок: {article['title_chosen']}")
    print(f"  категории: {article['categories']}")
    print(f"  ссылка на AddWine: {article['_link_used']['title']} → {article['_link_used']['url']}")
    print(f"  длина html: {len(article['html'])} символов")
    print(f"  длина image prompt: {len(article['image_prompts'][0])} симв.")

    article["title"] = article["title_chosen"]

    print("\n[3/4] Генерим 1 фото через gpt-image-1")
    images = []
    for i, prompt in enumerate(article["image_prompts"][:1], 1):
        print(f"  фото {i}/1 ...")
        print(f"     промпт (первые 150 симв.): {prompt[:150]}")
        try:
            img = openai_api.generate_image(prompt)
            images.append(img)
            print(f"     ok, {len(img)} байт")
        except Exception as e:
            print(f"     [!!] OpenAI упал: {type(e).__name__}: {e}")
            raise

    print("\n[4/4] Сохраняем + добавляем в feed.xml")
    slug = publisher.slugify(article["title"])
    image_urls = publisher.save_images(images, slug)
    for u in image_urls:
        print(f"  -> {u}")

    try:
        publisher.add_to_feed(article, image_urls, article["_link_used"]["url"], site_config)
    except Exception as e:
        print(f"  [!!] publisher.add_to_feed упал: {type(e).__name__}: {e}")
        raise

    progress_mod.append_history(progress, article["title"], progress.get("cycle_position", 1), rubric, article["_link_used"]["url"])
    progress[cfg["progress_key"]] = datetime.now(timezone.utc).isoformat()
    progress_mod.save_progress(progress)

    print(f"\n  progress.json обновлён, {cfg['progress_key']} = {progress[cfg['progress_key']][:19]}")
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
