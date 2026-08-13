"""
IndexNow — мгновенный пинг Яндекса о новых/обновлённых страницах.
Формат: https://yandex.com/support/webmaster/indexnow/
- Ключ хранится в файле <key>.txt в корне сайта
- POST на api.indexnow.org/indexnow с host + key + urlList

Использовать при публикации новой статьи и при массовом апдейте.
"""
import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://feed.addwine.ru"

# Ключ IndexNow — хеш из букв/цифр. Кладётся в файл <key>.txt в корне сайта.
INDEXNOW_KEY = "a7f2c5d9e1b3f4a6c8e2b9d5f1a3c7e0"
INDEXNOW_KEY_FILE = REPO_ROOT / f"{INDEXNOW_KEY}.txt"


def ensure_key_file():
    """Кладёт файл с ключом в корень репо (для верификации Яндекса)."""
    if not INDEXNOW_KEY_FILE.exists():
        INDEXNOW_KEY_FILE.write_text(INDEXNOW_KEY, encoding="utf-8")


def ping_urls(urls: list) -> bool:
    """Отправляет пинг Яндексу через IndexNow."""
    ensure_key_file()
    if not urls:
        return False

    payload = {
        "host": SITE_URL.replace("https://", "").replace("http://", ""),
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:10000],  # лимит API
    }

    endpoints = [
        "https://yandex.com/indexnow",
        "https://api.indexnow.org/indexnow",
    ]
    for ep in endpoints:
        try:
            r = requests.post(ep, json=payload, timeout=15,
                              headers={"Content-Type": "application/json; charset=utf-8"})
            if r.status_code in (200, 202):
                print(f"  [indexnow] ✅ {ep} → HTTP {r.status_code} ({len(urls)} URLs)")
                return True
            else:
                print(f"  [indexnow] ⚠️  {ep} → HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  [indexnow] {ep} → {type(e).__name__}: {e}")
    return False


def ping_single(url: str) -> bool:
    """Быстрый пинг одного URL через GET."""
    ensure_key_file()
    try:
        r = requests.get(
            f"https://yandex.com/indexnow?url={url}&key={INDEXNOW_KEY}",
            timeout=10,
        )
        ok = r.status_code in (200, 202)
        print(f"  [indexnow] {url} → HTTP {r.status_code} {'✅' if ok else '⚠️'}")
        return ok
    except Exception as e:
        print(f"  [indexnow] {url} → {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    # CLI: python indexnow_ping.py url1 url2 ...
    if len(sys.argv) > 1:
        ping_urls(sys.argv[1:])
    else:
        # По умолчанию — пингуем главную и sitemap
        ping_urls([
            f"{SITE_URL}/",
            f"{SITE_URL}/sitemap.xml",
        ])
