"""Round-trip rich-блоков через API wiki (tasks.md 1.3 p12-rich-tools;
design.md §1/§3; урок rich-v1 «потеря контента при вложении»).

Формат (design.md §1): блоки хранятся в существующем TEXT-поле content как
санитизированный HTML с data-атрибутами фиксированного словаря. Проверяется:
- PUT контента со всеми блоками и вложенностями матрицы §6 → GET идентичен
  (санитайзер уже-санитизированного контента — тождество);
- в сохраненном нет editor-артефактов (data-editor-узлы/атрибуты вырезаны —
  design.md §3, находка F1);
- revert версии с блоками возвращает контент (§1: состояния отображения в
  контенте нет — версии дешевые).

Юнит-паттерн test_wiki_api.py: TestClient + tmp-sqlite (DDL design §1) +
seed owner/сессия; стенд не нужен (авто-no-op _verify_url против
pytest-base-url, паттерн test_sanitize.py).

Запуск: python -m pytest tests/api/test_wiki_rich.py -v
"""

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Плагин pytest-base-url тянет conftest-овский base_url — TestClient-юнитам
# стенд не нужен; перекрываем no-op'ом (паттерн test_wiki_api.py).
@pytest.fixture(scope="session", autouse=True)
def _verify_url():
    yield


os.environ.setdefault("DB_PATH", f"/tmp/wiki-rich-{uuid.uuid4().hex}.db")
os.environ.setdefault("SECRET_KEY", "wiki-rich-unit-test-key")

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.middleware import SESSION_COOKIE_NAME  # noqa: E402

# DDL design.md §1 (pages + page_versions + минимальные users/sessions) —
# дословно как в test_wiki_api.py.
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
            " VALUES ('wiki-rich-token', 1, ?, ?)",
            (now.isoformat(), (now + timedelta(days=1)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr("app.config.settings.db_path", path)
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def client(db_path):
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "wiki-rich-token")
        yield client


def _create(client, title="Rich-страница", **payload) -> dict:
    resp = client.post("/api/wiki/pages", json={"title": title, **payload})
    assert resp.status_code == 201, resp.text
    return resp.json()


# Матрица вложенности §6 (design.md): спойлер/ячейка/вкладка ×
# спойлер/код/табы/таблица; запрещенное (table-in-table, блоки в коде)
# покрывают юниты test_sanitize.py — здесь только разрешенные связки.
MATRIX_CONTENT = (
    # спойлер в тексте
    '<div data-block="spoiler" data-title="Скрытые детали">'
    "<div data-block-part=\"body\"><p>тело</p></div></div>"
    # спойлер в спойлере (независимые состояния)
    '<div data-block="spoiler" data-title="Внешний">'
    '<div data-block-part="body">'
    '<div data-block="spoiler" data-title="Внутренний">'
    "<div data-block-part=\"body\"><p>двойное дно</p></div></div>"
    "</div></div>"
    # код-блок (чистый текст, без спанов подсветки)
    '<div data-block="code" data-lang="python"><pre><code>def f():'
    "\n    return 1</code></pre></div>"
    # код внутри спойлера
    '<div data-block="spoiler" data-title="Код скрыт">'
    '<div data-block-part="body">'
    '<div data-block="code" data-lang="bash"><pre><code>echo hi</code></pre>'
    "</div></div></div>"
    # табы, спойлер и код во вкладке
    '<div data-block="tabs">'
    '<div data-block-part="tab" data-title="Обзор"><p>первая</p></div>'
    '<div data-block-part="tab" data-title="Внутри">'
    '<div data-block="spoiler" data-title="Во вкладке">'
    "<div data-block-part=\"body\"><p>в табе</p></div></div>"
    '<div data-block="code" data-lang="json"><pre><code>{"a": 1}</code></pre>'
    "</div></div></div>"
    # табы внутри вкладки (§6: ДА)
    '<div data-block="tabs">'
    '<div data-block-part="tab" data-title="Снаружи">'
    '<div data-block="tabs">'
    '<div data-block-part="tab" data-title="Внутри"><p>вложенные табы</p></div>'
    "</div></div></div>"
    # спойлер компактный в ячейке таблицы
    "<table><thead><tr><th>Этап</th></tr></thead><tbody><tr><td>"
    '<div data-block="spoiler" data-title="Компакт">'
    "<div data-block-part=\"body\"><p>в ячейке</p></div></div>"
    "</td></tr></tbody></table>"
)


def test_roundtrip_all_blocks_and_nesting_matrix(client):
    """TC-richapi-001: POST контента со всеми блоками и вложенностями
    матрицы §6 → GET идентичен байт-в-байт (урок rich-v1: потеря контента
    при вложении не воспроизводится; design.md §3 — сохранение как есть)."""
    page = _create(client, content=MATRIX_CONTENT)
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert got["content"] == MATRIX_CONTENT


def test_roundtrip_put_then_get_identical(client):
    """TC-richapi-002: PUT со всеми блоками → GET идентичен; повторный PUT
    того же контента идемпотентен (санитайзер не искажает свои данные)."""
    page = _create(client)
    resp = client.put(
        f"/api/wiki/pages/{page['id']}", json={"content": MATRIX_CONTENT}
    )
    assert resp.status_code == 200, resp.text
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert got["content"] == MATRIX_CONTENT
    resp = client.put(
        f"/api/wiki/pages/{page['id']}", json={"content": MATRIX_CONTENT}
    )
    assert resp.status_code == 200
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert got["content"] == MATRIX_CONTENT


def test_saved_content_has_no_editor_artifacts(client):
    """TC-richapi-003 (design.md §3, находка F1): editor-артефакты
    (data-editor-узлы, inline-панели) не попадают в сохраненное — вырезаны
    детерминированным обходом; контентные узлы не тронуты."""
    dirty = (
        "<p>до</p>"
        '<div data-editor="" contenteditable="false">'
        '<button>+</button><span class="tabbar">панель</span></div>'
        '<div data-block="spoiler" data-title="T">'
        '<div data-block-part="body"><p>тело</p>'
        '<div data-editor="" contenteditable="false">'
        '<span class="spoiler-title-hint">подсказка</span></div>'
        "</div></div>"
        "<p>после</p>"
    )
    page = _create(client, content=dirty)
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    content = got["content"]
    # маркер артефакта снят вместе с атрибутами (кнопка — unwrap)
    assert "data-editor" not in content
    assert "contenteditable" not in content
    assert "<button>" not in content and "spoiler-title-hint" not in content
    # контент сохранен целиком (текст панели остается простым текстом —
    # вырезание поддерева data-editor делает editor.js до PUT, §3)
    assert "<p>до</p>" in content and "<p>после</p>" in content
    assert 'data-block="spoiler"' in content and "<p>тело</p>" in content


def test_revert_returns_block_content(client):
    """TC-richapi-004: revert версии с блоками возвращает контент
    (tasks.md 1.3; состояния отображения в контенте не хранятся — §1)."""
    page = _create(client, content=MATRIX_CONTENT)
    resp = client.put(
        f"/api/wiki/pages/{page['id']}",
        json={"content": "<p>переписали без блоков</p>"},
    )
    assert resp.status_code == 200
    versions = client.get(f"/api/wiki/pages/{page['id']}/versions").json()
    assert len(versions["versions"]) >= 2
    first_content_id = versions["versions"][-1]["id"]  # старейшая — с блоками
    resp = client.post(f"/api/wiki/pages/{page['id']}/revert/{first_content_id}")
    assert resp.status_code == 200, resp.text
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert got["content"] == MATRIX_CONTENT


def test_unknown_block_value_degrades_via_api(client):
    """TC-richapi-005 (NFR-39): контент с подмененным data-block сохраняется
    как обычный div-контент — текст не потерян, блока нет."""
    dirty = '<div data-block="future-widget">обычный текст</div>'
    page = _create(client, content=dirty)
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    assert got["content"] == "<div>обычный текст</div>"


def test_xss_vectors_inside_blocks_neutralized(client):
    """TC-richapi-006 (NFR-39/§8): script с содержимым, onclick и
    javascript:-ссылка внутри блоков режутся на записи; спойлер цел."""
    dirty = (
        '<div data-block="spoiler" data-title="X" onclick="evil()">'
        "<div data-block-part=\"body\"><script>alert(1)</script>"
        '<p>ок</p><a href="javascript:alert(2)">тыкни</a></div></div>'
    )
    page = _create(client, content=dirty)
    got = client.get(f"/api/wiki/pages/{page['id']}").json()
    content = got["content"]
    assert "script" not in content and "alert" not in content
    assert "onclick" not in content and "javascript" not in content
    assert 'data-block="spoiler"' in content and "<p>ок</p>" in content


def test_table_in_table_paste_unwrapped_idempotent(client):
    """QA D2, paste-путь (TC-rich-041/api::041): вложенная таблица при
    сохранении unwrap'ится санитайзером целиком (тексты обеих ячеек
    слипаются в одну — `<td>A1<br>B1</td>`), повторный PUT идемпотентен.
    Гейт в редакторе (editor.js, ячейка×таблица = НЕТ) закрывает только
    ВСТАВКУ — здесь проверен серверный путь «редактор не покажет то,
    что не сохранится»."""
    nested = (
        "<table><tbody><tr><td>"
        "<table><tbody><tr><td>A1</td><td>B1</td></tr></tbody></table>"
        "</td></tr></tbody></table>"
    )
    page = _create(client, "Таблица в таблице paste", content=nested)
    first = client.get(f"/api/wiki/pages/{page['id']}").json()["content"]
    assert first.count("<table>") == 1
    assert "<td>A1<br>B1</td>" in first
    resp = client.put(f"/api/wiki/pages/{page['id']}", json={"content": first})
    assert resp.status_code == 200, resp.text
    second = client.get(f"/api/wiki/pages/{page['id']}").json()["content"]
    assert second == first
