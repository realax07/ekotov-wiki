# BUG-006: `pytest tests/` не собирается — pytest_plugins в не-корневом conftest (hard error на pytest 8+)

- **ID:** BUG-006
- **Дата:** 2026-10-05
- **Окружение:** локальный стенд QA 2.1, ветка `add-microservices-full`, HEAD `785fa39`
  (родитель `54213db`); Python 3.11.16, pytest 9.1.1, venv `/home/openclaw/venvs/wiki`.
- **Severity:** major (блокер единого прогона полного регресса одной командой;
  обходной путь существует — покаталоговый запуск).
- **Корреляция flowctl:** 9ba2c5ec1030458f81c906b9150fa425 (QA-задача 2.1
  add-microservices-full).

## Трассировка

- TC-walk-001 (probe сквозного прогона, Флоу 4 enforcing) — команда
  `python -m pytest tests/ -q` из корня репозитория (эталон в tests/README.md,
  раздел «Запуск», п.3) прерывается на СБОРЕ тестов, до исполнения любого теста.
- Затронут весь совместный прогон api + web + probe (tests/README.md обещает
  «совместный прогон pytest tests/ работает», раздел «Примечание» R2).

## Шаги воспроизведения

```bash
cd /home/openclaw/ekotov-wiki
/home/openclaw/venvs/wiki/bin/python -m pytest tests/ -q --co
```

## Ожидание (tests/README.md)

Совместный сбор и прогон `pytest tests/` (api + web + probe) работает: README
R2 прямо проектирует отсутствие конфликта опций для совместного прогона.

## Факт

```
ERROR collecting tests/web
Defining 'pytest_plugins' in a non-top-level conftest is no longer supported:
It affects the entire test suite instead of just below the conftest as expected.
  /home/openclaw/ekotov-wiki/tests/web/conftest.py
Please move it to a top level conftest file at the rootdir:
  /home/openclaw/ekotov-wiki
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.57s
```

Точка: `tests/web/conftest.py:47` — `pytest_plugins = ["pytest_playwright"]`.
Начиная с pytest 8 объявление `pytest_plugins` вне КОРНЕВОГО conftest — hard
error (не deprecation). Прогон по частям работает: `pytest tests/api` и
`pytest tests/web` по отдельности собираются и проходят (в этой QA-сессии:
tests/api 201 passed / 9 skipped / 2 xfailed на маршрутизированном стенде).

## Анализ

- Регистрация `pytest_playwright` нужна только web-сьюту; при раздельном
  запуске `pytest tests/web` plugin загружается, при совместном `pytest tests/`
  мешает сбору. Раньше (pytest 7-эпоха написания R1/R2-сьютов) это был
  deprecation warning, поэтому эталонные команды README не падали.
- Варианты фикса (за пределами зоны записи QA, задача 2.1 — только фиксация):
  1. перенести `pytest_plugins = ["pytest_playwright"]` в корневой `conftest.py`
     репозитория (новый файл в rootdir; загрузка плагина для api-сьюта
     безвредна — фикстуры playwright просто не используются);
  2. либо заменить явную регистрацию на точку входа плагина через
     `pytest11`-автозагрузку (pytest-playwright регистрируется сам при наличии
     в окружении — достаточно удалить строку 47, если автозагрузка не
     отключена; проверить `PYTEST_DISABLE_PLUGIN_AUTOLOAD` в CI-окружении).

## Обходной путь, использованный в регрессе 2.1

Полный регресс выполнен покаталогово: `pytest tests/api tests/test_walkthrough_probe.py`
(плюс `pytest services/search/tests`) на маршрутизированном стенде; web-сьют —
вне скопа этой задачи (нужен playwright-браузер, отдельная сессия). После
фикса BUG-006 команда `pytest tests/ -q` из README станет исполняемой снова.
