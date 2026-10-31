"""Общий текстовый клиент DZEN: OpenAI Responses API, gpt-6.1-terra.

Имя модуля сохранено для существующих импортов. Промпты и контракт
generate_json(system, user, max_tokens, temperature) остаются прежними.
"""
import json
import os
import re

import requests

MODEL = "gpt-6.1-terra"
ENDPOINT = "https://api.openai.com/v1/responses"


def _response_text(response: dict) -> str:
    if response.get("status") != "completed":
        reason = (response.get("incomplete_details") or {}).get("reason", response.get("status"))
        raise RuntimeError(f"OpenAI не завершил текстовый ответ: {reason}")
    parts = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "refusal":
                raise RuntimeError("OpenAI отказался генерировать текст")
            if block.get("type") == "output_text":
                parts.append(block.get("text", ""))
    raw = "".join(parts).strip()
    if not raw:
        raise RuntimeError("OpenAI вернул пустой текстовый ответ")
    return raw


def generate_json(system: str, user: str, max_tokens: int = 8000, temperature: float = 0.7) -> dict:
    """Вернуть JSON-объект, сохранив параметры и промпты вызывающего сценария."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    payload = {
        "model": MODEL,
        "instructions": system,
        "input": [{"role": "user", "content": user}],
        "max_output_tokens": max_tokens,
        "reasoning": {"effort": "none"},
        "temperature": temperature,
        "text": {"format": {"type": "json_object"}},
        "store": False,
    }
    # Не повторяем POST автоматически: при таймауте его результат неизвестен.
    response = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "DZEN-Text/1.0"},
        json=payload,
        timeout=(10, 180),
    )
    if response.status_code != 200:
        try:
            error = response.json().get("error", {})
            detail = str(error.get("message", error.get("code", "request failed")))
        except (ValueError, AttributeError):
            detail = "non-JSON error response"
        detail = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[redacted]", detail.replace(api_key, "[redacted]"))
        raise RuntimeError(f"OpenAI HTTP {response.status_code}: {detail[:400]}")
    data = response.json()
    raw = _response_text(data)
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI вернул невалидный JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("OpenAI вернул JSON без объекта верхнего уровня")
    usage = data.get("usage") or {}
    print(f"  [text_api] OpenAI {MODEL}: completed; response_id={data.get('id')}; output_tokens={usage.get('output_tokens')}")
    return result
