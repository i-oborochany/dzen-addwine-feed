"""
Нативная вставка ссылки на addwine.ru в статью.
Парсит sitemap-brands.xml + sitemap-categories.xml, выбирает наиболее
тематически подходящую ссылку, Claude вставляет упоминание в одно из мест.
"""
import json
import re
import requests

import claude_api


SITEMAP_BRANDS = "https://addwine.ru/sitemap-brands.xml"
SITEMAP_CATEGORIES = "https://addwine.ru/sitemap-categories.xml"

UA = "Mozilla/5.0 (compatible; AddWineBot/1.0)"

# Словарь slug → читаемое русское название
SLUG_TO_TITLE = {
    # Бокалы
    "bokaly-dlya-vina": "бокалы для вина",
    "bokaly-dlyashampanskogo": "бокалы для шампанского",
    "bokaly-dlya-shampanskogo": "бокалы для шампанского",
    "bokaly-dlya-belogo-vina": "бокалы для белого вина",
    "bokaly-dlya-krasnogovina": "бокалы для красного вина",
    "bokaly-dlya-krasnogo-vina": "бокалы для красного вина",
    "bokaly-universalynye": "универсальные бокалы для вина",
    "bokaly-dlya-sladkix-vin": "бокалы для сладких и десертных вин",
    "degustacionnye-bokaly": "дегустационные бокалы",
    "bokaly-dlya-vermuta": "бокалы для вермута",
    "bokaly-dlya-koktejlej": "бокалы для коктейлей",
    "bokaly-dlia-krepkogo": "бокалы для крепких напитков",
    "bokaly-dlya-piva": "бокалы для пива",
    "nebyushhiesya-bokaly": "небьющиеся бокалы",
    "czvetnye-bokaly": "цветные бокалы",
    "bokaly-dlia-vina-bez-nozhki": "бокалы без ножки",
    "nabor-bokalov-dlia-vina": "наборы бокалов для вина",
    # Штопоры
    "shtopory": "штопоры",
    "shtopory_13": "ручные штопоры",
    "shtopory-czyganskie": "штопоры сомелье",
    "shtopory-pnevmaticheskie": "пневматические штопоры",
    "shtopory-eelektricheskie": "электрические штопоры",
    "shtopory-nastennye": "настенные штопоры",
    "shtopory-nastolynye": "настольные штопоры",
    "otkryvalki": "открывалки для бутылок",
    # Декантеры/Аэраторы/Графины
    "dekantery": "декантеры",
    "aeratory-dlya-vina": "аэраторы для вина",
    "grafiny-dlya-vina": "графины для вина",
    "kuvshiny-dlya-vina": "кувшины для вина",
    "markery-dlya-bokalov": "маркеры для бокалов",
    "plevatelnicy": "плевательницы для дегустации",
    # Сервировка
    "servirovka": "винные аксессуары для сервировки",
    "ohladiteli-dlya-vina": "охладители для вина",
    "kapleuloviteli": "каплеуловители",
    "obrezateli-folgi": "обрезатели фольги",
    "meshochki-dlya-degustaczij": "мешочки для дегустаций",
    "barnye-aksessuary": "барные аксессуары",
    "sabli": "сабли для сабража",
    "termometry-dlya-vina": "термометры для вина",
    "sredstva-uxoda": "средства ухода за бокалами",
    "klyuch-vina": "ключи для вина",
    # Хранение
    "hranenie": "винные аксессуары для хранения",
    "vinnye-probki": "винные пробки",
    "dispensery": "системы хранения и дозаторы",
    "argon-co2-i-n2o": "консерванты Argon, CO₂ и N₂O для вина",
    "vinnye-holodilniki": "винные шкафы и холодильники",
    "stellazhi-i-polki": "винные стеллажи и полки",
    "upakovka-dlya-vina": "упаковка для вина",
    # Подарки
    "izuchenie": "винные подарки",
    "podarochnye-nabory": "подарочные наборы для ценителей вина",
    "podarochnye-karty": "подарочные карты AddWine",
    "vinnaya-literatura": "винная литература",
    "vinnye-igry": "винные игры",
    "albomy-i-kopilki": "альбомы и копилки для пробок",
    # Бренды бокалов (премиум)
    "sydonios": "Sydonios",
    "markthomas": "MarkThomas",
    "zalto": "Zalto",
    "riedel": "Riedel",
    "spiegelau": "Spiegelau",
    "chef-and-sommelier": "Chef&Sommelier",
    "uno": "UNO",
    "sophienwald": "Sophienwald",
    # Бренды штопоров
    "durand": "Durand",
    "durands": "Durand",
    "the-durand": "The Durand",
    "pulltex": "Pulltex",
    "vacu-vin": "Vacu Vin",
    "vinoman": "Vinoman",
    "boj": "BOJ",
    "latelier-du-vin": "L'Atelier du Vin",
    "atelier-du-vin": "L'Atelier du Vin",
    # Прочие бренды
    "peugeot": "Peugeot",
    "le-nez-du-vin": "Le Nez du Vin",
    "tajima-glass": "Tajima Glass",
    "la-rochere": "La Rochere",
    "legnoart": "Legnoart",
    "markthomas-design": "MarkThomas Design",
    "solove": "Solove",
    "addbooks": "AddBooks",
    "final-touch": "Final Touch",
    "kitchen-craft": "Kitchen Craft",
    "pl-proff-cuisine": "P.L. Proff Cuisine",
    "astra-wine": "Astra Wine",
}


def _humanize_slug(slug: str) -> str:
    """Делает русское название из slug через словарь, иначе по дефолту."""
    s = re.sub(r"_\d+$", "", slug)  # убираем _123 в конце
    if s in SLUG_TO_TITLE:
        return SLUG_TO_TITLE[s]
    # дефолт: разделители на пробелы
    return s.replace("-", " ").replace("_", " ")


def fetch_links() -> list:
    """
    Возвращает список dict {url, title, kind}.
    kind: "brand" или "category".
    """
    out = []
    for sm_url, kind in [(SITEMAP_BRANDS, "brand"), (SITEMAP_CATEGORIES, "category")]:
        try:
            r = requests.get(sm_url, headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                continue
            urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
            for u in urls:
                slug = u.rstrip("/").split("/")[-1]
                title = _humanize_slug(slug)
                if len(title) < 3:
                    continue
                out.append({"url": u, "title": title, "kind": kind})
        except Exception as e:
            print(f"  [linker] не смог получить {sm_url}: {e}")
    return out


LINK_INJECTION_SYSTEM = """Ты — редактор винного журнала AddWine. Получаешь готовую статью и список доступных категорий и брендов с AddWine.ru. Задача — нативно вставить ОДНУ упоминание + ссылку, чтобы это выглядело как редакторская рекомендация, а не реклама.

ПРАВИЛА
- Выбери ИЗ СПИСКА только одну ссылку, которая ИДЕАЛЬНО тематически подходит под статью.
- Не пытайся вставлять ссылку, если ни одна категория или бренд не подходит к теме — в таком случае верни статью без изменений и поле "link_inserted": false.
- Найди в статье логичное место (предпочтительно в одном из последних двух абзацев) и нативно вплети мысль про категорию или бренд.
- Формат вставки: одно-два предложения, естественным редакторским языком. Без лозунгов, без призывов «купить», без «закажите» и «рекомендуем».
- Пример хороших формулировок:
  - «Раскрыть аромат таких вин помогут декантеры — например, классические модели от <a href="URL">Riedel</a>.»
  - «Для подачи игристых вин этого стиля подходят бокалы-тюльпаны — <a href="URL">подборка бокалов для шампанского</a>.»
  - «Штопоры с двойным рычагом, такие как <a href="URL">L'Atelier du Vin</a>, открывают плотные пробки старых вин аккуратнее всего.»
- Сохрани все остальные части статьи без изменений.
- НЕ добавляй новый заголовок «AddWine рекомендует» или другие явные CTA-блоки.

ФОРМАТ ОТВЕТА — строго JSON без markdown:
{
  "link_inserted": true|false,
  "selected_url": "<url или пустая строка>",
  "selected_title": "<название или пустая строка>",
  "html": "<обновлённый HTML статьи (или оригинал если не вставлено)>"
}"""


def inject_link(article_html: str, links: list = None) -> dict:
    """
    Принимает html статьи и список ссылок, возвращает {html, link_inserted, selected_url, selected_title}.
    Если ничего тематически не подошло — возвращает original без изменений.
    """
    if links is None:
        links = fetch_links()
    if not links:
        return {"html": article_html, "link_inserted": False, "selected_url": "", "selected_title": ""}

    # компактный список для промпта
    list_text = "\n".join(f"- [{l['kind']}] {l['title']} → {l['url']}" for l in links)

    user = f"""ДОСТУПНЫЕ КАТЕГОРИИ И БРЕНДЫ ({len(links)}):
{list_text}

СТАТЬЯ:
{article_html}

Выбери одну наиболее подходящую ссылку и нативно вставь упоминание. Если ни одна не подходит — верни статью без изменений с link_inserted=false."""

    result = claude_api.generate_json(LINK_INJECTION_SYSTEM, user, max_tokens=8000, temperature=0.5)
    # валидация
    if not isinstance(result, dict) or "html" not in result:
        return {"html": article_html, "link_inserted": False, "selected_url": "", "selected_title": ""}
    return result
