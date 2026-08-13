"""
Проверка каннибализации: находит статьи которые метят в один и тот же
семантический интент (общие entity в title). При каннибализации Яндекс не
понимает какую страницу ранжировать — и обе проседают.

Использует dedup.extract_entities для определения ключевых сущностей.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dedup

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"


def main():
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    # Пропускаем дайджесты и категории
    posts = [p for p in posts if not any(
        k in p.get("title", "").lower()
        for k in ["дайджест", "самое интересное", "события недели"]
    )]

    # Группируем статьи по общей entity
    entity_to_posts = defaultdict(list)
    for p in posts:
        text = p.get("title", "") + " " + p.get("lead", "")
        entities = dedup.extract_entities(text)
        # Отбираем сильные entities (не короткие общие слова)
        for e in entities:
            if len(e) >= 5:
                entity_to_posts[e].append(p)

    print(f"Проверяю {len(posts)} статей на каннибализацию")
    print()

    conflicts = []
    seen_pairs = set()
    for entity, entity_posts in entity_to_posts.items():
        if len(entity_posts) < 2:
            continue
        # Ищем пары в этой группе где entity действительно центральный (в title)
        strong_posts = [p for p in entity_posts if entity in p.get("title", "").lower()]
        if len(strong_posts) < 2:
            continue
        # Составляем пары
        for i, p1 in enumerate(strong_posts):
            for p2 in strong_posts[i+1:]:
                pair_key = tuple(sorted([p1["slug"], p2["slug"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                conflicts.append({
                    "entity": entity,
                    "slugs": [p1["slug"], p2["slug"]],
                    "titles": [p1.get("title", ""), p2.get("title", "")],
                    "dates": [p1.get("published_at", "")[:10], p2.get("published_at", "")[:10]],
                })

    if not conflicts:
        print("✅ Каннибализации не обнаружено")
        return 0

    print(f"⚠️  Найдено пар с общей entity: {len(conflicts)}\n")
    for c in conflicts:
        print(f"=== Общая сущность: «{c['entity']}» ===")
        for slug, title, date in zip(c["slugs"], c["titles"], c["dates"]):
            print(f"  {date}  /posts/{slug}/")
            print(f"           {title[:80]}")
        print()

    print("\n💡 Рекомендация: для каждой пары решите — оставить обе с разным фокусом,")
    print("   или объединить в одну сильную страницу и redirect с другой.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
