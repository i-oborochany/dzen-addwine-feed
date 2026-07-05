"""
Перегенерирует ВСЕ картинки в трёх дайджестах:
- 2026-07-05-vinnye-sobytiya-nedeli
- 2026-06-28-vinnye-sobytiya-nedeli
- 2026-06-21-vinnye-sobytiya-nedeli

Для каждого блока (h3) — свой уникальный gpt-image-1 промпт по заголовку.
URL картинок не меняются.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import openai_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "posts"
IMAGES_DIR = REPO_ROOT / "images"

TARGET_SLUGS = [
    "2026-07-05-vinnye-sobytiya-nedeli",
    "2026-06-28-vinnye-sobytiya-nedeli",
    "2026-06-21-vinnye-sobytiya-nedeli",
]


PROMPT_SYSTEM = """Ты — арт-директор винного журнала. Тебе дают заголовок винной новости. Сгенерируй ОДИН промпт для gpt-image-1 — атмосферное фото под эту новость.

СТИЛЬ: премиум-редакторская фотография как в Vogue Living / Robb Report. Тёплый свет, богатые материалы, тонкие бокалы уровня Sydonios/Zalto, реальные винные аксессуары. Палитра: тёплый кремовый + тёмно-сине-зелёный акцентами.

СЮЖЕТЫ ПО ТЕМАМ (подбирай по смыслу):
- Про рейтинги/премии/ресторан: интерьер премиум-ресторана с бокалами на мраморной стойке, серебряная сервировка.
- Про сорт/регион/терруар: виноградник в холмах на закате, крупный план грозди.
- Про винодельню/винодела: винный погреб с дубовыми бочками, приглушённый свет.
- Про технологии/науку: лаборатория с бокалами и рефрактометром, дегустационные бланки.
- Про рынки/цены/деньги: элегантный винный аукцион, редкие бутылки на подсвеченных полках.
- Про сомелье: сомелье в фартуке у барной стойки, спокойная поза, руки в свободном положении.
- Про женщин-виноделов: винодельня, женщина среднего плана в свободной позе, вдумчиво смотрит на бокал.
- Про международные новости: дегустационный стол с бокалами разного вина, без людей крупным планом.

АНАТОМИЯ ЖЁСТКО:
- НИКАКИХ крупных планов рук с бокалами.
- НИКАКИХ тостов и чокания крупным планом.
- Если люди в кадре — руки спокойные, бокал стоит на столе, только средний или дальний план.

БЕЗ текста, букв, цифр, логотипов на изображении.

Промпт минимум 100 слов, на русском. Включает: главный сюжет, ракурс камеры, освещение, окружение, атмосферу, время суток.

ФОРМАТ ОТВЕТА — строго JSON: {"prompt": "<промпт>"}"""


def extract_block_titles(html_path: Path, expected_count: int) -> list:
    if not html_path.exists():
        return []
    html = html_path.read_text(encoding="utf-8")
    h3s = re.findall(r"<h3[^>]*>(.*?)</h3>", html, flags=re.S | re.I)
    titles = []
    for raw in h3s:
        t = re.sub(r"<[^>]+>", "", raw).strip()
        if t and len(t) > 5:
            titles.append(t)
    return titles[:expected_count]


def process_slug(slug: str) -> None:
    print("\n" + "=" * 70)
    print(f"Обрабатываем: {slug}")
    print("=" * 70)

    folder = IMAGES_DIR / slug
    if not folder.exists():
        print(f"  Папка не найдена: {folder}")
        return

    covers = sorted(folder.glob("cover-*.jpg"))
    if not covers:
        print("  Нет cover-*.jpg — пропускаем")
        return

    print(f"  Всего картинок: {len(covers)}")

    html_path = POSTS_DIR / slug / "index.html"
    block_titles = extract_block_titles(html_path, len(covers))
    print(f"  Заголовков блоков в html: {len(block_titles)}")
    for i, t in enumerate(block_titles, 1):
        print(f"    h3 #{i}: {t[:80]}")

    if not block_titles:
        print("  Не смогли достать заголовки блоков — пропускаем")
        return

    for cover_path in covers:
        m = re.match(r"cover-(\d+)\.jpg", cover_path.name)
        if not m:
            continue
        idx = int(m.group(1))
        if idx > len(block_titles):
            block_title = block_titles[-1]
        else:
            block_title = block_titles[idx - 1]

        print(f"\n  --- {cover_path.name} (блок #{idx}) ---")
        print(f"    тема: {block_title[:100]}")

        try:
            user_msg = f"Заголовок винной новости: {block_title}\n\nСгенерируй тематичный промпт."
            r = claude_api.generate_json(PROMPT_SYSTEM, user_msg, max_tokens=800, temperature=0.6)
            prompt = r.get("prompt", "")
        except Exception as e:
            print(f"    [!] Claude не смог: {e}")
            prompt = f"Премиум-редакторское фото винной атмосферы под тему: {block_title}. Дегустационный стол с бокалами, тёплый вечерний свет, богатый интерьер ресторана, без людей на первом плане, без текста."

        if len(prompt) < 40:
            prompt = f"Премиум-фото винной атмосферы: {block_title}. Тёплый свет, дегустационный стол, тонкие бокалы, без людей крупным планом, без текста."

        print(f"    промпт ({len(prompt)} симв.): {prompt[:120]}...")

        try:
            img_bytes = openai_api.generate_image(prompt)
            cover_path.write_bytes(img_bytes)
            print(f"    ✅ {cover_path.name}: {len(img_bytes)} байт")
        except Exception as e:
            print(f"    [!] OpenAI упал: {e}")

        time.sleep(0.3)


def main():
    for slug in TARGET_SLUGS:
        try:
            process_slug(slug)
        except Exception as e:
            print(f"  [!] fatal при {slug}: {e}")

    print("\n" + "=" * 70)
    print("Готово. URL картинок не изменились. Обнови страницы с Cmd+Shift+R.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
