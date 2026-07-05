"""
Точка входа. Цикл из 5 статей:
- статьи 1..4: TREND mode (Claude пишет с нуля по актуальной теме)
- статья 5: CONTENT_PLAN mode (по строке плана с CTA)
"""
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources
import writer
import openai_api
import publisher
import progress as progress_mod
import addwine_linker


def already_published_today(progress: dict) -> bool:
    """Защита от двойного запуска: если сегодня уже публиковали, выходим."""
    history = progress.get("history", [])
    if not history:
        return False
    try:
        last_date = datetime.fromisoformat(history[0]["date"])
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        today = datetime.now(timezone.utc).date()
        return last_date.date() == today
    except Exception:
        return False


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    progress = progress_mod.load_progress()

    # дедуп: если сегодня уже было — пропускаем (защита от тройного cron)
    if already_published_today(progress) and not os.environ.get("FORCE_PUBLISH"):
        last = progress["history"][0]
        print(f"⚠️  Сегодня уже публиковали: '{last.get('title')}' в {last.get('date')}")
        print("    Пропускаем запуск. Чтобы форсировать — установи FORCE_PUBLISH=1")
        return 0

    cycle_pos = progress.get("cycle_position", 1)
    plan_idx = progress.get("content_plan_index", 0)

    print("=" * 60)
    print(f"Позиция в цикле: {cycle_pos}/5")

    if cycle_pos == 5:
        # CONTENT_PLAN режим
        plan = progress_mod.load_content_plan()
        if plan_idx >= len(plan):
            print(f"Контент-план исчерпан ({plan_idx}/{len(plan)}), начинаем сначала")
            plan_idx = 0
        plan_row = plan[plan_idx]

        print(f"\n[1/4] Контент-план строка #{plan_row['number']}: {plan_row['title']}")
        print(f"  Категория: {plan_row['promote_category']} → {plan_row['promote_link']}")

        print("\n[2/4] Claude пишет статью с CTA")
        article = writer.write_content_plan_article(plan_row)
        topic_type = "content_plan"
        source_url = plan_row["promote_link"]
    else:
        # TREND режим
        print("\n[1/4] Собираем заголовки-затравки из источников")
        seeds = sources.collect_seeds(config)
        print(f"  всего заголовков: {len(seeds)}")
        if len(seeds) < 5:
            print("  слишком мало затравок, выходим")
            return 1

        recent_titles = progress_mod.recent_titles(progress, days=60)
        print(f"  заголовков в истории (60 дней): {len(recent_titles)}")

        print("\n[2/4] Claude выбирает тему и пишет статью с нуля")
        article = writer.write_trend_article(seeds, recent_titles, config.get("brand_colors", {}))
        topic_type = "trend"
        source_url = ""

    print(f"  заголовок: {article['title_chosen']}")
    print(f"  длина html: {len(article['html'])} символов")

    # для совместимости с publisher.add_to_feed
    article["title"] = article["title_chosen"]

    # ---- Нативная вставка ссылки на addwine.ru ----
    print("\n[2.5/4] Нативная вставка ссылки на addwine.ru (категория или бренд)")
    try:
        links = addwine_linker.fetch_links()
        print(f"  доступно {len(links)} ссылок из sitemap'ов")
        result = addwine_linker.inject_link(article["html"], links)
        if result.get("link_inserted"):
            article["html"] = result["html"]
            print(f"  ✅ вставлена: {result.get('selected_title')} → {result.get('selected_url')}")
        else:
            print("  ⚠️  не вставлена (Claude не нашёл тематически подходящей)")
    except Exception as e:
        print(f"  [!] не критично: {e}")

    print("\n[3/4] Генерим 1 фото через gpt-image-1 (medium)")
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

    publisher.add_to_feed(article, image_urls, source_url, config)

    # обновляем journal
    progress_mod.append_history(progress, article["title"], cycle_pos, topic_type, source_url)
    progress_mod.advance_cycle(progress, topic_type)
    progress_mod.save_progress(progress)

    # дополнительно: дублируем в published.json для дедупликации URL
    if source_url:
        publisher.mark_published(source_url, article["title"])

    print("\nСохранили progress.json:")
    print(f"  следующая позиция: {progress['cycle_position']}/5")
    print(f"  индекс плана: {progress['content_plan_index']}")
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
