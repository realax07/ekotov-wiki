# Ревью 002 — add-wiki, задача 2.3 (роуты/каркас): повторное ревью после фикса

- Ревьюер: code_reviewer (независимый)
- Provenance: ветка `pipeline/p15-stage-a`, итерация 2 (фикс deleg_0b6702fc по review-001-2.1)
- Периметр: N1 (тесты navigation), N2 (js-подключение), M-2 (openapi) из review-001-2.1.md

## Проверка фикса

- N1: tests/api/test_navigation.py — 2 теста заглушки заменены на тесты новой
  спеки (scaffold-контейнеры, API существует); сайдбар-тест не тронут, зеленый.
  Осознанное решение: ассерт на todo-badge отсутствует (бейдж в base.html вне
  зоны задачи; снятие — волна 3/6.x) — принято.
- N2: подключение /static/js/wiki.js убрано из wiki.html; модули волны 3
  подключат свои (design §7).
- M-2: contracts/openapi.json перегенерирован export_openapi.py — 7 wiki-путей
  добавлены, тест test_openapi_r11 зеленый, детерминизм экспорта подтвержден.
- Верификация ПМ: test_navigation 5 passed, test_openapi_r11 4 passed; полный
  tests/api — профиль падений идентичен baseline main (средовые, не дифф).

## Вердикт: approve

- **Reviewer-Delegation:** deleg_37c4f8d4 (повторное ревью после RETURN; прогон 2)
