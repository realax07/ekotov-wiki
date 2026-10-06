"""QA 2.1 add-gallery-service — API-сьют стенда (TC-GAL-107..114).

Прогон по approved-кейсам test-model/approved/add-gallery-service/ через
nginx-стенд (EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443): app :8080 +
search :8378 + images :8379, images-семейство маршрутизируется nginx'ом
(X-Service: images), отдача файлов — /images/ (alias «тома»).

Трассировка TC:
- TC-GAL-107 — upload happy: JPEG/PNG приняты (201), превью ≤800px, файлы
  в «томе» (файлы, не BLOB), в БД только метаданные, ядро не тронуто.
- TC-GAL-108 — upload негативы: 12 МБ → 422 too_large; PDF под .jpg → 422
  bad_type (magic-байты); отказные не оставляют следов; ~10 МБ проходит
  (client_max_body_size 12m стенда).
- TC-GAL-109 — 401 без сессии на ВСЕХ images-эндпоинтах; данные не меняются.
- TC-GAL-110 — фильтры category/tag по отдельности, комбинация, пустой
  фильтр, created_at DESC, tags в списке; справочник галереи отделен от
  задач; неизвестная категория фильтра → 200 []; неизвестный числовой
  category_id при upload → 422.
- TC-GAL-111 — реакции: toggle-семантика (повторный same-sign PUT снимает),
  смена голоса, независимость голосов owner/PE, отсутствие дублей (upsert).
- TC-GAL-112 — комментарии: добавление/просмотр обоими, пустой → 422,
  удаление своего → 200, чужого → 403 (остается), несуществующего → 404.
- TC-GAL-113 — Э-6: /api/auth/me возвращает ровно 6 ключей с id.
- TC-GAL-114 — маршрут /gallery: аноним → 302 /login, сессия → 200;
  смоук существующих маршрутов.

Изоляция: все загрузки через эту сессию помечены original_name префиксом
`QAGAL-` и удаляются в teardown (API DELETE + файлы из тома по факту
удаления записи... сервис не имеет DELETE /api/images/{id} — очистка
прямыми средствами БД стенда (EKOTOV_WIKI_DB_PATH обязателен)).
"""

import io
import os
import sqlite3

import pytest
import requests
from PIL import Image

pytestmark = [pytest.mark.api, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH")

MARKER = "QAGAL-"

ME_KEYS_6 = {"user", "display_name", "role", "bio", "avatar_url", "id"}

UNAUTHORIZED = {"error": "unauthorized"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_png(w=1200, h=900, color=(120, 40, 200)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _make_jpeg(w=1600, h=1000) -> bytes:
    img = Image.new("RGB", (w, h), (200, 160, 40))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _upload(session, data: bytes, name: str, **extra) -> requests.Response:
    fields = [("file", (name, data, "image/png"))]
    fields += [(k, (None, v)) for k, v in extra.items()]
    return session.post(f"{BASE_URL}/api/images", files=fields)


def _db() -> sqlite3.Connection:
    assert DB_PATH, "EKOTOV_WIKI_DB_PATH обязателен (очистка стенда в teardown)"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _db_image_ids() -> list[int]:
    with _db() as conn:
        return [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM images WHERE original_name LIKE ?", (MARKER + "%",)
            )
        ]


def _cleanup_images(session):
    """Удаляет QAGAL-записи из БД стенда + файлы тома (сервис не имеет
    DELETE-эндпоинта для изображений; правки строго по префиксу QAGAL-)."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, filename, thumb_name FROM images"
            " WHERE original_name LIKE ?",
            (MARKER + "%",),
        ).fetchall()
        if not rows:
            return
        ids = [r["id"] for r in rows]
        q = ",".join("?" * len(ids))
        for table in ("image_tags", "image_reactions", "image_comments"):
            conn.execute(f"DELETE FROM {table} WHERE image_id IN ({q})", ids)
        files = []
        for r in rows:
            files += [r["filename"], r["thumb_name"]]
            conn.execute("DELETE FROM images WHERE id = ?", (r["id"],))
        conn.commit()
    images_dir = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa21-gallery/images")
    for f in files:
        try:
            os.remove(os.path.join(images_dir, f))
        except OSError:
            pass


def _cleanup_gallery_directory(conn):
    """Удаляет QAGAL-категории/теги справочника галереи (не ядро)."""
    conn.execute("DELETE FROM image_tags WHERE tag_id IN"
                 " (SELECT id FROM gallery_tags WHERE name LIKE ?)", (MARKER + "%",))
    conn.execute("DELETE FROM gallery_tags WHERE name LIKE ?", (MARKER + "%",))
    conn.execute("DELETE FROM images WHERE category_id IN"
                 " (SELECT id FROM image_categories WHERE name LIKE ?)", (MARKER + "%",))
    conn.execute("DELETE FROM image_categories WHERE name LIKE ?", (MARKER + "%",))
    conn.commit()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def owner():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "login": "owner",
            "password": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
        },
    )
    assert r.status_code == 200, r.text
    # Secure-кука по http (браузерное поведение localhost).
    for c in s.cookies:
        c.secure = False
    yield s
    s.close()


@pytest.fixture(scope="session")
def pe():
    """PE (wife) — паритет ОВ-4."""
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "login": "wife",
            "password": os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!"),
        },
    )
    assert r.status_code == 200, r.text
    for c in s.cookies:
        c.secure = False
    yield s
    s.close()


@pytest.fixture
def gallery(owner):
    """Чистый слот: до/после теста QAGAL-хвостов нет."""
    _cleanup_images(owner)
    with _db() as conn:
        _cleanup_gallery_directory(conn)
    yield owner
    _cleanup_images(owner)
    with _db() as conn:
        _cleanup_gallery_directory(conn)


@pytest.fixture
def uploaded(owner, gallery):
    """Одно загруженное изображение (QAGAL-имя)."""
    r = _upload(owner, _make_png(), MARKER + "fix.png")
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _comment(session, image_id, body):
    return session.post(
        f"{BASE_URL}/api/images/{image_id}/comments", json={"body": body}
    )


# ---------------------------------------------------------------------------
# TC-GAL-107 — upload happy
# ---------------------------------------------------------------------------


def test_tc_gal_107_upload_happy_png_jpeg_volume_and_core_intact(gallery):
    """TC-GAL-107: PNG и JPEG приняты (201); оригинал+превью — ФАЙЛЫ в томе;
    в БД только метаданные; превью ≤800px по длинной стороне; таблицы ядра
    не изменены (границы записи — только таблицы галереи)."""
    png = _make_png(1200, 900)
    jpeg = _make_jpeg(1600, 1000)
    core_before = {}
    with _db() as conn:
        for t in ("tasks", "comments", "categories", "sessions", "users"):
            core_before[t] = conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
        sessions_before = conn.execute("SELECT count(*) c FROM sessions").fetchone()["c"]

    r_png = _upload(gallery, png, MARKER + "a.png")
    assert r_png.status_code == 201, r_png.text
    body = r_png.json()
    assert body["original_name"] == MARKER + "a.png"
    assert body["mime"] == "image/png"
    assert body["url"].startswith("/images/")

    r_jpg = _upload(gallery, jpeg, MARKER + "b.jpg")
    assert r_jpg.status_code == 201, r_jpg.text
    assert r_jpg.json()["mime"] == "image/jpeg"

    # Том: файлы существуют, это не BLOB; размеры = размеру оригинала.
    images_dir = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa21-gallery/images")
    with _db() as conn:
        rows = conn.execute(
            "SELECT filename, thumb_name, size FROM images"
            " WHERE original_name LIKE ?",
            (MARKER + "%",),
        ).fetchall()
    assert len(rows) == 2
    for row in rows:
        orig = os.path.join(images_dir, row["filename"])
        thumb = os.path.join(images_dir, row["thumb_name"])
        assert os.path.isfile(orig) and os.path.getsize(orig) == row["size"]
        assert os.path.isfile(thumb)
        with Image.open(thumb) as im:
            assert max(im.size) <= 800, f"превью {im.size} > 800px"

    # Список и отдача файла (nginx alias тома).
    lst = gallery.get(f"{BASE_URL}/api/images").json()["images"]
    names = {i["original_name"] for i in lst}
    assert MARKER + "a.png" in names and MARKER + "b.jpg" in names
    f = gallery.get(f"{BASE_URL}{r_png.json()['thumb_url']}")
    assert f.status_code == 200
    assert f.headers["content-type"] == "image/jpeg"

    # Ядро не изменено (sessions — только +1 наша).
    with _db() as conn:
        for t in ("tasks", "comments", "categories", "users"):
            after = conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
            assert after == core_before[t], f"таблица ядра {t} изменена!"
        assert (
            conn.execute("SELECT count(*) c FROM sessions").fetchone()["c"]
            >= sessions_before
        )


def test_tc_gal_107_small_image_no_upscale(gallery):
    """TC-GAL-107 (гран.): изображение с длинной стороной < 800px НЕ
    апскейлится — превью сохраняет исходные размеры."""
    r = _upload(gallery, _make_png(640, 480), MARKER + "small.png")
    assert r.status_code == 201
    thumb_url = r.json()["thumb_url"]
    f = gallery.get(f"{BASE_URL}{thumb_url}")
    assert f.status_code == 200
    with Image.open(io.BytesIO(f.content)) as im:
        assert im.size == (640, 480), f"апскейл: {im.size}"


# ---------------------------------------------------------------------------
# TC-GAL-108 — upload негативы
# ---------------------------------------------------------------------------


def test_tc_gal_108_upload_too_large_over_10mb_422_and_no_trace(gallery):
    """TC-GAL-108 (шаг 1/4): валидный PNG СВЕРХ лимита 10 МБ, но в пределах
    nginx 12m → 422 too_large (валидация сервисом ДО записи в том); ни файла,
    ни записи. (Тело ровно 12 МиБ + multipart-обвязка превышает client_max_body_size
    12m — такое тело отсекает nginx 413 ДО сервиса; контракт «422 too_large»
    проверяется телом 11 МБ, см. docstring REPORT-2.1.)"""
    big = _make_png(100, 100)
    big = big + b"\x00" * (11 * 1024 * 1024 - len(big))
    r = _upload(gallery, big, MARKER + "big.png")
    assert r.status_code == 422, f"{r.status_code} {r.text[:200]}"
    assert "too_large" in r.text, r.text
    assert _db_image_ids() == []


def test_tc_gal_108_upload_12mib_over_nginx_limit_413():
    """TC-GAL-108 (факт стенда, дополнение): тело > client_max_body_size 12m
    (12 МиБ + multipart-обвязка) отсекается nginx'ом — 413 без записи (не 422:
    до валидации сервиса запрос не доходит). Граница 10 МБ (422 too_large) —
    предыдущий тест; 12m — верхняя граница транспортного контура (design §4)."""
    big = _make_png(100, 100)
    big = big + b"\x00" * (12 * 1024 * 1024 - len(big))
    r = _upload(requests.Session(), big, MARKER + "huge.png")
    assert r.status_code == 413, f"{r.status_code} {r.text[:200]}"


def test_tc_gal_108_upload_pdf_renamed_jpg_bad_type(gallery):
    """TC-GAL-108 (шаг 2/4): PDF, переименованный в .jpg (Content-Type
    подделан) → 422 bad_type — тип по magic-байтам."""
    pdf = b"%PDF-1.4\n%fake-pdf-for-qa\n" + b"\x00" * 500
    r = gallery.post(
        f"{BASE_URL}/api/images",
        files={"file": (MARKER + "fake.jpg", pdf, "image/jpeg")},
    )
    assert r.status_code == 422
    assert "bad_type" in r.text, r.text
    assert _db_image_ids() == []


def test_tc_gal_108_upload_corrupted_image_422(gallery):
    """TC-GAL-108 (шаг 3/4): поврежденное изображение (битые magic-байты) →
    422, следов не оставляет."""
    corrupt = b"\x89PNG\r\n\x1a\nGARBAGE" + b"\x00" * 300
    r = _upload(gallery, corrupt, MARKER + "corrupt.png")
    assert r.status_code == 422
    assert _db_image_ids() == []


def test_tc_gal_108_upload_10mb_within_limit_passes(gallery):
    """TC-GAL-108 (шаг 5): файл ~10 МБ (в пределах лимита) проходит через
    nginx целиком (client_max_body_size 12m) — гран. 10 МБ не отсекает.
    Проба — валидный PNG 9.5 МБ (pad-байты внутри PNG-контейнера: tEXt-чанк,
    валидатор декодирует и принимает; noise-pad после IEND ломал бы magic-
    валидацию трейлинг-данными — вариант заменен на валидную пробу)."""
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (200, 200), (10, 140, 90))
    buf = io.BytesIO()
    img.save(buf, "PNG", compress_level=0)
    data = buf.getvalue()
    pad = 9_500_000 - len(data)
    assert pad > 0, len(data)
    # Валидный tEXt-чанк перед IEND: len("qagPad")+data, CRC нулевой не
    # сойдет — считаем честный CRC через struct/zlib.
    import struct
    import zlib

    chunk_data = b"qag" + b"Q" * pad
    chunk = (
        struct.pack(">I", len(chunk_data) - 4 + 4)
        + b"tEXt"
        + chunk_data
        + struct.pack(">I", zlib.crc32(b"tEXt" + chunk_data) & 0xFFFFFFFF)
    )
    iend = b"\x00\x00\x00\x00IEND\xaeB`\x82"
    body_no_iend = data[: -len(iend)]
    data = body_no_iend + chunk + iend
    assert 9 * 1024 * 1024 < len(data) <= 10 * 1024 * 1024, len(data)
    r = _upload(gallery, data, MARKER + "ten.png")
    assert r.status_code == 201, f"{r.status_code} {r.text[:200]}"
    assert r.json()["size"] == len(data)


# ---------------------------------------------------------------------------
# TC-GAL-109 — 401 без сессии
# ---------------------------------------------------------------------------


def test_tc_gal_109_all_endpoints_401_anonymous(uploaded):
    """TC-GAL-109: все API images без сессии → 401; данные не изменяются."""
    anon = requests.Session()
    image_id = uploaded
    checks = [
        ("GET", f"{BASE_URL}/api/images", None),
        ("GET", f"{BASE_URL}/api/images/{image_id}", None),
        (
            "POST",
            f"{BASE_URL}/api/images",
            {"files": {"file": (MARKER + "anon.png", _make_png(50, 50), "image/png")}},
        ),
        ("PUT", f"{BASE_URL}/api/images/{image_id}/like", None),
        ("PUT", f"{BASE_URL}/api/images/{image_id}/dislike", None),
        ("POST", f"{BASE_URL}/api/images/{image_id}/comments", {"json": {"body": "x"}}),
        ("DELETE", f"{BASE_URL}/api/images/{image_id}/comments/1", None),
    ]
    try:
        for method, url, kw in checks:
            r = anon.request(method, url, **(kw or {}))
            assert r.status_code == 401, f"{method} {url}: {r.status_code}"
            assert r.json() == UNAUTHORIZED
    finally:
        anon.close()
    # Шаг 5: состояние без изменений.
    with _db() as conn:
        assert conn.execute(
            "SELECT count(*) c FROM image_reactions WHERE image_id = ?", (image_id,)
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT count(*) c FROM image_comments WHERE image_id = ?", (image_id,)
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT count(*) c FROM images WHERE original_name LIKE ?",
            (MARKER + "anon%",),
        ).fetchone()["c"] == 0


# ---------------------------------------------------------------------------
# TC-GAL-110 — фильтры
# ---------------------------------------------------------------------------


@pytest.fixture
def filter_data(owner, gallery):
    """(A) категория «семья» + теги лето/дача; (B) та же категория без тегов;
    (C) без категории/тегов. Разные времена загрузки недостижимы без сна —
    сортировка DESC проверяется по совпадающим created_at (tie-break id DESC)."""
    cat = MARKER + "семья"
    tag1, tag2 = MARKER + "лето", MARKER + "дача"
    ra = _upload(owner, _make_png(60, 60), MARKER + "A.png",
                 category=cat, tags=f"{tag1},{tag2}")
    rb = _upload(owner, _make_png(60, 60), MARKER + "B.png", category=cat)
    rc = _upload(owner, _make_png(60, 60), MARKER + "C.png")
    assert all(r.status_code == 201 for r in (ra, rb, rc))
    return {"cat": cat, "tag1": tag1, "tag2": tag2,
            "ids": [ra.json()["id"], rb.json()["id"], rc.json()["id"]]}


def test_tc_gal_110_directory_isolated_from_tasks_and_reused(filter_data, owner):
    """TC-GAL-110 (шаг 1): справочник галереи отделен от задач; повторная
    загрузка переиспользует значения (дублей нет)."""
    cat, tag1 = filter_data["cat"], filter_data["tag1"]
    with _db() as conn:
        ids = conn.execute(
            "SELECT id FROM image_categories WHERE name = ?", (cat,)
        ).fetchall()
        assert len(ids) == 1
        task_cats = conn.execute(
            "SELECT count(*) c FROM categories WHERE name = ?", (cat,)
        ).fetchone()["c"]
        assert task_cats == 0, "категория протекла в справочник задач"
    # Повторная загрузка — переиспользование.
    r = _upload(owner, _make_png(60, 60), MARKER + "A2.png",
                category=cat, tags=tag1)
    assert r.status_code == 201
    with _db() as conn:
        assert conn.execute(
            "SELECT count(*) c FROM image_categories WHERE name = ?", (cat,)
        ).fetchone()["c"] == 1
        assert conn.execute(
            "SELECT count(*) c FROM gallery_tags WHERE name = ?", (tag1,)
        ).fetchone()["c"] == 1


def test_tc_gal_110_filters_category_tag_combination_empty(filter_data, owner):
    """TC-GAL-110 (шаги 2–6): фильтры по отдельности, комбинация (конъюнкция),
    пустой фильтр — все, created_at DESC, tags в списке, неизвестная категория
    фильтра → 200 []."""
    A, B, C = filter_data["ids"]
    cat, tag1 = filter_data["cat"], filter_data["tag1"]

    r = owner.get(f"{BASE_URL}/api/images", params={"category": cat})
    assert r.status_code == 200
    assert {i["id"] for i in r.json()["images"]} == {A, B}

    r = owner.get(f"{BASE_URL}/api/images", params={"tag": tag1})
    assert [i["id"] for i in r.json()["images"]] == [A]

    r = owner.get(f"{BASE_URL}/api/images", params={"category": cat, "tag": tag1})
    assert [i["id"] for i in r.json()["images"]] == [A]

    r = owner.get(f"{BASE_URL}/api/images")
    imgs = r.json()["images"]
    assert {i["id"] for i in imgs} == {A, B, C}
    # created_at DESC (tie-break: id DESC).
    created = [(i["created_at"], i["id"]) for i in imgs]
    assert created == sorted(created, reverse=True), created
    # tags в списке (Э-3/1.6): у A оба, у C — [].
    by_id = {i["id"]: i for i in imgs}
    assert set(by_id[A]["tags"]) == {tag1, filter_data["tag2"]}
    assert by_id[C]["tags"] == []

    r = owner.get(f"{BASE_URL}/api/images", params={"category": MARKER + "нет-такой"})
    assert r.status_code == 200
    assert r.json()["images"] == []


def test_tc_gal_110_upload_unknown_numeric_category_id_422(owner, gallery):
    """TC-GAL-110 (шаг 7): неизвестный ЧИСЛОВОЙ category_id при upload → 422."""
    r = _upload(owner, _make_png(60, 60), MARKER + "x.png", category="999999")
    assert r.status_code == 422, f"{r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# TC-GAL-111 — реакции
# ---------------------------------------------------------------------------


def test_tc_gal_111_reaction_toggle_change_independence(uploaded, owner, pe):
    """TC-GAL-111: toggle-семантика (повтор same-sign PUT снимает голос,
    дубля нет); смена голоса — смещение ровно на один; голоса owner/PE
    независимы; my_reaction/счетчики корректны в списке и детали."""
    img = uploaded

    # Шаг 1: лайк; повторный same-sign PUT — снятие (toggle FR-81).
    r1 = owner.put(f"{BASE_URL}/api/images/{img}/like")
    assert r1.status_code == 200, r1.text
    assert r1.json()["my_reaction"] == 1 and r1.json()["likes"] == 1
    r2 = owner.put(f"{BASE_URL}/api/images/{img}/like")
    assert r2.status_code == 200
    assert r2.json()["my_reaction"] is None and r2.json()["likes"] == 0

    with _db() as conn:  # шаг 5: дублей нет (PK upsert)
        assert conn.execute(
            "SELECT count(*) c FROM image_reactions WHERE image_id = ?", (img,)
        ).fetchone()["c"] == 0

    # Шаг 2: смена голоса с чистого состояния (like → dislike = 0/1).
    owner.put(f"{BASE_URL}/api/images/{img}/like")
    r3 = owner.put(f"{BASE_URL}/api/images/{img}/dislike")
    assert r3.status_code == 200
    body = r3.json()
    assert body["my_reaction"] == -1
    assert body["likes"] == 0 and body["dislikes"] == 1, body  # ровно +1

    # Шаг 3: повторный same-sign dislike — снятие.
    r4 = owner.put(f"{BASE_URL}/api/images/{img}/dislike")
    assert r4.json()["my_reaction"] is None and r4.json()["dislikes"] == 0

    # Шаг 4: независимость голосов двух пользователей.
    owner.put(f"{BASE_URL}/api/images/{img}/like")
    rp = pe.put(f"{BASE_URL}/api/images/{img}/like")
    assert rp.status_code == 200
    assert rp.json()["likes"] == 2 and rp.json()["my_reaction"] == 1
    ro = owner.get(f"{BASE_URL}/api/images/{img}")
    assert ro.json()["likes"] == 2 and ro.json()["my_reaction"] == 1

    with _db() as conn:
        rows = conn.execute(
            "SELECT user_id, value FROM image_reactions WHERE image_id = ?", (img,)
        ).fetchall()
        assert sorted((r["user_id"], r["value"]) for r in rows) == [(1, 1), (2, 1)]

    # Шаг 6: список тоже несет my_reaction/счетчики.
    lst = owner.get(f"{BASE_URL}/api/images").json()["images"]
    mine = [i for i in lst if i["id"] == img][0]
    assert mine["likes"] == 2 and mine["my_reaction"] == 1


# ---------------------------------------------------------------------------
# TC-GAL-112 — комментарии
# ---------------------------------------------------------------------------


def test_tc_gal_112_comments_lifecycle(uploaded, owner, pe):
    """TC-GAL-112: добавление (виден обоим с автором/временем), пустой → 422,
    свой → удаление 200, чужой → 403 (остался), несуществующий → 404."""
    img = uploaded

    r = _comment(owner, img, "QAGAL-комментарий owner")
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["author"] == "owner"
    assert r.json()["created_at"]

    detail = pe.get(f"{BASE_URL}/api/images/{img}").json()  # шаг 2: виден PE
    assert [c["body"] for c in detail["comments"]] == ["QAGAL-комментарий owner"]

    r = _comment(owner, img, "   ")  # шаг 3: из одних пробелов
    assert r.status_code == 422
    r = _comment(owner, img, "")
    assert r.status_code == 422

    r = pe.delete(f"{BASE_URL}/api/images/{img}/comments/{cid}")  # шаг 5: чужой
    assert r.status_code == 403
    assert len(pe.get(f"{BASE_URL}/api/images/{img}").json()["comments"]) == 1

    r = owner.delete(f"{BASE_URL}/api/images/{img}/comments/{cid}")  # шаг 4: свой
    assert r.status_code == 200
    assert pe.get(f"{BASE_URL}/api/images/{img}").json()["comments"] == []

    r = owner.delete(f"{BASE_URL}/api/images/{img}/comments/999999")  # шаг 6
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# TC-GAL-113 — Э-6: /api/auth/me 6 ключей
# ---------------------------------------------------------------------------


def test_tc_gal_113_me_returns_exactly_six_keys_with_id(owner):
    """TC-GAL-113 (шаг 2): /api/auth/me — ровно 6 ключей
    {user, display_name, role, bio, avatar_url, id}; id = users.id."""
    r = owner.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == ME_KEYS_6, body
    with _db() as conn:
        uid = conn.execute(
            "SELECT id FROM users WHERE login = 'owner'"
        ).fetchone()["id"]
    assert body["id"] == uid


def test_tc_gal_113_me_without_session_401():
    """TC-GAL-113 (шаг 5): без сессии — 401."""
    r = requests.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 401
    assert r.json() == UNAUTHORIZED


# ---------------------------------------------------------------------------
# TC-GAL-114 — маршрут /gallery
# ---------------------------------------------------------------------------


def test_tc_gal_114_gallery_route_anon_redirect_login(owner):
    """TC-GAL-114 (шаг 1): анонимно /gallery → редирект на /login."""
    r = requests.get(f"{BASE_URL}/gallery", allow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_tc_gal_114_gallery_route_with_session_200(owner):
    """TC-GAL-114 (шаг 2): с сессией /gallery → 200, страница галереи."""
    r = owner.get(f"{BASE_URL}/gallery")
    assert r.status_code == 200
    assert "gallery" in r.text.lower() or "Галерея" in r.text


def test_tc_gal_114_smoke_existing_routes_not_broken(owner):
    """TC-GAL-114 (шаг 3): смоук-матрица /board, /login, /search, /wiki —
    работают как прежде (маршрута «/» в ядре нет — pages.py: /login, /board,
    /search, /wiki, /settings, /settings/profile, /gallery)."""
    for path, code in (("/board", 200), ("/login", 200),
                       ("/search", 200), ("/wiki", 200)):
        r = owner.get(f"{BASE_URL}{path}", allow_redirects=False)
        assert r.status_code == code, f"{path}: {r.status_code}"
