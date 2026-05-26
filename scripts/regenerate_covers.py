"""
Перегенерирует cover-1.jpg для последних N статей.
URL в feed.xml не меняется — заменяется только содержимое файла.
Все картинки гарантированно без текста.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import openai_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
IMAGES_DIR = REPO_ROOT / "images"

# Сколько последних статей перегенерить (можно изменить)
N_LAST = 2


PROMPT_SYSTEM = """Ты — арт-директор винного журнала. Получаешь заголовок и лид статьи, генерируешь промпт для гpt-image-1 для заголовочной фотографии.

ТРЕБОВАНИЯ К ФОТО:
- Профессиональная современная фотография как для глянцевого журнала
- Современный (не древний), технологичный, аккуратный, минималистичный, но богатый интерьер
- Палитра: тёплый кремовый (Pantone 7403) и тёмно-сине-зелёный (Pantone 302) — как акценты в интерьере, без фанатизма, не заливкой
- Реальные винные аксессуары (реальные модели бокалов, штопоров, декантеров — не выдуманные кривые формы)
- Бокалы только большого объёма, тонкая ножка, тонкое стекло
- Рука держит аксессуар правильно: штопор — за рычаг, бокал — за ножку, декантер — за горловину
- Обязательно фигура человека (можно не целиком — рабочая область: руки, торс, плечо)
- Реальное использование за столом, дома или в ресторане
- НЕ нарушать физические законы (жидкость в бокале естественно)
- БЕЗ ТЕКСТА, БЕЗ НАДПИСЕЙ, БЕЗ ЛОГОТИПОВ, БЕЗ ВОДЯНЫХ ЗНАКОВ — только чистая фотография

Промпт минимум 70 слов на русском. Включай: главный объект, кто и что делает, ракурс камеры, освещение, окружение, эмоциональный тон.

ФОРМАТ ОТВЕТА — JSON: {"prompt": "..."}"""


def make_prompt(title: str, lead: str) -> str:
    user = f"Заголовок: {title}\nЛид: {lead}\n\nСгенерируй промпт для заголовочного фото."
    result = claude_api.generate_json(PROMPT_SYSTEM, user, max_tokens=600, temperature=0.7)
    return result["prompt"]


def main():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    posts = sorted(posts, key=lambda p: p.get("published_at", ""), reverse=True)
    target = posts[:N_LAST]

    print(f"Перегенерим cover-1.jpg для {len(target)} последних статей:")
    for p in target:
        print(f"  - {p['title'][:70]}")

    for p in target:
        slug = p["slug"]
        folder = IMAGES_DIR / slug
        cover_path = folder / "cover-1.jpg"
        print(f"\n=== {slug} ===")

        if not folder.exists():
            print(f"  [!] папка не найдена: {folder}")
            continue

        print(f"  Claude генерит новый промпт ...")
        try:
            prompt = make_prompt(p["title"], p.get("lead", ""))
            print(f"  промпт: {prompt[:150]}...")
        except Exception as e:
            print(f"  [!] Claude упал: {e}")
            continue

        print(f"  OpenAI генерит новое фото ...")
        try:
            img = openai_api.generate_image(prompt)
            cover_path.write_bytes(img)
            print(f"  ✅ записан {cover_path.name} ({len(img)} байт)")
        except Exception as e:
            print(f"  [!] OpenAI упал: {e}")
            continue

    print("\nГотово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
