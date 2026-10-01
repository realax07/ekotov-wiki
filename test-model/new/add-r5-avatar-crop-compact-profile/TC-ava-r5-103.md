# TC-ava-r5-103 — Серверная нормализация: валидный JPEG не-квадратной геометрии → 256×256 PNG

- **CHK:** CHK-R5-3
- **Change:** add-r5-avatar-crop-compact-profile
- **Источник:** auth MODIFIED «Загрузка аватара», Scenario «Серверная нормализация не доверяет клиенту» (ОВ-СА-2, Д-13, NFR-11); design §2 «независимо от входной геометрии»; ТЗ СЦ-6 (вариант А)
- **Тип:** поз. | **Приоритет:** Must
- **Маркер:** api
- **Среда/предусловия:** API-стенд tests/api (EKOTOV_WIKI_BASE_URL/DB_PATH/AVATARS_DIR); сессия owner (conftest); teardown: файл owner.png удален, avatar_path/avatar_updated_at = NULL (как TC-ava-r5-101).
- **Шаги:**
  1. Сформировать валидный JPEG 900×600 (не квадрат, PIL, несимметричная заливка для отличия от пустого).
  2. `POST /api/profile/avatar` multipart `file` (photo.jpg, image/jpeg) от сессии owner.
  3. Прочитать файл `/tmp/.../avatars/<owner_id>.png` с диска, открыть PIL.
- **Ожидаемый результат:** ответ 200 `{"ok": true, "avatar_url": "/avatars/<id>.png?v=..."}`; на диске файл формата PNG размером ровно 256×256 (нормализация не зависит от исходного формата: jpg-вход → png-выход, не-квадрат → квадрат).
- **Тестовые данные:** JPEG 900×600, заливка (30,120,220).
