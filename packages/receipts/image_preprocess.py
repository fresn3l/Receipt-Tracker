from pathlib import Path

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:  # pragma: no cover
    Image = None


def preprocess_receipt_image(image_path: Path) -> None:
    if Image is None:
        return

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img.save(image_path, quality=92)
