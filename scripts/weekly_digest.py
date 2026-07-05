"""
Еженедельный дайджест — трейлеры собственных статей блога за неделю.
Каждая запись — заголовок-ссылка на статью на feed.addwine.ru + короткая выжимка (трейлер) 2-3 абзаца.
Картинки — существующие cover-1.jpg каждой статьи (без генерации).
Никаких внешних ссылок кроме своих статей.
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_api

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"


DIGEST_SYSTEM = """Ты — главный редактор винного журнала AddWine. Твоя задача — собрать еженедельный дайджест-трейлер из наших собственных статей за неделю. Формат — «Самое интересное за неделю».

ЦЕЛЬ ДАЙДЖЕСТА
Побудить читателя перейти в конкретную статью на feed.addwine.ru и дочитать её. Значит трейлер должен быть коротким, интригующим и говорить о ГЛАВНОМ — но не раскрывать всё.

ПРИНЦИПЫ ДАЙДЖЕСТА
- Для каждой статьи — краткая выжимка (2 абзаца, ~80–140 слов суммарно), которая цепляет и не пересказывает статью целиком.
- Заголовок каждого блока — гиперссылка <a href="URL_СТАТЬИ">Заголовок</a>. URL передаётся в исходных данных.
- Тон: экспертный, тёплый, редакторский. Без «читайте далее», «узнайте больше», «переходите по ссылке» — это уже подразумевается заголовком-ссылкой.
- Без CTA на addwine.ru или другие ресурсы. Только внутренняя навигация по нашим статьям.
- HTML-теги ТОЛЬКО: <p>, <h2>, <h3>, <a>, <b>, <i>, <ul>, <li>
- НЕ используй <strong>, <em>, <br>, <div>, <span>, <hr>, <img>, <figure>.

СТРУКТУРА HTML-ДАЙДЖЕСТА
- В начале — 1 короткий вступительный абзац (1–2 предложения), общая мысль о неделе.
- Затем для каждой статьи блок ровно в таком порядке:
  <p>[[IMG_N]]</p>
  <h3><a href="URL">Заголовок статьи</a></h3>
  <p>Первый абзац трейлера — что в статье, о ком, какая цепляющая идея.</p>
  <p>Второй абзац — почему это интересно / кому будет полезно / какая интрига.</p>

Где N — порядковый номер блока (1, 2, 3, ...). URL и заголовки бери из исходных данных.

ЗАГОЛОВОК ДАЙДЖЕСТА
Информативный, нейтральный:
- «Самое интересное за неделю в журнале AddWine»
- «Главные статьи недели: винный дайджест»
- «Что почитать: винный дайджест недели»

КАТЕГОРИИ
Основная: «Дайджест». Вторая: «Винные новости».

ФОРМАТ ОТВЕТА — строго JSON без markdown:
{
  "title": "<заголовок дайджеста>",
  "lead": "<один абзац — короткий обзор недели>",
  "html": "<полный HTML дайджеста>",
  "categories": ["Дайджест", "Винные новости"]
}
"""


def load_posts_for_week(days: int = 7) -> list:
    """Читаем posts_index.json, возвращаем статьи за N дней (кроме самих дайджестов)."""
    if not POSTS_INDEX.exists():
        return []
    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for p in posts:
        # пропускаем прошлые дайджесты чтобы не рекурсивно ссылаться
        title_low = p.get("title", "").lower()
        if any(kw in title_low for kw in ["дайджест", "самое интересное за нед", "события недели", "главные статьи нед"]):
            continue
        try:
            pd = datetime.fromisoformat(p["published_at"])
            if pd.tzinfo is None:
                pd = pd.replace(tzinfo=timezone.utc)
            if pd < cutoff:
                continue
            p["_pub_dt"] = pd
            result.append(p)
        except Exception:
            continue
    result.sort(key=lambda x: x["_pub_dt"], reverse=True)
    return result


def build_digest(posts: list, pages_base: str) -> dict:
    """
    posts: список dict {slug, title, lead, categories, published_at, ...}
    pages_base: 'https://feed.addwine.ru'
    """
    if not posts:
        raise RuntimeError("Нет статей за неделю")

    items_text = ""
    for i, p in enumerate(posts, 1):
        url = f"{pages_base}/posts/{p['slug']}/"
        items_text += f"\n--- Статья #{i} ---\n"
        items_text += f"URL: {url}\n"
        items_text += f"Заголовок: {p['title']}\n"
        items_text += f"Лид: {p.get('lead', '')}\n"
        cats = p.get("categories", [])
        if cats:
            items_text += f"Категории: {', '.join(cats)}\n"

    user = f"""Наши статьи в блоге AddWine за прошедшую неделю ({len(posts)} штук):
{items_text}

Составь дайджест-трейлер по правилам системного промпта. Для каждой статьи — короткая цепляющая выжимка 2 абзаца.
В html используй ровно {len(posts)} плейсхолдеров [[IMG_1]]..[[IMG_{len(posts)}]] в порядке появления статей.
Заголовок каждого блока — гиперссылка на URL статьи."""

    result = claude_api.generate_json(DIGEST_SYSTEM, user, max_tokens=8000, temperature=0.7)
    _validate(result)
    return result


def _validate(result: dict) -> None:
    for f in ("title", "lead", "html", "categories"):
        if f not in result:
            raise RuntimeError(f"Поле {f} отсутствует в ответе Claude")
    cats = result.get("categories") or []
    if "Дайджест" not in cats:
        cats = ["Дайджест"] + [c for c in cats if c != "Дайджест"]
    result["categories"] = cats[:2]
    result["html"] = re.sub(r"  +", " ", result["html"])
