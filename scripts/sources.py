"""
Сбор заголовков-затравок из RSS и HTML-источников.
Возвращает плоский список строк (только заголовки).
Используется только в TREND-режиме как подсказка Claude об актуальных темах.
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
TIMEOUT = 15


def _parse_date(value):
    if not value:
        return None
    try:
        if isinstance(value, time.struct_time):
            return datetime(*value[:6], tzinfo=timezone.utc)
        return date_parser.parse(str(value))
    except Exception:
        return None


def _fetch_rss(source: dict, cutoff) -> list:
    try:
        feed = feedparser.parse(source["url"], request_headers=HEADERS)
    except Exception:
        return []
    titles = []
    for entry in feed.entries[:20]:
        published = _parse_date(entry.get("published") or entry.get("updated"))
        if cutoff and published and published < cutoff:
            continue
        title = (entry.get("title") or "").strip()
        if title and 20 < len(title) < 200:
            titles.append(title)
    return titles


def _fetch_html(source: dict) -> list:
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    titles = []
    seen = set()
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if not title or len(title) < 20 or len(title) > 200:
            continue
        if title in seen:
            continue
        seen.add(title)
        titles.append(title)
    return titles[:25]


def collect_seeds(config: dict) -> list:
    """Собирает заголовки-затравки со всех источников. Фильтрует по винным ключевым словам."""
    fresh_days = config.get("freshness_window_days", 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=fresh_days)
    keywords = [k.lower() for k in config.get("wine_keywords", [])]
    exclude = ["addwine"]

    all_titles = []
    for src_list in (config.get("sources_ru", []), config.get("sources_en", [])):
        for source in src_list:
            print(f"  -> {source['name']} ({source['type']})")
            if source["type"] == "rss":
                titles = _fetch_rss(source, cutoff)
            elif source["type"] == "html":
                titles = _fetch_html(source)
            else:
                continue

            # фильтр: оставляем только винные темы, выкидываем addwine
            filtered = []
            for t in titles:
                t_low = t.lower()
                if any(x in t_low for x in exclude):
                    continue
                if keywords and not any(k in t_low for k in keywords):
                    continue
                filtered.append(t)
            print(f"     {len(titles)} → {len(filtered)} после фильтра")
            all_titles.extend(filtered)

    # дедупликация
    seen = set()
    deduped = []
    for t in all_titles:
        key = t.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped
