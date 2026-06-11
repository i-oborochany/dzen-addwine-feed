"""
Парсер 4-х источников винных новостей для еженедельного дайджеста:
- provina.ru/novosti
- swn.ru (Simple Wine News)
- vino.ru/novosti
- simplewine.ru/blog
"""
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "ru,en;q=0.8"}
TIMEOUT = 20


def _get(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""


def _parse_date_safe(s: str):
    if not s:
        return None
    try:
        return date_parser.parse(s, dayfirst=True)
    except Exception:
        return None


def _abs_url(href: str, base: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def _fetch_article(url: str) -> dict:
    """
    Скачивает страницу новости и возвращает {title, lead, image_url, pub_date}.
    """
    html = _get(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")

    # Title — h1 или title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        t = soup.find("title")
        if t:
            title = t.get_text(strip=True)

    # Lead — первый существенный <p>
    lead = ""
    article = soup.find("article") or soup.find("main") or soup.body
    if article:
        for p in article.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 80 and len(text) < 800:
                lead = text
                break
    if not lead:
        # fallback meta description
        m = soup.find("meta", attrs={"name": "description"})
        if m:
            lead = (m.get("content") or "").strip()

    # Image — первое крупное изображение
    image_url = ""
    # OpenGraph image
    og = soup.find("meta", property="og:image")
    if og:
        image_url = (og.get("content") or "").strip()
    if not image_url and article:
        for img in article.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if not src or "logo" in src.lower() or "icon" in src.lower():
                continue
            image_url = src
            break

    # PubDate — meta или time
    pub_date = None
    for sel in [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "publishdate"}),
        ("meta", {"itemprop": "datePublished"}),
        ("time", {"datetime": True}),
    ]:
        el = soup.find(sel[0], attrs=sel[1])
        if el:
            val = el.get("content") or el.get("datetime") or el.get_text(strip=True)
            pub_date = _parse_date_safe(val)
            if pub_date:
                break

    return {
        "title": title,
        "lead": lead[:1000],
        "image_url": _abs_url(image_url, url) if image_url else "",
        "pub_date": pub_date,
    }


def fetch_provina(limit: int = 20, days: int = 7) -> list:
    """Парсит provina.ru/novosti — берёт свежие ссылки."""
    html = _get("https://www.provina.ru/novosti")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    # ссылки вида /novosti/NNNN-...
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/novosti/\d+-", href):
            links.add("https://www.provina.ru" + href)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    for url in list(links)[:limit]:
        art = _fetch_article(url)
        if not art or not art["title"]:
            continue
        # фильтр свежести (если дата есть)
        if art["pub_date"]:
            dt = art["pub_date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
        art["source"] = "provina.ru"
        art["source_url"] = url
        results.append(art)
        time.sleep(0.5)
    return results


def fetch_swn(limit: int = 15, days: int = 7) -> list:
    """Парсит swn.ru (Simple Wine News) — главная страница."""
    html = _get("https://swn.ru/")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # пути вида /articles/<slug> или /news/<slug>
        if re.match(r"^/(articles|news)/[^/]+/?$", href):
            links.add(urljoin("https://swn.ru", href))
        elif href.startswith("https://swn.ru/") and re.search(r"/(articles|news)/", href):
            links.add(href)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    for url in list(links)[:limit]:
        art = _fetch_article(url)
        if not art or not art["title"] or len(art["title"]) < 15:
            continue
        if art["pub_date"]:
            dt = art["pub_date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
        art["source"] = "swn.ru"
        art["source_url"] = url
        results.append(art)
        time.sleep(0.5)
    return results


def fetch_vino_ru(limit: int = 15, days: int = 7) -> list:
    """Парсит vino.ru/novosti/."""
    html = _get("https://vino.ru/novosti/")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/novosti/[^/]+/?$", href) and href != "/novosti/":
            links.add("https://vino.ru" + href)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    for url in list(links)[:limit]:
        art = _fetch_article(url)
        if not art or not art["title"] or len(art["title"]) < 15:
            continue
        if art["pub_date"]:
            dt = art["pub_date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
        art["source"] = "vino.ru"
        art["source_url"] = url
        results.append(art)
        time.sleep(0.5)
    return results


def fetch_simplewine_blog(limit: int = 15, days: int = 7) -> list:
    """Парсит simplewine.ru/blog/."""
    html = _get("https://simplewine.ru/blog/")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.match(r"^/blog/[^/]+/?$", href) and href != "/blog/":
            links.add("https://simplewine.ru" + href)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    for url in list(links)[:limit]:
        art = _fetch_article(url)
        if not art or not art["title"] or len(art["title"]) < 15:
            continue
        if art["pub_date"]:
            dt = art["pub_date"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
        art["source"] = "simplewine.ru"
        art["source_url"] = url
        results.append(art)
        time.sleep(0.5)
    return results


def collect_all(days: int = 7, date_from=None, date_to=None) -> list:
    """
    Собирает свежие статьи со всех 4 источников.
    Если переданы date_from/date_to (datetime с tz), фильтруем строго по окну.
    Иначе — берём последние `days` дней до now.
    """
    all_items = []
    for fetcher, name in [
        (fetch_provina, "provina.ru"),
        (fetch_swn, "swn.ru"),
        (fetch_vino_ru, "vino.ru"),
        (fetch_simplewine_blog, "simplewine.ru"),
    ]:
        try:
            print(f"  Парсим {name} ...")
            # Берём с запасом, потом отфильтруем по окну
            items = fetcher(limit=20, days=max(days, 14))
            # Если задано явное окно — фильтруем строго по нему
            if date_from and date_to:
                filtered = []
                for art in items:
                    pd = art.get("pub_date")
                    if pd is None:
                        continue
                    if pd.tzinfo is None:
                        pd = pd.replace(tzinfo=timezone.utc)
                    if date_from <= pd <= date_to:
                        filtered.append(art)
                items = filtered
            print(f"     найдено {len(items)} статей в окне")
            all_items.extend(items)
        except Exception as e:
            print(f"     [!] {e}")
    return all_items


def download_image_to(url: str, save_path) -> bool:
    """Качает картинку и сохраняет в save_path."""
    if not url:
        return False
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return False
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(r.content)
        return True
    except Exception:
        return False
