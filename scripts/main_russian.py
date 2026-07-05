"""
Точка входа для публикации статьи про российское виноделие.
Запускается раз в 3 дня отдельным workflow.
Идёт в тот же feed.xml и на сайт feed.addwine.ru через publisher.add_to_feed.
"""
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import russian_writer
import openai_api
import publisher
import progress as progress_mod
import addwine_linker


RUSSIAN_INTERVAL_DAYS = 3


def can_publish_today(progress: dict) -> bool:
    """Защита от двойной публикации: проверяем что прошло >= 3 дня с последней русской статьи."""
    last = progress.get("last_russian_post")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        days_passed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
        return days_passed >= RUSSIAN_INTERVAL_DAYS - 0.1  # небольшой допуск
    except Exception:
        return True


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    progress = progress_mod.load_progress()

    if not can_publish_today(progress) and not os.environ.get("FORCE_PUBLISH"):
        last = progress.get("last_russian_post", "?")
        print(f"⚠️  Последняя русская статья была {last}, ещё не прошло {RUSSIAN_INTERVAL_DAYS} дней. Пропускаем.")
        print("    Чтобы форсировать — установи FORCE_PUBLISH=1")
        return 0

    # история русских заголовков для дедупа
    russian_titles = []
    for h in progress.get("history", []):
        if h.get("topic_type") == "russian":
            russian_titles.append(h.get("title", ""))

    print("=" * 60)
    print(f"РУССКОЕ ВИНОДЕЛИЕ — публикация {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Уже опубликовано русских статей: {len(russian_titles)}")

    print("\n[1/4] Выбираем тему")
    topic = russian_writer.pick_topic(russian_titles)
    print(f"  → {topic}")

    print("\n[2/4] Claude пишет статью в патриотическом тоне")
    article = russian_writer.write_russian_article(topic, russian_titles)
    print(f"  заголовок: {article['title_chosen']}")
    print(f"  категории: {article['categories']}")
    print(f"  длина html: {len(article['html'])} символов")

    # для совместимости с publisher
    article["title"] = article["title_chosen"]

    print("\n[2.5/4] Нативная вставка ссылки на addwine.ru")
    try:
        links = addwine_linker.fetch_links()
        print(f"  доступно {len(links)} ссылок")
        result = addwine_linker.inject_link(article["html"], links)
        if result.get("link_inserted"):
            article["html"] = result["html"]
            print(f"  ✅ вставлена: {result.get('selected_title')}")
        else:
            print("  ⚠️  пропущено (нет подходящей)")
    except Exception as e:
        print(f"  [!] {e}")

    print("\n[3/4] Генерим 1 фото через gpt-image-1 (без людей, без лиц, без текста)")
    images = []
    for i, prompt in enumerate(article["image_prompts"][:1], 1):
        print(f"  фото {i}/1 ...")
        try:
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

    publisher.add_to_feed(article, image_urls, "", config)

    # обновляем history с пометкой russian
    progress_mod.append_history(progress, article["title"], progress.get("cycle_position", 1), "russian", "")
    # сохраняем дату последней русской публикации
    progress["last_russian_post"] = datetime.now(timezone.utc).isoformat()
    progress_mod.save_progress(progress)

    print("\n  progress.json обновлён, last_russian_post =", progress["last_russian_post"][:19])
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
