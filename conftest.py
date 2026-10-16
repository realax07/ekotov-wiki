"""Корневой conftest набора tests/ (этап 3.3, add-rich-editor).

pytest >= 8 запрещает `pytest_plugins` в не-корневых conftest (ошибка сбора
`python -m pytest tests/ -q`) — регистрация pytest_playwright перенесена сюда
из tests/web/conftest.py без изменения поведения (документированная миграция
pytest: «move it to a top level conftest file at the rootdir»).
"""

pytest_plugins = ["pytest_playwright"]
