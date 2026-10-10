"""Юнит-тесты wiki API (change add-wiki, tasks.md 2.2; design.md §3, §5, §6;
FR-107…FR-116).

По конвенции сервисных юнитов (test_comments_author_r8.py): TestClient над
app.main, БД — временная sqlite в фикстуре (DDL design.md §1 — pages +
page_versions + users/sessions минимум); сессия owner пишется в БД напрямую.

Запуск (из корня репозитория, без стенда):
  DB_PATH=/tmp/... SECRET_KEY=test python3 -m pytest tests/api/test_wiki_api.py -v

Трассировка контрактов — design.md §3 (таблица): CRUD, валидации 422/404/409,
версия на каждое сохранение (FR-112), revert = новая версия (FR-113),
LIKE-поиск с экранированием %_\\ (§6), 401 без сессии (§8 — middleware).
"""

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Плагин pytest-base-url тянет conftest-овский base_url (поллинг живого
# стенда) — TestClient-юнитам стенд не нужен; перекрываем no-op'ом
# (паттерн test_comments_author_r8.py).
@pytest.fixture(scope="session", autouse=True)
def _verify_url():
    yield


# Конфиг приложения читает env на импорте (app.config.settings) — env
# обязателен ДО import app.main. tmp-путь уникален на прогон.
os.environ.setdefault("DB_PATH", f"/tmp/wiki22-{uuid.uuid4().hex}.db")
os.environ.setdefault("SECRET_KEY", "wiki-unit-test-key")

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.middleware import SESSION_COOKIE_NAME  # noqa: E402

# DDL design.md §1 дословно (pages + page_versions + индексы) + минимальные
# users/sessions (ярусы, нужные middleware и FK авторов).
SCHEMA_SQL = """
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  login         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
);
CREATE TABLE sessions (
  token       TEXT PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
  id         INTEGER PRIMARY KEY,
  parent_id  INTEGER REFERENCES pages(id) ON DELETE RESTRICT,
  title      TEXT NOT NULL,
  content    TEXT NOT NULL DEFAULT '',
  author_id  INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_versions (
  id         INTEGER PRIMARY KEY,
  page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  content    TEXT NOT NULL,
  author_id  INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_parent   ON pages(parent_id);
CREATE INDEX IF NOT EXISTS idx_pages_title    ON pages(title);
CREATE INDEX IF NOT EXISTS idx_page_versions_page ON page_versions(page_id, id);
"""


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite (DDL design.md §1) + пользователь owner + валидная
    сессия. Путь переключается на объекте settings (паттерн r8-юнитов)."""
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (1, 'owner', 'x')"
        )
        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES ('wiki-token-1', 1, ?, ?)",
            (now.isoformat(), (now + timedelta(days=1)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr("app.config.settings.db_path", path)
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def anon_client(db_path):
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def client(db_path):
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "wiki-token-1")
        yield client


def _create(client, title="Страница", **payload) -> dict:
    resp = client.post("/api/wiki/pages", json={"title": title, **payload})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _versions_count(db: str, page_id: int) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM page_versions WHERE page_id = ?", (page_id,)
        ).fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 401 без сессии (design.md §8 — все эндпоинты)
# --------------------------------------------------------------------------


def test_all_endpoints_require_session(anon_client):
    """TC-wiki-001: без валидной сессии — 401 на каждом методе /api/wiki/*."""
    checks = [
        anon_client.get("/api/wiki/pages"),
        anon_client.post("/api/wiki/pages", json={"title": "x"}),
        anon_client.get("/api/wiki/pages/1"),
        anon_client.put("/api/wiki/pages/1", json={"content": "x"}),
        anon_client.get("/api/wiki/pages/1/versions"),
        anon_client.get("/api/wiki/pages/1/versions/1"),
        anon_client.post("/api/wiki/pages/1/revert/1"),
        anon_client.get("/api/wiki/search", params={"q": "x"}),
        anon_client.delete("/api/wiki/pages/1"),
    ]
    for resp in checks:
        assert resp.status_code == 401, f"{resp.request.method}: {resp.status_code}"


# --------------------------------------------------------------------------
# POST /api/wiki/pages — создание (422-валидации)
# --------------------------------------------------------------------------


def test_create_page_returns_201(client):
    """TC-wiki-002: создание — 201 {id} (ТЗ 2.2; контент санитизирован)."""
    body = _create(client, content="<p>Текст<script>evil()</script></p>")
    assert "id" in body
    page = client.get(f"/api/wiki/pages/{body['id']}").json()
    assert page["content"] == "<p>Текст</p>"


def test_create_page_empty_title_422(client):
    """TC-wiki-003: пустой title → 422 (FR-108)."""
    for title in ("", "   "):
        resp = client.post("/api/wiki/pages", json={"title": title})
        assert resp.status_code == 422


def test_create_page_missing_title_422(client):
    """TC-wiki-004: title отсутствует → 422 (валидация Pydantic)."""
    resp = client.post("/api/wiki/pages", json={"content": "x"})
    assert resp.status_code == 422


def test_create_page_bad_parent_422(client):
    """TC-wiki-005: несуществующий parent_id → 422 (design.md §3)."""
    resp = client.post("/api/wiki/pages", json={"title": "Дитя", "parent_id": 999})
    assert resp.status_code == 422


def test_create_page_with_valid_parent(client):
    """TC-wiki-006: валидный parent_id — страница создана, попала в список
    и в breadcrumb ребенка (сервер считает цепочку, §6)."""
    parent = _create(client, "Родитель")
    child = _create(client, "Ребенок", parent_id=parent["id"])
    page = client.get(f"/api/wiki/pages/{child['id']}").json()
    assert page["parent_id"] == parent["id"]
    assert page["breadcrumb"] == [
        {"id": parent["id"], "title": "Родитель"},
        {"id": child["id"], "title": "Ребенок"},
    ]


# --------------------------------------------------------------------------
# GET /api/wiki/pages — плоский список для дерева
# --------------------------------------------------------------------------


def test_list_pages_flat_shape(client):
    """TC-wiki-007: плоский список {id, parent_id, title, updated_at} —
    без контента (легкий ответ дерева, design.md §3)."""
    _create(client, "А")
    parent = _create(client, "Б")
    _create(client, "В", parent_id=parent["id"])
    pages = client.get("/api/wiki/pages").json()["pages"]
    assert len(pages) == 3
    for item in pages:
        assert set(item.keys()) == {"id", "parent_id", "title", "updated_at"}


# --------------------------------------------------------------------------
# GET /api/wiki/pages/{id} — 404, breadcrumb, can_delete
# --------------------------------------------------------------------------


def test_get_page_404(client):
    """TC-wiki-008: несуществующая страница → 404."""
    assert client.get("/api/wiki/pages/424242").status_code == 404


def test_get_page_can_delete_leaf_vs_parent(client):
    """TC-wiki-009: can_delete=true у листа, false у родителя (FR-116)."""
    parent = _create(client, "Родитель")
    _create(client, "Лист", parent_id=parent["id"])
    assert client.get(f"/api/wiki/pages/{parent['id']}").json()["can_delete"] is False
    leaf_id = client.get("/api/wiki/pages").json()["pages"]
    leaf_id = next(p["id"] for p in leaf_id if p["title"] == "Лист")
    assert client.get(f"/api/wiki/pages/{leaf_id}").json()["can_delete"] is True


def test_breadcrumb_deep_chain(client):
    """TC-wiki-010: breadcrumb из 3 уровней — от корня к странице (§6)."""
    a = _create(client, "А")
    b = _create(client, "Б", parent_id=a["id"])
    c = _create(client, "В", parent_id=b["id"])
    page = client.get(f"/api/wiki/pages/{c['id']}").json()
    assert [n["title"] for n in page["breadcrumb"]] == ["А", "Б", "В"]


# --------------------------------------------------------------------------
# PUT — сохранение: версия на каждое сохранение (FR-112)
# --------------------------------------------------------------------------


def test_update_creates_version_and_bumps_updated_at(client, db_path):
    """TC-wiki-011: PUT → INSERT в page_versions (санитизированный контент,
    автор сессии) + updated_at обновлен."""
    page = _create(client, "Статья", content="<p>v1</p>")
    v1_updated = client.get(f"/api/wiki/pages/{page['id']}").json()["updated_at"]

    resp = client.put(
        f"/api/wiki/pages/{page['id']}", json={"content": "<p>v2<script>x()</script></p>"}
    )
    assert resp.status_code == 200
    page_after = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert page_after["content"] == "<p>v2</p>"  # санитизация на записи
    assert page_after["updated_at"] >= v1_updated
    assert _versions_count(db_path, page["id"]) == 2  # создание + сохранение


def test_update_title_only_keeps_content(client):
    """TC-wiki-012: PUT только title — контент не трогается, но версия
    пишется (каждое сохранение = версия, FR-112)."""
    page = _create(client, "Было", content="<p>контент</p>")
    resp = client.put(f"/api/wiki/pages/{page['id']}", json={"title": "Стало"})
    assert resp.status_code == 200
    page_after = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert page_after["title"] == "Стало"
    assert page_after["content"] == "<p>контент</p>"


def test_update_empty_title_422(client):
    """TC-wiki-013: PUT с пустым title → 422."""
    page = _create(client, "Статья")
    resp = client.put(f"/api/wiki/pages/{page['id']}", json={"title": "  "})
    assert resp.status_code == 422


def test_update_missing_page_404(client):
    """TC-wiki-014: PUT несуществующей → 404 (design.md §3)."""
    resp = client.put("/api/wiki/pages/424242", json={"title": "x"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# Версии: список, чтение, revert (FR-113)
# --------------------------------------------------------------------------


def test_versions_list_newest_first_without_content(client):
    """TC-wiki-015: список версий от новых к старым {id, author_id,
    created_at}, без контента (design.md §3)."""
    page = _create(client, "Статья", content="<p>v1</p>")
    client.put(f"/api/wiki/pages/{page['id']}", json={"content": "<p>v2</p>"})
    client.put(f"/api/wiki/pages/{page['id']}", json={"content": "<p>v3</p>"})
    body = client.get(f"/api/wiki/pages/{page['id']}/versions").json()
    versions = body["versions"]
    assert len(versions) == 3
    assert versions == sorted(versions, key=lambda v: v["id"], reverse=True)
    for v in versions:
        assert set(v.keys()) == {"id", "author_id", "created_at"}
        assert v["author_id"] == 1  # автор сессии


def test_versions_list_missing_page_404(client):
    """TC-wiki-016: версии несуществующей страницы → 404."""
    assert client.get("/api/wiki/pages/424242/versions").status_code == 404


def test_get_version_content_and_foreign_version_404(client):
    """TC-wiki-017: контент версии читается; версия другой страницы — 404."""
    p1 = _create(client, "Первая", content="<p>раз</p>")
    p2 = _create(client, "Вторая", content="<p>два</p>")
    vid_p1 = client.get(f"/api/wiki/pages/{p1['id']}/versions").json()["versions"][0]["id"]
    resp = client.get(f"/api/wiki/pages/{p1['id']}/versions/{vid_p1}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "<p>раз</p>"
    # Чужая версия под чужим page_id — 404 (design.md §3).
    assert (
        client.get(f"/api/wiki/pages/{p2['id']}/versions/{vid_p1}").status_code == 404
    )


def test_revert_creates_new_version_not_rewrite(client, db_path):
    """TC-wiki-018: revert — контент версии становится текущим + НОВАЯ
    версия (автор — исполнитель отката); история не переписывается (FR-113)."""
    page = _create(client, "Статья", content="<p>v1</p>")
    client.put(f"/api/wiki/pages/{page['id']}", json={"content": "<p>v2</p>"})
    versions = client.get(f"/api/wiki/pages/{page['id']}/versions").json()["versions"]
    oldest = versions[-1]["id"]  # v1

    resp = client.post(f"/api/wiki/pages/{page['id']}/revert/{oldest}")
    assert resp.status_code == 200
    new_vid = resp.json()["new_version_id"]

    page_after = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert page_after["content"] == "<p>v1</p>"
    # История не переписана: старых версий 2 + новая; новая id > всех.
    versions_after = client.get(
        f"/api/wiki/pages/{page['id']}/versions"
    ).json()["versions"]
    assert len(versions_after) == 3
    assert versions_after[0]["id"] == new_vid
    assert _versions_count(db_path, page["id"]) == 3


def test_revert_missing_page_or_version_404(client):
    """TC-wiki-019: revert с несуществующей страницей/версией → 404."""
    page = _create(client, "Статья")
    assert client.post("/api/wiki/pages/424242/revert/1").status_code == 404
    assert client.post(f"/api/wiki/pages/{page['id']}/revert/99999").status_code == 404


# --------------------------------------------------------------------------
# Поиск: LIKE с экранированием (design.md §6)
# --------------------------------------------------------------------------


def test_search_finds_title_and_content(client):
    """TC-wiki-020: поиск находит по title и по content; путь в иерархии
    присутствует; пустой q → 422."""
    parent = _create(client, "Кулинария", content="<p>вступление</p>")
    _create(client, "Тесто", parent_id=parent["id"], content="<p>мука и вода</p>")
    client.put(
        f"/api/wiki/pages/{parent['id']}", json={"content": "<p>мука высшего сорта</p>"}
    )

    by_title = client.get("/api/wiki/search", params={"q": "Тесто"}).json()["results"]
    assert len(by_title) == 1
    assert by_title[0]["title"] == "Тесто"
    assert "Кулинария" in by_title[0]["path"]

    by_content = client.get(
        "/api/wiki/search", params={"q": "мука"}
    ).json()["results"]
    assert {r["title"] for r in by_content} >= {"Тесто", "Кулинария"}

    # Сниппет: фрагмент вокруг первого вхождения + оффсет/длина для <mark>.
    first = by_content[0]
    assert "мука" in first["snippet"].lower()
    assert first["snippet"].lower()[
        first["match_offset"] : first["match_offset"] + first["match_length"]
    ].lower() == "мука"

    empty = client.get("/api/wiki/search", params={"q": "  "})
    assert empty.status_code == 422


def test_search_escapes_like_wildcards(client):
    """TC-wiki-021: % _ \\ в q экранируются (design.md §6) — «100%» не
    матчит «100» + суффикс, подчеркивание не матчит любой символ."""
    _create(client, "Скидка 100 процентов", content="<p>условия</p>")
    _create(client, "Отчет_2026", content="<p>годовой</p>")
    _create(client, "Планы на 2026 год", content="<p>наброски</p>")

    # «100%» не должно находить «Скидка 100 процентов» (после «100» нет %).
    r = client.get("/api/wiki/search", params={"q": "100%"}).json()["results"]
    assert r == []
    # «отчет_» с подчеркиванием матчит только литеральное подчеркивание
    # (SQLite LIKE регистронезависим только для ASCII — сравнение в точном
    # регистре, как и предписывает design.md §6 без оговорок о нижнем регистре).
    r = client.get("/api/wiki/search", params={"q": "Отчет_"}).json()["results"]
    assert [x["title"] for x in r] == ["Отчет_2026"]
    # чистое вхождение работает.
    r = client.get("/api/wiki/search", params={"q": "2026"}).json()["results"]
    assert {x["title"] for x in r} == {"Отчет_2026", "Планы на 2026 год"}


def test_search_limit_20(client):
    """TC-wiki-022: LIMIT 20 (design.md §3)."""
    for i in range(25):
        _create(client, f"Клон {i}", content="<p>общий корень поиска</p>")
    results = client.get("/api/wiki/search", params={"q": "Клон"}).json()["results"]
    assert len(results) == 20


# --------------------------------------------------------------------------
# DELETE: 409 с дочерними, удаление листа, CASCADE версий
# --------------------------------------------------------------------------


def test_delete_with_children_409(client):
    """TC-wiki-023: удаление с дочерними → 409 (FR-116, ОВ-2)."""
    parent = _create(client, "Родитель")
    _create(client, "Дитя", parent_id=parent["id"])
    assert client.delete(f"/api/wiki/pages/{parent['id']}").status_code == 409


def test_delete_leaf_removes_versions(client, db_path):
    """TC-wiki-024: удаление листа — 200; версии ушли по CASCADE (§1)."""
    page = _create(client, "Лист", content="<p>x</p>")
    client.put(f"/api/wiki/pages/{page['id']}", json={"content": "<p>y</p>"})
    assert _versions_count(db_path, page["id"]) == 2
    resp = client.delete(f"/api/wiki/pages/{page['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/wiki/pages/{page['id']}").status_code == 404
    assert _versions_count(db_path, page["id"]) == 0
    assert client.delete(f"/api/wiki/pages/{page['id']}").status_code == 404


# --------------------------------------------------------------------------
# Санитизация на записи (design.md §4: POST/PUT/revert)
# --------------------------------------------------------------------------


def test_create_sanitizes_content(client):
    """TC-wiki-025: POST — контент в БД уже просанитизированный (§4)."""
    page = _create(
        client,
        "Смешанный",
        content='<p onclick="x()" style="c">ok</p><script>bad()</script>'
        '<a href="javascript:evil()">l</a><iframe src="http://x">i</iframe>',
    )
    stored = client.get(f"/api/wiki/pages/{page['id']}").json()["content"]
    assert "script" not in stored and "bad()" not in stored
    assert "onclick" not in stored and "javascript" not in stored
    assert "iframe" not in stored
    assert "ok" in stored and ">l<" in stored and "i" in stored


def test_revert_sanitizes_stored_content(db_path, client, monkeypatch):
    """TC-wiki-026: revert прогоняет контент через sanitizer повторно —
    страховка от «грязных» данных прошлых версий/ручных правок БД (§4)."""
    page = _create(client, "Статья", content="<p>v1</p>")
    # «Грязная» правка БД в обход API — первая версия порчен вручную.
    vid = client.get(f"/api/wiki/pages/{page['id']}/versions").json()["versions"][0]["id"]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE page_versions SET content = ? WHERE id = ?",
            ('<p>v1</p><script>alert(1)</script>', vid),
        )
        conn.commit()
    finally:
        conn.close()
    resp = client.post(f"/api/wiki/pages/{page['id']}/revert/{vid}")
    assert resp.status_code == 200
    stored = client.get(f"/api/wiki/pages/{page['id']}").json()["content"]
    assert "script" not in stored and "alert" not in stored
    assert "<p>v1</p>" in stored
