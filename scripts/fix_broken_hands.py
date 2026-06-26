"""
Точечно перегенерирует cover-1.jpg И cover-2.jpg для статьи про
«21 российский ресторан в Wine Spectator Awards 2026».
Промпт с жёсткими правилами анатомии: без крупных рук, без чокания.
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

# Подстрока для поиска нужной статьи
TARGET_KEYWORDS = ["wine spectator", "21 российск"]


PROMPT_SYSTEM = """Ты — арт-директор премиум-журнала AddWine. Тебе дают заголовок и лид статьи. Сгенерируй ДВА промпта для gpt-image-1: заголовочное фото и финальное атмосферное.

ВИЗУАЛЬНЫЙ КОД ADDWINE
Роскошь, богатство, статус, VIP — без вычурности. Стиль, вкус, экспертность. Эстетика Vogue Living / Robb Report / Condé Nast Traveller.

Стиль фото: профессиональная редакторская съёмка. Глубокая цветокоррекция, тёплый «золотой час» или мягкий вечерний свет, богатые материалы (мрамор, дерево, бархат, лён, латунь, кожа), хрустальная посуда, тонкие бокалы Sydonios/Zalto-уровня.

Палитра: тёплый кремовый (Pantone 7403) + глубокий тёмно-сине-зелёный (Pantone 302) как акценты.

АНАТОМИЯ И КОМПОЗИЦИЯ — ЖЁСТКИЕ ПРАВИЛА:
- НИКАКИХ крупных планов рук, держащих бокалы.
- НИКАКИХ тостов и чокания крупным планом — это самая частая зона провала AI.
- Если люди в кадре, то:
  • либо смотрят на собеседника или на бокал, руки спокойно лежат на столе;
  • либо бокалы стоят на столе перед людьми;
  • либо бокал держат частично за основание, ракурс не показывает кисть подробно.
- Предпочтительные сюжеты для ресторанной/винной темы:
  • Интерьер премиум-ресторана с видом, бокалы на мраморной стойке.
  • Дегустационный стол с несколькими бокалами разного вина, без людей или с дальним планом гостей.
  • Сервированный стол ресторана с блюдами и бокалами, без рук.
  • Сомелье в фартуке стоит у барной стойки, бокалы на стойке (руки в свободном положении).
  • Винный погреб с бочками, бокалы на дегустационном столе.
  • Сцена дегустации в зале, люди в среднем плане, бокалы перед каждым.
- Эмоции — только довольные, утончённые, расслабленные.

ВСЕ кадры — БЕЗ текста, надписей, букв, цифр, логотипов.
2 кадра должны быть ВИЗУАЛЬНО РАЗНЫМИ.

Каждый промпт минимум 80 слов. Включает: главный сюжет, ракурс камеры, освещение, окружение, эмоциональный тон.

ФОРМАТ ОТВЕТА — JSON: {"prompts": ["<промпт 1: заглавный>", "<промпт 2: финальный>"]}"""


def find_target_post():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    for p in posts:
        title_low = p.get("title", "").lower()
        if any(kw in title_low for kw in TARGET_KEYWORDS):
            return p
    return None


def main():
    post = find_target_post()
    if not post:
        print(f"Статья не найдена по словам: {TARGET_KEYWORDS}")
        return 1

    slug = post["slug"]
    folder = IMAGES_DIR / slug
    if not folder.exists():
        print(f"Папка не найдена: {folder}")
        return 1

    print(f"Статья: {post['title']}")
    print(f"slug: {slug}")
    print(f"Папка: {folder}")

    # Просим Claude сгенерить 2 промпта
    print("\n[1/3] Claude генерит новые промпты")
    user = f"Заголовок: {post['title']}\n\nЛид: {post.get('lead','')}\n\nСгенерируй 2 промпта."
    result = claude_api.generate_json(PROMPT_SYSTEM, user, max_tokens=1500, temperature=0.6)
    prompts = result.get("prompts", [])
    if len(prompts) < 2:
        print("Claude дал меньше 2 промптов")
        return 1
    print(f"  prompt 1 ({len(prompts[0])} симв.): {prompts[0][:120]}...")
    print(f"  prompt 2 ({len(prompts[1])} симв.): {prompts[1][:120]}...")

    # Перегенерируем cover-1 и cover-2
    print("\n[2/3] OpenAI генерит cover-1.jpg")
    img1 = openai_api.generate_image(prompts[0])
    (folder / "cover-1.jpg").write_bytes(img1)
    print(f"  ✅ cover-1.jpg: {len(img1)} байт")

    print("\n[3/3] OpenAI генерит cover-2.jpg")
    img2 = openai_api.generate_image(prompts[1])
    (folder / "cover-2.jpg").write_bytes(img2)
    print(f"  ✅ cover-2.jpg: {len(img2)} байт")

    print("\nГотово. URL картинок не поменялся, поэтому feed.xml и страницы трогать не надо.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
