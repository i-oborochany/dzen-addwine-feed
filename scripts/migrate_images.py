"""
Одноразовый скрипт: пересоздаёт картинки для всех статей в feed.xml.
Для каждой статьи:
1. Удаляет старые <img> теги из тела
2. Просит Claude расставить плейсхолдеры [[IMG_1]]..[[IMG_4]] по сценарию (заголовок/боль/решение/финал)
   и сгенерировать 4 новых детальных image prompts
3. Генерирует 4 картинки через Recraft V3 в едином стиле
4. Сохраняет в images/<slug>/cover-N.jpg (перезаписывает старые)
5. Обновляет yandex:full-text в feed.xml
6. Перегенерирует posts/<slug>/index.html и главную
"""
import json
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

# модули
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


def strip_images(html: str) -> str:
    """Убирает <p><img.../></p> и одинокие <img> теги."""
    # <p>...<img.../>...</p> где p содержит только img
    html = re.sub(r"<p>\s*<img[^>]*/?>\s*</p>", "", html, flags=re.IGNORECASE)
    # одинокие <img>
    html = re.sub(r"<img[^>]*/?>", "", html, flags=re.IGNORECASE)
    return html.strip()


CLAUDE_SYSTEM = """Ты — редактор винного журнала AddWine. Тебе дают готовую статью без картинок.
Твоя задача:
1. Расставить в HTML 4 плейсхолдера [[IMG_1]]..[[IMG_4]] (каждый внутри своего <p>) в правильных смысловых местах по сценарию: заголовок → боль → решение → финал.
2. Придумать 4 детальных промпта для генератора фото Recraft (на русском, фотореализм).

ПРАВИЛА РАЗМЕЩЕНИЯ:
- [[IMG_1]] — заголовочная картинка. ВНУТРИ html, после первого вступительного абзаца, до первого <h2>.
- [[IMG_2]] — «боль». Вставь в раздел где описывается проблема, ошибка, неправильный выбор. Внутри (после первого-второго параграфа) этого раздела.
- [[IMG_3]] — «решение». Вставь в раздел где даётся конкретный совет, описывается правильный аксессуар.
- [[IMG_4]] — «финал». Вставь перед финальным выводом, или перед блоком "AddWine рекомендует" если он есть.

ПРАВИЛА ПРОМПТОВ ДЛЯ ФОТО (минимум 60 слов каждый):
- Все 4 в едином премиальном стиле фото-журнала.
- Палитра: тёплый кремовый и глубокий тёмно-сине-зелёный (как Pantone 302 и 7403).
- Бокалы: большого объёма, с тонкой ножкой и тонким стеклом.
- В каждом промпте — конкретное действие, освещение, ракурс, рабочая область человека (руки или часть фигуры).
- 4 кадра должны быть ВИЗУАЛЬНО РАЗНЫМИ: разный ракурс, действие, эмоция, освещение, композиция.
- Без видимого текста на картинке.

ФОРМАТ ОТВЕТА — строго JSON без markdown:
{
  "html_with_placeholders": "<полный HTML статьи со вставленными [[IMG_N]] плейсхолдерами>",
  "image_prompts": ["<промпт 1: заголовок>", "<промпт 2: боль>", "<промпт 3: решение>", "<промпт 4: финал>"]
}
"""


def claude_redistribute(title: str, lead: str, body_html: str) -> dict:
    user = f"""Заголовок: {title}
Лид: {lead}

HTML статьи (без картинок):
{body_html}

Расставь 4 плейсхолдера и придумай 4 промпта по правилам из системного сообщения. Ответ строго в JSON."""
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

        # 1. убираем старые картинки из тела
        body_clean = strip_images(full_html)
        print(f"  тело очищено: {len(body_clean)} символов")

        # 2. Claude расставляет плейсхолдеры + новые промпты
        try:
            result = claude_redistribute(title, lead, body_clean)
        except Exception as e:
            print(f"  [!] Claude упал: {e}, пропускаем")
            continue

        new_html = result["html_with_placeholders"]
        prompts = result["image_prompts"]
        if len(prompts) != 4:
            print(f"  [!] промптов получено {len(prompts)}, ожидаем 4 — пропускаем")
            continue
        print(f"  Claude вернул HTML с плейсхолдерами + 4 промпта")

        # 3. Генерируем 4 картинки через Recraft
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
                time.sleep(1)  # лёгкая пауза от rate-limit
            except Exception as e:
                print(f"     [!] {e}")
                if image_urls:
                    image_urls.append(image_urls[0])
                else:
                    image_urls.append(f"images/{slug}/cover-1.jpg")  # placeholder

        # 4. embed_images подставляет реальные URL в плейсхолдеры
        final_html = publisher.embed_images(new_html, image_urls, PAGES_BASE)

        # 5. обновляем full-text в feed.xml
        ft_el.text = final_html

        # 6. обновляем enclosure (главная картинка) — берём IMG_1
        main_url = f"{PAGES_BASE}/{image_urls[0]}"
        if enc is not None:
            enc.set("url", main_url)
        else:
            ET.SubElement(item, "enclosure", attrib={"url": main_url, "type": "image/jpeg"})

        print(f"  feed.xml обновлён для этой статьи")

    # сохраняем обновлённый feed.xml
    tree.write(str(FEED_PATH), encoding="utf-8", xml_declaration=True)
    print("\nfeed.xml сохранён")

    # перегенерируем страницы статей и главную
    print("\nПерегенерируем HTML-страницы и главную ...")
    html_renderer.rebuild_from_feed(PAGES_BASE)
    print("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
