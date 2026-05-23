"""
Тонкая обёртка над GigaChat API.
- OAuth: получает access_token по Authorization key.
- chat(): обычный chat completions.
- generate_image(): просит модель сгенерировать картинку через function_call,
  возвращает bytes изображения.
"""
import os
import re
import uuid
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_BASE = "https://gigachat.devices.sberbank.ru/api/v1"

_token_cache = {"value": None, "expires_at": 0}


def _get_token() -> str:
    """Кэшируем токен на 25 минут (живёт 30)."""
    if _token_cache["value"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["value"]

    auth_key = os.environ.get("GIGACHAT_AUTH_KEY")
    if not auth_key:
        raise RuntimeError("GIGACHAT_AUTH_KEY env var not set")

    headers = {
        "Authorization": f"Basic {auth_key}",
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(
        OAUTH_URL,
        headers=headers,
        data={"scope": "GIGACHAT_API_PERS"},
        verify=False,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + 25 * 60
    return data["access_token"]


def chat(
    messages: list,
    model: str = "GigaChat",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    function_call: str | dict | None = None,
) -> dict:
    """Один вызов chat completions. Возвращает весь JSON-ответ."""
    token = _get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if function_call is not None:
        payload["function_call"] = function_call

    resp = requests.post(
        f"{API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        verify=False,
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"Chat error {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def chat_text(messages: list, **kwargs) -> str:
    """Удобный shortcut: вернёт только текстовое содержимое ответа."""
    response = chat(messages, **kwargs)
    return response["choices"][0]["message"]["content"]


def _download_image(file_id: str) -> bytes:
    """Скачивает картинку по UUID из ответа GigaChat."""
    token = _get_token()
    resp = requests.get(
        f"{API_BASE}/files/{file_id}/content",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/jpg"},
        verify=False,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def generate_image(prompt: str) -> bytes:
    """
    Генерирует одну картинку. Возвращает bytes (JPEG).
    Использует function_call с встроенной функцией text2image.
    """
    response = chat(
        messages=[
            {"role": "system", "content": "Ты — генератор изображений."},
            {"role": "user", "content": prompt},
        ],
        model="GigaChat",
        function_call="auto",
        max_tokens=1500,
    )
    content = response["choices"][0]["message"].get("content", "")

    # GigaChat возвращает картинку как HTML-тег: <img src="UUID" fuse="true"/>
    match = re.search(r'<img\s+src="([a-f0-9-]+)"', content)
    if not match:
        raise RuntimeError(f"No image UUID in response: {content[:200]}")

    file_id = match.group(1)
    return _download_image(file_id)
