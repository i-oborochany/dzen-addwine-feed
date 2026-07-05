"""
Точка входа для еженедельного дайджеста-трейлера.
- Читает posts_index.json
- Берёт все статьи за прошедшие 7 дней (кроме самих дайджестов)
- Claude пишет трейлеры с заголовками-ссылками на статьи на feed.addwine.ru
- Картинки НЕ генерирует — использует существующие cover-1.jpg из папок статей.
"""
import os
import sys
import shutil
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_digest
import publisher
import progress as progress_mod

DIGEST_INTERVAL_DAYS = 6
MIN_ARTICLES = 2

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


def find_cover_for_post(slug: str) -> Path:
    """Ищет cover-1.jpg в папке images/<slug>/. Возвращает Path или None."""
    p = IMAGES_DIR / slug / "cover-1.jpg"
    if p.exists() and p.stat().st_size > 1000:
        return p
    return None


def main() -> int:
    config_path = REPO_ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    pages_base = config["channel"]["pages_base_url"].rstrip("/")

    progress = progress_mod.load_progress()

    if not can_publish_today(progress) and not os.environ.get("FORCE_PUBLISH"):
        last = progress.get("last_digest_post", "?")
        print(f"⚠️  Последний дайджест был {last}, ещё не прошло {DIGEST_INTERVAL_DAYS} дней. Пропускаем.")
        return 0

    print("=" * 60)
    print(f"ДАЙДЖЕСТ-ТРЕЙЛЕР — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    print("\n[1/4] Читаем posts_index.json — статьи за прошедшие 7 дней")
    posts = weekly_digest.load_posts_for_week(days=7)
    print(f"  найдено: {len(posts)}")
    for i, p in enumerate(posts, 1):
        print(f"  {i}. {p['title'][:70]}  ({p.get('published_at', '')[:10]})")

    if len(posts) < MIN_ARTICLES:
        print(f"  ⚠️  меньше {MIN_ARTICLES} — пропускаем")
        return 0

    # slug дайджеста
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"{today}-samoe-interesnoe-za-nedelyu"
    folder = IMAGES_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    print(f"\n[2/4] Копируем существующие cover-1.jpg каждой статьи в {folder.name}/")
    image_urls = []
    valid_posts = []
    for i, p in enumerate(posts, 1):
        src = find_cover_for_post(p["slug"])
        if src is None:
            print(f"  {i}. ⚠️  нет cover-1.jpg у «{p['title'][:50]}» — пропускаем статью")
            continue
        dst = folder / f"cover-{len(valid_posts) + 1}.jpg"
        shutil.copy(src, dst)
        image_urls.append(f"images/{slug}/{dst.name}")
        valid_posts.append(p)
        print(f"  {len(valid_posts)}. ✅ {p['slug']} → {dst.name} ({dst.stat().st_size} байт)")

    if len(valid_posts) < MIN_ARTICLES:
        print(f"  ⚠️  меньше {MIN_ARTICLES} валидных статей — пропускаем")
        return 0

    print(f"\n[3/4] Claude пишет дайджест-трейлер из {len(valid_posts)} статей")
    digest = weekly_digest.build_digest(valid_posts, pages_base)
    print(f"  заголовок: {digest['title']}")
    print(f"  длина HTML: {len(digest['html'])} символов")

    digest["title_chosen"] = digest["title"]

    print("\n[4/4] Публикуем в feed.xml и на сайт")
    publisher.add_to_feed(digest, image_urls, "", config)

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
