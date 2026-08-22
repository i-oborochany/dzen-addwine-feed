"""
Тонкая обёртка над Anthropic API для генерации текста статей.
Используем claude-sonnet-4-6.
"""
import json
import os
import re

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY env var not set")
        _client = Anthropic(api_key=api_key)
    return _client


def generate_json(system: str, user: str, max_tokens: int = 8000, temperature: float = 0.7) -> dict:
    """
    Дёргает Claude, ожидает JSON в ответе. Парсит и возвращает dict.
    Совместимо со старым и новым SDK: новые версии anthropic убрали
    параметр temperature из messages.create() — при TypeError повторяем без него.
    """
    client = _get_client()
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    try:
        response = client.messages.create(temperature=temperature, **kwargs)
    except TypeError:
        # новый SDK без temperature
        response = client.messages.create(**kwargs)
    raw = response.content[0].text.strip()

    # снимаем markdown-обрамление если есть
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # пытаемся выдернуть JSON-объект из текста
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise RuntimeError(f"Не JSON в ответе Claude: {raw[:500]}")
        return json.loads(m.group(0))
