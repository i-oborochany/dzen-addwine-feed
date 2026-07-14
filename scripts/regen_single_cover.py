"""
Перегенерирует cover-1.jpg (и cover-1.webp) конкретной статьи.
SLUG задаётся через env TARGET_SLUG.
"""
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import openai_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
IMAGES_DIR = REPO_ROOT / "images"


PROMPT_SYSTEM = """Ты — арт-директор винного журнала AddWine. Тебе дают заголовок и лид статьи. Верни ОДИН промпт для gpt-image-1 — атмосферное премиум-фото под эту статью.

СТИЛЬ: премиум-редакторская фотография для глянцевого журнала. Тёплый свет, богатые материалы (мрамор, дерево, бархат, латунь), тонкие бокалы большой чаши премиум-класса. Палитра: тёплый кремовый + тёмно-сине-зелёный акцентами.

ЖЁСТКИЕ ПРАВИЛА:
- НИ В КОЕМ СЛУЧАЕ не пиши на изображении какие-либо надписи, названия журналов, логотипы брендов, тексты, буквы, цифры, водяные знаки, подписи. Это чистое фото без единой буквы или символа.
- НИКАКИХ крупных планов рук с бокалами.
- НИКАКИХ тостов и чокания.
- Люди — только в среднем/дальнем плане, довольные лица, спокойные позы.

Промпт минимум 100 слов на русском. Включает: главный сюжет, ракурс камеры, освещение, окружение, атмосферу, время суток.

ФОРМАТ ОТВЕТА — строго JSON:
{"prompt": "<промпт>"}"""


def main():
    slug = os.environ.get("TARGET_SLUG", "").strip()
    if not slug:
        print("❌ TARGET_SLUG env var не задан")
        return 1

    print(f"Перегенерация cover-1 для: {slug}")

    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    post = next((p for p in posts if p.get("slug") == slug), None)
    if not post:
        print(f"❌ Статья не найдена в posts_index.json")
        return 1

    print(f"Title: {post['title']}")
    print(f"Lead: {post.get('lead', '')[:100]}...")

    folder = IMAGES_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    # Claude генерит промпт
    user = f"Заголовок: {post['title']}\n\nЛид: {post.get('lead', '')[:400]}\n\nСгенерируй промпт."
    result = claude_api.generate_json(PROMPT_SYSTEM, user, max_tokens=800, temperature=0.6)
    prompt = result.get("prompt", "")
    if len(prompt) < 40:
        prompt = f"Премиум-фото винной атмосферы под тему: {post['title']}. Тёплый свет, богатый интерьер, без людей крупным планом, без единой буквы или надписи."

    print(f"\nПромпт: {prompt[:200]}...")

    # OpenAI генерит картинку
    print("\nГенерируем через gpt-image-1...")
    img_bytes = openai_api.generate_image(prompt)
    jpg_path = folder / "cover-1.jpg"
    jpg_path.write_bytes(img_bytes)
    print(f"✅ cover-1.jpg: {len(img_bytes)} байт")

    # WebP версия
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        webp_path = folder / "cover-1.webp"
        im.save(webp_path, "WEBP", quality=82, method=6)
        print(f"✅ cover-1.webp создан")
    except Exception as e:
        print(f"⚠️  WebP не создан: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
