"""
Анти-монотонность заголовков: запрещает повторять формулу начала заголовка,
если она уже использовалась в недавних статьях («Гид по…», «Как выбрать…» и т.д.).

Использование в writers:
    import title_rules
    block = title_rules.forbidden_starts_block(recent_titles)
    # добавить block в user-промпт
"""
from collections import Counter

# Формулы, которые чаще всего залипают
KNOWN_FORMULAS = [
    "гид по", "как выбрать", "как понять", "как раскрыть", "разбор",
    "что такое", "почему", "обзор", "топ-", "5 ", "7 ", "10 ",
    "всё, что", "все, что", "полный гид",
]


def _extract_formula(title: str) -> str:
    """Определяет формулу начала заголовка (первые 1-2 значимых слова)."""
    t = (title or "").lower().strip()
    for f in KNOWN_FORMULAS:
        if t.startswith(f):
            return f.strip()
    words = t.split()
    return " ".join(words[:2]) if len(words) >= 2 else t


def forbidden_starts_block(recent_titles: list, last_n: int = 10) -> str:
    """
    Возвращает блок для промпта: какие начала заголовков запрещены.
    Запрещаем формулы, встречавшиеся в последних last_n заголовках хотя бы раз.
    """
    recent = [t for t in (recent_titles or []) if t][:last_n]
    if not recent:
        return ""

    counts = Counter(_extract_formula(t) for t in recent)
    banned = [f for f, c in counts.items() if f and len(f) >= 3]
    if not banned:
        return ""

    banned_str = ", ".join(f"«{b}…»" for b in sorted(set(banned))[:12])
    return f"""
РАЗНООБРАЗИЕ ЗАГОЛОВКОВ — ЖЁСТКОЕ ПРАВИЛО:
Недавние статьи уже начинались с: {banned_str}.
ЗАПРЕЩЕНО начинать любой из 3 вариантов заголовка с этих формул.
Используй ДРУГИЕ формы: вопрос («Что скрывает…?», «Стоит ли…?»), утверждение
(«Оранжевое вино возвращается»), число в середине («Шесть регионов, где…»),
сравнение («X против Y»), интригующий факт без кликбейта, именительная тема
(«Петнат: игристое без правил»). Каждый из 3 вариантов — с разной формулой."""
