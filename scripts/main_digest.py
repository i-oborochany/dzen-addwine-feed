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
import claude_api
import openai_api


COVER_PROMPT_SYSTEM = """Ты — арт-директор винного журнала. Тебе дают заголовок винной новости. Сгенерируй ОДИН промпт для gpt-image-1 — атмосферное премиум-фото под эту новость.

СТИЛЬ: премиум-редакторская фотография как в Vogue Living / Robb Report. Тёплый свет, богатые материалы (мрамор, дерево, бархат, латунь), тонкие бокалы уровня Sydonios/Zalto, реальные винные аксессуары. Палитра: тёплый кремовый Pantone 7403 + тёмно-сине-зелёный Pantone 302 акцентами.

СЮЖЕТЫ ПО ТИПАМ НОВОСТЕЙ:
- Рейтинги/премии/ресторан: интерьер премиум-ресторана с бокалами на мраморной стойке, серебряная сервировка.
- Сорт/регион/терруар: виноградник в холмах на закате, крупный план грозди.
- Винодельня/винодел: винный погреб с дубовыми бочками, приглушённый свет.
- Технологии/наука: лаборатория с бокалами и рефрактометром, дегустационные бланки.
- Рынки/цены/деньги: элегантный винный аукцион, редкие бутылки на подсвеченных полках.
- Сомелье: сомелье в фартуке у барной стойки, спокойная поза, руки в свободном положении.
- Международные новости: дегустационный стол с бокалами разного вина, без людей крупным планом.

АНАТОМИЯ ЖЁСТКО:
- НИКАКИХ крупных планов рук с бокалами.
- НИКАКИХ тостов и чокания крупным планом.
- Если люди в кадре — руки спокойные, бокал стоит на столе, средний план.

БЕЗ текста, букв, цифр, логотипов на изображении.

Промпт минимум 100 слов, на русском. Включает: главный сюжет, ракурс, освещение, окружение, атмосферу, время суток.

ФОРМАТ ОТВЕТА — строго JSON: {"prompt": "<промпт>"}"""


def generate_cover_prompt(title: str, lead: str) -> str:
    """Через Claude просим промпт для конкретной новости."""
    try:
        user = f"Заголовок винной новости: {title}\n\nЛид: {lead[:400]}\n\nСгенерируй тематичный премиум-промпт."
        r = claude_api.generate_json(COVER_PROMPT_SYSTEM, user, max_tokens=800, temperature=0.6)
        prompt = r.get("prompt", "")
        if len(prompt) >= 50:
            return prompt
    except Exception as e:
        print(f"    [!] Claude не смог сгенерить промпт: {e}")
    return f"Премиум-редакторское фото винной атмосферы под тему: {title}. Тёплый свет, дегустационный стол с бокалами, богатый интерьер, без крупных планов рук, без текста."

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
    print(f"  всего по строгому окну: {len(articles)} статей")

    # Fallback: если по строгому окну мало — берём просто свежие за 14 дней без фильтра
    if len(articles) < MIN_ARTICLES:
        print(f"  ⚠️  меньше {MIN_ARTICLES} — fallback на просто свежие")
        articles = digest_sources.collect_all(days=14)
        print(f"  по fallback: {len(articles)} статей")

    if len(articles) < MIN_ARTICLES:
        print(f"  всё ещё слишком мало (<{MIN_ARTICLES}), выходим")
        return 1

    # нормализуем pub_date к tz-aware (UTC) — у некоторых сайтов datetime без tz
    def _norm_date(art):
        pd = art.get("pub_date")
        if pd is None:
            return datetime(2000, 1, 1, tzinfo=timezone.utc)
        if pd.tzinfo is None:
            return pd.replace(tzinfo=timezone.utc)
        return pd

    # сортируем по дате (свежие первые), берём топ
    articles = sorted(articles, key=_norm_date, reverse=True)[:MAX_ARTICLES]
    print(f"\n  Отобрано в дайджест: {len(articles)}")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. [{a['source']}] {a['title'][:80]}")

    # slug дайджеста
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"{today}-vinnye-sobytiya-nedeli"
    folder = IMAGES_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    print("\n[2/5] Генерим уникальные картинки через gpt-image-1 по заголовкам новостей")
    image_urls = []
    for i, art in enumerate(articles, 1):
        fname = f"cover-{i}.jpg"
        save_path = folder / fname
        print(f"  {i}. промпт для «{art['title'][:60]}...»")
        prompt = generate_cover_prompt(art["title"], art.get("lead", ""))
        print(f"     → {prompt[:100]}...")
        try:
            img_bytes = openai_api.generate_image(prompt)
            save_path.write_bytes(img_bytes)
            print(f"     ✅ {len(img_bytes)} байт")
            image_urls.append(f"images/{slug}/{fname}")
        except Exception as e:
            print(f"     [!] не удалось сгенерить: {e}")
            if image_urls:
                # если уже есть хоть одна — копируем последнюю как fallback
                import shutil
                shutil.copy(folder / image_urls[-1].split("/")[-1], save_path)
                image_urls.append(f"images/{slug}/{fname}")
            else:
                art["_skip"] = True

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
