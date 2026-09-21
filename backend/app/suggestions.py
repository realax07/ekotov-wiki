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
