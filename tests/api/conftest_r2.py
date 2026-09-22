"""Конфигурация набора add-r2-categories-settings: категории, миграция,
fast×priority, seed/cleanup справочника (tests/README.md, раздел Релиз 2).

Разделяемые константы и session-scope фикстуры (кейсы TC-env-001/002 —
сами фикстуры-тесты, см. test_r2_env.py):

- ``r2_seed_categories`` (session): seed справочника `Дом`/`Работа`/`Личное`
  ДО любого прогона (TC-env-001, CHK-139) + cleanup `QAT-*`-хвостов после
  сессии и контроль целостности seed (TC-env-002, CHK-140);
- ``category_directory``: API-хелпер справочника (list/create/rename/delete)
  с фабрикой гарантированного удаления QAT-категорий в teardown;
- ``r2_fast_line``: вход без активных fast-задач (предусловие негативов
  fast×priority) с восстановлением исходного состояния после теста;
- ``migr_temp_db``: временная копия БД для прогонов миграционного скрипта
  (`python -m app.migrate_categories`) с гарантированным удалением;
- ``verify_snapshot_dir``: каталог снимков «до/после» миграции (CSV),
  удаляется в teardown.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import uuid

import pytest
import requests

from conftest import (
    OWNER_LOGIN,
    OWNER_PASSWORD,
    TITLE_PREFIX,
    login_session,
)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend")
PYTHON_ENV = os.environ.get("R2QA_PYTHON", sys.executable)

# Seed-список справочника (TC-env-001, тестовые данные кейса).
SEED_CATEGORIES = ("Дом", "Работа", "Личное")


class CategoriesApi:
    """Хелпер /api/categories (sdd r2 §3.1) + фабрика cleanup-категорий."""

    def __init__(self, base_url: str, session: requests.Session):
        self.base_url = base_url
        self.session = session
        self._tracked: list[int] = []

    def list_all(self) -> requests.Response:
        return self.session.get(f"{self.base_url}/api/categories")

    def names(self) -> list:
        resp = self.list_all()
        assert resp.status_code == 200, f"setup: GET /api/categories: {resp.status_code} {resp.text}"
        return [c["name"] for c in resp.json()["categories"]]

    def create(self, name: str) -> requests.Response:
        return self.session.post(f"{self.base_url}/api/categories", json={"name": name})

    def create_ok(self, name: str) -> dict:
        """Создать категорию, вернуть тело 201; id берется под cleanup."""
        resp = self.create(name)
        assert resp.status_code == 201, f"setup: POST /api/categories {name!r}: {resp.status_code} {resp.text}"
        body = resp.json()
        self.track(body["id"])
        return body

    def rename(self, category_id: int, name: str) -> requests.Response:
        return self.session.patch(f"{self.base_url}/api/categories/{category_id}", json={"name": name})

    def delete(self, category_id: int) -> requests.Response:
        return self.session.delete(f"{self.base_url}/api/categories/{category_id}")

    def track(self, category_id: int) -> None:
        """Категория удаляется в teardown (если еще существует)."""
        if category_id not in self._tracked:
            self._tracked.append(category_id)

    def untrack(self, category_id: int) -> None:
        """Категория уже удалена самим тестом — teardown не трогает."""
        if category_id in self._tracked:
            self._tracked.remove(category_id)

    def cleanup_tracked(self) -> None:
        """Удалить отслеженные QAT-категории (перевод задач-носителей —
        зона конкретного теста: справочник чистит только свои записи)."""
        for category_id in self._tracked:
            try:
                resp = self.delete(category_id)
                if resp.status_code == 409:  # задачи-носители — убрать самому
                    detail = resp.json()
                    assert False, f"teardown: категория {category_id} используется: {detail}"
            except requests.RequestException:
                pass
        self._tracked.clear()


@pytest.fixture(scope="session")
def categories_api_factory(base_url):
    """Фабрика CategoriesApi — используется session-scope seed-фикстурой."""

    def _make() -> CategoriesApi:
        session = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
        return CategoriesApi(base_url, session)

    return _make


@pytest.fixture(scope="session")
def r2_seed_categories(base_url, categories_api_factory):
    """Seed справочника категорий на сессию (TC-env-001/002, CHK-139/140).

    ДО любого прогона: в справочнике есть `Дом`, `Работа`, `Личное` —
    создаются при отсутствии (идемпотентно; 409 дубля = уже есть = ОК).
    ПОСЛЕ сессии: удаление `QAT-*`-хвостов упавших тестов (справочник
    общесистемный — ОГР-7; cleanup фикстуры убирает и категории, impact §4.2).
    """
    api = categories_api_factory()
    for name in SEED_CATEGORIES:
        resp = api.create(name)
        assert resp.status_code in (201, 409), (
            f"seed: создание категории {name!r}: {resp.status_code} {resp.text}"
        )
    names = api.names()
    for name in SEED_CATEGORIES:
        assert name in names, f"seed: категории {name!r} нет в справочнике: {names}"
    try:
        yield api
    finally:
        # cleanup QAT-хвостов (TC-env-002 шаг 4: 0 забытых QAT-* категорий)
        try:
            for name in api.names():
                if name.startswith(TITLE_PREFIX):
                    listed = api.list_all().json()["categories"]
                    category_id = next(c["id"] for c in listed if c["name"] == name)
                    api.delete(category_id)
        except requests.RequestException:
            pass
        api.session.close()


@pytest.fixture
def category_directory(r2_seed_categories, owner_session, base_url) -> CategoriesApi:
    """Хелпер справочника на тест: seed-гарантия + cleanup своих категорий."""
    api = CategoriesApi(base_url, owner_session)
    yield api
    api.cleanup_tracked()


@pytest.fixture
def r2_fast_line(api) -> dict:
    """Вход «активных fast-задач нет» (негативы fast×priority, кейсы
    TC-fast2-004…008) с восстановлением после теста.

    До теста: активные fast-задачи (чужие/хвосты) переводятся в done.
    После теста: доска возвращается к исходному набору активных fast
    (задачи теста удаляются собственным teardown через `api`).
    """
    done_fast = []

    def _free() -> None:
        board = api.board()
        assert board.status_code == 200, f"setup: GET /api/board: {board.status_code}"
        for column in board.json()["columns"].values():
            for task in column:
                if task["is_fast"] and task["status"] in ("todo", "in_progress"):
                    if task["id"] not in done_fast:
                        done_fast.append(task["id"])
                        resp = api.move(task["id"], "done")
                        assert resp.status_code == 200, (
                            f"setup: вывод fast {task['title']!r} в done: {resp.status_code} {resp.text}"
                        )

    _free()
    yield {"freed": done_fast}
    # восстановление: переводим back (best-effort — статус мог измениться)
    for task_id in done_fast:
        try:
            api.move(task_id, "todo")
        except requests.RequestException:
            pass


# ==========================================================================
# Миграционный контур: временная БД + запуск скрипта миграции (sdd r2 §5,
# python -m app.migrate_categories). Ничего на стенде не меняется.
# ==========================================================================


def _copy_db(source_db_path: str, target_path: str) -> None:
    """Копия SQLite-БД со sweet-файлами WAL/SHM (консистентный слепок:
    контрольная точка WAL через sqlite3.Connection.backup)."""
    src = sqlite3.connect(source_db_path)
    try:
        dst = sqlite3.connect(target_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _run_migration(db_path: str) -> subprocess.CompletedProcess:
    """Запуск скрипта миграции (sdd r2 §5) на указанной БД.

    Возвращает CompletedProcess; выход 0 — сверка зелёная, 1 — расхождение
    (NFR-8: внедрение не завершено).
    """
    env = dict(os.environ)
    env["DB_PATH"] = db_path
    env["SECRET_KEY"] = env.get("SECRET_KEY", "qa-migration-secret")
    env.pop("EKOTOV_WIKI_DB_PATH", None)
    return subprocess.run(
        [PYTHON_ENV, "-m", "app.migrate_categories"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="session")
def backend_dir() -> str:
    return BACKEND_DIR


@pytest.fixture
def migr_temp_db(tmp_path):
    """Временная копия БД стенда для миграционных прогонов (TC-migr-*, TC-fast2-010).

    Возвращает (path, run_migration, execute):
    - path — файл временной БД (schema+data = слепок стенда);
    - run_migration() -> CompletedProcess — прогон скрипта миграции;
    - execute(sql, params) — прямой SQL по временной БД (подготовка данных «до»).
    """
    source_db = os.environ.get("EKOTOV_WIKI_DB_PATH")
    if not source_db:
        pytest.skip("нужен env EKOTOV_WIKI_DB_PATH (путь SQLite-БД приложения)")
    db_path = str(tmp_path / "migr.db")
    _copy_db(source_db, db_path)
    # миграционные кейсы требуют «чистый» справочник ДО миграции (предусловие
    # TC-migr-001…006, TC-fast2-010): seed-категории стенда в копию не попадают
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM categories")
        conn.commit()
    finally:
        conn.close()

    def execute(sql: str, params: tuple = ()) -> list:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(sql, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def run_migration() -> subprocess.CompletedProcess:
        return _run_migration(db_path)

    yield db_path, run_migration, execute
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def verify_snapshot_dir(tmp_path):
    """Каталог снимков миграции (snapshot_tasks_before/after.csv, TC-migr-005)."""
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    yield str(snapshot_dir)
    shutil.rmtree(snapshot_dir, ignore_errors=True)


@pytest.fixture
def unique_category() -> str:
    """Уникальное имя тестовой категории (изоляция параллельных прогонов)."""
    return f"{TITLE_PREFIX}{uuid.uuid4().hex[:8]}"
