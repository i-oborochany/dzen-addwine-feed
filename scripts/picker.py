"""
Выбор лучшей темы из пула кандидатов через GigaChat.
Возвращает один dict выбранной статьи.
"""
import json
import random
from datetime import datetime, timezone

import gigachat


def _score(item: dict) -> float:
    """Базовая ранжировка: свежее = выше, заголовок длиннее = выше."""
    score = 0.0
    # свежесть
    if item.get("published"):
        delta_days = (datetime.now(timezone.utc) - item["published"]).total_seconds() / 86400
        score += max(0, 30 - delta_days) / 30  # 0..1
    else:
        score += 0.3  # HTML без даты — не штрафуем сильно
    # длина заголовка (часто кликабельные заголовки длиннее)
    score += min(len(item["title"]) / 100, 1.0)
    # шум-фильтр: служебные слова в URL понижают
    bad = ["category", "tag/", "page/", "archive", "/feed", "rss"]
    if any(b in item["url"].lower() for b in bad):
        score -= 0.5
    return score


def pick_topic(items: list, config: dict, published_urls: set) -> dict:
    """
    1. отсеиваем уже опубликованные URL
    2. ранжируем
    3. берём топ-N
    4. просим GigaChat выбрать одного фаворита для канала
    """
    fresh = [i for i in items if i["url"] not in published_urls]
    if not fresh:
        raise RuntimeError("Все кандидаты уже публиковались — пул источников исчерпан")

    fresh.sort(key=_score, reverse=True)
    top = fresh[: config.get("candidate_pool_size", 20)]

    # формируем список для GigaChat
    candidates_text = "\n".join(
        f"{i+1}. [{c['source']}] {c['title']} (lang={c['lang']})"
        for i, c in enumerate(top)
    )

    system = (
        "Ты — главный редактор винного канала на Дзене. "
        "Канал «Addwine» рассказывает о вине, виноделии, культуре потребления, "
        "винных аксессуарах, ресторанах и сомелье. "
        "Аудитория — взрослые ценители вина, 25–55 лет, средний и выше доход. "
        "Тебе нужно выбрать ОДНУ статью из списка кандидатов, которая лучше всего подходит "
        "для публикации сегодня: интересна аудитории, не дублирует уже изданное, "
        "имеет потенциал виральности (лайки, комментарии, репосты). "
        "Избегай чисто рекламных и сугубо корпоративных пресс-релизов."
    )

    user = (
        f"Кандидаты на сегодня:\n\n{candidates_text}\n\n"
        f"Ответь в JSON-формате без пояснений: "
        f'{{"index": <номер от 1 до {len(top)}>, "reason": "<краткое обоснование>"}}'
    )

    raw = gigachat.chat_text(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=200,
    )

    # парсим JSON (модель может вернуть мусор вокруг)
    try:
        import re
        m = re.search(r"\{[^{}]*\}", raw)
        if not m:
            raise ValueError(f"No JSON in response: {raw[:200]}")
        choice = json.loads(m.group(0))
        idx = int(choice["index"]) - 1
        if idx < 0 or idx >= len(top):
            raise ValueError(f"Index out of range: {idx}")
        winner = top[idx]
        winner["pick_reason"] = choice.get("reason", "")
        return winner
    except Exception as e:
        print(f"[picker] не смог распарсить ответ GigaChat: {e}")
        print(f"[picker] raw: {raw[:300]}")
        # fallback: берём первого по score
        return top[0]
