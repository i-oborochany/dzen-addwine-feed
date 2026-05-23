"""
Тестовый скрипт для проверки GigaChat API.
Запускается в GitHub Actions, читает GIGACHAT_AUTH_KEY из переменной окружения.
"""
import os
import sys
import uuid
import requests

AUTH_KEY = os.environ.get("GIGACHAT_AUTH_KEY")
if not AUTH_KEY:
    print("ERROR: GIGACHAT_AUTH_KEY not set")
    sys.exit(1)

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


def get_access_token() -> str:
    headers = {
        "Authorization": f"Basic {AUTH_KEY}",
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"scope": "GIGACHAT_API_PERS"}
    resp = requests.post(OAUTH_URL, headers=headers, data=data, verify=False, timeout=30)
    print(f"OAuth status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"OAuth response: {resp.text}")
        resp.raise_for_status()
    return resp.json()["access_token"]


def test_chat(token: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "user", "content": "Скажи одно слово на тест: вино"}
        ],
        "temperature": 0.1,
        "max_tokens": 20,
    }
    resp = requests.post(CHAT_URL, headers=headers, json=payload, verify=False, timeout=30)
    print(f"Chat status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Chat response: {resp.text}")
        resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"]
    print(f"GigaChat answer: {answer}")


if __name__ == "__main__":
    # отключаем шумные warnings про verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("=== GigaChat API test ===")
    token = get_access_token()
    print("OAuth: OK, access_token received")
    test_chat(token)
    print("=== SUCCESS ===")
