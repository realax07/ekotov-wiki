"""Юнит-тесты storage-модуля (задача 1.6, video-hosting кусок A;
TC-vid-040…044 — изоляция путей: uuid-каталоги, отказ построения пути
из имени пользователя, удаление каталога).

Зона ответственности storage.py — единственный владелец путей тома
(sdd §2 шов): uuid-каталоги, пути из имен пользователя НЕ строятся
(design §8, path traversal), удаление каталога целиком. Без сети/БД.
"""

import os

import pytest

from app import storage


@pytest.fixture()
def volume(tmp_path, monkeypatch):
    d = str(tmp_path / "videos-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", d)
    return d


def test_new_video_id_is_uuid_hex():
    """id — uuid4 hex (32 hex-символа), уникален, годен как имя каталога."""
    ids = {storage.new_video_id() for _ in range(50)}
    assert len(ids) == 50
    for video_id in ids:
        assert len(video_id) == 32
        int(video_id, 16)  # hex


def test_is_video_id_rejects_foreign_strings():
    """Только uuid-hex проходит проверку: traversal/слэши/имя файла — нет."""
    assert storage.is_video_id(storage.new_video_id())
    for bad in ("", "../../etc", "a/b", "..", "имя", "a" * 31, "a" * 33,
                "not-a-uuid", "original.mkv", "%2e%2e%2f"):
        assert not storage.is_video_id(bad), bad


def test_normalize_ext_never_builds_path_from_name():
    """Из имени клиента берется ТОЛЬКО нормализованное расширение
    (^[a-z0-9]{1,8}$, иначе «bin») — путь из имени не строится."""
    assert storage.normalize_ext("clip.mkv") == "mkv"
    assert storage.normalize_ext("ВИДЕО.MP4") == "mp4"  # регистр срезается
    assert storage.normalize_ext("../../etc/passwd") == "bin"
    assert storage.normalize_ext("no-extension") == "bin"
    assert storage.normalize_ext("") == "bin"
    assert storage.normalize_ext(None) == "bin"
    assert storage.normalize_ext("x." + "a" * 9) == "bin"  # слишком длинное
    assert storage.normalize_ext("x.a b") == "bin"         # пробел
    assert storage.normalize_ext("x.кир") == "bin"         # не латиница


def test_paths_are_volume_id_fixed_names(volume):
    """Все пути — <vol>/<uuid>/ + фиксированное имя; произвольные
    компоненты отвергаются."""
    video_id = storage.new_video_id()
    assert storage.video_dir(video_id) == os.path.join(volume, video_id)
    assert storage.original_path(video_id, "mkv") == os.path.join(
        volume, video_id, "original.mkv"
    )
    assert storage.mp4_path(video_id) == os.path.join(volume, video_id, "video.mp4")
    assert storage.preview_path(video_id) == os.path.join(
        volume, video_id, "preview.jpg"
    )
    with pytest.raises(ValueError):
        storage.video_dir("../../etc")
    with pytest.raises(ValueError):
        storage.original_path(video_id, "../x")


def test_store_and_playable_path(volume):
    """store_original кладет байты как есть; playable_path: сначала
    original, после появления video.mp4 — mp4 (переключение куска B)."""
    video_id = storage.new_video_id()
    storage.create_video_dir(video_id)
    src = os.path.join(volume, "..", "spool.tmp")
    with open(src, "wb") as f:
        f.write(b"payload")
    dest = storage.store_original(video_id, "mkv", src)
    assert dest == storage.original_path(video_id, "mkv")
    assert not os.path.exists(src)  # атомарный перенос
    with open(dest, "rb") as f:
        assert f.read() == b"payload"

    assert storage.playable_path(video_id) == dest
    assert storage.playable_url(video_id) == f"/videos/{video_id}/original.mkv"

    with open(storage.mp4_path(video_id), "wb") as f:
        f.write(b"mp4")
    assert storage.playable_path(video_id) == storage.mp4_path(video_id)
    assert storage.playable_url(video_id) == f"/videos/{video_id}/video.mp4"


def test_playable_path_missing_dir_none(volume):
    """Нет каталога/файла → None и None-URL (404 на уровне API)."""
    video_id = storage.new_video_id()
    assert storage.playable_path(video_id) is None
    assert storage.playable_url(video_id) is None


def test_delete_video_dir_removes_everything(volume):
    """Удаление каталога целиком (оригинал+mp4+превью одним rmtree);
    отсутствие каталога — не ошибка."""
    video_id = storage.new_video_id()
    d = storage.create_video_dir(video_id)
    for name in ("original.mkv", "video.mp4", "preview.jpg"):
        with open(os.path.join(d, name), "wb") as f:
            f.write(b"x")
    storage.delete_video_dir(video_id)
    assert not os.path.exists(d)
    storage.delete_video_dir(video_id)  # idempotent
