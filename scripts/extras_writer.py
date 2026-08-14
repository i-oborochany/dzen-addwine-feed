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


def pick_topic(rubric_config: dict, used_titles: list, history: list = None) -> str:
    """
    Выбирает тему из банка. Если передана history (dict с date+title),
    применяется семантический дедуп на 90 дней (см. dedup.py).
    """
    topics = load_topics(rubric_config)
    used_lower = [t.lower() for t in used_titles]

    # 1. Отбраковка по первым 30 символам темы (быстрый прямой дедуп)
    fresh = [t for t in topics if not any(t.lower()[:30] in u for u in used_lower)]
    if not fresh:
        fresh = topics

    # 1.5. Стоп-лист тем/брендов (не пересекаться с коммерческим блогом)
    import stop_list
    filtered = stop_list.filter_topics(fresh)
    if filtered:
        fresh = filtered

    # 2. Семантический дедуп через dedup.py на 90 дней
    if history:
        import dedup
        no_dupes = dedup.filter_topics(fresh, history, days=90)
        if no_dupes:
            fresh = no_dupes
            print(f"  [dedup] после фильтра 90 дней осталось {len(fresh)} тем")
        else:
            print(f"  [dedup] ⚠️  все темы имеют семантический дубль за 90 дней — берём наименее свежий")

    return fresh[0]


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
- Объём: 4800–5800 знаков с пробелами (глубокие тексты Яндекс ранжирует лучше).
- ОБЯЗАТЕЛЬНАЯ секция FAQ в конце статьи для расширенных сниппетов в Яндекс/Google. Формат:
  <h2>Частые вопросы</h2>
  <div class="faq">
    <h3>Вопрос 1?</h3>
    <p>Ответ 1 (полный, 30-60 слов).</p>
    <h3>Вопрос 2?</h3>
    <p>Ответ 2.</p>
    <h3>Вопрос 3?</h3>
    <p>Ответ 3.</p>
    <h3>Вопрос 4?</h3>
    <p>Ответ 4.</p>
  </div>
  Вопросы должны быть реалистичными: «Как выбрать...», «С чем пить...», «Сколько стоит...», «Чем отличается X от Y», «Как хранить...».
- ЕСЛИ тема — конкретный коктейль (Негрони, Мохито, Мартини, Маргарита и т.д.) — ОБЯЗАТЕЛЬНО в первой трети статьи добавь блок с рецептом:
  <h2>Рецепт [название коктейля]</h2>
  <div class="recipe">
    <p><b>Ингредиенты:</b></p>
    <ul>
      <li>30 мл джина</li>
      <li>30 мл кампари</li>
      <li>...</li>
    </ul>
    <p><b>Способ приготовления:</b></p>
    <ol>
      <li>Шаг 1 (полное предложение).</li>
      <li>Шаг 2.</li>
      <li>Шаг 3.</li>
    </ol>
  </div>
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


def write_article(rubric: str, topic_idea: str, recent_titles: list, keywords_hint: str = "") -> dict:
    """Основная функция генерации."""
    cfg = load_config(rubric)
    system = build_system_prompt(cfg)
    link = pick_link(cfg, topic_idea)
    history = "\n".join(f"- {t}" for t in recent_titles[:30]) if recent_titles else "(пусто)"

    seo_block = f"\n\n{keywords_hint}\n" if keywords_hint else ""

    user = f"""ИДЕЯ ДЛЯ СТАТЬИ: {topic_idea}

Уже публиковали в этой рубрике (не повторяйся):
{history}

Нативно упомяни в одном месте статьи наш раздел: {link['title']} — {link['url']}
Формат: обычная HTML-ссылка <a href="..."> внутри абзаца, органично встроенная в текст. Одна фраза, не CTA-блок.
{seo_block}
Напиши статью по правилам системного промпта. Ответ — строго JSON."""

    result = claude_api.generate_json(system, user, max_tokens=8000, temperature=0.7)
    _validate(result, cfg)
    result["_link_used"] = link
    result["_rubric_config"] = cfg
    return result


def _validate(result: dict, cfg: dict) -> None:
    # мягкая валидация обязательных полей
    for f in ("title_chosen", "lead", "html"):
        if f not in result or not result[f]:
            raise RuntimeError(f"Поле '{f}' отсутствует или пустое в ответе Claude. Keys: {list(result.keys())}")

    # image_prompts может быть строкой — приведём к списку
    ip = result.get("image_prompts")
    if isinstance(ip, str):
        ip = [ip]
    elif ip is None:
        # запасной вариант — генерим базовый промпт из темы и стиля
        ip = [f"Премиум-редакторское фото по теме: {result['title_chosen']}. {cfg.get('image_style_note', '')[:400]}"]
    if not isinstance(ip, list) or len(ip) < 1:
        raise RuntimeError(f"image_prompts некорректный: {type(ip).__name__}")
    result["image_prompts"] = ip[:1]

    # titles — может отсутствовать
    if "titles" not in result:
        result["titles"] = [result["title_chosen"]]

    # comment_question — может отсутствовать
    if "comment_question" not in result:
        result["comment_question"] = ""

    cats = result.get("categories") or []
    if isinstance(cats, str):
        cats = [cats]
    main = cfg["cat_main"]
    if main not in cats:
        cats = [main] + [c for c in cats if c != main]
    result["categories"] = cats[:2]

    result["html"] = re.sub(r"  +", " ", result["html"])
