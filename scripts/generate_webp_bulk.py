"""
Одноразовый скрипт: конвертирует все существующие cover-*.jpg в cover-*.webp.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images"


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Pillow не установлен — pip install Pillow")
        return 1

    made = 0
    for jpg in IMAGES_DIR.rglob("cover-*.jpg"):
        webp = jpg.with_suffix(".webp")
        if webp.exists():
            continue
        try:
            im = Image.open(jpg).convert("RGB")
            im.save(webp, "WEBP", quality=82, method=6)
            made += 1
        except Exception as e:
            print(f"[!] {jpg.name}: {e}")

    print(f"✅ Создано WebP: {made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
