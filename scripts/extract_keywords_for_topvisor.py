"""
Извлекает SEO-ключи из всех статей для загрузки в Топвизор.

Логика:
1. Читаем posts/posts_index.json
2. Для каждой статьи берём title + lead
3. Батчами по 15 отправляем в Claude — просим 3 ключа на статью
4. Собираем уникальный список, сортируем
5. Сохраняем в TOPVISOR_KEYWORDS.txt (по одному ключу на строку)
6. Пользователь копирует содержимое → в Топвизор → добавить запросы
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
OUTPUT_FILE = REPO_ROOT / "TOPVISOR_KEYWORDS.txt"

BATCH_SIZE = 15  # статей за один запрос к Claude
KEYS_PER_ARTICLE = 3  # сколько ключей на статью

SYSTEM_PROMPT = """Ты — SEO-редактор винного журнала. Твоя задача — для каждой статьи предложить SEO-ключи, по которым её нужно отслеживать в Топвизоре (сервис мониторинга позиций).

ПРАВИЛА:
1. Ключи — на русском, в именительном падеже как их вбивают в поиск.
2. По 2-3 ключа на статью, обязательно РАЗНЫЕ по смыслу (не «негрони рецепт» и «рецепт негрони»).
3. Ключи должны быть реальными поисковыми запросами (то что человек в Яндексе вбьёт). Не бренд-запросы, не длинные фразы больше 5-6 слов.
4. Отдавай ТОЛЬКО те ключи, по которым статья реально может ранжироваться (это ЕЁ основная тема).
5. Если статья очень нишевая или это дайджест — верни только 1 самый точный ключ.
6. Дайджесты и «События недели» — пропускай (верни пустой массив).

ФОРМАТ ОТВЕТА — строго JSON:
{
  "slug-1": ["ключ 1", "ключ 2", "ключ 3"],
  "slug-2": ["ключ 1", "ключ 2"],
  ...
}
"""


def is_digest(post):
    t = post.get("title", "").lower()
    return any(w in t for w in ["дайджест", "самое интересное", "события недели"])


def extract_batch(posts_batch):
    """Батч статей → dict {slug: [keys]}"""
    lines = []
    for p in posts_batch:
        slug = p.get("slug", "")
        title = p.get("title", "")[:120]
        lead = p.get("lead", "")[:200]
        lines.append(f"---\nSLUG: {slug}\nTITLE: {title}\nLEAD: {lead}")

    user = "СТАТЬИ:\n\n" + "\n".join(lines) + "\n\nВерни JSON по формату из системного промпта."

    try:
        result = claude_api.generate_json(SYSTEM_PROMPT, user, max_tokens=3000, temperature=0.2)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"  [!] Claude упал: {e}")
        return {}


def normalize_key(key):
    """Приводит ключ к каноничному виду."""
    k = key.lower().strip()
    k = re.sub(r"\s+", " ", k)
    k = re.sub(r"[.,!?«»\"'()]+", "", k)
    return k


def main():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    posts = [p for p in posts if not is_digest(p) and p.get("slug")]
    print(f"Всего статей (без дайджестов): {len(posts)}")

    all_keys = set()
    per_article = {}  # для отладки: slug → keys

    for i in range(0, len(posts), BATCH_SIZE):
        batch = posts[i:i + BATCH_SIZE]
        print(f"\nБатч {i//BATCH_SIZE + 1}: статьи {i+1}-{i+len(batch)}")
        result = extract_batch(batch)
        if not result:
            print(f"  [!] пустой ответ, пропускаю батч")
            continue
        for slug, keys in result.items():
            if not isinstance(keys, list):
                continue
            for k in keys[:KEYS_PER_ARTICLE]:
                if not isinstance(k, str):
                    continue
                nk = normalize_key(k)
                if len(nk) < 3 or len(nk.split()) > 6:
                    continue
                all_keys.add(nk)
                per_article.setdefault(slug, []).append(nk)
            print(f"  {slug[:60]:60} → {len(keys)} ключей")

    # Сортируем алфавитно, сохраняем
    sorted_keys = sorted(all_keys)
    OUTPUT_FILE.write_text("\n".join(sorted_keys) + "\n", encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"✅ Сохранено {len(sorted_keys)} уникальных ключей в TOPVISOR_KEYWORDS.txt")
    print(f"   Статей обработано: {len(per_article)} / {len(posts)}")
    print(f"{'=' * 60}")
    print(f"\nПервые 30 ключей для примера:")
    for k in sorted_keys[:30]:
        print(f"  {k}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
