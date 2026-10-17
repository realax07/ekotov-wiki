"""Хранилище тома videos-data — единственный владелец путей (tasks 1.3,
video-hosting волна 1; design §5/§8; sdd §2 шов: videos.py/converter.py
вызывают storage.*, никто больше путей не строит).

Структура тома (design §5):
  <videos-dir>/<id>/original.<ext>   — исходник (любой формат, как есть)
  <videos-dir>/<id>/video.mp4        — сконвертированное видео (кусок B, 3.1)
  <videos-dir>/<id>/preview.jpg      — превью-кадр (кусок B, 3.1)

Безопасность путей (design §8): каталог = uuid, ГЕНЕРИРУЕМЫЙ сервисом;
пути из имен пользователя НЕ строятся — от имени клиента берется только
расширение, и то после жесткой нормализации (^[a-z0-9]{1,8}$, иначе
«bin»). Каждый публичный id дополнительно проверяется _is_video_id —
путь из произвольной строки URL построен быть не может (path traversal
отключен по построению).
"""

import os
import re
import shutil
import uuid

# Том видео (deploy задачи 1.2 смонтирует videos-data:/data/videos).
DEFAULT_VIDEOS_DIR = "/data/videos"

# uuid4().hex — 32 hex-символа; единственная разрешенная форма каталога.
_VIDEO_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Нормализация расширения имени клиента: только латиница/цифры, 1–8 символов.
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")

# Расширение по умолчанию, когда из имени клиента безопасное не извлекается.
DEFAULT_EXT = "bin"


def get_videos_dir() -> str:
    """Каталог тома videos-data: env EKOTOV_WIKI_VIDEOS_DIR или дефолт.

    Читается на каждый запрос (не на импорт): путь — конфигурация
    окружения; в тестах env переключается фикстурой на временный каталог.
    """
    return os.environ.get("EKOTOV_WIKI_VIDEOS_DIR", DEFAULT_VIDEOS_DIR)


def new_video_id() -> str:
    """Новый id видео = uuid4 (hex) — он же имя каталога в томе (sdd §4)."""
    return uuid.uuid4().hex


def is_video_id(video_id: str) -> bool:
    """Строгая проверка формы id (uuid4 hex) — защита от path traversal."""
    return bool(_VIDEO_ID_RE.match(video_id or ""))


def normalize_ext(filename: str | None) -> str:
    """Расширение имени клиента → безопасный суффикс пути.

    Из имени берется ТОЛЬКО хвост после последней точки, приводится к
    нижнему регистру и проверяется по ^[a-z0-9]{1,8}$; все остальное
    (пусто, кириллица, слэши, «..», слишком длинное) → DEFAULT_EXT.
    Имя в путь не попадает — только нормализованное расширение.
    """
    name = (filename or "").rsplit(".", 1)[-1].lower()
    if _EXT_RE.match(name):
        return name
    return DEFAULT_EXT


def video_dir(video_id: str) -> str:
    """Каталог видео в томе: <videos-dir>/<id>/ (только для валидных id)."""
    if not is_video_id(video_id):
        raise ValueError(f"invalid video id: {video_id!r}")
    return os.path.join(get_videos_dir(), video_id)


def original_path(video_id: str, ext: str) -> str:
    """Путь исходника <id>/original.<ext> (ext — после normalize_ext)."""
    if not _EXT_RE.match(ext or ""):
        raise ValueError(f"invalid extension: {ext!r}")
    return os.path.join(video_dir(video_id), f"original.{ext}")


def mp4_path(video_id: str) -> str:
    """Путь готового видео <id>/video.mp4 (создает конвертер — кусок B)."""
    return os.path.join(video_dir(video_id), "video.mp4")


def preview_path(video_id: str) -> str:
    """Путь превью-кадра <id>/preview.jpg (создает конвертер — кусок B)."""
    return os.path.join(video_dir(video_id), "preview.jpg")


def create_video_dir(video_id: str) -> str:
    """Создает каталог <id>/ в томе (вызывается при сохранении исходника)."""
    d = video_dir(video_id)
    os.makedirs(d, exist_ok=True)
    return d


def store_original(video_id: str, ext: str, tmp_path: str) -> str:
    """Перемещает подготовленный временный файл в том:
    <tmp> → <id>/original.<ext>. Возвращает итоговый путь.

    shutil.move: на одном ФС — атомарный rename; temp (системный /tmp
    контейнера) и том могут быть на разных устройствах — тогда
    копирование+удаление (частичный файл появляется только в томе и
    только после валидации размера; при копировании ошибок записи
    исключение оставляет приемку без записи в БД, сироты чистит
    вызывающий код)."""
    dest = original_path(video_id, ext)
    shutil.move(tmp_path, dest)
    # Tempfile создается с 0600: отдачу из тома ведет nginx (другой uid,
    # design §5) — права на чтение всеми, запись только владельцу.
    os.chmod(dest, 0o644)
    return dest


def playable_path(video_id: str) -> str | None:
    """Файл для playback: готовый mp4, иначе исходник, иначе None.

    Кусок A: исходник отдается как есть (любой формат); кусок B после
    конвертации в каталоге появится video.mp4 — отдача переключится на
    него без изменений вызывающего кода.
    """
    mp4 = mp4_path(video_id)
    if os.path.isfile(mp4):
        return mp4
    d = video_dir(video_id)
    if not os.path.isdir(d):
        return None
    for name in sorted(os.listdir(d)):
        if name.startswith("original."):
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    return None


def playable_url(video_id: str) -> str | None:
    """Публичный (за auth_request) URL файла для списка/плеера:
    /videos/<id>/video.mp4 либо /videos/<id>/original.<ext>."""
    path = playable_path(video_id)
    if path is None:
        return None
    return "/videos/" + video_id + "/" + os.path.basename(path)


def delete_video_dir(video_id: str) -> None:
    """Удаляет каталог <id>/ целиком (оригинал, mp4, превью — атомарно
    в смысле «каталога нет»); отсутствие каталога не ошибка."""
    shutil.rmtree(video_dir(video_id), ignore_errors=True)
