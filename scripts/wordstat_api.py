"""
Yandex Wordstat API v2 через AI Studio Search API.
Endpoint: POST https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests
Документация: https://aistudio.yandex.ru/docs/ru/search-api/api-ref/Wordstat/getTop

По теме статьи возвращает топ ключевых слов с частотами (count).
Если API-ключ не задан или запрос упал — возвращает пустой список
(генерация статьи не блокируется, просто без SEO-подсказок).
"""
import os
import re
from typing import List, Dict

import requests

API_URL = os.environ.get(
    "YANDEX_WORDSTAT_API_URL",
    "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
)
TIMEOUT = 20
REGION_RUSSIA = "225"  # geo-id России (Wordstat принимает строкой)


def _headers() -> Dict[str, str]:
    key = os.environ.get("YANDEX_WORDSTAT_API_KEY", "").strip()
    if not key:
        return {}
    return {
        "Authorization": f"Api-Key {key}",
        "Content-Type": "application/json",
    }


def _folder_id() -> str:
    return os.environ.get("YANDEX_FOLDER_ID", "").strip()


def _extract_seed(topic: str) -> str:
    """Из полного заголовка вытаскиваем короткий seed для Wordstat (2-4 слова)."""
    t = re.split(r"[:—\-–\(]", topic, 1)[0]
    t = t.strip().lower()
    stop = {"как", "что", "почему", "зачем", "чем", "какой", "какая", "какие",
            "гид", "по", "и", "или", "в", "на", "с", "у", "от", "до",
            "5", "10", "разбор", "правила", "правило"}
    words = [w for w in re.findall(r"[a-zа-яё]+", t) if w not in stop and len(w) > 2]
    return " ".join(words[:4]) if words else topic[:40].lower()


def get_keywords(topic: str, limit: int = 20) -> List[Dict]:
    """
    Возвращает список dict {"phrase": "рецепт негрони", "count": 8500}.
    В случае ошибки — пустой список.
    """
    headers = _headers()
    if not headers:
        print("  [wordstat] API-ключ не задан, пропускаем")
        return []

    seed = _extract_seed(topic)
    print(f"  [wordstat] seed: '{seed}'")

    body = {
        "phrase": seed,
        "numPhrases": str(limit),
        "regions": [REGION_RUSSIA],
        "devices": ["DEVICE_ALL"],
    }
    folder_id = _folder_id()
    if folder_id:
        body["folderId"] = folder_id

    try:
        r = requests.post(API_URL, json=body, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            phrases = _parse_response(data, limit, seed=seed)
            print(f"  [wordstat] получено {len(phrases)} ключей (после фильтра)")
            return phrases
        else:
            print(f"  [wordstat] HTTP {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"  [wordstat] {type(e).__name__}: {e}")
    return []


ADULT_STOPWORDS = {
    "blacked", "porn", "xxx", "секс", "порно", "18+", "hentai", "хентай",
    "brazzers", "onlyfans", "camgirl", "escort", "трах", "ебл", "минет",
}


def _is_relevant(phrase: str, seed: str) -> bool:
    """Фраза релевантна если содержит хотя бы одно слово из seed'а и не adult."""
    low = phrase.lower()
    if any(bad in low for bad in ADULT_STOPWORDS):
        return False
    # каждое слово seed'а длиннее 3 симв. проверяем на вхождение (учитывая опечатки)
    seed_words = [w for w in seed.lower().split() if len(w) > 3]
    if not seed_words:
        return True
    return any(_word_matches(low, w) for w in seed_words)


def _word_matches(text: str, seed_word: str) -> bool:
    """Проверяет вхождение с допуском опечаток / склонений: первые 4 символа совпали."""
    if seed_word in text:
        return True
    stem = seed_word[:4]
    # ищем как отдельное слово с любым окончанием
    return re.search(rf"\b{re.escape(stem)}\w*", text) is not None


def _parse_response(data: dict, limit: int, seed: str = "") -> List[Dict]:
    """
    Схема ответа: {"results": [{phrase, count}], "associations": [{phrase, count}]}
    - Берём ТОЛЬКО results (в них фразы содержащие ключ, не семантические ассоциации).
    - Фильтруем adult и нерелевантные.
    """
    parsed = []
    seen = set()
    # associations игнорируем — там семантические соседи, часто мусор
    for it in data.get("results", []) or []:
        phrase = (it.get("phrase") or "").strip()
        try:
            count = int(it.get("count") or 0)
        except Exception:
            count = 0
        if not phrase or phrase.lower() in seen or count <= 0:
            continue
        if seed and not _is_relevant(phrase, seed):
            continue
        seen.add(phrase.lower())
        parsed.append({"phrase": phrase, "count": count})

    parsed.sort(key=lambda x: x["count"], reverse=True)
    return parsed[:limit]


def format_for_prompt(keywords: List[Dict]) -> str:
    """Форматирует ключи как список для промпта Claude'у."""
    if not keywords:
        return ""
    lines = ["РЕАЛЬНЫЕ КЛЮЧЕВЫЕ СЛОВА ИЗ ЯНДЕКС.WORDSTAT (используй их в title, H2, первых 100 словах лида, meta description):"]
    for kw in keywords[:15]:
        lines.append(f"  - «{kw['phrase']}» ({kw['count']} показов/мес)")
    lines.append("")
    lines.append("Правила SEO:")
    lines.append("- Топ-1 ключ обязательно в title (H1) и первом предложении лида.")
    lines.append("- Топ-3 ключей — в первых 100 словах статьи (натурально, не спам).")
    lines.append("- Long-tail ключи (низкочастотные) — в подзаголовках H2/H3.")
    lines.append("- Meta description — включи топ-1 ключ и топ-2 ключ вариацию.")
    return "\n".join(lines)
