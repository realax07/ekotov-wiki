"""Общая обвязка сервисных тестов video (волна 3, tasks 3.2).

Импортируется pytest'ом ДО тестовых модулей — env здесь успевает
встать до `from app.main import app` (импорт стартует воркер):

- EKOTOV_WIKI_CONVERTER=off — воркер конвертации на старте main не
  поднимается: тесты кусков A/D детерминированы (POST оставляет
  статус «uploaded», писателя статуса нет — design §3). Тесты
  конвертера (test_converter.py) гоняют converter.* напрямую, включая
  явный start_worker() с чистым окружением.
"""

import os

os.environ.setdefault("EKOTOV_WIKI_CONVERTER", "off")
