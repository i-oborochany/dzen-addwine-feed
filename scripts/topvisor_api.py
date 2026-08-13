"""
Обёртка над API Topvisor v2.
Документация: https://topvisor.com/ru/api/

Получает позиции ключевых запросов проекта в Яндексе и Google.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict

import requests

API_URL = "https://api.topvisor.com/v2/json"
TIMEOUT = 30


def _headers() -> Dict[str, str]:
    api_key = os.environ.get("TOPVISOR_API_KEY", "").strip()
    user_id = os.environ.get("TOPVISOR_USER_ID", "").strip()
    return {
        "Authorization": f"bearer {api_key}",
        "User-Id": user_id,
        "Content-Type": "application/json",
    }


def _project_id() -> str:
    return os.environ.get("TOPVISOR_PROJECT_ID", "").strip()


def _post(path: str, payload: dict) -> dict:
    """Универсальный POST-запрос к Topvisor API."""
    url = f"{API_URL}/{path.lstrip('/')}"
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  [topvisor] {url} → HTTP {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"  [topvisor] {url} → {type(e).__name__}: {e}")
    return {}


def _get_project_regions(project_id: int) -> List[int]:
    """
    Достаёт список индексов регионов конкретного проекта.
    Разные проекты имеют разные regions_indexes.
    """
    data = _post("get/projects_2/searchers_regions", {"project_id": project_id})
    if not data:
        return []
    raw = data.get("result")
    if not raw:
        return []
    indexes = []
    try:
        for item in (raw if isinstance(raw, list) else raw.get("regions", [])):
            if isinstance(item, dict):
                idx = item.get("index")
                if idx is not None:
                    indexes.append(int(idx))
    except Exception as e:
        print(f"  [topvisor] regions parse: {e}")
    return indexes


def get_positions(days_back: int = 7, debug: bool = False) -> List[Dict]:
    """
    Получает последние позиции по всем ключам проекта.
    Возвращает [{keyword, se: 'yandex'/'google', region, position, url}]
    """
    project_id = _project_id()
    if not project_id:
        print("  [topvisor] TOPVISOR_PROJECT_ID не задан")
        return []

    date_to = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Сначала узнаём реальные regions_indexes проекта (у каждого свои)
    regions = _get_project_regions(int(project_id))
    if not regions:
        print("  [topvisor] не удалось получить регионы проекта")
        return []

    payload = {
        "project_id": int(project_id),
        "regions_indexes": regions,
        "date1": date_from,
        "date2": date_to,
        "show_headers": 1,
        "show_exists_dates": 1,
        "fields": ["name", "id"],
        "positions_fields": ["position", "relevant_url"],
    }
    data = _post("get/positions_2/history", payload)
    if not data:
        return []

    if debug:
        import json as _j
        print("[debug] Топ-уровневые ключи ответа:", list(data.keys()))
        errors = data.get("errors")
        if errors:
            print("[debug] Ошибки API:", _j.dumps(errors, ensure_ascii=False, indent=2))
        print("[debug] Сырой ответ (первые 2000 симв.):")
        print(_j.dumps(data, ensure_ascii=False, indent=2)[:2000])

    # Проверяем что result не null и не пустой
    raw = data.get("result")
    if raw is None:
        print("  [topvisor] result: null (обычно значит что позиции ещё не собраны или ошибка)")
        return []

    result = []
    try:
        # result может быть dict или list в разных версиях API
        if isinstance(raw, list):
            keywords = raw
        elif isinstance(raw, dict):
            keywords = raw.get("keywords") or raw.get("data") or []
        else:
            keywords = []

        for kw in keywords:
            if not isinstance(kw, dict):
                continue
            name = kw.get("name", "")
            positions_data = kw.get("positionsData") or kw.get("positions_data") or {}
            if not isinstance(positions_data, dict):
                continue
            for region_key, positions in positions_data.items():
                if not positions or not isinstance(positions, dict):
                    continue
                # Берём последнюю дату
                latest_key = sorted(positions.keys())[-1] if positions else None
                if not latest_key:
                    continue
                latest = positions.get(latest_key)
                if not isinstance(latest, dict):
                    continue
                position = latest.get("position", 0)
                url = latest.get("url", "") or latest.get("relevant_url", "")
                parts = region_key.split(":")
                se_index = parts[1] if len(parts) > 1 else "0"
                se = "yandex" if se_index == "0" else "google"
                try:
                    position_int = int(position)
                except Exception:
                    continue
                if position_int > 0 and position_int < 200:
                    result.append({
                        "keyword": name,
                        "se": se,
                        "position": position_int,
                        "url": url,
                    })
    except Exception as e:
        print(f"  [topvisor] парсинг: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    return result


def find_boost_candidates(min_pos: int = 4, max_pos: int = 15) -> List[Dict]:
    """
    Находит статьи которые почти в топе (позиции min_pos - max_pos).
    Возвращает список URL с ключами и позициями.
    """
    positions = get_positions()
    candidates = {}
    for p in positions:
        if min_pos <= p["position"] <= max_pos and p["url"]:
            key = p["url"]
            if key not in candidates:
                candidates[key] = {
                    "url": p["url"],
                    "keywords": [],
                }
            candidates[key]["keywords"].append({
                "kw": p["keyword"],
                "pos": p["position"],
                "se": p["se"],
            })
    return list(candidates.values())


def test_connection() -> bool:
    """Проверяет что API-доступы валидные."""
    print(f"TOPVISOR_USER_ID задан: {bool(os.environ.get('TOPVISOR_USER_ID'))}")
    print(f"TOPVISOR_API_KEY задан: {bool(os.environ.get('TOPVISOR_API_KEY'))}")
    print(f"TOPVISOR_PROJECT_ID задан: {bool(os.environ.get('TOPVISOR_PROJECT_ID'))}")
    print()

    # Пробуем получить список проектов
    data = _post("get/projects_2/projects", {"show_headers": 1})
    if not data:
        print("❌ API недоступно или ключи неверные")
        return False

    projects = data.get("result", [])
    print(f"✅ Топвизор ответил, проектов у аккаунта: {len(projects)}")
    for p in projects[:5]:
        print(f"  · id={p.get('id')} site={p.get('site')} name={p.get('name')}")

    # Пробуем получить позиции
    positions = get_positions()
    print(f"\nПозиций получено: {len(positions)}")
    for p in positions[:10]:
        print(f"  {p['se']:6}  #{p['position']:3}  «{p['keyword'][:50]}»  → {p['url'][:60]}")

    # Кандидаты на дожим
    candidates = find_boost_candidates()
    print(f"\nСтраниц-кандидатов на дожим (позиции 4-15): {len(candidates)}")
    for c in candidates[:5]:
        keys = ", ".join(f"«{k['kw']}» #{k['pos']}" for k in c["keywords"][:3])
        print(f"  {c['url']}")
        print(f"    {keys}")

    return True


if __name__ == "__main__":
    test_connection()
