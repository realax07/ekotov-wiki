"""Поиск: GET /api/search + POST /api/search/advanced (sdd.md §3.5).

Задача 7.1 — GET (структурированные условия); задача 7.2 — advanced:
parse()/build() (текст ↔ SearchFilters) и POST /api/search/advanced.

Контракт GET — дословно sdd.md §3.5:
- Query-параметры (все опциональны; пустой набор = ВСЕ задачи, включая
  архивные — спека search, Scenario «Поиск без заданных условий»):
  `priority`, `category`, `tag` (повторяемый), `due_before`, `due_after`,
  `archived=true|false|all` (по умолчанию `all`); Релиз 4 (FR-46, ОВ-24):
  `assigned` (login | `none` = без исполнителя), `creator` (login).
- Ответ 200: {"results": [Task]} — Task по схеме sdd §3.2 (11 полей,
  включая done_at и archived_at; archived_at = признак архивности, FR-10)
  плюс (Релиз 4, FR-45/FR-46) `creator`/`assigned` — логины пользователей;
  assigned = null у задачи без исполнителя (ОВ-24).
- Ошибки: 422 (невозможное значение параметра — невалидный priority/
  дата/archived; Релиз 4: assigned/creator — не login существующего
  пользователя и не `none`); 401 — middleware (без сессии).

Контракт POST /api/search/advanced — sdd.md §3.5:
- Запрос: {"query": "priority = \"high\" AND tag IN (\"home\")"};
  Релиз 4 (FR-46, ОВ-24): поля `assigned`/`creator` с операторами `=`
  и `IS NULL` (assigned IS NULL — задачи без исполнителя).
- Ответ 200: {"results": [Task], "normalized_query": "…"} — normalized
  сериализует РАСПАРСЕННЫЙ фильтр (build()), это не эхо ввода.
- Ошибки: 400 {"error": "filter syntax: <позиция/причина>"} — и запрос
  К БД НЕ ВЫПОЛНЯЕТСЯ (parse до get_connection); 401 — middleware.

Семантика фильтра (design.md §6):
- разные признаки объединяются по И (спека search, Scenario
  «Комбинация условий по нескольким признакам»: «удовлетворяющие
  ОБОИМ условиям»);
- НЕСКОЛЬКО значений одного признака (повторяемый tag) — через IN,
  т.е. ИЛИ внутри признака: сериализация в design.md §6 —
  `tag IN ("home", "car")`.

Безопасность (NFR-7): SQL только параметризованный — значения фильтра
никогда не конкатенируются в текст запроса, только bind-параметры;
имена полей/операторы — белый список, зашитый в build_where(). Парсер
7.2 строит ТОЛЬКО SearchFilters — пользовательский текст физически не
может попасть в SQL-строку.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.db import get_connection
from app.tasks import TASK_COLUMNS, _row_to_task

router = APIRouter(prefix="/api/search")

# Белый список значений (sdd §3.5, §3.2 CHECK): иное — 422.
Priority = Literal["low", "medium", "high"]
Archived = Literal["true", "false", "all"]


@dataclass
class SearchFilters:
    """Валидированный структурированный фильтр (внутреннее представление).

    Точка стыковки GET (7.1) и advanced (7.2): parse() текста строит такой
    же объект, и исполнение пойдет через тот же build_where (design.md §6).
    """

    priority: str | None = None
    priority_ne: str | None = None  # advanced `priority != "..."`; GET не выставляет
    category: str | None = None
    category_ne: str | None = None  # advanced `category != "..."`
    tags: list[str] = field(default_factory=list)
    due_before: date | None = None
    due_after: date | None = None
    archived: str = "all"
    # Релиз 4 (FR-46, ОВ-24): фильтры по пользователю. assigned хранит
    # login; поиск «без исполнителя» — через assigned_is_null (IS NULL).
    # `!=` для assigned/creator не поддерживается (5.2: только = и IS NULL).
    assigned: str | None = None
    assigned_is_null: bool = False
    creator: str | None = None
    creator_is_null: bool = False


# Значение GET-параметра assigned = «без исполнителя» (ОВ-24): маппится в
# `tasks.assigned_to_id IS NULL`. Логин «none» коллизирует с маркером —
# валидация пользователя ниже это исключает (логины seed: owner/wife).
UNASSIGNED = "none"


def build_where(f: SearchFilters) -> tuple[str, list]:
    """SearchFilters → (WHERE-фрагмент, bind-параметры).

    Чистая функция без FastAPI. Каждый предикат — фиксированный шаблон
    с плейсхолдерами; значения ТОЛЬКО через bind-параметры (NFR-7):
    инъекционный текст в tag/category/priority просто не совпадет
    со значением в БД, SQL он не меняет. Имена полей — не из ввода.
    """
    clauses: list[str] = []
    params: list = []

    if f.priority is not None:
        clauses.append("tasks.priority = ?")
        params.append(f.priority)

    if f.priority_ne is not None:
        # NULL-семантика SQL: != не матчит NULL — трактуем «не равно» как
        # «не равно ИЛИ признака нет» (задача без признака условию не равна).
        clauses.append("(tasks.priority != ? OR tasks.priority IS NULL)")
        params.append(f.priority_ne)

    if f.category is not None:
        clauses.append("tasks.category = ?")
        params.append(f.category)

    if f.category_ne is not None:
        clauses.append("(tasks.category != ? OR tasks.category IS NULL)")
        params.append(f.category_ne)

    # Повторяемый tag: ИЛИ внутри признака = IN (design.md §6:
    # сериализация `tag IN ("home", "car")`). EXISTS — задача обязана
    # иметь ХОТЯ БЫ ОДИН из перечисленных тегов.
    if f.tags:
        placeholders = ", ".join("?" for _ in f.tags)
        clauses.append(
            "EXISTS (SELECT 1 FROM task_tags tt "
            "JOIN tags t ON t.id = tt.tag_id "
            f"WHERE tt.task_id = tasks.id AND t.name IN ({placeholders}))"
        )
        params.extend(f.tags)

    # Границы срока — ВКЛЮЧИТЕЛЬНО (due_before = «срок не позднее»).
    # В спеке/design инклюзивность не оговорена — см. ОТЧЕТ 7.1 (вопрос 2).
    if f.due_before is not None:
        clauses.append("tasks.due_date <= ?")
        params.append(f.due_before.isoformat())

    if f.due_after is not None:
        clauses.append("tasks.due_date >= ?")
        params.append(f.due_after.isoformat())

    # Архивность (sdd §3.5): true → только архивные, false → только
    # активные, all (дефолт) → без условия (и архив, и активные).
    if f.archived == "true":
        clauses.append("tasks.archived_at IS NOT NULL")
    elif f.archived == "false":
        clauses.append("tasks.archived_at IS NULL")
    # "all" — предиката нет (пустой фильтр не ограничивает выборку).

    # Релиз 4 (FR-46, ОВ-24): фильтры по пользователю через JOIN users
    # (задача 5.2 — search.py своими предикатами, tasks.py не трогается).
    # Значение — bind-параметр (NFR-7); логин проверен на существование
    # до сюда (422 на несуществующего), в SQL он только сравнивается.
    if f.assigned is not None:
        clauses.append("assigned_user.login = ?")
        params.append(f.assigned)
    if f.assigned_is_null:
        clauses.append("tasks.assigned_to_id IS NULL")
    if f.creator is not None:
        clauses.append("creator_user.login = ?")
        params.append(f.creator)
    if f.creator_is_null:
        clauses.append("tasks.creator_id IS NULL")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# SELECT выдачи поиска (свой, 5.2): столбцы Task (TASK_COLUMNS) + логины
# creator/assigned JOIN'ом users (sdd §3.2/§3.5: ответ поиска содержит
# creator/assigned — имена пользователей; null → null в JSON, ОВ-24).
# tasks.py не изменяется: JOIN и проекция — зона search.py.
# TASK_COLUMNS — короткие имена (id, title, ...); с JOIN users (у users
# тоже id/login) неоднозначность исключается префиксом tasks. для КАЖДОГО
# столбца — SQL в SELECT-проекции, не во WHERE, префикс валиден.
_TASK_SEARCH_COLUMNS = ", ".join(
    "tasks." + col.strip() for col in TASK_COLUMNS.split(",")
)
_SEARCH_SELECT_SQL = f"""
SELECT {_TASK_SEARCH_COLUMNS},
       creator_user.login,
       assigned_user.login
FROM tasks
LEFT JOIN users AS creator_user ON creator_user.id = tasks.creator_id
LEFT JOIN users AS assigned_user ON assigned_user.id = tasks.assigned_to_id
"""


def run_search(conn: sqlite3.Connection, f: SearchFilters) -> list[dict]:
    """Выполняет параметризованный SELECT, возвращает Task-объекты.

    Релиз 4 (FR-45/FR-46): каждая задача дополнена `creator`/`assigned`
    (логины; null у задачи без пользователя — ОВ-24 «Unassigned»).
    """
    where, params = build_where(f)
    rows = conn.execute(
        _SEARCH_SELECT_SQL + where + " ORDER BY tasks.id",
        params,
    ).fetchall()
    return [_row_to_task_with_users(conn, row) for row in rows]


def _row_to_task_with_users(conn: sqlite3.Connection, row: tuple) -> dict:
    """Строка поиска (TASK_COLUMNS + creator.login + assigned.login) → Task.

    Поля 0…9 — в точности _row_to_task из tasks.py (нумерация TASK_COLUMNS);
    creator/assigned добавляются поверх (sdd §3.2: creator: login,
    assigned: login|null). tasks.py не трогается — своя проекция.
    Теги грузятся по id ЗАДАЧИ (row[0]) — row[10]/row[11] после JOIN 5.2
    суть ЛОГИНЫ creator/assigned (дефект волны 5.2: передача row[10]
    давала пустой tags в каждой строке выдачи поиска).
    """
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "priority": row[3],
        "category": row[4],
        "due_date": row[5],
        "tags": _load_search_tags(conn, row[0]),
        "is_fast": bool(row[6]),
        "status": row[7],
        "done_at": row[8],
        "archived_at": row[9],
        "creator": row[10],
        "assigned": row[11],
    }


def _load_search_tags(conn: sqlite3.Connection, task_id: int) -> list[str]:
    """Теги задачи (тот же SELECT, что tasks._load_tags — копия, зона 5.2)."""
    rows = conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN task_tags tt ON tt.tag_id = t.id "
        "WHERE tt.task_id = ? ORDER BY t.id",
        (task_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _validate_user_logins(
    conn: sqlite3.Connection, assigned: str | None, creator: str | None
) -> JSONResponse | None:
    """422 на невозможное значение assigned/creator (sdd §3.5, FR-46).

    assigned принимает login существующего пользователя ИЛИ `none`
    («без исполнителя», ОВ-24); creator — только login. Логин не
    существует → 422 {"error": "validation error", "details": {...}}
    (формат ошибок sdd §3, обработчик RequestValidationError).
    Выполняется ПОСЛЕ pydantic-валидации типов, ДО выборки из БД.
    """
    unknown: dict[str, str] = {}
    for name, value in (("assigned", assigned), ("creator", creator)):
        if value is None or (name == "assigned" and value == UNASSIGNED):
            continue
        row = conn.execute(
            "SELECT 1 FROM users WHERE login = ?", (value,)
        ).fetchone()
        if row is None:
            unknown[name] = "unknown user"
    if unknown:
        return JSONResponse(
            status_code=422,
            content={"error": "validation error", "details": unknown},
        )
    return None


@router.get("", response_model=None)
def search(
    request: Request,
    priority: Priority | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: list[str] = Query(default_factory=list),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    archived: Archived = Query(default="all"),
    assigned: str | None = Query(default=None),
    creator: str | None = Query(default=None),
) -> dict | JSONResponse:
    """GET /api/search — структурированные условия (sdd §3.5, FR-10/11/8).

    Валидация типов/значений — FastAPI/pydantic: невалидный priority,
    дата не формата YYYY-MM-DD, archived вне true|false|all → 422
    (обработчик RequestValidationError, sdd §3). 401 без сессии —
    middleware. Пустой набор параметров = все задачи.
    Релиз 4 (FR-46, ОВ-24): assigned = login | none («без исполнителя»),
    creator = login; несуществующий логин → 422 (5.2, «422 на
    невозможное значение»).
    """
    filters = SearchFilters(
        priority=priority,
        category=category,
        tags=tag,
        due_before=due_before,
        due_after=due_after,
        archived=archived,
        assigned=assigned if assigned != UNASSIGNED else None,
        assigned_is_null=(assigned == UNASSIGNED),
        creator=creator,
    )
    conn = get_connection()
    try:
        invalid = _validate_user_logins(conn, assigned, creator)
        if invalid is not None:
            return invalid
        results = run_search(conn, filters)
    finally:
        conn.close()
    return {"results": jsonable_encoder(results)}


# ==========================================================================
# 7.2: advanced-фильтр — parse() (текст → SearchFilters) и build()
# (SearchFilters → текст). FR-12; sdd.md §3.5.
# ==========================================================================
#
# Грамматика (design.md §6: «список предикатов над полями задачи»,
# условия объединяются по И; OR в спеке/design НЕ оговорен — NOT
# supported, явная ошибка; см. ОТЧЕТ, решение 2):
#
#   query     := " | condition ( "AND" condition )*
#   condition := field op value | field "IS" "NULL"
#   field     := priority | category | tag | due | due_before | due_after
#                | archived | assigned | creator                (Релиз 4)
#   op        := "=" | "!=" | ">" | ">=" | "<" | "<=" | "IN"
#   value     := <дата YYYY-MM-DD> | <строка в двойных кавычках> | <слово>
#              | "(" <строка> ("," <строка>)* ")"     # только после IN
#
# Ограничения по полям (белый список; иное — 400 с позицией):
# - priority, category: = и !=; значение — строка (кавычки или слово);
#   priority — только low|medium|high (sdd §3.2 CHECK);
# - assigned, creator (Релиз 4, FR-46/ОВ-24): = и IS NULL —
#   `assigned = "<login>"`, `assigned IS NULL` (задачи без исполнителя);
#   значение = — кавычечная строка или слово; != не поддерживается;
# - tag: только IN (...); значения — кавычечные строки;
# - due: сравнения > >= < <= и = (значение — дата YYYY-MM-DD;
#   due = D — фиксированный день: эквивалент due >= D AND due <= D);
# - due_before: < <= =; due_after: > >= = (значение — дата);
# - archived: = с true|false|all (голое слово; кавычки тоже допустимы);
# - AND — единственная логическая связка; OR → 400 «OR not supported»;
# - пустой текст = пустой фильтр (все задачи, как GET без параметров).
#
# БЕЗОПАСНОСТЬ (NFR-7): parse() возвращает ТОЛЬКО SearchFilters; значения
# (в т.ч. инъекционный текст в кавычках) попадают в SQL исключительно
# как bind-параметры build_where(). normalized_query — build(фильтра),
# сериализация структуры, не эхо пользовательского ввода.


class FilterSyntaxError(ValueError):
    """Синтаксическая ошибка advanced-фильтра → 400 (без выполнения).

    pos — 0-based смещение в исходном тексте, reason — человекочитаемая
    причина (sdd §3.5: "filter syntax: <позиция/причина>").
    """

    def __init__(self, pos: int, reason: str):
        super().__init__(f"filter syntax: position {pos}: {reason}")
        self.pos = pos
        self.reason = reason


# --- Токенизация ----------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<ne>!=)
    | (?P<ge>>=)
    | (?P<le><=)
    | (?P<gt>>)
    | (?P<lt><)
    | (?P<eq>=)
    | (?P<lpar>\()
    | (?P<rpar>\))
    | (?P<comma>,)
    | (?P<date>\d{4}-\d{2}-\d{2})
    | (?P<word>[A-Za-z_][A-Za-z0-9_-]*)
    | (?P<qstr>"(?:[^"\\]|\\.)*")
    | (?P<garbage>[^\s])
    """,
    re.VERBOSE,
)


@dataclass
class _Tok:
    kind: str  # op | lpar | rpar | comma | date | word | qstr
    value: str
    pos: int  # 0-based смещение в исходном тексте


def _tokenize(text: str) -> list[_Tok]:
    tokens: list[_Tok] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None:  # недостижимо: garbage покрывает любой не-пробел
            raise FilterSyntaxError(pos, "unexpected character")
        kind = m.lastgroup or ""
        raw = m.group()
        if kind == "garbage":
            raise FilterSyntaxError(pos, f"unexpected character {raw!r}")
        if kind == "ws":
            pass
        elif kind in ("ne", "ge", "le", "gt", "lt", "eq"):
            tokens.append(_Tok("op", raw, pos))
        elif kind == "qstr":
            # Снимаем кавычки, разворачиваем escape: \" → ", \\ → \.
            body = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            tokens.append(_Tok("qstr", body, pos))
        else:  # date | word | lpar | rpar | comma
            tokens.append(_Tok(kind, raw, pos))
        pos = m.end()
    return tokens


# --- Парсинг --------------------------------------------------------------

_PRIORITY_VALUES = {"low", "medium", "high"}
_ARCHIVED_VALUES = {"true", "false", "all"}
_FIELDS = {
    "priority", "category", "tag",
    "due", "due_before", "due_after",
    "archived",
    "assigned", "creator",  # Релиз 4 (FR-46): = и IS NULL
}


def _expect(tokens: list[_Tok], i: int, kind: str, what: str) -> _Tok:
    if i >= len(tokens):
        pos = tokens[-1].pos if tokens else 0
        raise FilterSyntaxError(pos, f"unexpected end of filter: expected {what}")
    tok = tokens[i]
    if tok.kind != kind:
        raise FilterSyntaxError(tok.pos, f"expected {what}, got {tok.value!r}")
    return tok


def _parse_single_value(tokens: list[_Tok], i: int) -> tuple[_Tok, str]:
    """Значение одиночного условия; возвращает (токен, сорт).

    Сорт: "date" (распознан лексером как YYYY-MM-DD), "str" (кавычки),
    "word" (голое слово).
    """
    tok = _expect_value(tokens, i)
    sort = {"date": "date", "qstr": "str", "word": "word"}[tok.kind]
    return tok, sort


def _expect_value(tokens: list[_Tok], i: int) -> _Tok:
    if i >= len(tokens):
        pos = tokens[-1].pos if tokens else 0
        raise FilterSyntaxError(pos, "unexpected end of filter: expected a value")
    tok = tokens[i]
    if tok.kind not in ("date", "qstr", "word"):
        raise FilterSyntaxError(
            tok.pos, f"expected a value (date, quoted string, or word), got {tok.value!r}"
        )
    return tok


def _parse_condition(
    tokens: list[_Tok], i: int
) -> tuple[str, str, object, int, int]:
    """Одно условие `field op value` → (field, op, значение, next_i, field_pos).

    Значение: для одиночного условия — (сорт, текст); для IN — список
    строк. field_pos — позиция токена поля в исходном тексте: ошибки
    валидации значения/оператора получают её напрямую (без повторного
    поиска по токенам). Дальнейшую валидацию (какие операторы у какого
    поля) делает _apply_predicate.
    """
    field_tok = _expect(tokens, i, "word", "field name")
    if field_tok.value not in _FIELDS:
        raise FilterSyntaxError(field_tok.pos, f"unknown field {field_tok.value!r}")
    i += 1

    # `field IS NULL` (Релиз 4, FR-46/ОВ-24): IS — лексически word;
    # следующий токен обязан быть словом NULL (регистр как в SQL —
    # заглавными; строчное null = неизвестное поле-значение → 400).
    if (
        i < len(tokens)
        and tokens[i].kind == "word"
        and tokens[i].value == "IS"
    ):
        null_tok = _expect(tokens, i + 1, "word", "'NULL' after IS")
        if null_tok.value != "NULL":
            raise FilterSyntaxError(
                null_tok.pos, f"expected NULL after IS, got {null_tok.value!r}"
            )
        return field_tok.value, "IS_NULL", None, i + 2, field_tok.pos

    # IN — лексически word: в позиции оператора слово IN признается
    # оператором; op-токены (= != > >= < <=) распознал лексер.
    if i < len(tokens) and tokens[i].kind == "word" and tokens[i].value == "IN":
        op_tok = tokens[i]
    else:
        op_tok = _expect(tokens, i, "op", "operator (= != > >= < <= IN)")
    op = op_tok.value
    i += 1

    if op == "IN":
        _expect(tokens, i, "lpar", "'(' after IN")
        i += 1
        values: list[str] = []
        while True:
            vt = _expect(tokens, i, "qstr", "quoted string inside IN (...)")
            values.append(vt.value)
            i += 1
            if i < len(tokens) and tokens[i].kind == "comma":
                i += 1
                continue
            break
        _expect(tokens, i, "rpar", "')' closing IN (...)")
        i += 1
        return field_tok.value, op, values, i, field_tok.pos

    vt, sort = _parse_single_value(tokens, i)
    i += 1
    return field_tok.value, op, (sort, vt.value), i, field_tok.pos


def parse(query: str) -> SearchFilters:
    """Текст advanced-фильтра → SearchFilters (структура, не SQL).

    Чистая функция: без FastAPI и без БД. Бросает FilterSyntaxError
    (позиция + причина); HTTP-слой превращает её в 400. Выполнение
    запроса в этом случае невозможно по построению: parse завершается
    до всякого обращения к БД (sdd §3.5 — «без выполнения»).
    """
    tokens = _tokenize(query)
    filters = SearchFilters()  # archived="all" — дефолт, как в GET
    if not tokens:
        return filters  # пустой текст = пустой фильтр = все задачи

    i = 0
    while True:
        fname, op, value, i, field_pos = _parse_condition(tokens, i)
        _apply_predicate(filters, fname, op, value, field_pos)
        if i < len(tokens):
            connector = tokens[i]
            if connector.kind == "word" and connector.value == "AND":
                i += 1
                continue
            if connector.kind == "word" and connector.value == "OR":
                raise FilterSyntaxError(
                    connector.pos,
                    "OR not supported: conditions are combined with AND only",
                )
            raise FilterSyntaxError(
                connector.pos,
                f"expected AND or end of filter, got {connector.value!r}",
            )
        break
    return filters


def _parse_pred_date(pos: int, sort: str, raw: str) -> date:
    if sort != "date":
        raise FilterSyntaxError(
            pos, f"requires a date YYYY-MM-DD, got {raw!r}"
        )
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise FilterSyntaxError(pos, f"invalid date {raw!r}") from None


def _apply_predicate(
    f: SearchFilters, fname: str, op: str, value: object, pos: int
) -> None:
    """Предикат → поля SearchFilters + валидация значений/операторов.

    Инъекционный текст в значении — обычная строка: он будет сравнен
    с содержимым БД через bind-параметр и просто не совпадет.
    pos — позиция токена поля в исходном тексте (от _parse_condition),
    к ней привязываются ошибки значений/операторов.

    Повтор поля — синтаксическая ошибка «duplicate field X»: молчаливое
    «последний побеждает» маскирует ошибку пользователя (единообразно
    с tag, где дубликат был 400 изначально). Исключение — диапазон дат
    `due >= A AND due <= B`: предикаты пишут РАЗНЫЕ слоты фильтра
    (due_after/due_before), это не дубликат. Дубликат = попытка
    перезаписать уже заданный слот.
    """
    if fname == "tag":
        if op != "IN":
            raise FilterSyntaxError(pos, "tag supports only IN (...)")
        assert isinstance(value, list)
        if f.tags:
            raise FilterSyntaxError(pos, "duplicate field tag")
        f.tags = list(value)  # строки-значения, НЕ SQL
        return

    if fname == "archived":
        if op != "=":
            raise FilterSyntaxError(pos, "archived supports only =")
        sort, raw = value  # type: ignore[misc]
        if raw not in _ARCHIVED_VALUES:
            raise FilterSyntaxError(
                pos, f"archived must be true|false|all, got {raw!r}"
            )
        if f.archived != "all":
            raise FilterSyntaxError(pos, "duplicate field archived")
        f.archived = raw
        return

    if fname in ("assigned", "creator"):
        # Релиз 4 (FR-46, ОВ-24): = и IS NULL; значение = — логин
        # (существование НЕ проверяем в parse — parse без БД по
        # построению; несуществующий логин просто не совпадет ни с
        # одной строкой JOIN'а: пустая выдача, не ошибка).
        if op == "IS_NULL":
            if fname == "assigned":
                if f.assigned is not None or f.assigned_is_null:
                    raise FilterSyntaxError(pos, "duplicate field assigned")
                f.assigned_is_null = True
            else:
                if f.creator is not None or f.creator_is_null:
                    raise FilterSyntaxError(pos, "duplicate field creator")
                f.creator_is_null = True
            return
        if op != "=":
            raise FilterSyntaxError(
                pos, f"{fname} supports = and IS NULL"
            )
        sort, raw = value  # type: ignore[misc]
        if sort == "date":
            raise FilterSyntaxError(
                pos, f"{fname} requires a login (quoted string or word)"
            )
        if fname == "assigned":
            if f.assigned is not None or f.assigned_is_null:
                raise FilterSyntaxError(pos, "duplicate field assigned")
            f.assigned = raw
        else:
            if f.creator is not None or f.creator_is_null:
                raise FilterSyntaxError(pos, "duplicate field creator")
            f.creator = raw
        return

    if fname in ("priority", "category"):
        if op not in ("=", "!="):
            raise FilterSyntaxError(
                pos, f"{fname} supports = and != (multiple values — only tag IN)"
            )
        sort, raw = value  # type: ignore[misc]
        if fname == "priority" and raw not in _PRIORITY_VALUES:
            raise FilterSyntaxError(
                pos, f"priority must be low|medium|high, got {raw!r}"
            )
        if op == "=":
            if fname == "priority":
                if f.priority is not None or f.priority_ne is not None:
                    raise FilterSyntaxError(pos, "duplicate field priority")
                f.priority = raw
            else:
                if f.category is not None or f.category_ne is not None:
                    raise FilterSyntaxError(pos, "duplicate field category")
                f.category = raw
        else:
            # NULL-семантика SQL: != не матчит NULL — в build_where
            # «не равно» трактуется как «не равно ИЛИ признака нет»
            # (задача без признака условию не равна).
            if fname == "priority":
                if f.priority_ne is not None or f.priority is not None:
                    raise FilterSyntaxError(pos, "duplicate field priority")
                f.priority_ne = raw
            else:
                if f.category_ne is not None or f.category is not None:
                    raise FilterSyntaxError(pos, "duplicate field category")
                f.category_ne = raw
        return

    # due / due_before / due_after — сравнения дат.
    sort, raw = value  # type: ignore[misc]
    d = _parse_pred_date(pos, sort, raw)
    if fname == "due":
        if op in ("<", "<="):
            if f.due_before is not None:
                raise FilterSyntaxError(pos, "duplicate field due")
            f.due_before = d
        elif op in (">", ">="):
            if f.due_after is not None:
                raise FilterSyntaxError(pos, "duplicate field due")
            f.due_after = d
        elif op == "=":
            # Фиксированный день = диапазон [D, D] (границы включительны).
            if f.due_after is not None or f.due_before is not None:
                raise FilterSyntaxError(pos, "duplicate field due")
            f.due_after = d
            f.due_before = d
        else:
            raise FilterSyntaxError(pos, "due supports > >= < <= and =")
    elif fname == "due_before":
        if op not in ("<", "<=", "="):
            raise FilterSyntaxError(pos, "due_before supports < <= and =")
        if f.due_before is not None:
            raise FilterSyntaxError(pos, "duplicate field due_before")
        f.due_before = d
    else:  # due_after
        if op not in (">", ">=", "="):
            raise FilterSyntaxError(pos, "due_after supports > >= and =")
        if f.due_after is not None:
            raise FilterSyntaxError(pos, "duplicate field due_after")
        f.due_after = d


# --- Сериализация (build) ---------------------------------------------------

def _quote(s: str) -> str:
    """Строка → строковый литерал грамматики (escape \\ и ")."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build(f: SearchFilters) -> str:
    """SearchFilters → канонический текст фильтра (design.md §6).

    Обратная синхронизация конструктор → advanced (Scenario
    «Переключение конструктора в advanced»). normalized_query в ответе
    POST /api/search/advanced — вывод этой функции над РАСПАРСЕННЫМ
    фильтром: сериализация структуры, не эхо ввода.
    """
    parts: list[str] = []
    if f.priority is not None:
        parts.append(f"priority = {_quote(f.priority)}")
    if f.priority_ne is not None:
        parts.append(f"priority != {_quote(f.priority_ne)}")
    if f.category is not None:
        parts.append(f"category = {_quote(f.category)}")
    if f.category_ne is not None:
        parts.append(f"category != {_quote(f.category_ne)}")
    if f.tags:
        parts.append("tag IN (" + ", ".join(_quote(t) for t in f.tags) + ")")
    # Релиз 4 (FR-46, ОВ-24): assigned/creator — синхронно с фильтром.
    if f.assigned is not None:
        parts.append(f"assigned = {_quote(f.assigned)}")
    if f.assigned_is_null:
        parts.append("assigned IS NULL")
    if f.creator is not None:
        parts.append(f"creator = {_quote(f.creator)}")
    if f.creator_is_null:
        parts.append("creator IS NULL")
    if f.due_after is not None and f.due_after == f.due_before:
        # due = D — каноническая форма равенства (build(parse) устойчив).
        parts.append(f"due = {f.due_after.isoformat()}")
    else:
        if f.due_after is not None:
            parts.append(f"due >= {f.due_after.isoformat()}")
        if f.due_before is not None:
            parts.append(f"due <= {f.due_before.isoformat()}")
    if f.archived != "all":
        parts.append(f"archived = {f.archived}")
    return " AND ".join(parts)


@router.post("/advanced")
async def search_advanced(request: Request) -> JSONResponse:
    """POST /api/search/advanced (sdd.md §3.5; FR-12).

    Тело: {"query": "<SQL-подобный текст фильтра>"}.
    - 200: {"results": [Task], "normalized_query": build(фильтра)}.
    - 400 {"error": "filter syntax: position N: причина"} — синтаксическая
      ошибка; запрос к БД не выполняется (parse до get_connection).
      Невалидное JSON-тело тоже 400 (формат ошибок этого эндпоинта,
      sdd §3.5), не 500: битый JSON = нечитаемый фильтр.
    - 401 без сессии — middleware.
    - 422 (тело читается, но query — не строка) — обработчик sdd §3.
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — прием любого тела; невалидный JSON = 400 (задача 7.2)
        return JSONResponse(
            status_code=400,
            content={"error": "filter syntax: invalid JSON body"},
        )
    query = body.get("query") if isinstance(body, dict) else None
    if not isinstance(query, str):
        return JSONResponse(
            status_code=422,
            content={"error": "validation error",
                     "details": {"query": "string required"}},
        )

    try:
        filters = parse(query)
    except FilterSyntaxError as e:
        # ЗАПРОС НЕ ВЫПОЛНЕН: до этого места БД не открывалась.
        return JSONResponse(
            status_code=400,
            content={"error": f"filter syntax: position {e.pos}: {e.reason}"},
        )

    normalized = build(filters)
    conn = get_connection()
    try:
        results = run_search(conn, filters)
    finally:
        conn.close()
    return {"results": jsonable_encoder(results), "normalized_query": normalized}
