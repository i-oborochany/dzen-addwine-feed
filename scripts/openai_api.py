"""
Обёртка над OpenAI Images API для gpt-image-1.
Возвращает bytes JPEG.
"""
import base64
import os
import time
import requests

ENDPOINT = "https://api.openai.com/v1/images/generations"
MODEL = "gpt-image-1"
SIZE = "1536x1024"   # 16:9 landscape, оптимально для обложек Дзена
QUALITY = "medium"   # low | medium | high


def _get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    return key


def generate_image(prompt: str, retries: int = 2, quality: str = QUALITY) -> bytes:
    """
    Генерирует одну картинку через gpt-image-1. Возвращает bytes (JPEG).
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": SIZE,
        "quality": quality,
        "output_format": "jpeg",
    }

    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=180)
            if resp.status_code != 200:
                print(f"  OpenAI error {resp.status_code}: {resp.text[:400]}")
                resp.raise_for_status()
            data = resp.json()
            b64 = data["data"][0].get("b64_json")
            if b64:
                return base64.b64decode(b64)
            # fallback: URL (на всякий случай)
            url = data["data"][0].get("url")
            if url:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                return r.content
            raise RuntimeError(f"OpenAI вернул пустой data: {data}")
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"  OpenAI таймаут ({attempt+1}/{retries+1}), ждём {wait}с")
                time.sleep(wait)
            else:
                raise
    raise last_err
