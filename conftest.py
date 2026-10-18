"""Корневой conftest набора tests/.

pytest >= 8 запрещает `pytest_plugins` в не-корневых conftest (ошибка сбора
`python -m pytest tests/ -q`) — регистрация pytest_playwright перенесена сюда
из tests/web/conftest.py без изменения поведения (документированная миграция
pytest: «move it to a top level conftest file at the rootdir»).
Восстановлено после rollback rich-editor (92bd2c8), убравшего корневой
conftest целиком.
"""

pytest_plugins = ["pytest_playwright"]
