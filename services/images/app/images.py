"""Валидация и обработка загружаемых изображений (задача 1.2, design §3).

Требования (NFR-21, scenario «Негативный: превышение размера» /
«Негативный: недопустимый тип»):
- тип определяется по МАГИЧЕСКИМ БАЙТАМ, не по Content-Type и не по
  расширению (PDF, переименованный в .jpg, обязан отклоняться);
- лимит размера ≤ 10 МБ проверяется ДО записи файла на диск (обе
  проверки — до создания файлов в томе).
"""

import io

from PIL import Image

# NFR-21: JPEG/PNG/GIF/WebP, ≤ 10 МБ.
MAX_SIZE_BYTES = 10 * 1024 * 1024

# Магические подписи форматов (проверка содержимого, не декларации клиента).
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

# WebP: RIFF....WEBP (длина в RIFF-заголовке пропускается).
_WEBP_MAGIC = (b"RIFF", b"WEBP")


def detect_mime(head: bytes) -> str | None:
    """mime по магическим байтам или None (формат не поддержан)."""
    for magic, mime in _MAGIC:
        if head.startswith(magic):
            return mime
    if head[:4] == _WEBP_MAGIC[0] and head[8:12] == _WEBP_MAGIC[1]:
        return "image/webp"
    return None


def validate_upload(data: bytes) -> tuple[str, Image.Image]:
    """Валидирует содержимое загрузки: возвращает (mime, Pillow-изображение).

    Бросает UploadValidationError с кодом ошибки для 422-ответа:
    - "too_large" — размер > MAX_SIZE_BYTES (проверка ДО декодирования и
      ДО любой записи на диск);
    - "bad_type" — магические байты не JPEG/PNG/GIF/WebP;
    - "not_image" — сигнатура узнана, но Pillow не может декодировать
      (битый/обрезанный файл).
    """
    if len(data) > MAX_SIZE_BYTES:
        raise UploadValidationError("too_large")
    mime = detect_mime(data[:16])
    if mime is None:
        raise UploadValidationError("bad_type")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # декодируем сразу: битый файл отклоняем до записи
    except Exception:
        raise UploadValidationError("not_image")
    return mime, img


class UploadValidationError(Exception):
    """Нарушение лимитов загрузки (маппится на 422, design §3)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def make_thumbnail(img: Image.Image, max_side: int = 800) -> Image.Image:
    """Превью: длинная сторона ≤ max_side (design §3, research №5).

    Пропорции сохраняются; апскейл не выполняется (изображение меньше
    800px по длинной стороне возвращается как есть). Для GIF/WebP берется
    первый кадр — превью статичное JPEG.
    """
    im = img
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    if im.mode in ("RGBA", "P", "LA"):
        im = im.convert("RGB")
    elif im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        im = im.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))),
            getattr(Image, "LANCZOS", 1),  # LANCZOS: Pillow≥9.1 (в прод-образе 12.x)
        )
    return im
