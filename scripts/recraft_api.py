"""
Обёртка над Recraft API для генерации изображений.
Используем Recraft V3 в стиле realistic_image/natural_light для премиум-фото.
"""
import os
import time
import requests

ENDPOINT = "https://external.api.recraft.ai/v1/images/generations"

# Размер 1820x1024 — близкий к 16:9, оптимально для обложек Дзена
DEFAULT_SIZE = "1820x1024"
DEFAULT_STYLE = "realistic_image/natural_light"
DEFAULT_MODEL = "recraftv3"


def _get_api_key() -> str:
    key = os.environ.get("RECRAFT_API_KEY")
    if not key:
        raise RuntimeError("RECRAFT_API_KEY env var not set")
    return key


def generate_image(prompt: str, retries: int = 2, style: str = DEFAULT_STYLE) -> bytes:
    """
    Генерирует одну картинку через Recraft V3.
    Возвращает bytes JPEG.
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "model": DEFAULT_MODEL,
        "style": style,
        "size": DEFAULT_SIZE,
        "n": 1,
        "response_format": "url",
    }

    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=120)
            if resp.status_code != 200:
                print(f"  Recraft error {resp.status_code}: {resp.text[:300]}")
                resp.raise_for_status()
            data = resp.json()
            image_url = data["data"][0]["url"]

            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            return img_resp.content
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"  Recraft таймаут (попытка {attempt+1}/{retries+1}), ждём {wait}с")
                time.sleep(wait)
            else:
                raise
    raise last_err
