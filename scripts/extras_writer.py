"""
Универсальный генератор статей для 4 «extra»-рубрик:
- spirits (Крепкий алкоголь)
- beer (Пиво и сидр)
- water (Вода, коктейли, безалкогольное)
- fortified (Вермуты и креплёные)

Читает <rubric>_config.json + <rubric>_topics.json и генерит статью.
Стилистика формируется из полей rubric_name / tone / image_style_note / links.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config(rubric: str) -> dict:
    p = REPO_ROOT / f"{rubric}_config.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_topics(rubric_config: dict) -> list:
    p = REPO_ROOT / rubric_config["topics_file"]
    return json.loads(p.read_text(encoding="utf-8"))["topics"]


def pick_topic(rubric_config: dict, used_titles: list) -> str:
    topics = load_topics(rubric_config)
    used_lower = [t.lower() for t in used_titles]
    for topic in topics:
        if not any(topic.lower()[:30] in u for u in used_lower):
            return topic
    return topics[0]


def pick_link(rubric_config: dict, topic: str) -> dict:
    """Ищет ссылку с максимальным совпадением ключей в теме."""
    topic_low = topic.lower()
    best = None
    best_score = -1
    for link in rubric_config["links"]:
        keys = link.get("keywords", [])
        score = sum(1 for k in keys if k in topic_low)
        # если у ссылки нет ключей, она fallback — низкий приоритет
        if not keys:
            score = 0.1 if best_score < 0 else 0
        if score > best_score:
            best_score = score
            best = link
    return best or rubric_config["links"][0]


def build_system_prompt(rubric_config: dict) -> str:
    cat_main = rubric_config["cat_main"]
    cat_secondary = ", ".join(f'«{c}»' for c in rubric_config["cat_secondary"])
    return f"""Ты — редактор винного журнала AddWine, ведёшь рубрику «{rubric_config['rubric_name']}». Пишешь одну статью на заданную тему.

ТОН И ПОЗИЦИОНИРОВАНИЕ
{rubric_config['tone']}

АУДИТОРИЯ
Ценители напитков 28-55 лет, гурманы, посетители баров и ресторанов, профессионалы отрасли.

ТРЕБОВАНИЯ К СТАТЬЕ
- Объём: 3000–3800 знаков с пробелами.
- Первый абзац — крепкий тезис по теме.
- 3–5 подзаголовков H2/H3 — от истории и производства к практике сервировки и гастрономии.
- Конкретика: имена, регионы, годы, цифры, бренды.
- Без снобизма, без CTA-заигрываний.
- В одном месте текста — короткая нативная упомянутая ссылка на addwine.ru (её передадут отдельно). Формат: одна фраза внутри абзаца, органично встроенная.
- HTML-теги ТОЛЬКО: <p>, <h2>, <h3>, <h4>, <ul>, <ol>, <li>, <blockquote>, <b>, <i>, <a>
- НЕ используй <strong>, <em>, <br>, <div>, <span>, инлайн-стили.

ЗАГОЛОВОК
3 варианта в стиле «Как…», «Что…», «Почему…», «Гид по…», «Разбор…», «5 фактов…». БЕЗ кликбейта.

КАТЕГОРИЯ
Основная категория всегда: «{cat_main}». Второстепенная — на выбор из: {cat_secondary}.

РАЗМЕЩЕНИЕ КАРТИНКИ
Расставь в html ровно 1 плейсхолдер: <p>[[IMG_1]]</p>.
- [[IMG_1]] — сразу после первого вводного абзаца, до первого <h2>.

ПРОМПТ ДЛЯ КАРТИНКИ (image_prompts) — РОВНО 1, минимум 100 слов на русском.

СТИЛЬ ФОТО
{rubric_config['image_style_note']}

АНАТОМИЯ ЖЁСТКО:
- НИКАКИХ крупных планов рук с бокалами / стаканами.
- НИКАКИХ тостов и чокания.
- Если люди в кадре — руки спокойные, бокал стоит на столе, средний или дальний план.

БЕЗ текста, надписей, букв, цифр, логотипов, водяных знаков на изображении.

Промпт включает: главный сюжет, ракурс, освещение, окружение, атмосферу, время суток.

ВОПРОС-ЗАТРАВКА ДЛЯ КОММЕНТАРИЕВ
Один вопрос до 70 знаков по теме статьи, провоцирует обсуждение.

ФОРМАТ ОТВЕТА — строго JSON без markdown:
{{
  "titles": ["заголовок 1", "заголовок 2", "заголовок 3"],
  "title_chosen": "<один из titles>",
  "lead": "<один-два предложения>",
  "html": "<полная html-статья с плейсхолдером [[IMG_1]]>",
  "image_prompts": ["промпт заглавного фото"],
  "comment_question": "<вопрос>",
  "categories": ["{cat_main}", "Дополнительная категория"]
}}
"""


def write_article(rubric: str, topic_idea: str, recent_titles: list) -> dict:
    """Основная функция генерации."""
    cfg = load_config(rubric)
    system = build_system_prompt(cfg)
    link = pick_link(cfg, topic_idea)
    history = "\n".join(f"- {t}" for t in recent_titles[:30]) if recent_titles else "(пусто)"

    user = f"""ИДЕЯ ДЛЯ СТАТЬИ: {topic_idea}

Уже публиковали в этой рубрике (не повторяйся):
{history}

Нативно упомяни в одном месте статьи наш раздел: {link['title']} — {link['url']}
Формат: обычная HTML-ссылка <a href="..."> внутри абзаца, органично встроенная в текст. Одна фраза, не CTA-блок.

Напиши статью по правилам системного промпта. Ответ — строго JSON."""

    result = claude_api.generate_json(system, user, max_tokens=8000, temperature=0.7)
    _validate(result, cfg)
    result["_link_used"] = link
    result["_rubric_config"] = cfg
    return result


def _validate(result: dict, cfg: dict) -> None:
    required = ["titles", "title_chosen", "lead", "html", "image_prompts", "comment_question", "categories"]
    for f in required:
        if f not in result:
            raise RuntimeError(f"Поле '{f}' отсутствует в ответе Claude")
    if len(result["image_prompts"]) < 1:
        raise RuntimeError("image_prompts пустой")
    result["image_prompts"] = result["image_prompts"][:1]

    cats = result.get("categories") or []
    main = cfg["cat_main"]
    if main not in cats:
        cats = [main] + [c for c in cats if c != main]
    result["categories"] = cats[:2]

    result["html"] = re.sub(r"  +", " ", result["html"])
