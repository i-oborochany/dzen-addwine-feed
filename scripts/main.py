"""
Точка входа. Запускается из GitHub Actions ежедневно.
"""
import os
import sys
import traceback
from pathlib import Path

import yaml

# импорты из того же каталога scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources
import picker
import writer
import gigachat
import publisher


def main() -> int:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("[1/6] Собираем кандидатов из источников")
    candidates = sources.collect_all(config)
    print(f"  всего кандидатов: {len(candidates)}")
    if not candidates:
        print("  пусто, выходим")
        return 1

    print("\n[2/6] Выбираем тему через GigaChat")
    published_urls = publisher.load_published()
    print(f"  ранее опубликовано: {len(published_urls)} статей")
    topic = picker.pick_topic(candidates, config, published_urls)
    print(f"  -> {topic['title']}")
    print(f"  источник: {topic['source']}, url: {topic['url']}")
    print(f"  причина: {topic.get('pick_reason', '')[:200]}")

    print("\n[3/6] Скачиваем оригинал и рерайтим")
    full_text = writer.fetch_article_text(topic["url"])
    print(f"  оригинал: {len(full_text)} символов")
    article = writer.rewrite_article(topic, full_text, config)
    print(f"  новый заголовок: {article['title']}")
    print(f"  длина html: {len(article['html'])} символов")

    print("\n[4/6] Генерим 4 обложки через Kandinsky")
    images = []
    for i, prompt in enumerate(article["image_prompts"], 1):
        print(f"  обложка {i}/4 ...")
        try:
            img = gigachat.generate_image(prompt)
            images.append(img)
            print(f"     ok, {len(img)} байт")
        except Exception as e:
            print(f"     [!] ошибка: {e}")
            # если хотя бы одна картинка есть — переиспользуем; иначе падаем
            if images:
                images.append(images[0])
            else:
                raise

    print("\n[5/6] Сохраняем картинки в репозитории")
    slug = publisher.slugify(article["title"])
    image_urls = publisher.save_images(images, slug)
    for u in image_urls:
        print(f"  -> {u}")

    print("\n[6/6] Добавляем в feed.xml и помечаем опубликованным")
    publisher.add_to_feed(article, image_urls, topic["url"], config)
    publisher.mark_published(topic["url"], article["title"])
    print("  feed.xml обновлён")
    print("=" * 60)
    print("SUCCESS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)
