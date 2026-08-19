"""
Пингует IndexNow ПОСЛЕ деплоя GitHub Pages.

Проблема которую решает: раньше пинг летел из скрипта публикации — до git push
и до сборки Pages. Яндекс приходил мгновенно и получал 404 (страницы ещё нет).

Логика:
1. Берёт последние N статей из posts_index.json
2. Ждёт пока самая свежая начнёт отдавать HTTP 200 (Pages собирается 1-3 мин)
3. Пингует IndexNow все N URL

Запускается отдельным шагом воркфлоу после commit & push.
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indexnow_ping

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_INDEX = REPO_ROOT / "posts" / "posts_index.json"
SITE = "https://feed.addwine.ru"

RECENT_N = 3          # сколько последних URL пинговать
MAX_WAIT_SEC = 360    # максимум ждём деплой 6 минут
POLL_SEC = 20


def main():
    if not POSTS_INDEX.exists():
        print("[ping_recent] posts_index.json не найден — нечего пинговать")
        return 0

    posts = json.loads(POSTS_INDEX.read_text(encoding="utf-8"))
    posts = sorted(posts, key=lambda p: p.get("published_at", ""), reverse=True)[:RECENT_N]
    if not posts:
        print("[ping_recent] нет статей")
        return 0

    urls = [f"{SITE}/posts/{p['slug']}/" for p in posts if p.get("slug")]
    freshest = urls[0]

    # Ждём пока самая свежая страница задеплоится
    print(f"[ping_recent] жду деплой: {freshest}")
    deadline = time.time() + MAX_WAIT_SEC
    ok = False
    while time.time() < deadline:
        try:
            r = requests.get(freshest, timeout=15, headers={"User-Agent": "AddWineBot/1.0"})
            if r.status_code == 200:
                ok = True
                break
            print(f"  ...ещё {r.status_code}, ждём {POLL_SEC}с")
        except Exception as e:
            print(f"  ...{type(e).__name__}, ждём {POLL_SEC}с")
        time.sleep(POLL_SEC)

    if not ok:
        print(f"[ping_recent] ⚠️  страница так и не отдала 200 за {MAX_WAIT_SEC}с — пингую всё равно")
    else:
        print(f"[ping_recent] ✅ страница живая, пингую IndexNow: {len(urls)} URL")

    indexnow_ping.ping_urls(urls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
