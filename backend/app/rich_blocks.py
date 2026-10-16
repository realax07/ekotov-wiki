"""Парсер/валидатор/сериализатор блочного диалекта rich-редактора
(change add-rich-editor, tasks.md 1.1; design.md §1 D1; FR-117, FR-118,
FR-127).

Грамматика (design.md §1 дословно):
- GFM-таблицы: ``| a | b |`` + разделитель ``|---|`` (FR-117);
- ``:::columns`` … ``:::`` с разделителями колонок ``<<<`` (FR-118);
- ``:::callout type=info|warn|success`` … ``:::`` (FR-119);
- ``:::aside`` … ``:::`` (FR-120);
- ``:::spoiler title="…"`` … ``:::`` (FR-121);
- fenced code `` ```lang `` … `` ``` `` (FR-122);
- ``![alt](/images/{id}){width=N}`` — строка-кандидат: целиком одна строка
  с этой разметкой → блок-изображение (масштаб, FR-123; N∈10..100).

Контент страницы — смесь legacy-HTML и блоков диалекта в одной колонке
`content` (design §1): строки вне блоков — узел ``text`` (legacy-путь БЕЗ
изменений), строки блока — узел соответствующего типа. Вложенность
контейнеров — рекурсивно (FR-127).

Fallback-политика (design §1, ревью A-2): ``parse`` ТОЛЕРАНТЕН — кандидат
в блок, не прошедший разбор (незакрытый контейнер, ``:::`` без типа,
GFM-шапка без разделителя), остается узлом ``text``; исключений ``parse``
не бросает. Строгая проверка — ``validate`` (ValueError с позицией строки):
ее зовет шов сохранения (wiki.py, задача 1.3), и падение означает
ТОЛЕРАНТНЫЙ fallback «plain text + лог, БЕЗ 422», а не отказ в сохранении.
Строгая валидация НОВОГО rich-контента — на фронте до отправки (фронтовый
парсер зеркалит грамматику, design §4).

Круговая преобразуемость (tasks.md 1.1б): ``serialize(parse(t))`` —
каноническая форма; ``parse(serialize(nodes)) == nodes``; для любой строки
``serialize(parse(serialize(parse(t)))) == serialize(parse(t))``.

Сырой HTML внутри блоков диалекта не поддерживается (design §1) —
хранится и отображается как текст; нейтрализация HTML-векторов —
sanitize_rich.py (задача 1.2), здесь текст блоков не интерпретируется.
"""

import re

# Типы контейнеров ``:::`` (design §1). Новый тип блока = тип здесь +
# блок-модуль на фронте (design §2: расширение без правки ядра).
CONTAINER_TYPES = ("columns", "callout", "aside", "spoiler")

# Лимит глубины вложенности контейнеров (review-001-4.1 #1, major): ~400+
# вложенных :::callout без лимита роняли рекурсию RecursionError'ом —
# необработанный 500 на POST/PUT/revert. Превышение = структурная ошибка
# диалекта: strict (validate) → RichSyntaxError (ValueError) → толерантный
# fallback шва wiki.py (A-2, plain text + лог, БЕЗ 422); толерантный parse →
# текст + warning. Зеркальный лимит — frontend/static/js/wiki/rich/
# block-parser.js (MAX_DEPTH), страховка RecursionError — шов wiki.py.
MAX_DEPTH = 100

CALLOUT_TYPES = ("info", "warn", "success")

# width∈10..100 — whitelist атрибута масштаба (tasks.md 1.2б; NFR-34 не меняется)
WIDTH_MIN = 10
WIDTH_MAX = 100

# --------------------------------------------------------------------------
# Строчные паттерны грамматики
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")
_CONTAINER_RE = re.compile(r"^:::([a-zA-Z]+)(.*)$")
_CONTAINER_CLOSE_RE = re.compile(r"^:::\s*$")
_COLUMN_SEP_RE = re.compile(r"^<<<\s*$")

# title="…" в атрибутах контейнера (\" — экранированная кавычка)
_SPOILER_TITLE_RE = re.compile(r'title="((?:[^"\\]|\\.)*)"')
_CALLOUT_TYPE_RE = re.compile(r"type=([a-zA-Z]+)")

# ![alt](src){width=N} — единственная строка-кандидат в блок-изображение
_IMAGE_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)(?:\{width=(\d+)\})?\s*$")


class RichSyntaxError(ValueError):
    """Структурная ошибка диалекта (tasks.md 1.1в). ValueError по контракту
    шва 1.3: перехватывается толерантным fallback'ом, НЕ превращается в 422."""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"{message} (строка {line})")
        self.line = line


def _text_node(text: str) -> dict:
    return {"type": "text", "text": text}


# --------------------------------------------------------------------------
# Таблицы (FR-117)
# --------------------------------------------------------------------------


def _split_row(line: str) -> list[str]:
    """Строка ``| a | b |`` → ['a', 'b']; ``\\|`` — экранированная вертикальная
    черта (GFM), в ячейке становится литеральным ``|``."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells: list[str] = []
    buffer: list[str] = []
    escaped = False
    for char in body:
        if escaped:
            buffer.append("|" if char == "|" else "\\" + char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(buffer).strip())
            buffer = []
            continue
        buffer.append(char)
    if escaped:
        buffer.append("\\")
    cells.append("".join(buffer).strip())
    return cells


def _parse_align(cell: str) -> str | None:
    """Ячейка разделителя: ``---`` → 'default', ``:---`` → 'left',
    ``---:`` → 'right', ``:---:`` → 'center'; мусор → None (кандидат не
    таблица). 'default' отличен от 'left': каноническая сериализация
    ``---`` сохраняется (круговая преобразуемость 1.1б)."""
    stripped = cell.strip().replace(" ", "")
    if not stripped or set(stripped) - {"-", ":"}:
        return None
    left = stripped.startswith(":")
    right = stripped.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return "default"


def _serialize_align(align: str | None) -> str:
    return {
        None: "---",
        "default": "---",
        "left": ":---",
        "center": ":---:",
        "right": "---:",
    }[align]


def _try_parse_table(lines: list[str], start: int) -> tuple[dict, int] | None:
    """GFM-таблица с позиции start (строка-шапка) → (узел, след. позиция).
    None — кандидат не прошел разбор (нет валидного разделителя под шапкой):
    по fallback-политике строки останутся текстом (ревью A-2)."""
    if start + 1 >= len(lines):
        return None
    header = _split_row(lines[start])
    if not header or not lines[start].lstrip().startswith("|"):
        return None
    sep_cells = _split_row(lines[start + 1])
    if len(sep_cells) != len(header):
        return None
    aligns = [_parse_align(cell) for cell in sep_cells]
    if any(align is None for align in aligns):
        return None
    rows: list[list[str]] = []
    pos = start + 2
    while pos < len(lines) and lines[pos].lstrip().startswith("|"):
        cells = _split_row(lines[pos])
        # Короткая строка добивается пустыми, длинная обрезается — GFM-поведение
        rows.append((cells + [""] * len(header))[: len(header)])
        pos += 1
    return {"type": "table", "header": header, "align": aligns, "rows": rows}, pos


def _escape_cell(cell: str) -> str:
    """Ячейка → GFM-текст: ``|`` экранируется ``\\|`` (обратимо с _split_row),
    иначе ячейка «a | b» разорвала бы строку таблицы."""
    return cell.replace("\\|", "\\\\|").replace("|", "\\|")


def _serialize_table(node: dict) -> str:
    lines = ["| " + " | ".join(_escape_cell(c) for c in node["header"]) + " |"]
    lines.append("| " + " | ".join(_serialize_align(a) for a in node["align"]) + " |")
    for row in node["rows"]:
        lines.append("| " + " | ".join(_escape_cell(c) for c in row) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Изображение с масштабом (FR-123): ![alt](src){width=N}, N∈10..100
# --------------------------------------------------------------------------


def _parse_image_line(line: str) -> dict | None:
    match = _IMAGE_LINE_RE.match(line)
    if match is None:
        return None
    width: int | None = None
    if match.group(3) is not None:
        candidate = int(match.group(3))
        # Вне whitelist — атрибут отбрасывается (sanitize_rich 1.2б), парсинг
        # не валится: изображение остается без width (fallback не нужен).
        if WIDTH_MIN <= candidate <= WIDTH_MAX:
            width = candidate
    return {
        "type": "image",
        "alt": match.group(1),
        "src": match.group(2),
        "width": width,
    }


def _serialize_image(node: dict) -> str:
    line = f'![{node["alt"]}]({node["src"]})'
    if node.get("width") is not None:
        line += f'{{width={node["width"]}}}'
    return line


# --------------------------------------------------------------------------
# Контейнеры ::: (рекурсивно, FR-127)
# --------------------------------------------------------------------------


def _parse_spoiler_title(attrs: str, line_no: int) -> str:
    match = _SPOILER_TITLE_RE.search(attrs)
    if match is None:
        raise RichSyntaxError('spoiler требует title="…"', line_no)
    return match.group(1).replace('\\"', '"').replace("\\\\", "\\")


def _serialize_spoiler_title(title: str) -> str:
    return title.replace("\\", "\\\\").replace('"', '\\"')


def _serialize_container(node: dict) -> str:
    kind = node["type"]
    if kind == "columns":
        body = "\n<<<\n".join(serialize_nodes(c) for c in node["columns"])
        return f":::columns\n{body}\n:::"
    if kind == "callout":
        opener = f":::callout type={node['callout_type']}"
    elif kind == "spoiler":
        opener = f':::spoiler title="{_serialize_spoiler_title(node["title"])}"'
    else:
        opener = f":::{kind}"
    return f"{opener}\n{serialize_nodes(node['children'])}\n:::"


# --------------------------------------------------------------------------
# Ядро: построчный разбор
# --------------------------------------------------------------------------
#
# _parse_lines возвращает (узлы, след. позиция, закрыт_ли_контейнер):
# закрыт=True — остановка ПОСЛЕ строки :::; False — дошли до конца входа.


def _parse_lines(
    lines: list[str],
    start: int,
    stop_at_close: bool,
    strict: bool,
    warnings: list[str],
    depth: int = 0,
) -> tuple[list[dict], int, bool]:
    nodes: list[dict] = []
    text_buffer: list[str] = []
    pos = start

    def flush_text() -> None:
        if text_buffer:
            nodes.append(_text_node("\n".join(text_buffer)))
            text_buffer.clear()

    while pos < len(lines):
        line = lines[pos]

        if stop_at_close and _CONTAINER_CLOSE_RE.match(line):
            flush_text()
            return nodes, pos + 1, True

        # --- fenced code (FR-122): содержимое — буквальные строки --------
        fence = _FENCE_RE.match(line)
        if fence is not None:
            close = None
            scan = pos + 1
            while scan < len(lines):
                if _FENCE_CLOSE_RE.match(lines[scan]):
                    close = scan
                    break
                scan += 1
            if close is None:
                if strict:
                    raise RichSyntaxError("незакрытый fenced code ```", pos + 1)
                warnings.append(f"строка {pos + 1}: незакрытый ``` — текст")
                text_buffer.append(line)
                pos += 1
                continue
            flush_text()
            nodes.append(
                {
                    "type": "code",
                    "lang": fence.group(1).strip(),
                    "code": "\n".join(lines[pos + 1 : close]),
                }
            )
            pos = close + 1
            continue

        # --- контейнер :::type … ::: -------------------------------------
        container = _CONTAINER_RE.match(line)
        if container is not None:
            block_type = container.group(1).lower()
            if block_type not in CONTAINER_TYPES:
                if strict:
                    raise RichSyntaxError(
                        f"неизвестный тип контейнера :::{block_type}", pos + 1
                    )
                warnings.append(
                    f"строка {pos + 1}: неизвестный контейнер :::{block_type} — текст"
                )
                text_buffer.append(line)
                pos += 1
                continue
            if depth >= MAX_DEPTH:
                # Лимит вложенности (review-001-4.1 #1): превышение —
                # структурная ошибка, а не падение рекурсии.
                if strict:
                    raise RichSyntaxError(
                        f"превышена глубина вложенности (максимум {MAX_DEPTH})",
                        pos + 1,
                    )
                warnings.append(
                    f"строка {pos + 1}: превышена глубина вложенности — текст"
                )
                text_buffer.append(line)
                pos += 1
                continue
            flush_text()
            node, pos, _ = _parse_container(
                lines, pos, block_type, container.group(2), strict, warnings, depth
            )
            if node["type"] == "text":
                text_buffer.append(node["text"])
            else:
                nodes.append(node)
            continue

        # --- <<< вне колонок: кандидат не блок (текст / строгая ошибка) ---
        if _COLUMN_SEP_RE.match(line):
            if strict:
                raise RichSyntaxError("<<< вне контейнера :::columns", pos + 1)
            warnings.append(f"строка {pos + 1}: <<< вне колонок — текст")
            text_buffer.append(line)
            pos += 1
            continue

        # --- GFM-таблица (FR-117) ----------------------------------------
        if line.lstrip().startswith("|"):
            candidate = _try_parse_table(lines, pos)
            if candidate is not None:
                flush_text()
                nodes.append(candidate[0])
                pos = candidate[1]
                continue
            # GFM-шапка без валидного разделителя — НЕ блок (legacy-текст,
            # похожий на диалект; ревью A-2)

        # --- изображение-строка (FR-123) ----------------------------------
        image = _parse_image_line(line.strip())
        if image is not None:
            flush_text()
            nodes.append(image)
            pos += 1
            continue

        text_buffer.append(line)
        pos += 1

    flush_text()
    return nodes, pos, False


def _parse_container(
    lines: list[str],
    start: int,
    block_type: str,
    attrs: str,
    strict: bool,
    warnings: list[str],
    depth: int = 0,
) -> tuple[dict, int, bool]:
    """Разбор ``:::type … :::`` с рекурсивным содержимым (FR-127).
    Возвращает (узел, след. позиция, закрыт) — узел text при толерантном
    fallback'е. ``depth`` — уровень вложенности открываемого контейнера."""
    line_no = start + 1
    fallback = _fallback_text(lines, start)

    if block_type == "columns":
        return _parse_columns(lines, start, strict, warnings, fallback, depth)

    # callout / aside / spoiler: содержимое — рекурсивный _parse_lines
    if block_type == "callout":
        match = _CALLOUT_TYPE_RE.search(attrs)
        value = match.group(1).lower() if match else ""
        if value not in CALLOUT_TYPES:
            if strict:
                raise RichSyntaxError("callout требует type=info|warn|success", line_no)
            warnings.append(
                f"строка {line_no}: callout с недопустимым type={value!r} — текст"
            )
            return fallback
        children, pos, closed = _parse_lines(
            lines,
            start + 1,
            stop_at_close=True,
            strict=strict,
            warnings=warnings,
            depth=depth + 1,
        )
        if not closed:
            if strict:
                raise RichSyntaxError(f"незакрытый контейнер :::{block_type}", line_no)
            warnings.append(f"строка {line_no}: незакрытый :::{block_type} — текст")
            return fallback
        return {"type": "callout", "callout_type": value, "children": children}, pos, True

    if block_type == "aside":
        children, pos, closed = _parse_lines(
            lines,
            start + 1,
            stop_at_close=True,
            strict=strict,
            warnings=warnings,
            depth=depth + 1,
        )
        if not closed:
            if strict:
                raise RichSyntaxError("незакрытый контейнер :::aside", line_no)
            warnings.append(f"строка {line_no}: незакрытый :::aside — текст")
            return fallback
        return {"type": "aside", "children": children}, pos, True

    assert block_type == "spoiler"
    try:
        title = _parse_spoiler_title(attrs, line_no)
    except RichSyntaxError:
        if strict:
            raise
        warnings.append(f"строка {line_no}: spoiler без title — текст")
        return fallback
    children, pos, closed = _parse_lines(
        lines,
        start + 1,
        stop_at_close=True,
        strict=strict,
        warnings=warnings,
        depth=depth + 1,
    )
    if not closed:
        if strict:
            raise RichSyntaxError("незакрытый контейнер :::spoiler", line_no)
        warnings.append(f"строка {line_no}: незакрытый :::spoiler — текст")
        return fallback
    return {"type": "spoiler", "title": title, "children": children}, pos, True


def _fallback_text(lines: list[str], start: int) -> tuple[dict, int, bool]:
    """Толерантный fallback (ревью A-2): сырые строки кандидата от opener до
    закрывающего ::: (или до конца) возвращаются в текст КАК ЕСТЬ — re-save
    старой страницы не меняет контент."""
    collected: list[str] = []
    pos = start
    while pos < len(lines):
        collected.append(lines[pos])
        if _CONTAINER_CLOSE_RE.match(lines[pos]):
            return _text_node("\n".join(collected)), pos + 1, True
        pos += 1
    return _text_node("\n".join(collected)), pos, False


def _parse_columns(
    lines: list[str],
    start: int,
    strict: bool,
    warnings: list[str],
    fallback: tuple[dict, int, bool],
    depth: int = 0,
) -> tuple[dict, int, bool]:
    """``:::columns`` … ``:::``: колонок минимум две, разделитель ``<<<``
    строкой верхнего уровня (FR-118); содержимое колонки — рекурсивный разбор
    (FR-127: таблица/код/контейнер внутри колонки). Сканер учитывает глубину
    контейнеров и fenced code, чтобы ``<<<`` внутри вложенного блока не
    делил колонки внешнего."""
    line_no = start + 1
    segments: list[list[str]] = [[]]
    depth = 0
    in_fence = False
    pos = start + 1
    closed = False
    while pos < len(lines):
        line = lines[pos]
        if in_fence:
            segments[-1].append(line)
            if _FENCE_CLOSE_RE.match(line):
                in_fence = False
            pos += 1
            continue
        if _FENCE_RE.match(line):
            in_fence = True
            segments[-1].append(line)
            pos += 1
            continue
        opener = _CONTAINER_RE.match(line)
        if opener is not None:
            depth += 1
            segments[-1].append(line)
            pos += 1
            continue
        if _CONTAINER_CLOSE_RE.match(line):
            if depth == 0:
                closed = True
                pos += 1
                break
            depth -= 1
            segments[-1].append(line)
            pos += 1
            continue
        if depth == 0 and _COLUMN_SEP_RE.match(line):
            segments.append([])
            pos += 1
            continue
        segments[-1].append(line)
        pos += 1
    if not closed:
        if strict:
            raise RichSyntaxError("незакрытый контейнер :::columns", line_no)
        warnings.append(f"строка {line_no}: незакрытый :::columns — текст")
        return fallback
    if in_fence and not strict:
        # fence может продолжаться до конца входа — внутренний разбор seg
        # сам вернет текст (незакрытый ``` — текст)
        pass
    if len(segments) < 2:
        if strict:
            raise RichSyntaxError("колонок меньше двух (нужен разделитель <<<)", line_no)
        warnings.append(f"строка {line_no}: одна колонка в :::columns — текст")
        return fallback
    columns: list[list[dict]] = []
    for segment in segments:
        nodes, _, _ = _parse_lines(
            segment,
            0,
            stop_at_close=False,
            strict=strict,
            warnings=warnings,
            depth=depth + 1,
        )
        if strict and not any(
            node["type"] != "text" or node["text"].strip() for node in nodes
        ):
            raise RichSyntaxError("колонка без содержимого", line_no)
        columns.append(nodes)
    return {"type": "columns", "columns": columns}, pos, True


# --------------------------------------------------------------------------
# Публичный контракт
# --------------------------------------------------------------------------


def parse(content: str) -> list[dict]:
    """Толерантный разбор контента → список узлов (design §1 fallback-политика):
    кандидат в блок, не прошедший разбор, остается текстом; исключений нет."""
    if content == "":
        return []
    nodes, _, _ = _parse_lines(
        content.split("\n"), 0, stop_at_close=False, strict=False, warnings=[]
    )
    return nodes


def parse_strict(content: str) -> list[dict]:
    """Строгий разбор (новый rich-контент редактора): структурная ошибка →
    RichSyntaxError (подкласс ValueError) с позицией строки."""
    nodes, _, _ = _parse_lines(
        content.split("\n"), 0, stop_at_close=False, strict=True, warnings=[]
    )
    return nodes


def validate(content: str) -> list[dict]:
    """Валидация контента швом сохранения (wiki.py, задача 1.3): структурная
    ошибка → RichSyntaxError (ValueError) с позицией; успешный результат —
    дерево. Шов перехватывает ValueError → толерантный fallback (БЕЗ 422)."""
    return parse_strict(content)


def has_rich_blocks(nodes: list[dict]) -> bool:
    """Есть ли в дереве хотя бы один блок диалекта (чек legacy passthrough)."""
    return any(node["type"] != "text" for node in nodes)


def content_has_blocks(content: "str | list[dict]") -> bool:
    """Чек по контенту ИЛИ по готовому дереву: есть ли блок диалекта."""
    if isinstance(content, str):
        content = parse(content)
    return has_rich_blocks(content)


def serialize_nodes(nodes: list[dict]) -> str:
    """Дерево → текст диалекта (tasks.md 1.1б); text-узлы — как есть."""
    return "\n".join(_serialize_node(node) for node in nodes)


def _serialize_node(node: dict) -> str:
    kind = node["type"]
    if kind == "text":
        return node["text"]
    if kind == "table":
        return _serialize_table(node)
    if kind == "code":
        return f"```{node['lang']}\n{node['code']}\n```"
    if kind == "image":
        return _serialize_image(node)
    return _serialize_container(node)


def serialize(content_or_nodes: "str | list[dict]") -> str:
    """serialize(nodes) → текст; serialize(text) → каноническая форма текста
    (толерантный разбор + сериализация)."""
    if isinstance(content_or_nodes, str):
        return serialize_nodes(parse(content_or_nodes))
    return serialize_nodes(content_or_nodes)
