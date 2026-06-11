"""
Точка входа для еженедельного дайджеста винных новостей.
Запускается каждое воскресенье через workflow weekly_digest.yml.
"""
import os
import re
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digest_sources
import weekly_digest
import publisher
import progress as progress_mod

DIGEST_INTERVAL_DAYS = 6  # каждое воскресенье (с допуском)
MAX_ARTICLES = 7
MIN_ARTICLES = 3

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"


def can_publish_today(progress: dict) -> bool:
    last = progress.get("last_digest_post")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        days_passed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
        return days_passed >= DIGEST_INTERVAL_DAYS - 0.5
    except Exception:
        return True


def main() -> int:
    config_path = REPO_ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    progress = progress_mod.load_progress()

    if not can_publish_today(progress) and not os.environ.get("FORCE_PUBLISH"):
        last = progress.get("last_digest_post", "?")
        print(f"⚠️  Последний дайджест был {last}, ещё не прошло {DIGEST_INTERVAL_DAYS} дней. Пропускаем.")
        return 0

    print("=" * 60)
    print(f"ВИННЫЙ ДАЙДЖЕСТ — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # окно дат: либо явное из env (для теста), либо последние 7 дней
    date_from = None
    date_to = None
    env_from = os.environ.get("DIGEST_DATE_FROM", "").strip()
    env_to = os.environ.get("DIGEST_DATE_TO", "").strip()
    if env_from and env_to:
        try:
            date_from = datetime.fromisoformat(env_from).replace(tzinfo=timezone.utc)
            # date_to до конца дня
            date_to = datetime.fromisoformat(env_to).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            print(f"\nОкно дат (явно из env): {date_from.date()} — {date_to.date()}")
        except Exception as e:
            print(f"  [!] не смог распарсить даты: {e}, использую последние 7 дней")
            date_from = date_to = None

    print("\n[1/5] Собираем статьи с 4 источников")
    articles = digest_sources.collect_all(days=7, date_from=date_from, date_to=date_to)
    print(f"  всего: {len(articles)} статей")

    if len(articles) < MIN_ARTICLES:
        print(f"  слишком мало (<{MIN_ARTICLES}), выходим")
        return 1

    # сортируем по дате (свежие первые), берём топ
    articles = sorted(
        articles,
        key=lambda a: a["pub_date"] or datetime(2000, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )[:MAX_ARTICLES]
    print(f"\n  Отобрано в дайджест: {len(articles)}")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. [{a['source']}] {a['title'][:80]}")

    # slug дайджеста
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"{today}-vinnye-sobytiya-nedeli"
    folder = IMAGES_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    print("\n[2/5] Скачиваем картинки")
    image_urls = []
    for i, art in enumerate(articles, 1):
        fname = f"cover-{i}.jpg"
        save_path = folder / fname
        ok = digest_sources.download_image_to(art["image_url"], save_path)
        if ok and save_path.exists() and save_path.stat().st_size > 1000:
            print(f"  {i}. ✅ {save_path.stat().st_size} байт")
            image_urls.append(f"images/{slug}/{fname}")
        else:
            print(f"  {i}. ⚠️  не удалось скачать — используем первую картинку как fallback")
            if image_urls:
                # копируем первую
                import shutil
                shutil.copy(folder / "cover-1.jpg", save_path)
                image_urls.append(f"images/{slug}/{fname}")
            else:
                # вообще нет картинок — пропускаем эту статью
                art["_skip"] = True

    # убираем те новости где картинка не загрузилась И не было fallback'а
    articles = [a for a in articles if not a.get("_skip")]
    image_urls = image_urls[:len(articles)]

    if not articles:
        print("  ни одной картинки — отменяем публикацию")
        return 1

    print(f"\n[3/5] Claude собирает дайджест из {len(articles)} новостей")
    digest = weekly_digest.build_digest(articles)
    print(f"  заголовок: {digest['title']}")
    print(f"  длина HTML: {len(digest['html'])} символов")

    # для совместимости с publisher
    digest["title_chosen"] = digest["title"]

    print("\n[4/5] Публикуем в feed.xml и на сайт")
    publisher.add_to_feed(digest, image_urls, "", config)

    print("\n[5/5] Обновляем progress.json")
    progress_mod.append_history(progress, digest["title"], 0, "digest", "")
    progress["last_digest_post"] = datetime.now(timezone.utc).isoformat()
    progress_mod.save_progress(progress)

    print(f"  last_digest_post = {progress['last_digest_post'][:19]}")
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
