"""Дыра покрытия FR-17: GET /api/suggestions, «только заведенные» (QA-цикл 1.5).

4 approved-кейса `test-model/approved/add-suggestions/sugg-01.md`
(review-001 — вердикт «одобрить», 5 minor):
- TC-sugg-006 (CHK-S-6) — осиротевший тег и пустая (NULL) категория
  отсутствуют в подсказках (Scenario 6 спеки add-suggestions);
- TC-sugg-008 (CHK-S-8) — категории «пустая строка» и NULL не проходят
  в список: в подвыборке префикса только теги;
- TC-sugg-009 (CHK-S-9) — DELETE задачи убирает ее теги/категорию из
  подсказок без рестарта приложения (пересчет на каждый GET).

Кейс TC-sugg-007 — UI (datalist + свободный ввод на /search), размещен
в `tests/web/test_search_suggestions_ui.py` (скоуп Playwright-сьюта).

Учет minor ревью-001 при развертке кейсов:
- №2: доступное имя поля — дословно «Теги (через запятую)» (search.html);
  касается TC-sugg-007, учтено в web-тесте;
- №3: вместо строгой идентичности полного списка — префиксное сравнение
  подвыборки `QAT-SUGG*` (общий стенд, чужие записи между снимками не
  роняют тест); инвариант сортировки `s == sorted(s)` сохранен;
- №4: все созданные задачи удаляются в teardown (fixture-финализаторы);
- №1: вход owner выполняется фикстурой `owner_session` (логин/пароль
  seed из `tests/api/conftest.py`, источник — `app/seed_users.py`);
- №5: основание префиксной подвыборки QAT-SUGG8 (TC-sugg-008) — SQL
  фильтра `category IS NOT NULL AND category != ''` действует построчно
  на каждой задаче, поэтому подвыборка эквивалентно проверяет границу
  на общем стенде без воспроизведения «ВСЕ категории пусты».

Изоляция: уникальные префиксы QAT-SUGG/QAT-SUGG8/QAT-SUGG9 не пересекаются
с dev-тестами (`QAT-` в test_suggestions.py) и между собой; удаление
тестовых задач — только через DELETE /api/tasks/{id} (физическое; строки
task_tags каскадом, tags остаются — источник осиротевших тегов кейса).
"""

import pytest

pytestmark = [pytest.mark.api, pytest.mark.should]


@pytest.fixture
# regression: keep — fixture данных keep-тестов FR-17 (TC-sugg-006/008/009):
# устойчивое поведение спеки add-suggestions, не разовое.
def sugg_gap_tasks(api):
    """Фабрика задач кейсов FR-17 с гарантированной уборкой в teardown.

    Возвращает create(title, **payload) -> dict; все созданные id удаляются
    через DELETE /api/tasks/{id} после теста (minor №4 ревью-001).
    """
    created: list[dict] = []

    def _create(title: str, **payload) -> dict:
        task = api.create_ok(title, **payload)
        created.append(task)
        return task

    yield _create

    for task in created:
        api.delete(task["id"])


def _suggestions(owner_session, base_url) -> list[str]:
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"suggestions"}
    assert isinstance(body["suggestions"], list)
    return body["suggestions"]


# regression: keep — устойчивое поведение FR-17 (Scenario 6 спеки:
# «только заведенные» — постоянное контрактное требование, не разовое).
def test_suggestions_exclude_orphan_tag_and_null_category(
    owner_session, base_url, sugg_gap_tasks, r2_seed_categories
):
    """TC-sugg-006 (CHK-S-6, негативный): осиротевший тег и пустая (NULL)
    категория отсутствуют в подсказках; живой тег присутствует; пустой
    строки нет; список отсортирован (Scenario 6 спеки add-suggestions).

    R2: QAT-SUGG-Кат-А заводится в справочнике (FR-21), cleanup в конце."""
    category_id = r2_seed_categories.create_ok("QAT-SUGG-Кат-А")["id"]
    # Шаг 1: задача-носитель будущего осиротевшего тега.
    carrier = sugg_gap_tasks(
        "QAT-SUGG-носитель",
        category="QAT-SUGG-Кат-А",
        tags=["QAT-SUGG-Тег-Осирот"],
    )
    # Шаг 2: задача с пустой категорией (поле не передано → NULL, sdd §3.2)
    # и живым тегом.
    sugg_gap_tasks("QAT-SUGG-пустая-кат", tags=["QAT-SUGG-Тег-Б"])
    # Шаг 3: удалить задачу-носитель (204; контроль 404 — физическое
    # удаление, sdd §3.2). Строка tags остается (каскад только task_tags,
    # sdd §4) — тег становится осиротевшим.
    resp = owner_session.delete(f"{base_url}/api/tasks/{carrier['id']}")
    assert resp.status_code == 204
    assert owner_session.get(
        f"{base_url}/api/tasks/{carrier['id']}"
    ).status_code == 404

    # Шаг 4: подсказки.
    suggestions = _suggestions(owner_session, base_url)

    assert "QAT-SUGG-Тег-Осирот" not in suggestions, (
        "осиротевший тег (только у удаленной задачи) попал в подсказки"
    )
    assert "QAT-SUGG-Тег-Б" in suggestions, (
        "живой тег существующей задачи отсутствует"
    )
    assert "" not in suggestions, "пустая строка прошла в подсказки"
    assert "QAT-SUGG-Кат-А" not in suggestions, (
        "категория удаленного носителя всплыла в подсказках"
    )
    # Инвариант сортировки (minor №3: инвариант сохранен).
    assert suggestions == sorted(suggestions)
    # teardown r2: категория свободна (носитель удален) → удалить
    r2_seed_categories.untrack(category_id)
    assert r2_seed_categories.delete(category_id).status_code == 200


# regression: keep — устойчивое поведение FR-17: граница фильтра категорий
# (пустая строка/NULL) — постоянный инвариант UNION, не разовый случай.
def test_suggestions_all_categories_empty_only_tags(
    owner_session, base_url, sugg_gap_tasks
):
    """TC-sugg-008 (CHK-S-8, граничный): категории «пустая строка» и NULL
    в подсказки не проходят — в подвыборке префикса QAT-SUGG8 ровно два
    тега; пустой строки и строко-подобных null нет; подвыборка отсортирована."""
    # Основание подвыборки (minor №5 ревью-001): фильтр
    # `category IS NOT NULL AND category != ''` действует на каждую задачу,
    # поэтому префиксная подвыборка эквивалентно проверяет границу на общем
    # стенде — воспроизводить «ВСЕ категории пусты» не требуется.
    # Шаг 1: категория — пустая строка.
    sugg_gap_tasks(
        "QAT-SUGG8-гран-пустая", category="", tags=["QAT-SUGG8-Тег-1"]
    )
    # Шаг 2: категория не задана вовсе (NULL).
    sugg_gap_tasks("QAT-SUGG8-гран-null", tags=["QAT-SUGG8-Тег-2"])

    # Шаг 3: подсказки, подвыборка префикса QAT-SUGG8 (minor №3).
    suggestions = _suggestions(owner_session, base_url)
    subset = [s for s in suggestions if s.startswith("QAT-SUGG8")]

    assert sorted(subset) == ["QAT-SUGG8-Тег-1", "QAT-SUGG8-Тег-2"], (
        f"подвыборка QAT-SUGG8 != [Тег-1, Тег-2]: {subset}"
    )
    assert "" not in suggestions, "пустая строка прошла в подсказки"
    for null_like in ("null", "None", "[]"):
        assert null_like not in suggestions, (
            f"строко-подобный null {null_like!r} прошел в подсказки"
        )
    assert subset == sorted(subset)


# regression: keep — устойчивое поведение FR-17 (состояние): пересчет
# подсказок на каждый GET без кеша — постоянное контрактное свойство.
def test_suggestions_task_delete_updates_without_restart(
    owner_session, base_url, sugg_gap_tasks, r2_seed_categories
):
    """TC-sugg-009 (CHK-S-9, негативный): DELETE задачи убирает ее теги
    и категорию из подсказок без рестарта приложения и сброса кеша —
    состояние пересчитывается на каждый GET; прочие значения подвыборки
    не искажены; список отсортирован.

    R2: QAT-SUGG9-Кат заводится в справочнике (FR-21), cleanup в конце."""
    category_id = r2_seed_categories.create_ok("QAT-SUGG9-Кат")["id"]
    # Шаг 1: задача с уникальными категорией и тегом (префикс QAT-SUGG9 —
    # исключает «спасение» значений другими задачами).
    task = sugg_gap_tasks(
        "QAT-SUGG9-исходная",
        category="QAT-SUGG9-Кат",
        tags=["QAT-SUGG9-Тег"],
    )

    def subset(items: list[str]) -> list[str]:
        return [s for s in items if s.startswith("QAT-SUGG9")]

    # Шаг 2: контроль «до» — оба значения присутствуют.
    before = _suggestions(owner_session, base_url)
    assert "QAT-SUGG9-Кат" in before
    assert "QAT-SUGG9-Тег" in before
    before_subset = subset(before)

    # Шаг 3: удалить задачу (204, физическое удаление).
    resp = owner_session.delete(f"{base_url}/api/tasks/{task['id']}")
    assert resp.status_code == 204

    # Шаг 4: контроль «после», без рестарта и сброса кеша (minor №3:
    # префиксное сравнение вместо строгой идентичности полного списка).
    after = _suggestions(owner_session, base_url)
    assert "QAT-SUGG9-Кат" not in after, (
        "категория удаленной задачи осталась в подсказках"
    )
    assert "QAT-SUGG9-Тег" not in after, (
        "тег удаленной задачи остался в подсказках"
    )
    expected_remaining = [
        s for s in before_subset if s not in ("QAT-SUGG9-Кат", "QAT-SUGG9-Тег")
    ]
    assert subset(after) == expected_remaining, (
        "прочие значения подвыборки QAT-SUGG9 искажены"
    )
    assert after == sorted(after)
    # teardown r2: носитель удален (шаг 3), категория свободна → удалить
    r2_seed_categories.untrack(category_id)
    assert r2_seed_categories.delete(category_id).status_code == 200
