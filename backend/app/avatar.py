"""Загрузка аватара: POST /api/profile/avatar (tasks.md 2.3 Релиза 4; FR-42,
NFR-10, ОГР-16, Д-8, ОВ-22; design.md пакета §2, sdd r10 §3.1a-кватер).

Контракт (design §2 / sdd §3.1a-кватер):
- multipart/form-data, поле ``file``;
- 200 {"ok": true, "avatar_url": "..."}; 422 {"error": "invalid file type"}
  — не png/jpg (в т.ч. битый файл с png-расширением — ошибка декодирования);
  422 {"error": "file too large"} — >2 МБ (NFR-10/ОВ-22); 401 — без сессии
  (middleware, эндпоинт вне exempt-списка, NFR-7).

Безопасность (NFR-7): имя файла генерирует СЕРВЕР (<user_id>.png) — путь не
из пользовательского ввода; содержимое валидируется как изображение
(Pillow-декодирование), а не по расширению; размер проверяется ДО декодирования
(чтение не более LIMIT+1 байт — защита памяти VPS, NFR-10).

Сжатие (Д-8/Д-13, r5 задача 2.1): безусловное приведение декодированного
изображения к 256×256 LANCZOS (img.resize((256, 256), LANCZOS)) НЕЗАВИСИМО
от входной геометрии (ОВ-СА-2: сервер не доверяет клиенту — пришедший
не-квадрат все равно нормализуется к 256×256); формат содержимого приводится
к png независимо от исходника (design §2).

Хранение (blocker C-1 ревью review-001, ОГР-16): каталог AVATARS_DIR
(конфигурация через окружение, дефолт /var/lib/ekotov-wiki/avatars/) — вне
rsync-корня прода; создается идемпотентно при первом сохранении (mkdir -p),
владелец — пользователь процесса (wiki). Запись атомарная (tmp + os.replace) —
повторная загрузка перезаписывает файл целиком. При сохранении обновляются
users.avatar_path и users.avatar_updated_at (minor B-3 ревью) — версия для
кеш-бастинга ``?v=<avatar_updated_at>`` (ОГР-16).

DELETE аватара спекой не предусмотрен (дельта auth, Requirement
«Загрузка аватара»: только загрузка и fallback-кружок FR-33) — не реализуется.
"""

import io
import os
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile
from PIL import Image
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import SESSION_COOKIE_NAME
from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/api/profile")

# Лимит исходника (NFR-10, ОВ-22): 2 МБ = 2 * 1024 * 1024 байт.
MAX_AVATAR_BYTES = 2 * 1024 * 1024

# Допустимые типы (FR-42): только png/jpg — по декларации запроса И по
# фактическому формату декодированного содержимого (Pillow).
_ALLOWED_DECLARED_EXT = {".png", ".jpg", ".jpeg"}
_ALLOWED_DECLARED_CT = {"image/png", "image/jpeg"}
_ALLOWED_PILLOW_FORMATS = {"PNG", "JPEG"}

# Целевой размер после сжатия (Д-8): квадрат 256×256.
AVATAR_SIZE = 256

INVALID_FILE_TYPE_BODY = {"error": "invalid file type"}
FILE_TOO_LARGE_BODY = {"error": "file too large"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _declared_type_allowed(upload: UploadFile) -> bool:
    """Декларированный тип (content-type или расширение имени) — png/jpg?"""
    content_type = (upload.content_type or "").lower()
    if content_type in _ALLOWED_DECLARED_CT:
        return True
    filename = upload.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    return ext in _ALLOWED_DECLARED_EXT


def _normalize_256(img: Image.Image) -> Image.Image:
    """Безусловное приведение к 256×256 LANCZOS (Д-8/Д-13, ОВ-СА-2).

    Входная геометрия игнорируется: честный клиент присылает готовый квадрат
    256×256 (resize — no-op), подмененный/старый — что угодно (все равно
    получит 256×256 PNG).
    """
    return img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)  # type: ignore[attr-defined]  # Pillow alias Image.Resampling.LANCZOS


@router.post("/avatar")
async def upload_avatar(request: Request, file: UploadFile) -> JSONResponse:
    """Загрузка и серверное автосжатие аватара пользователя сессии.

    Сюда попадают только запросы с действующей сессией (middleware;
    эндпоинт вне exempt-списка, NFR-7). Пользователь — только из сессии
    (свой аватар, FR-39/FR-42); имя файла генерирует сервер.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT u.id FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        user_id = row[0]

        # 1) Декларированный тип — png/jpl иначе 422 (FR-42).
        if not _declared_type_allowed(file):
            return JSONResponse(status_code=422, content=INVALID_FILE_TYPE_BODY)

        # 2) Размер ≤2 МБ ДО декодирования (NFR-10): читаем не более
        #    LIMIT+1 байт — память не зависит от размера присланного тела.
        data = await file.read(MAX_AVATAR_BYTES + 1)
        if len(data) > MAX_AVATAR_BYTES:
            return JSONResponse(status_code=422, content=FILE_TOO_LARGE_BODY)

        # 3) Содержимое — изображение (Pillow-декодирование, не расширение):
        #    битый файл с png-расширением → 422 invalid file type (design §2).
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            if img.format not in _ALLOWED_PILLOW_FORMATS:
                return JSONResponse(status_code=422, content=INVALID_FILE_TYPE_BODY)
        except Exception:
            return JSONResponse(status_code=422, content=INVALID_FILE_TYPE_BODY)

        # 4) Сжатие: безусловная нормализация к 256×256 LANCZOS независимо
        #    от входной геометрии (Д-8/Д-13, ОВ-СА-2); формат содержимого
        #    приводится к png независимо от исходника (design §2).
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        avatar_img = _normalize_256(img)

        # 5) Сохранение: <AVATARS_DIR>/<user_id>.png — имя генерирует сервер
        #    (NFR-7); каталог создается идемпотентно при первом сохранении
        #    (blocker C-1: хранение вне rsync-корня, ОГР-16). Запись атомарная.
        avatars_dir = settings.avatars_dir
        os.makedirs(avatars_dir, exist_ok=True)
        file_path = os.path.join(avatars_dir, f"{user_id}.png")
        tmp_path = file_path + ".tmp"
        with open(tmp_path, "wb") as out:
            avatar_img.save(out, format="PNG")
        os.replace(tmp_path, file_path)

        # 6) avatar_path + avatar_updated_at (sdd §4, minor B-3) — версия
        #    для кеш-бастинга ?v= (ОГР-16).
        updated_at = _utcnow_iso()
        conn.execute(
            "UPDATE users SET avatar_path = ?, avatar_updated_at = ? WHERE id = ?",
            (file_path, updated_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    avatar_url = f"/avatars/{user_id}.png?v={updated_at}"
    return JSONResponse(content={"ok": True, "avatar_url": avatar_url})
