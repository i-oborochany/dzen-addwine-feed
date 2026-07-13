"""
Семантический дедуп тем на 90 дней.
Правило: если в теме есть винное/барное имя собственное или ключевое понятие
(Негрони, Каберне, Сингл-молт, Michelin, Тамань...), и такое же уже было
в опубликованных статьях за N дней — тема считается дублем.
"""
from datetime import datetime, timedelta, timezone


# Расширенный словарь именованных сущностей из винной/барной/гастрономической тематики.
# Всё в нижнем регистре, проверяется как подстрока.
KNOWN_ENTITIES = {
    # Коктейли IBA
    "негрони", "мохито", "мартини", "маргарита", "олд фэшн", "манхэттен",
    "дайкири", "гимлет", "джулеп", "виски-сауэр", "виски сауэр", "май-тай",
    "май тай", "космополит", "пина-колада", "пина колада", "блади-мэри",
    "блади мэри", "апероль-шприц", "апероль шприц", "беллини", "кир-рояль",
    "сайдкар", "фрэнч 75", "пенициллин", "эспрессо-мартини",
    "ирландский кофе",

    # Сорта винограда
    "каберне совиньон", "каберне", "совиньон блан", "совиньон", "мерло",
    "шардоне", "пино нуар", "пино гриджо", "пино гри", "рислинг", "сира",
    "шираз", "мальбек", "гевюрцтраминер", "гевюрц", "темпранильо",
    "санджовезе", "неббиоло", "гренаш", "верменти́но", "вионье",
    "цимлянский чёрный", "красностоп", "сибирьковый", "саперави",

    # Крепкий алкоголь — категории и стили
    "виски", "бурбон", "скотч", "сингл-молт", "сингл молт", "блендед",
    "single malt", "blended", "irish whiskey", "японский виски",
    "коньяк", "арманьяк", "кальвадос",
    "ром", "рhum agricole",
    "текила", "мескаль", "мескал",
    "джин", "london dry", "old tom", "plymouth", "женевер",
    "водка",
    "граппа", "аквавит", "абсент", "сотол",
    "самбука", "узо", "шочу", "байцзю", "cachaça", "cachaca",
    "писко",

    # Пиво/сидр
    "пиво", "ipa", "ipa", "стаут", "портер", "лагер", "пилснер",
    "эль", "ламбик", "гёз", "гез", "витбир", "хефевайцен", "барливайн",
    "milk stout", "coffee stout", "session ipa", "raucher", "rauchbier",
    "сидр", "пуаре", "перри",

    # Креплёные, десертные, вермуты
    "херес", "fino", "manzanilla", "amontillado", "oloroso", "palo cortado",
    "pedro ximénez", "pedro ximenez", "cream sherry",
    "портвейн", "порто", "ruby", "tawny", "vintage port", "lbv",
    "мадера", "sercial", "verdelho", "boal", "malvasia",
    "марсала", "малага",
    "токай", "aszú", "assu", "essencia", "эссенция",
    "сотерн", "барсак",
    "мускат", "мускат beaumes-de-venise", "beaumes-de-venise",
    "vin santo", "recioto", "ripasso", "пассито",
    "айсвайн", "eiswein", "ice wine",
    "вермут", "cinzano", "martini rosso", "carpano", "noilly prat",
    "punt e mes",

    # Знаменитые бренды и хозяйства
    "michelin", "мишлен", "wine spectator", "decanter", "robert parker",
    "james suckling", "wine enthusiast",
    "hennessy", "rémy martin", "remy martin", "martell", "courvoisier",
    "chivas", "johnnie walker", "jack daniels", "макаллан", "macallan",
    "yamazaki", "hibiki", "nikka",
    "l'atelier du vin", "atelier du vin", "sydonios", "riedel", "zalto",
    "chef&sommelier", "chef sommelier", "peugeot", "legnoart",
    # российские хозяйства
    "абрау-дюрсо", "абрау дюрсо", "абрау", "лефкадия",
    "имение сикоры", "сикоры", "château tamagne", "chateau tamagne",
    "фанагория", "fanagoria", "мысхако", "кубань-вино", "кубань вино",
    "инкерман", "новый свет", "alma valley", "гай-кодзор", "гай кодзор",
    "ведерниковъ", "ведерников", "усадьба белогорье", "белогорье",
    "usadba divnomorskoe", "дивноморское",

    # Регионы и терруары
    "тамань", "анапа", "новороссийск", "геленджик", "крымск",
    "крым", "балаклава", "севастополь", "массандра",
    "краснодар", "кубань",
    "долина дона", "долина дон", "цимлянский район",
    "дагестан", "северный кавказ", "ставропольский край", "ставрополь",
    "ростовская область", "ростов",
    "воронежская область", "воронеж",
    "подмосковье", "волгоград", "волгоградская область",
    "бордо", "бургундия", "бургундский", "тоскана", "тосканский",
    "прованс", "долина луары", "луара", "долина роны", "рона",
    "шампань", "рейнгау", "мозель", "рислинг мозеля",
    "риоха", "приорат", "penedès", "penedes",
    "пьемонт", "бароло", "барбареско", "кьянти", "brunello",

    # Гастрономия — блюда и продукты
    "стейк", "рибай", "филе-миньон", "филе миньон", "оссобуко", "оссо-буко",
    "баранина", "утка", "утиная грудка", "телятина", "свинина",
    "лосось", "тунец", "морской окунь", "гребешки", "устрицы", "мидии",
    "тартар", "севиче", "суши", "сашими",
    "фондю", "тартифлетт", "раклетт", "тирамису", "крем-брюле", "крем брюле",
    "паста арабьята", "паста", "ризотто", "пицц", "хамон",
    "оливье", "селёдка", "сельдь",

    # Аксессуары / категории каталога
    "штопор", "бокал", "декантер", "охладитель",
    "мельница для соли", "мельница для перца", "нож", "кофемолка",
    "форма для запекания", "блендер",

    # Термины
    "терруар", "биодинамика", "органик", "органическ",
    "натуральное вино", "оранж-вайн", "orange wine",
}


import re


def _stem_match(entity: str, low_text: str) -> bool:
    """
    Ищет entity в тексте с учётом русских падежей.
    Для однословных entity берётся стем (первые 6 символов) и ищется как \\b<стем>\\w*.
    Для многословных — точная подстрока.
    """
    entity = entity.lower()
    if " " in entity or "-" in entity:
        # многословное — точная подстрока
        return entity in low_text
    if len(entity) <= 4:
        # короткое слово — точное совпадение с word boundary
        return re.search(rf"\b{re.escape(entity)}\b", low_text) is not None
    # стемминг: первые max(4, len-2) символов, любое окончание
    stem_len = max(4, len(entity) - 2)
    stem = entity[:stem_len]
    return re.search(rf"\b{re.escape(stem)}\w*", low_text) is not None


def extract_entities(text: str) -> set:
    """Возвращает набор entities которые нашлись в тексте (учитываются падежи)."""
    low = (text or "").lower()
    return {e for e in KNOWN_ENTITIES if _stem_match(e, low)}


def _parse_date(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def is_topic_duplicate(topic: str, history: list, days: int = 90) -> bool:
    """
    history — список dict с полями title и date (например из progress.json history).
    Если хотя бы один entity темы уже был за последние `days` дней — дубль.
    """
    topic_ents = extract_entities(topic)
    if not topic_ents:
        return False  # тема без сильных entities — пропускаем без блокировки

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for h in history:
        dt = _parse_date(h.get("date") or h.get("published_at"))
        if not dt or dt < cutoff:
            continue
        past_title = h.get("title") or ""
        past_ents = extract_entities(past_title)
        if topic_ents & past_ents:
            return True
    return False


def filter_topics(candidates: list, history: list, days: int = 90) -> list:
    """Возвращает список тем-кандидатов без семантических дублей за `days` дней."""
    return [t for t in candidates if not is_topic_duplicate(t, history, days)]
