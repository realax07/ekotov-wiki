"""QA-контур 4.1 Р5 (change add-r5-avatar-crop-compact-profile): гэпы.

5 approved-кейсов `test-model/new/add-r5-avatar-crop-compact-profile/`
(чеклист CHK-R5-3/6/9/12/13; impact — раздел 3 «Новые тестовые требования»):
- TC-ava-r5-103 (CHK-R5-3)  — нормализация jpg-входа: JPEG 900×600 →
  256×256 PNG (нормализация не зависит от исходного формата; существующие
  TC-ava-r5-101/102 — только png);
- TC-ava-r5-104 (CHK-R5-6)  — граница лимита 2 МБ (NFR-10/12, ОВ-22):
  ровно 2 097 152 байт ПРИНЯТ (спека отклоняет «более 2 МБ»), 2 МБ + 1 байт
  → 422 file too large ДО декодирования. TC-ava-005 — ~27 МБ (не граница),
  web-тест 2 МБ+1 — клиентская ветка до виджета; серверная граница не была
  покрыта;
- TC-ava-r5-105 (CHK-R5-12) — изоляция пользователей: загрузка wife не
  меняет байт-в-байт файл и БД-строку owner (хвост CHK-R4-25 Р4 «покрыт
  косвенно»);
- TC-ava-r5-106 (CHK-R5-9)  — backward-compat ОГР-21/СЦ-13: файл «старого»
  аватара (center-crop Р4) не перекрашивается: sha256 инвариантен при
  открытии профиля/me (нормализация — только в потоке новой загрузки);
- TC-ava-r5-107 (CHK-R5-13) — EXIF-портрет (Orientation=6, «фото с
  телефона», design §7 риск): сервер принимает EXIF-jpeg и нормализует
  к 256×256 PNG (ориентацию применяет браузер при декодировании — вариант
  А, ОВ-СА-1; ассерт на пиксельную ориентацию НЕ ставится).

Существующие тесты не дублируются и не изменяются (TC-ava-001…007,
TC-ava-r5-101/102). Формат: 1 кейс = 1 тест; TC-ID в docstring; маркеры api;
изоляция — teardown-гигиена аватара обоих пользователей (как в test_avatar_r4);
time.sleep = 0.
"""

import hashlib
import io
import os
import sqlite3

import pytest
import requests
from PIL import Image

pytestmark = [pytest.mark.api]

OWNER = "owner"
WIFE = "wife"

UNAUTHORIZED = {"error": "unauthorized"}  # middleware, единый текст
INVALID_FILE_TYPE = {"error": "invalid file type"}
FILE_TOO_LARGE = {"error": "file too large"}

LIMIT = 2 * 1024 * 1024  # NFR-10/ОВ-22


# --- helpers (по образцу test_avatar_r4/r5) -------------------------------


def _db_path() -> str:
    return os.environ["EKOTOV_WIKI_DB_PATH"]


def _avatars_dir() -> str:
    return os.environ["EKOTOV_WIKI_AVATARS_DIR"]


def _user_row_by_login(login: str) -> tuple:
    conn = sqlite3.connect(_db_path())
    try:
        return conn.execute(
            "SELECT id, avatar_path, avatar_updated_at FROM users WHERE login = ?",
            (login,),
        ).fetchone()
    finally:
        conn.close()


def _user_id(login: str) -> int:
    return _user_row_by_login(login)[0]


def _avatar_file(login: str) -> str:
    return os.path.join(_avatars_dir(), f"{_user_id(login)}.png")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _reset_avatar(login: str) -> None:
    try:
        os.remove(_avatar_file(login))
    except OSError:
        pass
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            "UPDATE users SET avatar_path = NULL, avatar_updated_at = NULL"
            " WHERE login = ?",
            (login,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def owner_hygiene():
    """Teardown-гигиена аватара owner (как owner_user_id в test_avatar_r4)."""
    yield
    _reset_avatar(OWNER)


@pytest.fixture
def both_hygiene():
    """Teardown-гигиена аватаров owner И wife (кейс изоляции)."""
    yield
    _reset_avatar(OWNER)
    _reset_avatar(WIFE)


def _png_bytes(size: tuple[int, int], color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(size: tuple[int, int], color=(30, 120, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _upload(session: requests.Session, base_url: str, data: bytes,
            filename: str, content_type: str) -> requests.Response:
    return session.post(
        f"{base_url}/api/profile/avatar",
        files={"file": (filename, data, content_type)},
    )


def _saved_image(login: str):
    return Image.open(_avatar_file(login))


# ==========================================================================
# TC-ava-r5-103: нормализация jpg-входа (CHK-R5-3)
# ==========================================================================


@pytest.mark.must
def test_normalization_jpeg_non_square_to_256_png(
    base_url, owner_session, owner_hygiene
):
    """TC-ava-r5-103: валидный JPEG 900×600 → 200, на диске ровно 256×256
    PNG — серверная нормализация не зависит от исходного формата
    (ОВ-СА-2, Д-13; спека auth «Серверная нормализация не доверяет
    клиенту»: «в любом случае»)."""
    resp = _upload(
        owner_session, base_url, _jpeg_bytes((900, 600)), "photo.jpg", "image/jpeg"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    owner_id = _user_id(OWNER)
    assert body["avatar_url"].startswith(f"/avatars/{owner_id}.png?v=")

    with _saved_image(OWNER) as img:
        assert img.format == "PNG"
        assert img.size == (256, 256)


# ==========================================================================
# TC-ava-r5-104: граница лимита 2 МБ (CHK-R5-6)
# ==========================================================================


def _png_of_exact_size(target: int) -> bytes:
    """Валидный PNG с длиной файла ровно target байт (декодируем PIL).

    Длина PNG с tEXt-данными = базовая_длина + len('x'*n) (chunk линейно
    переносится в размер файла), поэтому n = target - базовая_длина - 0:
    подбираем размер базового шумного изображения так, чтобы базовая длина
    была меньше target, затем добиваем точный размер tEXt-пэдом.
    """
    from PIL import PngImagePlugin

    side = 16
    while True:
        img = _noise_image(side)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        base = len(buf.getvalue())
        if base < target - 16:
            break  # остается место под tEXt-пэд
        if base > target:
            raise RuntimeError("базовый PNG превышает целевой размер")
        side *= 2

    # tEXt-чанк добавляет фикс. оверхед (длина имени+CRС ~ 16 байт сверх
    # данных) — вычисляем его эмпирически один раз.
    probe_meta = PngImagePlugin.PngInfo()
    probe_meta.add_text("pad", "x" * 10)
    probe_buf = io.BytesIO()
    img.save(probe_buf, format="PNG", pnginfo=probe_meta)
    overhead = (len(probe_buf.getvalue()) - base) - 10
    assert overhead > 0, "подготовка: tEXt-оверхед не измерен"

    pad = target - base - overhead  # данных в tEXt
    assert pad > 0, f"подготовка: pad={pad} (база+оверхед >= target)"
    meta = PngImagePlugin.PngInfo()
    meta.add_text("pad", "x" * pad)
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    data = buf.getvalue()
    assert len(data) == target, f"подготовка: {len(data)} != {target}"
    return data


def _noise_image(side: int) -> Image.Image:
    import random

    rng = random.Random(42)
    img = Image.new("RGB", (side, side))
    img.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256))
         for _ in range(side * side)]
    )
    return img


@pytest.mark.must
def test_size_limit_boundary_exactly_2mb_accepted_plus_one_rejected(
    base_url, owner_session, owner_hygiene
):
    """TC-ava-r5-104: граница NFR-10/12 — ровно 2 МБ (2 097 152 байта)
    принят (спека отклоняет «более 2 МБ»); 2 МБ + 1 байт → 422
    {"error": "file too large"} ДО декодирования; аватар после отказа
    не изменен (mtime + БД-строка)."""
    exact = _png_of_exact_size(LIMIT)
    assert len(exact) == LIMIT

    # Граница включительно — ПРИНЯТ.
    resp = _upload(owner_session, base_url, exact, "exact.png", "image/png")
    assert resp.status_code == 200, resp.text
    owner_id = _user_id(OWNER)
    assert resp.json()["avatar_url"].startswith(f"/avatars/{owner_id}.png?v=")
    path = _avatar_file(OWNER)
    with Image.open(path) as img:
        assert img.format == "PNG" and img.size == (256, 256)

    before_row = _user_row_by_login(OWNER)
    mtime_before = os.path.getmtime(path)

    # Граница + 1 байт — 422 file too large (не invalid file type: размер
    # проверяется ДО декодирования, design/avatar.py шаг 2).
    plus_one = _png_of_exact_size(LIMIT + 1)
    assert len(plus_one) == LIMIT + 1
    resp2 = _upload(owner_session, base_url, plus_one, "big.png", "image/png")
    assert resp2.status_code == 422, resp2.text
    assert resp2.json() == FILE_TOO_LARGE

    assert _user_row_by_login(OWNER) == before_row
    assert os.path.getmtime(path) == mtime_before  # файл не перезаписан


# ==========================================================================
# TC-ava-r5-105: изоляция пользователей (CHK-R5-12)
# ==========================================================================


@pytest.mark.must
def test_wife_upload_does_not_touch_owner_avatar(
    base_url, owner_session, wife_session, both_hygiene
):
    """TC-ava-r5-105: загрузка аватара wife → 200; файл и БД-строка owner
    байт-в-байт/поле-в-поле прежние; файлы независимы
    (<user_id>.png генерирует сервер из сессии — user-параметра в
    контракте нет, «аватар загружается только свой», NFR-7)."""
    owner_png = _png_bytes((640, 480), color=(200, 30, 30))
    first = _upload(owner_session, base_url, owner_png, "a.png", "image/png")
    assert first.status_code == 200, first.text

    owner_path = _avatar_file(OWNER)
    sha_before = _sha256(owner_path)
    row_before = _user_row_by_login(OWNER)

    second = _upload(
        wife_session, base_url, _jpeg_bytes((500, 700)), "b.jpg", "image/jpeg"
    )
    assert second.status_code == 200, second.text

    # Owner не затронут ни в файле, ни в БД.
    assert _sha256(owner_path) == sha_before
    assert _user_row_by_login(OWNER) == row_before

    # Два независимых файла; wife-файл существует и корректен.
    wife_path = _avatar_file(WIFE)
    assert wife_path != owner_path
    assert os.path.exists(wife_path)
    with _saved_image(WIFE) as img:
        assert img.format == "PNG" and img.size == (256, 256)


# ==========================================================================
# TC-ava-r5-106: backward-compat ОГР-21 (CHK-R5-9)
# ==========================================================================


@pytest.mark.must
def test_pre_release_avatar_file_not_repainted(
    base_url, owner_session, owner_hygiene
):
    """TC-ava-r5-106 (ОГР-21, СЦ-13): «старый» аватар (сохранен до r5,
    center-crop Р4 — здесь: любая загрузка, затем только ЧТЕНИЕ профиля)
    не перекрашивается: sha256/размер файла и avatar_updated_at/?v=
    инвариантны после GET /api/profile и GET /api/auth/me; нормализация
    применяется только к новым загрузкам."""
    old_avatar = _png_bytes((640, 640), color=(90, 140, 40))
    first = _upload(owner_session, base_url, old_avatar, "old.png", "image/png")
    assert first.status_code == 200, first.text
    url_before = first.json()["avatar_url"]

    path = _avatar_file(OWNER)
    sha_before = _sha256(path)
    size_before = os.path.getsize(path)
    row_before = _user_row_by_login(OWNER)

    # Пользователь «открывает профиль»: чтение профиля и me (r5 — та же
    # сущность страницы). Никаких POST — перекраски быть не должно.
    prof = owner_session.get(f"{base_url}/api/profile")
    assert prof.status_code == 200, prof.text
    me = owner_session.get(f"{base_url}/api/auth/me")
    assert me.status_code == 200, me.text
    assert prof.json()["avatar_url"] == url_before
    # me: ключ "user" — логин строкой (backward-compat R1/R3), avatar_url
    # лежит на верхнем уровне (TC-me4-001).
    assert me.json()["avatar_url"] == url_before
    assert me.json()["user"] == OWNER

    # Файл и БД-строка не изменились (никакой фоновой нормализации).
    assert _sha256(path) == sha_before
    assert os.path.getsize(path) == size_before
    assert _user_row_by_login(OWNER) == row_before


# ==========================================================================
# TC-ava-r5-107: EXIF-портрет с телефона (CHK-R5-13)
# ==========================================================================


def _jpeg_with_exif_orientation(size: tuple[int, int], orientation: int = 6) -> bytes:
    """JPEG с EXIF Orientation (6 = поворот 90° — типичный портрет)."""
    from PIL import Image as PILImage

    img = PILImage.new("RGB", size, (120, 60, 160))
    buf = io.BytesIO()
    # PIL: exif через save (INFO не переносит произвольные теги — собираем
    # через Image.Exif).
    exif = PILImage.Exif()
    exif[0x0112] = orientation  # Orientation
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


@pytest.mark.must
def test_exif_portrait_jpeg_accepted_and_normalized(
    base_url, owner_session, owner_hygiene
):
    """TC-ava-r5-107: jpg с EXIF Orientation=6 («портрет с телефона»,
    design §7 риск) → 200 (не 422: содержимое валидный jpeg), на диске
    256×256 PNG. Ориентацию пикселей НЕ ассертим: вариант А (ОВ-СА-1) —
    ориентацию применяет браузер при декодировании; сервер обязан лишь
    принять и нормализовать геометрию."""
    data = _jpeg_with_exif_orientation((1200, 800), orientation=6)
    # Контроль подготовки: PIL декодирует, EXIF-тег присутствует.
    probe = Image.open(io.BytesIO(data))
    assert probe.format == "JPEG"
    assert int((probe.getexif() or {}).get(0x0112, 0)) == 6

    resp = _upload(owner_session, base_url, data, "phone.jpg", "image/jpeg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    with _saved_image(OWNER) as img:
        assert img.format == "PNG"
        assert img.size == (256, 256)
