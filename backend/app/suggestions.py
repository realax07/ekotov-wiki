"""Подсказки значений фильтра: GET /api/suggestions (Релиз 1, задача 1.3 / P4).

Контракт (уточнение Заказчика, дословно): «саджест формируется по двум
столбцам, теги и категории, и выбирался типом set(), множество, только
из уже заведенных вариантов».

- Метод/путь: GET /api/suggestions.
- Ответ 200: {"suggestions": ["..."]} — ОБЪЕДИНЕНИЕ имен тегов и категорий
  СУЩЕСТВУЮЩИХ задач (tags ∪ categories), set-семантика (без дублей),
  отсортировано по возрастанию (Python sorted() по кодовым точкам).
- Значение из тегов и категорий одновременно (например тег «home» и
  категория «home») входит в множество ОДИН раз.
- «Только уже заведенные варианты»: новые значения эндпоинт не принимает
  (только GET); теги удаленных задач (осиротевшие строки tags) не
  попадают — join идет через task_tags до задач; пустые/NULL категории
  не являются «заведенным вариантом» и исключаются.
- Авторизация: обязательна — путь не в exempt-списке middleware
  (app/middleware.py), без валидной сессии — 401 {"error": "unauthorized"}.

Потребитель: search.js заполняет <datalist id="tag-hints"> на /search;
datalist привязан к обоим полям конструктора (теги и категория) через
list="tag-hints" (search.html).

Релиз 4 (задача 5.2, FR-46): GET /api/suggestions/users — уникальные
логины для подсказок фильтров assigned/creator конструктора. Тот же
механизм «значения из данных» (FR-35/DEF-001): DISTINCT по JOIN
tasks→users — только пользователи, реально встречающиеся в столбцах
tasks.creator_id / tasks.assigned_to_id, НЕ весь справочник /api/users
(состав фильтра = что есть в данных). Ответ 200:
{"users": ["<login>", ...]} — отсортировано; 401 без сессии — middleware.
Отдельный путь, а не расширение /api/suggestions: контракт последнего
зафиксирован уточнением Заказчика (единственный ключ "suggestions",
множество tags ∪ categories) — тесты TC-API-SUGG-001/004 проверяют
{set(body.keys()) == {"suggestions"}}; новое множество клиентов ломало бы
их. «Без исполнителя» — не подсказка из БД, а специальная опция клиента
(статическая в search.html, значение none → assigned IS NULL, ОВ-24).

Примечание к реализации: ТЗ упоминало json_each по tasks.tags, но
фактическая схема — нормализованная (tags + task_tags, sdd §4); источник
данных тот же (теги существующих задач), контракт не меняется.
"""

from fastapi import APIRouter

from app.db import get_connection

router = APIRouter(prefix="/api/suggestions")

# Множество «заведенных вариантов» (уточнение Заказчика): DISTINCT внутри
# каждой ветки, UNION (не ALL) снимает пересечение тегов и категорий,
# ORDER BY — сортировка ответа. Пустые категории не «заведены».
_SUGGESTIONS_SQL = """
SELECT DISTINCT tags.name
FROM tags
JOIN task_tags ON task_tags.tag_id = tags.id
UNION
SELECT DISTINCT category
FROM tasks
WHERE category IS NOT NULL AND category != ''
ORDER BY 1
"""


@router.get("")
def suggestions() -> dict:
    """GET /api/suggestions → {"suggestions": [str, ...]} (см. docstring модуля)."""
    conn = get_connection()
    try:
        rows = conn.execute(_SUGGESTIONS_SQL).fetchall()
    finally:
        conn.close()
    return {"suggestions": sorted(row[0] for row in rows)}


# Релиз 4 (5.2, FR-46): уникальные логины в столбцах creator/assigned
# существующих задач (механизм FR-35/DEF-001 — «значения из данных»).
# UNION снимает пересечение (один пользователь и создатель, и исполнитель
# входит ОДИН раз); задачи без пользователя (NULL) не подсказываются.
_USER_SUGGESTIONS_SQL = """
SELECT DISTINCT u.login
FROM tasks t
JOIN users u ON u.id = t.creator_id
UNION
SELECT DISTINCT u.login
FROM tasks t
JOIN users u ON u.id = t.assigned_to_id
ORDER BY 1
"""


@router.get("/users")
def user_suggestions() -> dict:
    """GET /api/suggestions/users → {"users": [login, ...]} (5.2, FR-46).

    Уникальные логины из tasks.creator_id ∪ tasks.assigned_to_id (JOIN
    tasks→users), отсортированы. 401 без сессии — middleware (путь не в
    exempt-списке). Потребитель: опции select'ов «Исполнитель»/
    «Создатель» конструктора поиска (search.js); опцию «без исполнителя»
    добавляет клиент (статическая, ОВ-24).
    """
    conn = get_connection()
    try:
        rows = conn.execute(_USER_SUGGESTIONS_SQL).fetchall()
    finally:
        conn.close()
    return {"users": sorted(row[0] for row in rows)}
