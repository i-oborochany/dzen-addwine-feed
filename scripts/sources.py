"""
Сбор кандидатов-статей из всех источников (RSS и HTML).
Возвращает плоский список dict-ов: {title, url, published, source, lang}.
"""
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.8"}
TIMEOUT = 20


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, time.struct_time):
            return datetime(*value[:6], tzinfo=timezone.utc)
        return date_parser.parse(str(value))
    except Exception:
        return None


def fetch_rss(source: dict, lang: str) -> list:
    """Парсит RSS-ленту."""
    try:
        feed = feedparser.parse(source["url"], request_headers=HEADERS)
    except Exception as e:
        print(f"  [!] {source['name']}: {e}")
        return []

    items = []
    for entry in feed.entries[:30]:
        published = _parse_date(entry.get("published") or entry.get("updated"))
        items.append({
            "title": (entry.get("title") or "").strip(),
            "url": entry.get("link") or "",
            "published": published,
            "summary": (entry.get("summary") or "")[:500],
            "source": source["name"],
            "lang": lang,
        })
    return items


def fetch_html(source: dict, lang: str) -> list:
    """
    Грубый HTML-парсер: вытаскивает все ссылки на статьи с главной/индексной страницы.
    Эвристика: ссылка ведёт на тот же домен, имеет осмысленный текст,
    содержит вин-тематику в URL или тексте.
    """
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  [!] {source['name']}: HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"  [!] {source['name']}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(strip=True)
        if not title or len(title) < 20 or len(title) > 200:
            continue
        full_url = urljoin(source["url"], href)
        if full_url in seen_urls:
            continue
        # фильтр по домену
        if not re.match(r"^https?://", full_url):
            continue
        seen_urls.add(full_url)

        items.append({
            "title": title,
            "url": full_url,
            "published": None,  # HTML обычно не отдаёт дату на индексе
            "summary": "",
            "source": source["name"],
            "lang": lang,
        })

    return items[:50]


def is_wine_related(item: dict, keywords: list) -> bool:
    haystack = (item["title"] + " " + item.get("summary", "") + " " + item["url"]).lower()
    return any(k.lower() in haystack for k in keywords)


def is_excluded(item: dict, exclude_keywords: list) -> bool:
    if not exclude_keywords:
        return False
    haystack = (item["title"] + " " + item["url"]).lower()
    return any(k.lower() in haystack for k in exclude_keywords)


def collect_all(config: dict) -> list:
    """Собирает все кандидаты из всех источников."""
    all_items = []
    keywords = config["wine_keywords"]
    fresh_days = config["freshness_window_days"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=fresh_days)

    for src_list, lang in [
        (config.get("sources_ru", []), "ru"),
        (config.get("sources_en", []), "en"),
    ]:
        for source in src_list:
            print(f"  -> {source['name']} ({source['type']})")
            if source["type"] == "rss":
                items = fetch_rss(source, lang)
            elif source["type"] == "html":
                items = fetch_html(source, lang)
            else:
                continue

            # фильтры
            kept = []
            for it in items:
                if not is_wine_related(it, keywords):
                    continue
                if is_excluded(it, source.get("exclude_keywords", [])):
                    continue
                # фильтр по свежести (только если есть дата)
                if it["published"] and it["published"] < cutoff:
                    continue
                kept.append(it)

            print(f"     найдено {len(items)}, оставлено {len(kept)}")
            all_items.extend(kept)

    return all_items
