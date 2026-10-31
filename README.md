# dzen-addwine-feed
статьи для Дзен

## Генерация обложек

С 31.10.2026 общий клиент `scripts/openai_api.py` использует `gpt-image-2.5-flare` вместо отключённой 23.10.2026 модели `gpt-image-1`. Формат JPEG, размер 1536×1024 и качество `medium` сохранены. Все сценарии, вызывающие `openai_api.generate_image`, используют общую настройку модели.

[Описание модели](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare) · [Отключение старой модели](https://developers.openai.com/api/docs/deprecations)

Для разовой генерации вне расписания: Actions → Daily Wine Post → Run workflow → включить `force`. Обычное расписание не меняется. Этот ручной запуск генерирует статью и обложку и публикует результат в репозитории; `force` также пропускает проверку уже состоявшейся публикации за день.
