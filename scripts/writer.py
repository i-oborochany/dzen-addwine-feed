"""
Получение полного текста выбранной статьи и рерайт через GigaChat.
"""
import json
import re
import requests
from bs4 import BeautifulSoup

import gigachat

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.8",
}


def fetch_article_text(url: str) -> str:
    """Скачивает HTML и грубо извлекает основной текст статьи."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Не удалось скачать {url}: {e}")

    soup = BeautifulSoup(resp.text, "lxml")
    # удаляем шум
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    # ищем article, иначе main, иначе body
    article = soup.find("article") or soup.find("main") or soup.body
    if not article:
        return ""

    paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 40]
    text = "\n\n".join(paragraphs)
    # обрезаем до 8000 символов чтобы влезть в контекст
    return text[:8000]


def rewrite_article(topic: dict, full_text: str, config: dict) -> dict:
    """
    Возвращает dict с полями:
    - title: SEO-заголовок
    - lead: подводка 1–2 предложения
    - html: HTML тела статьи (разрешённые теги для Дзена)
    - image_prompts: список из 4 промптов для Kandinsky
    """
    target_len = config["publishing"]["target_length"]
    lang_hint = "Это статья на английском — переведи на русский." if topic["lang"] == "en" else ""

    system = (
        "Ты — копирайтер винного канала Addwine на Дзене. "
        "Твоя задача — сделать качественный рерайт исходной статьи: "
        "сохранить факты, переписать своими словами, добавить интересный заголовок и подводку. "
        "Стиль: экспертный, тёплый, без канцелярита и пафоса. "
        "Аудитория — взрослые ценители вина."
    )

    user = f"""Исходная статья:
Заголовок: {topic['title']}
Источник: {topic['source']}
URL: {topic['url']}
{lang_hint}

Полный текст:
{full_text}

Перепиши статью для Дзена со следующими требованиями:
- объём примерно {target_len} символов (±500)
- свой собственный заголовок (а не копия исходного)
- лид 1–2 предложения
- 3–5 подзаголовков H2/H3 внутри текста
- используй ТОЛЬКО HTML-теги: <p>, <h2>, <h3>, <ul>, <ol>, <li>, <blockquote>, <strong>, <em>, <br>
- НЕ используй <div>, <span>, <script>, инлайн-стили
- упомяни источник в конце фразой: «По материалам {topic['source']}»

Также придумай 4 промпта для генератора картинок (Kandinsky), 4 обложки одной статьи в едином стиле:
- картинка 1: заголовочная — отражает тему статьи
- картинка 2: «боль» читателя — проблема, которую решает статья
- картинка 3: решение — то, что предлагает статья
- картинка 4: финал — уверение что решение работает

Стиль обложек (вшей в каждый промпт): классический интерьер, тёмно-синий и кремовый
цвета (Pantone 302 и 7403), бокалы с тонкой ножкой, фигура человека (частично),
сцена «за столом, дома или в ресторане», без видимого текста на картинке.

Ответь СТРОГО в JSON без markdown-обрамления:
{{
  "title": "...",
  "lead": "...",
  "html": "<p>...</p><h2>...</h2><p>...</p>...",
  "image_prompts": ["...", "...", "...", "..."]
}}"""

    raw = gigachat.chat_text(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    # парсим JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # пытаемся вытащить большой JSON-объект
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise RuntimeError(f"Не JSON в ответе модели: {raw[:300]}")
        result = json.loads(m.group(0))

    # валидация
    for field in ("title", "lead", "html", "image_prompts"):
        if field not in result:
            raise RuntimeError(f"Поле '{field}' отсутствует в ответе модели")
    if len(result["image_prompts"]) != 4:
        # докинем/обрежем до 4
        while len(result["image_prompts"]) < 4:
            result["image_prompts"].append(result["image_prompts"][-1])
        result["image_prompts"] = result["image_prompts"][:4]

    # дисклеймер
    if config["publishing"]["add_disclaimer"]:
        result["html"] += f"\n\n<p><em>{config['publishing']['disclaimer_text']}</em></p>"

    return result
