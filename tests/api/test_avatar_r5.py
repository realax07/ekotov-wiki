"""Домен avatar-r5, задача 2.1 (пакет add-r5-avatar-crop-compact-profile):
безусловная серверная нормализация к 256×256 LANCZOS (ОВ-СА-2, Д-8/Д-13).

Сценарий спеки auth «Серверная нормализация не доверяет клиенту»: валидный
png НЕ-квадратной геометрии (512×300 — подмененный/устаревший клиент) →
200, на диске ровно 256×256 PNG. Плюс no-op-ветка: честный клиент прислал
готовый квадрат 256×256 → тоже 256×256. Существующие ТС-ava-001…007
(tests/api/test_avatar_r4.py) не дублируются и не изменяются.
"""

import io
import os
import sqlite3

import pytest
import requests
from PIL import Image

pytestmark = pytest.mark.api


@pytest.fixture
def owner_user_id(owner_session, base_url) -> int:
    """id owner-сессии + очистка аватара после теста (как в test_avatar_r4)."""
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        token = owner_session.cookies.get("session")
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "сессия теста не найдена в БД стенда"
    user_id = row[0]
    yield user_id
    try:
        os.remove(_avatar_file_path(user_id))
    except OSError:
        pass
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        conn.execute(
            "UPDATE users SET avatar_path = NULL, avatar_updated_at = NULL WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()



def _avatars_dir() -> str:
    return os.environ["EKOTOV_WIKI_AVATARS_DIR"]


def _avatar_file_path(user_id: int) -> str:
    return os.path.join(_avatars_dir(), f"{user_id}.png")


def _png_bytes(size: tuple[int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(session: requests.Session, base_url: str, data: bytes) -> requests.Response:
    return session.post(
        f"{base_url}/api/profile/avatar",
        files={"file": ("a.png", data, "image/png")},
    )


def test_server_normalizes_non_square_to_256(base_url, owner_session, owner_user_id):
    """TC-ava-r5-101: серверная нормализация — png 512×300 →
    сохранен ровно 256×256 PNG (200; ОВ-СА-2, Д-13)."""
    try:
        resp = _upload(owner_session, base_url, _png_bytes((512, 300)))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["avatar_url"].startswith(f"/avatars/{owner_user_id}.png?v=")
        with Image.open(_avatar_file_path(owner_user_id)) as saved:
            assert saved.format == "PNG"
            assert saved.size == (256, 256)
    finally:
        if os.path.exists(_avatar_file_path(owner_user_id)):
            os.remove(_avatar_file_path(owner_user_id))


def test_server_normalization_noop_for_honest_client(base_url, owner_session, owner_user_id):
    """TC-ava-r5-102: no-op — квадрат 256×256 от честного клиента →
    200, на диске 256×256 PNG (контракт варианта А)."""
    try:
        resp = _upload(owner_session, base_url, _png_bytes((256, 256)))
        assert resp.status_code == 200, resp.text
        with Image.open(_avatar_file_path(owner_user_id)) as saved:
            assert saved.format == "PNG"
            assert saved.size == (256, 256)
    finally:
        if os.path.exists(_avatar_file_path(owner_user_id)):
            os.remove(_avatar_file_path(owner_user_id))

