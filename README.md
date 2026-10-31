# dzen-addwine-feed
статьи для Дзен

## Генерация обложек

С 31.10.2026 общий клиент `scripts/openai_api.py` использует `gpt-image-2.5-flare` вместо отключённой 23.10.2026 модели `gpt-image-1`. Формат JPEG, размер 1536×1024 и качество `medium` сохранены. Все сценарии, вызывающие `openai_api.generate_image`, используют общую настройку модели.

[Описание модели](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare) · [Отключение старой модели](https://developers.openai.com/api/docs/deprecations)

Для разовой генерации вне расписания: Actions → Daily Wine Post → Run workflow → включить `force`. Обычное расписание не меняется. Этот ручной запуск генерирует статью и обложку и публикует результат в репозитории; `force` также пропускает проверку уже состоявшейся публикации за день.

## Генерация текста

С 31.10.2026 все сценарии через общий `scripts/claude_api.py` используют OpenAI Responses API и `gpt-6.1-terra`: статьи, SEO-фразы, перелинковка и дайджесты. Историческое имя модуля сохранено для совместимости импортов; обращения к Anthropic больше не выполняются. Нужен `OPENAI_API_KEY` из GitHub Secrets, в том числе в weekly digest.

Промпты, параметры температуры и лимиты ответа вызывающих сценариев сохранены. Используются JSON mode, `reasoning.effort=none` и `store=false`. Незавершённые ответы, отказы и невалидный JSON останавливают обработку; автоматических повторов неопределённого POST нет. Bootstrap проверяет текущий клиент, а не восстанавливает прежний Anthropic-код.

[Модель для текста](https://developers.openai.com/api/docs/models/gpt-6.1-terra) · [Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)

Проверки клиента: `python -m unittest discover -s tests -v`.

Системный промпт передаётся отдельным сообщением `system` в `input`, без изменения текста: это сохраняет исходные роли и обеспечивает проверку JSON mode также для коротких запросов подбора фраз и перелинковки.
