"""
Точечная починка картинок последнего дайджеста.
- Находит последний dайджест-пост.
- Проверяет уникальность cover-N.jpg по SHA256.
- Дубли пересобирает через gpt-image-1 по заголовку блока из HTML.
- URL картинок остаются прежними.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import openai_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
POSTS_DIR = REPO_ROOT / "posts"
IMAGES_DIR = REPO_ROOT / "images"


PROMPT_SYSTEM = """Ты — арт-директор винного журнала. Тебе дают короткое описание новости из винной индустрии. Сгенерируй ОДИН промпт для gpt-image-1: атмосферное фото под эту новость.

СТИЛЬ: премиум-редакторская фотография как в Vogue Living / Robb Report. Тёплый свет, богатые материалы, тонкие бокалы, реальные винные аксессуары. Палитра: тёплый кремовый + тёмно-сине-зелёный акцентами.

АНАТОМИЯ ЖЁСТКО:
- НИКАКИХ крупных планов рук с бокалами.
- НИКАКИХ тостов и чокания.
- Если люди в кадре — руки спокойно, бокал на столе, средний план.

БЕЗ текста, букв, цифр, логотипов на изображении.

Промпт минимум 80 слов, на русском. Включает: главный сюжет, ракурс, освещение, окружение, эмоциональный тон.

ФОРМАТ ОТВЕТА — JSON: {"prompt": "<промпт>"}"""


def find_last_digest():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    for p in posts:
        title_low = p.get("title", "").lower()
        if any(kw in title_low for kw in ["событ", "дайджест", "неделю", "главное в мире"]):
            return p
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def extract_block_titles(html_path: Path, expected_count: int) -> list:
    """Достаёт заголовки блоков (h3) из html-страницы дайджеста."""
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


def main():
    post = find_last_digest()
    if not post:
        print("Дайджест не найден в posts_index.json")
        return 1

    slug = post["slug"]
    folder = IMAGES_DIR / slug
    if not folder.exists():
        print(f"Папка не найдена: {folder}")
        return 1

    covers = sorted(folder.glob("cover-*.jpg"))
    print(f"Дайджест: {post['title']}")
    print(f"slug: {slug}")
    print(f"Всего картинок: {len(covers)}")

    if len(covers) < 2:
        print("Меньше 2 картинок, править нечего")
        return 0

    # хэшируем
    hashes = {c.name: sha256_file(c) for c in covers}
    print("\nХэши:")
    for name, h in hashes.items():
        print(f"  {name} → {h[:12]}...")

    # находим дубли
    hash_to_files = {}
    for name, h in hashes.items():
        hash_to_files.setdefault(h, []).append(name)

    duplicates = []  # список имён файлов, которые нужно перегенерить (все кроме первого в каждой группе)
    for h, files in hash_to_files.items():
        if len(files) > 1:
            duplicates.extend(sorted(files)[1:])  # оставляем первый, остальные — заменяем

    if not duplicates:
        print("\nДубликатов нет, всё уникально.")
        return 0

    print(f"\nНайдено дублей: {len(duplicates)} — {duplicates}")

    # достаём заголовки блоков из html
    html_path = POSTS_DIR / slug / "index.html"
    block_titles = extract_block_titles(html_path, len(covers))
    print(f"Заголовков блоков в html: {len(block_titles)}")
    for i, t in enumerate(block_titles, 1):
        print(f"  h3 #{i}: {t[:80]}")

    # перегенерим каждый дубль
    for fname in duplicates:
        # определяем индекс блока: cover-3.jpg → блок #3
        m = re.match(r"cover-(\d+)\.jpg", fname)
        if not m:
            continue
        idx = int(m.group(1))
        block_title = block_titles[idx - 1] if idx - 1 < len(block_titles) else post["title"]

        print(f"\n=== {fname} (блок #{idx}) ===")
        print(f"  тема: {block_title[:100]}")

        # Claude → промпт
        user_msg = f"Заголовок новости: {block_title}\n\nСгенерируй промпт для фото под эту новость."
        try:
            r = claude_api.generate_json(PROMPT_SYSTEM, user_msg, max_tokens=800, temperature=0.6)
            prompt = r.get("prompt", "")
        except Exception as e:
            print(f"  [!] Claude не смог: {e} — используем fallback")
            prompt = f"Премиум-фото винной атмосферы под тему: {block_title}. Стиль редакторский, тёплый свет, дегустационный стол с бокалами, без текста."

        if len(prompt) < 30:
            prompt = f"Премиум-фото винной атмосферы: {block_title}. Дегустационный стол с бокалами, тёплый вечерний свет, без людей на первом плане."

        print(f"  промпт: {prompt[:120]}...")

        try:
            img_bytes = openai_api.generate_image(prompt)
            (folder / fname).write_bytes(img_bytes)
            print(f"  ✅ {fname}: {len(img_bytes)} байт")
        except Exception as e:
            print(f"  [!] OpenAI упал: {e}")

    print("\nГотово. URL картинок не изменились.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
