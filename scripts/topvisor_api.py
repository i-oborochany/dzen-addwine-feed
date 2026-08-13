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


def _get_project_regions(project_id: int, debug: bool = False) -> List[int]:
    """
    Достаёт индексы регионов конкретного проекта.
    Пробует несколько путей API — Topvisor меняет их между версиями.
    """
    import json as _j

    # В Topvisor API v2 регионы возвращаются через positions_2/searchers
    endpoints = [
        ("get/positions_2/searchers", {"project_id": project_id}),
        ("get/positions_2/searchers/list", {"project_id": project_id}),
        ("get/projects_2/searchers_regions/list", {"project_id": project_id}),
        ("get/projects_2/projects", {"filters": [{"name": "id", "operator": "EQUALS", "values": [project_id]}], "fields": ["id", "name", "site"], "show_searchers_and_regions": 1}),
    ]

    for path, payload in endpoints:
        data = _post(path, payload)
        if debug:
            print(f"\n[debug] endpoint: {path}")
            print(f"[debug] ответ (первые 1500 симв):")
            print(_j.dumps(data, ensure_ascii=False, indent=2)[:1500])

        raw = data.get("result") if data else None
        if not raw:
            continue

        indexes = _extract_indexes(raw)
        if indexes:
            if debug:
                print(f"[debug] найдены индексы через {path}: {indexes}")
            return indexes

    return []


def _extract_indexes(raw) -> List[int]:
    """Универсальный извлекатель индексов регионов из разных схем ответа."""
    indexes = []

    def walk(obj):
        if isinstance(obj, dict):
            if "index" in obj and isinstance(obj["index"], (int, str)):
                try:
                    indexes.append(int(obj["index"]))
                except Exception:
                    pass
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(raw)
    # уникальные, отсортированные
    return sorted(set(indexes))


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


def find_project_by_site(site_substring: str) -> int:
    """Находит ID проекта по подстроке в site (например 'addwine')."""
    data = _post("get/projects_2/projects", {"show_headers": 1})
    if not data or not data.get("result"):
        return 0
    projects = data["result"] if isinstance(data["result"], list) else []
    for p in projects:
        if not isinstance(p, dict):
            continue
        for field in ("site", "url", "name"):
            val = str(p.get(field, "") or "")
            if site_substring.lower() in val.lower():
                return int(p.get("id", 0))
    return 0


def test_connection() -> bool:
    """Полная диагностика API — покажет всё что нужно для отладки."""
    import json as _j

    print(f"TOPVISOR_USER_ID задан: {bool(os.environ.get('TOPVISOR_USER_ID'))}")
    print(f"TOPVISOR_API_KEY задан: {bool(os.environ.get('TOPVISOR_API_KEY'))}")
    print(f"TOPVISOR_PROJECT_ID задан: {bool(os.environ.get('TOPVISOR_PROJECT_ID'))}")
    print(f"TOPVISOR_PROJECT_ID = {os.environ.get('TOPVISOR_PROJECT_ID', '')}")
    print()

    # 1. Список проектов с расширенными полями
    print("=" * 60)
    print("Шаг 1: список всех проектов (с site/name)")
    print("=" * 60)
    data = _post("get/projects_2/projects", {
        "show_headers": 1,
        "fields": ["id", "name", "site", "url", "on"],
    })
    if not data:
        print("❌ API недоступно")
        return False

    print(f"Сырой ответ (первые 2000 симв.):")
    print(_j.dumps(data, ensure_ascii=False, indent=2)[:2000])
    projects = data.get("result", []) if isinstance(data.get("result"), list) else []
    print(f"\nПроектов: {len(projects)}")

    # 2. Определяем ID проекта: приоритет — из секрета, иначе автопоиск
    print()
    print("=" * 60)
    print("Шаг 2: определяем ID проекта feed.addwine.ru")
    print("=" * 60)
    env_id = os.environ.get("TOPVISOR_PROJECT_ID", "").strip()
    our_id = 0
    if env_id:
        try:
            our_id = int(env_id)
            print(f"✅ Использую ID из секрета TOPVISOR_PROJECT_ID: {our_id}")
        except Exception:
            print(f"❌ Секрет TOPVISOR_PROJECT_ID некорректен: {env_id}")
    if not our_id:
        our_id = find_project_by_site("addwine")
        if our_id:
            print(f"✅ Найден автопоиском: id={our_id}")
        else:
            print("❌ Проект feed.addwine.ru не найден в аккаунте")

    # 3. Регионы для нашего проекта
    if our_id:
        print()
        print("=" * 60)
        print(f"Шаг 3: регионы проекта {our_id}")
        print("=" * 60)
        regions = _get_project_regions(our_id, debug=True)
        print(f"\n=== Найдено регионов: {len(regions)} → {regions} ===")

        # 4. Позиции
        print()
        print("=" * 60)
        print(f"Шаг 4: позиции ключей проекта {our_id}")
        print("=" * 60)
        os.environ["TOPVISOR_PROJECT_ID"] = str(our_id)
        positions = get_positions(debug=True)
        print(f"\n=== Позиций получено: {len(positions)} ===")
        for p in positions[:30]:
            print(f"  {p['se']:6}  #{p['position']:3}  «{p['keyword'][:55]}»  → {p['url'][:50]}")

        # 5. Кандидаты
        candidates = find_boost_candidates()
        print(f"\n=== Кандидатов на дожим (4-15): {len(candidates)} ===")
        for c in candidates[:10]:
            keys = ", ".join(f"«{k['kw']}» #{k['pos']}" for k in c["keywords"][:3])
            print(f"  {c['url']}")
            print(f"    {keys}")

    return True


if __name__ == "__main__":
    test_connection()
