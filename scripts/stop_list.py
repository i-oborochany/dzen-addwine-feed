"""
Стоп-лист тем и брендов для журнала feed.addwine.ru.

Основание: аудит от 14.08.2026. Журнал не должен конкурировать с
коммерческим блогом addwine.ru/articles/ по темам, которые продают.

Использование:
    from stop_list import should_skip_topic
    if should_skip_topic(candidate_title):
        continue  # пропускаем тему
"""
import re

# Темы, которые пишет коммерческий блог addwine.ru/articles/
# и на которые журнал НЕ должен писать никогда.
STOP_WORDS = [
    # Бокалы и посуда
    "бокал", "фужер", "стакан",
    # Декантация и подача
    "декантер", "графин", "аэратор",
    # Открывание
    "штопор", "нарзанник", "сабля", "сабраж", "пробка", "стоппер",
    # Консервация
    "вакуумн", "аргон", "капсул", "coravin", "коравин",
    # Хранение
    "винный шкаф", "хранение вина", "сохранение вина", "погреб",
    "ложемент", "стеллаж",
    # Подарки / сервировка (корни, не полные слова)
    "подар", "сервиров",
    "уход за бокалами", "мыть бокалы",
    # Аксессуары общего
    "аксессуар", "гаджет для вина",
    "термометр", "каплеуловитель", "дроп-стоп",
    "охладитель", "ведёрко", "ведерко", "кулер для вина",
    "маркер для бокал",
]

# Бренды, которые продаёт AddWine — про них пишет только коммерческий блог
STOP_BRANDS = [
    "riedel", "zalto", "josephine", "sydonios", "sophienwald",
    "spiegelau", "nachtmann", "gabriel glas", "markthomas", "grassl",
    "laguiole", "forge de laguiole",
    "durand", "pulltex", "vacu vin", "vinturi", "zzysh",
    "wecomatic", "repour", "ullo", "vspin",
    "l'atelier du vin", "atelier du vin", "l atelier du vin",
    "legnoart", "lalique", "peugeot", "le nez du vin",
]


def should_skip_topic(text: str) -> tuple:
    """
    Проверяет, попадает ли тема в стоп-лист.
    Возвращает (bool, reason) — True + причина, если тему надо пропустить.

    Ищет:
    - слово из STOP_WORDS в любом месте текста (case-insensitive)
    - бренд из STOP_BRANDS в любом месте
    """
    if not text:
        return False, ""
    t = text.lower()

    for word in STOP_WORDS:
        # Простой substring — для коротких слов надо word boundary
        if len(word) <= 5:
            pattern = r"\b" + re.escape(word) + r"[а-яa-z]*"
            if re.search(pattern, t):
                return True, f"стоп-слово «{word}»"
        else:
            if word in t:
                return True, f"стоп-слово «{word}»"

    for brand in STOP_BRANDS:
        if brand in t:
            return True, f"стоп-бренд «{brand}»"

    return False, ""


def filter_topics(topics: list) -> list:
    """Отфильтровывает темы, попавшие в стоп-лист. Печатает причины."""
    out = []
    skipped = 0
    for topic in topics:
        title = topic if isinstance(topic, str) else topic.get("title", "") or str(topic)
        skip, reason = should_skip_topic(title)
        if skip:
            print(f"  [stop-list] пропуск «{title[:60]}» — {reason}")
            skipped += 1
        else:
            out.append(topic)
    if skipped:
        print(f"  [stop-list] всего пропущено: {skipped} из {len(topics)}")
    return out


if __name__ == "__main__":
    # Быстрый self-test
    tests = [
        ("Как выбрать штопор", True),
        ("Пять лучших регионов российского виноделия", False),
        ("Декантер или аэратор — что нужнее", True),
        ("Riedel против Zalto", True),
        ("Что пить с рыбой", False),
        ("История шампанского", False),
        ("Топ-10 подарков винному другу", True),
        ("Крымское виноделие: 5 хозяйств для поездки", False),
    ]
    for text, expected in tests:
        skip, reason = should_skip_topic(text)
        status = "✅" if skip == expected else "❌"
        print(f"  {status}  «{text}» → skip={skip}  {reason}")
