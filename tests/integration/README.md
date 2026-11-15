# tests/integration — сквозные многокомпонентные тесты (J66)

Слой раскладки J66 (спека qa-pipeline): многокомпонентные тесты сервисного
слоя БЕЗ HTTP-клиента и браузера — стек уровня запрещает `requests` и
`playwright` (проверка flow_check, test-model/test-layout.json — strict).

Каталог заведен миграцией J66 (PR [chore] factory-reinit-1116); сквозных
сервисных тестов в проекте пока нет. Кандидаты будущего наполнения —
межсервисные контракты (app ↔ search/images/video/weather) на уровне
импорта сервисных модулей и тест-клиента TestClient.

Запуск (вместе с api-слоем, общий стенд):

```bash
pytest tests/api tests/integration -q
```
