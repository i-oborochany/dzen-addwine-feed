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
        # Печатаем структуру первого ключа отдельно чтобы увидеть positionsData
        raw_dbg = data.get("result")
        if isinstance(raw_dbg, dict):
            kws_dbg = raw_dbg.get("keywords") or []
            if kws_dbg and isinstance(kws_dbg[0], dict):
                print("[debug] Первый keyword целиком:")
                print(_j.dumps(kws_dbg[0], ensure_ascii=False, indent=2))
        print("[debug] Сырой ответ (первые 5000 симв.):")
        print(_j.dumps(data, ensure_ascii=False, indent=2)[:5000])

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
            headers = {}
        elif isinstance(raw, dict):
            keywords = raw.get("keywords") or raw.get("data") or []
            headers = raw.get("headers") or {}
        else:
            keywords = []
            headers = {}

        # Строим маппинг region_index → se_name из headers
        # headers.projects[N].searchers[M].regions[K].index + searchers[M].key
        region_to_se = {}
        for proj in headers.get("projects", []) or []:
            for searcher in proj.get("searchers", []) or []:
                se_key = searcher.get("key", 0)
                se_name = "yandex" if se_key == 0 else "google"
                for reg in searcher.get("regions", []) or []:
                    idx = reg.get("index")
                    try:
                        region_to_se[str(idx)] = se_name
                    except Exception:
                        pass
        if debug and region_to_se:
            print(f"[debug] Маппинг регионов: {region_to_se}")

        for kw in keywords:
            if not isinstance(kw, dict):
                continue
            name = kw.get("name", "")
            positions_data = kw.get("positionsData") or kw.get("positions_data") or {}
            if not isinstance(positions_data, dict):
                continue
            # Formatteр ключа в Topvisor: date:searcher_key:region_index:region_key:lang:device
            # Значение может быть либо сразу {position, relevant_url} (одноуровневая),
            # либо dict дат {date: {position, ...}} (двухуровневая).
            for full_key, val in positions_data.items():
                if not val or not isinstance(val, dict):
                    continue
                # Формат ключа: date:project_id:region_index
                parts = full_key.split(":")
                region_index = parts[-1] if parts else ""
                # Определяем se по маппингу из headers, fallback по index
                se = region_to_se.get(str(region_index))
                if not se:
                    # Fallback: 5 = yandex, 7 = google (типичные индексы РФ)
                    se = "yandex" if str(region_index) in ("5", "0") else "google"

                # Достаём position/url — либо напрямую, либо из вложенного dict дат
                position = val.get("position")
                url = val.get("url", "") or val.get("relevant_url", "")
                if position is None and all(isinstance(v, dict) for v in val.values()):
                    # это двухуровневая — берём последнюю дату
                    latest_key = sorted(val.keys())[-1] if val else None
                    if latest_key:
                        inner = val.get(latest_key, {})
                        if isinstance(inner, dict):
                            position = inner.get("position")
                            url = inner.get("url", "") or inner.get("relevant_url", "") or url

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
        # Пробуем сразу 30 дней истории — вдруг съём был давно
        positions = get_positions(days_back=30, debug=True)
        print(f"\n=== Позиций получено (реальных, не '--'): {len(positions)} ===")
        # Группируем по se
        by_se = {"yandex": 0, "google": 0}
        for p in positions:
            by_se[p["se"]] = by_se.get(p["se"], 0) + 1
        print(f"  Yandex: {by_se.get('yandex', 0)}, Google: {by_se.get('google', 0)}")
        for p in sorted(positions, key=lambda x: x["position"])[:30]:
            print(f"  {p['se']:6}  #{p['position']:3}  «{p['keyword'][:55]}»  → {p['url'][:60]}")

        # 5. Кандидаты (используем те же 30 дней)
        candidates = {}
        for p in positions:
            if 4 <= p["position"] <= 15 and p["url"]:
                key = p["url"]
                if key not in candidates:
                    candidates[key] = {"url": p["url"], "keywords": []}
                candidates[key]["keywords"].append({"kw": p["keyword"], "pos": p["position"], "se": p["se"]})
        candidates = list(candidates.values())
        print(f"\n=== Кандидатов на дожим (позиции 4-15): {len(candidates)} ===")
        for c in candidates[:10]:
            keys = ", ".join(f"«{k['kw']}» #{k['pos']}" for k in c["keywords"][:3])
            print(f"  {c['url']}")
            print(f"    {keys}")

    return True


if __name__ == "__main__":
    test_connection()
