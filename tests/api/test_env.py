"""Средовые кейсы env (Релиз 2): TC-env-001/002 (CHK-139/140;
approved/add-r2-categories-settings/TC-env-*.md) — сами session-scope
фикстуры, автоматизированные как тесты.

- TC-env-001: seed справочника `Дом`/`Работа`/`Личное` (плюс автосоздание
  QAT-*) выполнен session-scope фикстурой ``r2_seed_categories``
  (conftest.py) ДО любого прогона; тест проверяет состояние справочника
  и семантику фикстуры (создание при отсутствии, идемпотентность повторов).
- TC-env-002: изоляция и cleanup — снимки справочника до/после, 0 забытых
  QAT-* категорий, seed цел; teardown фикстуры ``r2_seed_categories``
  убирает QAT-хвосты (справочник общесистемный, ОГР-7, impact §4.2).
"""

import pytest

pytestmark = [pytest.mark.api]

SEED_CATEGORIES = ("Дом", "Работа", "Личное")


@pytest.mark.must
def test_seed_directory_present_before_any_run(r2_seed_categories):
    """TC-env-001 (CHK-139): после старта прогона справочник содержит
    `Дом`, `Работа`, `Личное` — seed создан session-scope фикстурой
    ДО тестов (шаги 1/3 кейса); зависимые тесты проходят setup (шаг 2 —
    весь набор r2 выполняется на этой фикстуре). Шаг 4 (негатив-контроль
    «без seed») — документирован здесь: падение зависимого теста без seed
    происходит на SETUP (422 category not in categories / отсутствие
    категории) — средовый отказ, не дефект продукта (impact §4.1)."""
    names = r2_seed_categories.names()
    for name in SEED_CATEGORIES:
        assert name in names, f"seed-категории {name!r} нет в справочнике: {names}"

    # семантика фикстуры: повторное создание существующей — не дубли (идемпотентно)
    resp = r2_seed_categories.create("Дом")
    assert resp.status_code == 409, f"повторный seed создал дубль: {resp.status_code} {resp.text}"
    names_after = r2_seed_categories.names()
    assert names_after.count("Дом") == 1


@pytest.mark.must
def test_directory_isolation_and_cleanup(category_directory, r2_seed_categories):
    """TC-env-002 (CHK-140): справочник до прогона = справочнику после
    (S1 == S0); 0 забытых QAT-* категорий; seed `Дом`/`Работа`/`Личное`
    цел. Внутри теста создается и удаляется QAT-категория (имитация
    категории кейсов) — fixture teardown + явный DELETE возвращают S0."""
    s0 = r2_seed_categories.names()

    created = category_directory.create_ok("QAT-изол-проверка")
    assert "QAT-изол-проверка" in r2_seed_categories.names()

    assert category_directory.delete(created["id"]).status_code == 200
    category_directory.untrack(created["id"])

    s1 = r2_seed_categories.names()
    assert s1 == s0, f"справочник изменился: S0={s0} S1={s1}"
    assert not [n for n in s1 if n.startswith("QAT-")], f"забытые QAT-*: {s1}"
    for name in SEED_CATEGORIES:
        assert name in s1, f"seed-категория {name!r} потеряна"
