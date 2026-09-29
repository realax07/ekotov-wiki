"""Домен avatar-r4 (Релиз 4): POST /api/profile/avatar (tasks.md 2.3; FR-42,
NFR-10, ОГР-16, Д-8, ОВ-22; design.md пакета §2, sdd r10 §3.1a-кватер;
дельта auth, Requirement «Загрузка аватара» — все 6 сценариев).

Сценарии → тесты:
1. «Успешная загрузка png»        → test_upload_png_success;
2. «Успешная загрузка jpg»        → test_upload_jpg_success;
3. «Серверное автосжатие …»       → test_center_crop_square_256 (плюс
     test_overwrite_updates_avatar_updated_at — повторная загрузка);
4. «Негативный: тип не png/jpg»   → test_reject_gif, test_reject_webp,
     test_reject_fake_png (битый файл с png-расширением — design §2);
5. «Негативный: исходник > 2 МБ»  → test_reject_oversize;
6. «Негативный: без сессии»       → test_401_without_session.

Каталог хранения — AVATARS_DIR из окружения стенда (tmp-каталог, blocker C-1:
вне rsync-корня; на стенде — scratch). Файл на диске проверяется напрямую:
квадрат ≤256px, формат PNG, имя <user_id>.png (генерирует сервер, NFR-7).
Состояние users (avatar_path/avatar_updated_at) — через EKOTOV_WIKI_DB_PATH.
"""

import io
import os
import sqlite3

import pytest
import requests
from PIL import Image

pytestmark = [pytest.mark.api]

AVATARS_DIR_ENV = "EKOTOV_WIKI_AVATARS_DIR"


def _avatars_dir() -> str | None:
    return os.environ.get(AVATARS_DIR_ENV)


def _db_path() -> str | None:
    return os.environ.get("EKOTOV_WIKI_DB_PATH")


def _make_png(width: int = 1000, height: int = 800, color=(200, 30, 30)) -> bytes:
    """Валидный png-исходник (по умолчанию 1000×800 — больше 256px по обеим)."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg(width: int = 640, height: int = 480, color=(30, 120, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_gif() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 200, 10)).save(buf, format="GIF")
    return buf.getvalue()


def _make_webp() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 10, 200)).save(buf, format="WEBP")
    return buf.getvalue()


def _upload(session: requests.Session, base_url: str, data: bytes, filename: str,
            content_type: str) -> requests.Response:
    return session.post(
        f"{base_url}/api/profile/avatar",
        files={"file": (filename, data, content_type)},
    )


def _avatar_file_path(user_id: int) -> str:
    return os.path.join(_avatars_dir(), f"{user_id}.png")


def _current_user_id(session: requests.Session, base_url: str) -> int:
    conn = sqlite3.connect(_db_path())
    try:
        token = session.cookies.get("session")
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "сессия теста не найдена в БД стенда"
    return row[0]


def _user_avatar_row(user_id: int) -> tuple:
    conn = sqlite3.connect(_db_path())
    try:
        return conn.execute(
            "SELECT avatar_path, avatar_updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _delete_avatar_file(user_id: int) -> None:
    try:
        os.remove(_avatar_file_path(user_id))
    except OSError:
        pass


def _reset_avatar_in_db(user_id: int) -> None:
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            "UPDATE users SET avatar_path = NULL, avatar_updated_at = NULL WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def owner_user_id(owner_session, base_url) -> int:
    """id owner-сессии + гарантированная очистка аватара после теста."""
    user_id = _current_user_id(owner_session, base_url)
    yield user_id
    _delete_avatar_file(user_id)
    _reset_avatar_in_db(user_id)


# ==========================================================================
# 1–2. Успешная загрузка png / jpg (сценарии 1–2)
# ==========================================================================


@pytest.mark.must
def test_upload_png_success(base_url, owner_session, owner_user_id):
    """TC-ava-001: png ≤2 МБ → 200 ok + avatar_url; файл на диске —
    квадрат ≤256px PNG с серверным именем <user_id>.png (FR-42, Д-8)."""
    resp = _upload(owner_session, base_url, _make_png(), "photo.png", "image/png")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    expected_url = f"/avatars/{owner_user_id}.png?v="
    assert body["avatar_url"].startswith(expected_url), body["avatar_url"]

    path = _avatar_file_path(owner_user_id)
    assert os.path.exists(path), f"файл аватара не сохранен: {path}"
    with Image.open(path) as img:
        assert img.format == "PNG"
        assert img.size == (256, 256), img.size


@pytest.mark.must
def test_upload_jpg_success(base_url, owner_session, owner_user_id):
    """TC-ava-002: jpg ≤2 МБ → 200; на диске PNG 256×256 — формат содержимого
    приведен к png независимо от исходника (design §2)."""
    resp = _upload(owner_session, base_url, _make_jpeg(), "photo.jpg", "image/jpeg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    with Image.open(_avatar_file_path(owner_user_id)) as img:
        assert img.format == "PNG"
        assert img.size == (256, 256)


# ==========================================================================
# 3. Серверное автосжатие (сценарий 3)
# ==========================================================================


@pytest.mark.must
def test_center_crop_square_256(base_url, owner_session, owner_user_id):
    """TC-ava-003: исходник 1000×800 → сохранен квадрат ровно 256×256 (Д-8);
    center-crop проверяется по цвету краев исходника."""
    # 1000×800: боковые полосы другого цвета — при center-crop до 800×800
    # они срезаются; в сохраненном 256×256 их быть не должно.
    img = Image.new("RGB", (1000, 800), (255, 255, 255))
    for x in range(0, 100):
        for y in range(0, 800):
            img.putpixel((x, y), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    resp = _upload(owner_session, base_url, buf.getvalue(), "wide.png", "image/png")
    assert resp.status_code == 200, resp.text

    with Image.open(_avatar_file_path(owner_user_id)) as saved:
        assert saved.size == (256, 256)
        rgb = saved.convert("RGB")
        assert rgb.getpixel((5, 128)) == (255, 255, 255), "center-crop не по центру"
        assert rgb.getpixel((250, 128)) == (255, 255, 255)


# ==========================================================================
# 4. Негатив: тип файла не png/jpg (сценарий 4; аватар не изменяется)
# ==========================================================================


@pytest.mark.must
def test_reject_gif(base_url, owner_session, owner_user_id):
    """TC-ava-004: gif → 422 invalid file type; ранее установленный аватар
    не изменяется (FR-42)."""
    # Предусловие: действующий аватар.
    first = _upload(owner_session, base_url, _make_png(), "a.png", "image/png")
    assert first.status_code == 200, first.text
    before = _user_avatar_row(owner_user_id)
    mtime_before = os.path.getmtime(_avatar_file_path(owner_user_id))

    resp = _upload(owner_session, base_url, _make_gif(), "anim.gif", "image/gif")
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"error": "invalid file type"}

    after = _user_avatar_row(owner_user_id)
    assert after == before, f"аватар изменился при отказе: {before} → {after}"
    assert os.path.getmtime(_avatar_file_path(owner_user_id)) == mtime_before


@pytest.mark.must
def test_reject_webp(base_url, owner_session, owner_user_id):
    """TC-ava-004b: webp → 422 invalid file type (FR-42: только png/jpg;
    WebP не требуется — design §2)."""
    resp = _upload(owner_session, base_url, _make_webp(), "pic.webp", "image/webp")
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"error": "invalid file type"}
    assert not os.path.exists(_avatar_file_path(owner_user_id))


@pytest.mark.must
def test_reject_fake_png(base_url, owner_session, owner_user_id):
    """TC-ava-004c: битый файл с png-расширением → 422 invalid file type —
    содержимое валидируется декодированием, не расширением (design §2, NFR-7)."""
    fake = b"\x89PNG\r\n\x1a\n" + b"this is not an image" * 100
    assert len(fake) <= 2 * 1024 * 1024
    resp = _upload(owner_session, base_url, fake, "fake.png", "image/png")
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"error": "invalid file type"}
    assert not os.path.exists(_avatar_file_path(owner_user_id))


# ==========================================================================
# 5. Негатив: исходник больше 2 МБ (сценарий 5)
# ==========================================================================


@pytest.mark.must
def test_reject_oversize(base_url, owner_session, owner_user_id):
    """TC-ava-005: корректный png >2 МБ → 422 file too large (NFR-10, ОВ-22);
    аватар не изменяется, ошибок приложения нет."""
    big = Image.new("RGB", (3000, 3000))
    # несжимаемый шум в каждый пиксель → png реально больше 2 МБ (формульный
    # и разреженный шум PNG сжимает; случайный — нет, ~27 МБ на 3000×3000)
    import random

    rng = random.Random(42)
    big.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(3000 * 3000)])
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    data = buf.getvalue()
    assert len(data) > 2 * 1024 * 1024, f"подготовка: png {len(data)} байт ≤ 2 МБ"

    resp = _upload(owner_session, base_url, data, "big.png", "image/png")
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"error": "file too large"}
    assert not os.path.exists(_avatar_file_path(owner_user_id))


# ==========================================================================
# 6. Негатив: без сессии (сценарий 6)
# ==========================================================================


@pytest.mark.must
def test_401_without_session(base_url):
    """TC-ava-006: без сессии → 401 unauthorized; файл не сохраняется
    (NFR-7 — эндпоинт вне exempt-списка)."""
    fresh = requests.Session()
    try:
        resp = fresh.post(
            f"{base_url}/api/profile/avatar",
            files={"file": ("x.png", _make_png(), "image/png")},
        )
    finally:
        fresh.close()
    assert resp.status_code == 401, resp.text
    assert resp.json() == {"error": "unauthorized"}


# ==========================================================================
# Повторная загрузка: перезапись + avatar_updated_at растет (задача 2.3)
# ==========================================================================


@pytest.mark.must
def test_overwrite_updates_avatar_updated_at(base_url, owner_session, owner_user_id):
    """TC-ava-007: повторная загрузка перезаписывает файл; avatar_updated_at
    строго растет — инверсия кеша ?v= (minor B-3 ревью, ОГР-16)."""
    first = _upload(owner_session, base_url, _make_png(), "a.png", "image/png")
    assert first.status_code == 200, first.text
    first_row = _user_avatar_row(owner_user_id)
    first_url = first.json()["avatar_url"]
    assert first_row[0] == _avatar_file_path(owner_user_id)
    assert first_url.endswith(f"?v={first_row[1]}")

    # avatar_updated_at — ISO-datetime с микросекундами; пауза НЕ нужна:
    # два последовательных сохранения в одном тесте различаются по часам
    # процесса стенда (детерминизм: sleep запрещен — спека qa-pipeline).
    second = _upload(owner_session, base_url, _make_jpeg(), "b.jpg", "image/jpeg")
    assert second.status_code == 200, second.text
    second_row = _user_avatar_row(owner_user_id)
    second_url = second.json()["avatar_url"]

    assert second_row[1] > first_row[1], f"{first_row[1]} !< {second_row[1]}"
    assert second_url.endswith(f"?v={second_row[1]}")
    assert second_url != first_url
    with Image.open(_avatar_file_path(owner_user_id)) as img:
        assert img.size == (256, 256)  # перезаписан новым содержимым
