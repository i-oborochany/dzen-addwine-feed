"""
Одноразовый скрипт: пересоздаёт картинки и категории для всех статей в feed.xml.
Для каждой статьи:
1. Удаляет старые <img> теги из тела
2. Просит Claude: расставить плейсхолдеры по сценарию + 4 детальных промпта (с реализмом) + 1-2 категории
3. Генерирует 4 картинки через Recraft V3 в едином стиле
4. Сохраняет в images/<slug>/cover-N.jpg
5. Обновляет yandex:full-text + <category> в feed.xml
6. Перегенерирует posts/<slug>/index.html и главную
"""
import json
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api
import recraft_api
import publisher
import html_renderer

REPO_ROOT = Path(__file__).resolve().parent.parent
FEED_PATH = REPO_ROOT / "feed.xml"
IMAGES_DIR = REPO_ROOT / "images"

NS = {"yandex": "http://news.yandex.ru"}
PAGES_BASE = "https://feed.addwine.ru"

CATEGORIES = [
    "Вино, культура и личности",
    "Винные новости",
    "Вино и путешествия",
    "Российское виноделие",
    "Технологии и инновации",
    "Вино и деньги",
    "Аксессуары для вина",
    "Дегустации и советы",
]


def strip_images(html: str) -> str:
    html = re.sub(r"<p>\s*<img[^>]*/?>\s*</p>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<img[^>]*/?>", "", html, flags=re.IGNORECASE)
    return html.strip()


CLAUDE_SYSTEM = """Ты — редактор винного журнала AddWine. Тебе дают готовую статью без картинок.
Задача:
1. Расставить в HTML 4 плейсхолдера: <p>[[IMG_1]]</p>, <p>[[IMG_2]]</p>, <p>[[IMG_3]]</p>, <p>[[IMG_4]]</p> в правильных смысловых местах:
   - IMG_1 — заголовочная, после первого вступительного абзаца, до первого <h2>.
   - IMG_2 — «боль», в разделе с проблемой/ошибкой.
   - IMG_3 — «решение», в разделе с конкретным советом.
   - IMG_4 — «финал», перед последним выводом или перед блоком "AddWine рекомендует" если есть.
2. Придумать 4 детальных промпта для Recraft (фотореалистичная генерация).
3. Присвоить статье 1-2 категории из списка.

ДОПУСТИМЫЕ КАТЕГОРИИ:
- "Вино, культура и личности"
- "Винные новости"
- "Вино и путешествия"
- "Российское виноделие"
- "Технологии и инновации"
- "Вино и деньги"
- "Аксессуары для вина"
- "Дегустации и советы"

ПРАВИЛА ПРОМПТОВ ФОТО (минимум 70 слов каждый, на русском):

Все 4 в едином стиле: профессиональная современная фотография как для глянцевого журнала. Стиль: современный (не древний), с новыми технологиями и аксессуарами, приятные люди, красивый, современный и богатый интерьер.

Палитра: тёплый кремовый (Pantone 7403) и глубокий тёмно-сине-зелёный (Pantone 302) — доминируют, но БЕЗ ФАНАТИЗМА, как акценты в интерьере и текстиле, а не заливка.

КРИТИЧЕСКИ ВАЖНО — РЕАЛИЗМ:
- Не нарушай физические законы. Жидкость в бокале должна вести себя естественно.
- Используй существующие винные аксессуары — реальные модели штопоров, декантеров, бокалов, а не выдуманные кривые формы.
- Рука держит аксессуар естественно и правильно: штопор — за рычаг, бокал — за ножку, декантер — за горловину.
- Бокалы только большого объёма, с тонкой ножкой и тонким стеклом.
- Обязательна фигура человека за работой с аксессуаром (можно не целиком — рабочая область: руки, торс, плечо).
- Реальное использование за столом, дома или в ресторане. Рядом могут быть другие люди.
- Без видимого текста и подписей.

4 кадра — ВИЗУАЛЬНО РАЗНЫЕ (ракурс, действие, освещение, композиция, эмоция).

Каждый промпт включает: главный объект; кто в кадре и что делает; ракурс камеры; освещение; окружение; эмоциональный тон.

Сценарий 4 кадров:
- prompts[0]: заголовочная — отражает тему статьи буквально.
- prompts[1]: «боль» — растерянность, ошибка, неудобство.
- prompts[2]: «решение» — правильный аксессуар или приём в действии, крупный план рук.
- prompts[3]: «финал» — атмосферная сцена результата, гости за столом.

ФОРМАТ ОТВЕТА — строго JSON без markdown:
{
  "html_with_placeholders": "<полный HTML статьи с вставленными плейсхолдерами>",
  "image_prompts": ["<промпт 1>", "<промпт 2>", "<промпт 3>", "<промпт 4>"],
  "categories": ["<основная категория>", "<доп. категория (опционально)>"]
}
"""


def claude_redistribute(title: str, lead: str, body_html: str) -> dict:
    user = f"""Заголовок: {title}
Лид: {lead}

HTML статьи (без картинок):
{body_html}

Расставь 4 плейсхолдера, придумай 4 фотореалистичных промпта по правилам, присвой 1-2 категории. Ответ строго в JSON."""
    return claude_api.generate_json(CLAUDE_SYSTEM, user, max_tokens=8000, temperature=0.6)


def slug_from_url(url: str) -> str:
    m = re.search(r"/images/([^/]+)/", url)
    if m:
        return m.group(1)
    return None


def migrate():
    if not FEED_PATH.exists():
        print("feed.xml не найден")
        return 1

    for prefix, uri in publisher.NSMAP.items():
        ET.register_namespace(prefix, uri)
    tree = ET.parse(str(FEED_PATH))
    root = tree.getroot()
    channel = root.find("channel")

    items = channel.findall("item")
    print(f"Найдено статей: {len(items)}")

    for idx, item in enumerate(items, 1):
        title = item.findtext("title", default="").strip()
        lead = item.findtext("description", default="").strip()
        ft_el = item.find("yandex:full-text", NS)
        if ft_el is None or not ft_el.text:
            print(f"  [{idx}/{len(items)}] {title[:60]} — нет full-text, пропускаем")
            continue
        full_html = ft_el.text

        enc = item.find("enclosure")
        cover_url = enc.get("url") if enc is not None else ""
        slug = slug_from_url(cover_url) or html_renderer._slug_from_title(title, publisher.datetime.now(publisher.timezone.utc))

        print(f"\n=== [{idx}/{len(items)}] {title[:70]} ===")
        print(f"  slug: {slug}")

        body_clean = strip_images(full_html)
        print(f"  тело очищено: {len(body_clean)} символов")

        try:
            result = claude_redistribute(title, lead, body_clean)
        except Exception as e:
            print(f"  [!] Claude упал: {e}, пропускаем")
            continue

        new_html = result["html_with_placeholders"]
        prompts = result.get("image_prompts", [])
        cats = [c for c in (result.get("categories") or []) if c in CATEGORIES][:2]
        if not cats:
            cats = ["Дегустации и советы"]

        if len(prompts) != 4:
            print(f"  [!] промптов получено {len(prompts)}, ожидаем 4 — пропускаем")
            continue
        print(f"  категории: {cats}")

        # генерируем картинки
        folder = IMAGES_DIR / slug
        folder.mkdir(parents=True, exist_ok=True)
        image_urls = []
        for i, prompt in enumerate(prompts, 1):
            print(f"  Recraft {i}/4 ...")
            try:
                img_bytes = recraft_api.generate_image(prompt)
                fname = f"cover-{i}.jpg"
                (folder / fname).write_bytes(img_bytes)
                image_urls.append(f"images/{slug}/{fname}")
                print(f"     ok {len(img_bytes)} байт")
                time.sleep(1)
            except Exception as e:
                print(f"     [!] {e}")
                if image_urls:
                    image_urls.append(image_urls[0])
                else:
                    image_urls.append(f"images/{slug}/cover-1.jpg")

        # вставляем картинки в плейсхолдеры
        final_html = publisher.embed_images(new_html, image_urls, PAGES_BASE)

        # обновляем feed.xml
        ft_el.text = final_html

        main_url = f"{PAGES_BASE}/{image_urls[0]}"
        if enc is not None:
            enc.set("url", main_url)
        else:
            ET.SubElement(item, "enclosure", attrib={"url": main_url, "type": "image/jpeg"})

        # удаляем старые <category> и добавляем новые
        for c in item.findall("category"):
            item.remove(c)
        for cat in cats:
            ET.SubElement(item, "category").text = cat

        print(f"  feed.xml обновлён")

    tree.write(str(FEED_PATH), encoding="utf-8", xml_declaration=True)
    print("\nfeed.xml сохранён")

    print("\nПерегенерируем HTML-страницы и главную ...")
    html_renderer.rebuild_from_feed(PAGES_BASE)
    print("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
