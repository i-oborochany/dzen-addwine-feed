"""
SEO-планирование ДО генерации статьи.
Даём тему → Claude предлагает 3-5 ключевых фраз → Wordstat → фильтр → топ ключей.
Статья потом пишется ПОД эти ключи.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import wordstat_api


SEED_SYSTEM = """Ты — SEO-специалист винного журнала AddWine. Тебе дают тему будущей статьи. Верни 3-5 ключевых фраз, которые нужно проверить в Яндекс.Wordstat для этой темы.

ТРЕБОВАНИЯ К ФРАЗАМ:
- 2-4 слова каждая, на русском (или транслит для брендов и международных терминов).
- Фразы должны отражать РЕАЛЬНЫЕ поисковые запросы аудитории по теме статьи.
- НЕ общие абстрактные слова («уникальный», «электрический», «российский» одним словом), а конкретные тематические сочетания («штопор для вина», «мерло сорт винограда», «michelin ресторан», «сортвіру»).
- Если в теме упоминаются регионы, бренды, имена — включи их.
- Все фразы должны быть на винной / барной / гастрономической тематике.

ФОРМАТ ОТВЕТА — строго JSON:
{
  "phrases": ["фраза 1", "фраза 2", "фраза 3", "фраза 4", "фраза 5"]
}
"""


def discover_keywords(topic: str, lead: str = "", limit: int = 15) -> list:
    """
    Полный цикл SEO-планирования темы.
    Возвращает список dict {phrase, count} или пустой если не получилось.
    """
    print(f"\n  [seo_planner] discovery для темы: «{topic[:80]}»")

    # Шаг 1: Claude предлагает фразы
    user = f"ТЕМА СТАТЬИ: {topic}\n"
    if lead:
        user += f"\nКОНТЕКСТ (лид): {lead[:300]}\n"
    user += "\nВерни 3-5 ключевых фраз для Wordstat."

    try:
        result = claude_api.generate_json(SEED_SYSTEM, user, max_tokens=500, temperature=0.3)
        phrases = result.get("phrases", [])
    except Exception as e:
        print(f"  [seo_planner] Claude упал: {e}")
        return []

    if not phrases:
        print(f"  [seo_planner] Claude не предложил фраз")
        return []
    print(f"  [seo_planner] Claude предложил: {phrases}")

    # Шаг 2: Wordstat + тематический whitelist (в wordstat_api уже есть)
    keywords = wordstat_api.get_keywords_from_phrases(phrases, limit=limit)
    if not keywords:
        print(f"  [seo_planner] релевантных ключей нет, статья пойдёт БЕЗ SEO-подсказок")
        return []

    print(f"  [seo_planner] итого топ ключей: {len(keywords)}")
    for kw in keywords[:5]:
        print(f"    - «{kw['phrase']}» ({kw['count']})")
    return keywords


def format_seo_brief(keywords: list) -> str:
    """
    Форматирует топ ключей в жёсткий SEO-бриф для промпта.
    Возвращает пустую строку если ключей нет.
    """
    if not keywords:
        return ""

    top = keywords[:12]
    lines = [
        "═════════════════════════════════════════════════════",
        "SEO-БРИФ ПОД ЭТУ СТАТЬЮ (данные Яндекс.Wordstat, реальные показы/мес):",
    ]
    for i, kw in enumerate(top, 1):
        lines.append(f"  {i}. «{kw['phrase']}» — {kw['count']} показов/мес")

    top1 = top[0]["phrase"]
    top2 = top[1]["phrase"] if len(top) > 1 else top1
    top3 = top[2]["phrase"] if len(top) > 2 else top1

    lines.extend([
        "",
        "СТАТЬЯ ПИШЕТСЯ ПОД ЭТИ КЛЮЧИ (это НЕ подсказка, а требование):",
        f"— В title (H1) ОБЯЗАТЕЛЬНО должен присутствовать ключ «{top1}» (можно в словоформе).",
        f"— Первое предложение лида должно содержать «{top1}».",
        f"— В первых 100 словах статьи ОБЯЗАТЕЛЬНО должны быть ключи: «{top1}», «{top2}», «{top3}» — естественно, не спам.",
        f"— В meta description (лид) должны быть «{top1}» и вариация «{top2}».",
        "— Хотя бы 3 из перечисленных ключей должны войти в подзаголовки H2/H3.",
        "— Long-tail ключи (низкочастотные из списка) — используй как заголовки H2/H3 и в тексте.",
        "— НЕ переспамливай: каждый ключ 1-2 раза максимум.",
        "═════════════════════════════════════════════════════",
    ])
    return "\n".join(lines)
