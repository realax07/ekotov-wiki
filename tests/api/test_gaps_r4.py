"""QA-цикл 6.1: гэпы Р4 (change add-r4-user-profile-ticket-view).

4 approved-кейса `test-model/new/add-r4-user-profile-ticket-view/`
(review-009 — вердикт APPROVE 8/8; автоматизированы api-кейсы, web —
tests/web/test_assignu_r4_ui.py, 3 кейса — manual, НЕ автоматизируются):
- TC-search-r4-101 (CHK-R4-99) — объект-сравнение ВСЕГО состава полей
  выдачи поиска GET + advanced, включая tags-массив (урок дефекта
  8225bbf: search.py row[10] давал tags=[] в каждой строке; класс
  дефекта переносится в API-сьют объект-сравнением, не выборочными
  проверками). Advanced-шаг — `tag IN (...)` по исправленному кейсу
  (грамматика advanced для tag допускает ТОЛЬКО IN — search.py
  «tag supports only IN (...)»; `tag = "..."` дает 400);
- TC-sugg-r4-101 (CHK-R4-102) — GET /api/suggestions/users: состав из
  данных (JOIN, не справочник), сортировка, UNION-уникальность по ветке
  wife (задача B: wife и creator, и исполнитель), 401 без сессии;
- TC-sugg-r4-102 (CHK-R4-102, частично) — шаги 1–3/5: пользователь
  «призрак» (только в справочнике users, без задач) НЕ попадает в
  подсказки. ШАГ 4 (пустая БД задач → 200 {"users": []}) НЕ
  автоматизирован: api-стенд по conftest — ВНЕШНИЙ (EKOTOV_WIKI_BASE_URL),
  «пустая БД» автотестом не создается; выполняется однократно вручную
  на временной БД (как tests/web conftest) либо отдельным ручным
  смоуком — примечание кейса и review-009; переводится в автопрогон
  без правки кейса при появлении session-scope стенда с tmp-БД;
- TC-profile-r4-101 (CHK-R4-103) — рассинхрон role в БД (значение вне
  справочника VALID_ROLES, мимо PUT-валидации): GET /api/profile и
  /api/auth/me отдают БД-значение как есть (не 5xx, без нормализации),
  права не зависят от role (ОВ-21/NFR-4), корректный PUT «лечит».
  Требует db-крюк EKOTOV_WIKI_DB_PATH (skip без env) — как
  TC-passwd-004/TC-me4-002 в test_profile_r4.py.

Формат: 1 кейс = 1 тест (contract 6); TC-ID в docstring; изоляция QAT-;
cleanup fixture-финализаторами; time.sleep = 0.
"""

import sqlite3

import pytest
import requests

pytestmark = [pytest.mark.api]

from conftest import DB_PATH_ENV  # noqa: E402

OWNER = "owner"
WIFE = "wife"

UNAUTHORIZED = {"error": "unauthorized"}  # app/middleware.py, единый текст

# Полный состав строки выдачи поиска (13 ключей контракта, sdd §3.2/§3.5).
SEARCH_KEYS = {
    "id",
    "title",
    "description",
    "priority",
    "category",
    "due_date",
    "tags",
    "is_fast",
    "status",
    "done_at",
    "archived_at",
    "creator",
    "assigned",
}

# Обязательный состав ответа профиля / me (sdd §3.1a-кватер).
PROFILE_KEYS = {"login", "display_name", "role", "bio", "avatar_url"}
ME_KEYS = {"user", "display_name", "role", "bio", "avatar_url", "id"}

OWNER_DEFAULT_ROLE = "Product manager"  # ОВ-21 (бэкфилл migrate_r4)
PE_ROLE = "Product engineer"


def _get_user_ids(base_url, session) -> dict:
    resp = session.get(f"{base_url}/api/users")
    assert resp.status_code == 200, resp.text
    return {u["login"]: u["id"] for u in resp.json()["users"]}


# ==========================================================================
# TC-search-r4-101 — объект-сравнение выдачи поиска (GET + advanced)
# ==========================================================================
@pytest.mark.must
def test_search_r4_101_object_comparison_get_and_advanced(api, wife_session):
    """TC-search-r4-101 (CHK-R4-99, гран. Must): выдача поиска — строка
    ПОБИТОВО равна эталонному объекту задачи (множество ключей + значения
    каждого поля), включая tags как МАССИВ ЗНАЧЕНИЙ — и в GET /api/search,
    и в POST /api/search/advanced (`tag IN (...)`). Граничный контроль:
    задача без тегов не находится по tag и имеет tags == [] (ровно пустой
    список). Объект-сравнение переносит класс дефекта 8225bbf (tags=[] в
    каждой строке) в API-сьют (урок волны 5)."""
    wife_id = _get_user_ids(api.base_url, api.session)[WIFE]

    # Шаг 2: эталонная задача со ВСЕМИ атрибутами; ответ POST — эталон E.
    reference = api.create_ok(
        "QAT-s101-эталон",
        description="QAT описание s101",
        priority="high",
        category="Работа",
        due_date="2026-12-01",
        tags=["QAT-s101-тег-А", "QAT-s101-тег-Б"],
        assigned_to_id=wife_id,
    )
    assert set(reference.keys()) == SEARCH_KEYS, reference.keys()

    def _assert_search_matches_reference(resp, source: str) -> None:
        assert resp.status_code == 200, f"{source}: {resp.status_code} {resp.text}"
        results = resp.json()["results"]
        assert [t["title"] for t in results] == ["QAT-s101-эталон"], (
            f"{source}: ровно эталон, получено {results}"
        )
        # Шаги 4/5: ОБЪЕКТ-СРАВНЕНИЕ (не выборочное) — полное равенство.
        assert results[0] == reference, (
            f"{source}: строка выдачи != эталону POST:\n{results[0]}\n!=\n{reference}"
        )
        # Точный состав и порядок tags (массив значений, не «не пустой»).
        assert results[0]["tags"] == ["QAT-s101-тег-А", "QAT-s101-тег-Б"]

    # Шаг 3–4: GET /api/search?tag=... — объект-сравнение с эталоном.
    _assert_search_matches_reference(api.search(tag="QAT-s101-тег-А"), "GET search")

    # Шаг 5: advanced — `tag IN (...)` (грамматика: только IN для tag),
    # та же _row_to_task_with_users → то же объект-сравнение.
    resp = api.advanced(f'assigned = "{WIFE}" AND tag IN ("QAT-s101-тег-А")')
    _assert_search_matches_reference(resp, "advanced")

    # Шаг 6: гран. контроль — задача БЕЗ тегов.
    untagged = api.create_ok("QAT-s101-без-тегов")
    resp = api.search(tag="QAT-s101-тег-А")
    assert [t["title"] for t in resp.json()["results"]] == ["QAT-s101-эталон"], (
        "задача без тегов найдена по чужому tag"
    )
    resp = api.search(archived="all")
    assert resp.status_code == 200
    match = [t for t in resp.json()["results"] if t["id"] == untagged["id"]]
    assert len(match) == 1, "задача без тегов не найдена в archived=all"
    # tags == [] — ровно пустой список (тип list, не null, не отсутствие).
    assert match[0]["tags"] == [] and isinstance(match[0]["tags"], list), match[0]


# ==========================================================================
# TC-sugg-r4-101 — GET /api/suggestions/users: состав/сортировка/UNION/401
# ==========================================================================
@pytest.mark.should
def test_sugg_r4_101_users_suggestions_composition_union_sorted_401(
    api, wife_session
):
    """TC-sugg-r4-101 (CHK-R4-102, Should): 401 без сессии; состав —
    только логины из creator/assigned существующих задач (JOIN, не весь
    справочник); задача B (сессия wife, assigned=wife) ставит wife в ОБЕ
    ветки UNION — wife входит ровно ОДИН раз; сортировка по возрастанию;
    каждый элемент — строка-логин."""
    wife_id = _get_user_ids(api.base_url, api.session)[WIFE]

    # Шаг 1: без сессии — 401 (путь не в exempt-списке, NFR-7).
    resp = requests.get(f"{api.base_url}/api/suggestions/users")
    assert resp.status_code == 401, resp.status_code
    assert resp.json() == UNAUTHORIZED

    # Шаг 2: A (owner, assigned=wife); B (сессия WIFE, assigned=wife —
    # wife в creator- И assigned-ветке UNION); C (owner, без исполнителя).
    api.create_ok("QAT-s102-А", assigned_to_id=wife_id)
    resp = wife_session.post(
        f"{api.base_url}/api/tasks",
        json={"title": "QAT-s102-Б", "assigned_to_id": wife_id},
    )
    assert resp.status_code == 201, resp.text
    api.create_ok("QAT-s102-В")

    # Шаг 3: подсказки (сессия owner).
    resp = api.session.get(f"{api.base_url}/api/suggestions/users")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Шаг 4: состав — единственный ключ users; только логины из данных.
    assert set(body.keys()) == {"users"}, body.keys()
    users = body["users"]
    assert OWNER in users and WIFE in users, users
    assert set(users) <= {OWNER, WIFE}, users  # посторонних логинов нет
    assert all(isinstance(u, str) for u in users), users

    # Шаг 5: сортировка и UNION-уникальность (wife из двух веток — один раз).
    assert users == sorted(users), users
    assert len(users) == len(set(users)), users


# ==========================================================================
# TC-sugg-r4-102 (частично: шаги 1–3/5) — «призрак» не попадает в подсказки
# ==========================================================================
@pytest.fixture
def sugg_db_path():
    """Путь SQLite-БД стенда; skip без env — как TC-passwd-004/TC-me4-002."""
    import os

    path = os.environ.get(DB_PATH_ENV)
    if not path:
        pytest.skip(f"нужен env {DB_PATH_ENV} (путь SQLite-БД приложения)")
    return path


@pytest.mark.should
def test_sugg_r4_102_directory_only_user_absent_from_suggestions(
    api, sugg_db_path
):
    """TC-sugg-r4-102 (CHK-R4-102, Should; автоматизированы шаги 1–3/5):
    пользователь из справочника users, НЕ встречающийся ни в creator_id,
    ни в assigned_to_id задач, отсутствует в GET /api/suggestions/users
    (контракт «JOIN, не весь справочник»). БД-правки атомарны и
    откатываются (шаги 2/5).

    ШАГ 4 (пустая БД задач → 200 {"users": []}) — НЕ автоматизирован:
    стенд api-сьюта внешний (EKOTOV_WIKI_BASE_URL), «пустая БД»
    автотестом не создается — ручной смоук на временной БД (примечание
    кейса/review-009); без правки кейса переводится в автопрогон при
    появлении session-scope стенда с tmp-БД (модель tests/web)."""
    # Шаг 1: убрать QAT-хвосты; контролировать отсутствие задач с логинами
    # seed у нашего стенда (на общем стенде с чужими данными —fallback
    # кейса: проверять только отсутствие «призрака»).
    api.cleanup_all()

    def _foreign_tasks() -> list:
        found = []
        for params in (
            {"assigned": OWNER, "archived": "all"},
            {"creator": OWNER, "archived": "all"},
            {"assigned": WIFE, "archived": "all"},
            {"creator": WIFE, "archived": "all"},
        ):
            resp = api.search(**params)
            assert resp.status_code == 200, resp.text
            found.extend(resp.json()["results"])
        return found

    foreign = _foreign_tasks()
    strict_empty = not foreign

    conn = sqlite3.connect(sugg_db_path)
    try:
        # Шаг 2: «призрак» — только в справочнике (password_hash NOT NULL,
        # placeholder); НИ ОДНОЙ задачи с ним в creator/assigned.
        conn.execute(
            "INSERT INTO users (login, password_hash) VALUES (?, ?)",
            ("QAT-s102-ghost", "qat-ghost-placeholder-not-a-hash"),
        )
        conn.commit()
        # Шаг 3: подсказки.
        resp = api.session.get(f"{api.base_url}/api/suggestions/users")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"users"}, body.keys()
        # Логин-«призрак» отсутствует: список = значения столбцов задач,
        # не справочник пользователей.
        assert "QAT-s102-ghost" not in body["users"], body
        if strict_empty:
            # Управляемое «почти пустое» множество: задач с seed-логинами
            # нет → подсказки пусты ровно (граница UNION над пустыми
            # ветками, близкая к ручному шагу 4).
            assert body["users"] == [], body
        else:
            assert set(body["users"]) <= {OWNER, WIFE}, body
    finally:
        # Шаг 5: откат БД-правки (fixture-финализатор семантики кейса).
        conn.execute("DELETE FROM users WHERE login = ?", ("QAT-s102-ghost",))
        conn.commit()
        row = conn.execute(
            "SELECT id FROM users WHERE login = ?", ("QAT-s102-ghost",)
        ).fetchone()
        assert row is None, "«призрак» не удален из справочника (teardown)"
        conn.close()


# ==========================================================================
# TC-profile-r4-101 — рассинхрон role (значение вне справочника в БД)
# ==========================================================================
@pytest.mark.should
def test_profile_r4_101_role_desync_read_and_heal(base_url, owner_session, api):
    """TC-profile-r4-101 (CHK-R4-103, гран. Should): БД-значение role вне
    справочника VALID_ROLES (мимо PUT-валидации) — GET /api/profile и
    /api/auth/me отвечают 200 и отдают значение КАК ЕСТЬ (read-only
    зеркало данных; 500/нормализация = дефект); права не зависят от role
    (board 200, создание задачи 201 — ОВ-21/NFR-4); корректный PUT с
    валидной ролью → 200 и «лечит» рассинхрон (read-back). Ни один шаг
    не дает 5xx. Требует db-крюк EKOTOV_WIKI_DB_PATH — skip без env."""
    import os

    db_path = os.environ.get(DB_PATH_ENV)
    if not db_path:
        pytest.skip(f"нужен env {DB_PATH_ENV} (путь SQLite-БД приложения)")

    from conftest import OWNER_LOGIN, db_select_one, db_update

    # Шаг 1: baseline — роль после миграции (ОВ-21).
    resp = owner_session.get(f"{base_url}/api/profile")
    assert resp.status_code == 200
    assert resp.json()["role"] == OWNER_DEFAULT_ROLE

    def _set_role(value: str) -> None:
        db_update(
            db_path,
            "UPDATE users SET role = ? WHERE login = ?",
            (value, OWNER_LOGIN),
        )
        row = db_select_one(
            db_path, "SELECT role FROM users WHERE login = ?", (OWNER_LOGIN,)
        )
        assert row[0] == value, row

    # Шаг 2: инъекция роли вне справочника (рассинхрон).
    _set_role("SuperAdmin")
    try:
        # Шаг 3: GET /api/profile — 200, роль как в БД, без нормализации.
        resp = owner_session.get(f"{base_url}/api/profile")
        assert resp.status_code == 200, resp.status_code
        body = resp.json()
        assert set(body.keys()) == PROFILE_KEYS
        assert body["role"] == "SuperAdmin", body

        # Шаг 4: GET /api/auth/me — 200, 5 ключей, роль — БД-строка.
        resp = owner_session.get(f"{base_url}/api/auth/me")
        assert resp.status_code == 200, resp.status_code
        me = resp.json()
        assert set(me.keys()) == ME_KEYS, me.keys()
        assert me["role"] == "SuperAdmin", me

        # Шаг 5: каскада нет — доска и создание задач работают
        # (роль — чисто отображаемое поле, NFR-4).
        resp = owner_session.get(f"{base_url}/api/board")
        assert resp.status_code == 200, resp.status_code
        trial = api.create_ok("QAT-s103-проба")
        resp = api.delete(trial["id"])
        assert resp.status_code == 204, resp.status_code

        # Шаг 6: PUT с валидной ролью «лечит» рассинхрон.
        resp = owner_session.put(
            f"{base_url}/api/profile",
            json={"display_name": None, "role": PE_ROLE, "bio": None},
        )
        assert resp.status_code == 200, resp.text
        resp = owner_session.get(f"{base_url}/api/profile")
        assert resp.status_code == 200
        assert resp.json()["role"] == PE_ROLE, resp.json()
    finally:
        # Шаг 7: teardown — восстановить роль (иначе повторный migrate_r4
        # упадет на сверке; см. impact §4.1), контроль SELECT.
        _set_role(OWNER_DEFAULT_ROLE)
