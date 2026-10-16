"""Санитизация rich-контента wiki (change add-rich-editor, tasks.md 1.2;
design.md §3 D3; FR-126, NFR-35).

ОТДЕЛЬНЫЙ модуль по директиве Заказчика: существующий ``sanitize.py`` не
переписывается и не дополняется — здесь переиспользуются его helpers через
импорт (``sanitize_html``, ``_safe_url``), сам файл не меняется.

Правила (tasks.md 1.2; design §1/§6):
- URL-фильтр в инлайн-разметке блоков: ``[text](url)``, ``![alt](src)`` —
  http/https/относительные проходят; ``javascript:``/``data:`` (и прочие
  схемы) — нейтрализуются (URL вырезается, текст остается);
- whitelist атрибутов диалекта: callout ``type`` ∈ {info,warn,success}
  (иное → info), spoiler ``title`` (текст), image ``width`` ∈ 10..100
  (вне whitelist — атрибут отбрасывается, NFR-34 не меняется);
- HTML-векторы в тексте блоков (``<script>``, ``<iframe>``, ``<object>``,
  ``on*=``, любые теги) нейтрализуются НА ЗАПИСИ экранированием ``<``/``>``
  — хранятся и отдаются как текст, в DOM не интерпретируются (рендер rich-
  пути строит DOM через createElement/textContent — второй слой защиты,
  design §6); экранирование идемпотентно (re-save не меняет контент);
- вложенные блоки (колонки/callout/врезки/спойлеры) — рекурсивно (FR-127);
- инвариант legacy-passthrough (ревью M-4): контент без блоков диалекта
  проходит ``sanitize_rich`` ИДЕНТИЧНО ``sanitize_html`` —
  ``sanitize_rich(legacy) == sanitize_html(legacy)``; re-save старой
  страницы не меняет контент (NFR-36/38).

Место применения — НА ЗАПИСИ (POST/PUT/revert, шов wiki.py задачи 1.3).
GET отдает контент как сохранен (ревью A-1: слоя повторной санитизации
при отдаче нет и не заводится).
"""

import re

from app.rich_blocks import (
    CALLOUT_TYPES,
    WIDTH_MAX,
    WIDTH_MIN,
    parse,
    serialize_nodes,
)
from app.sanitize import _safe_url, sanitize_html

# Экранирование только < и > — идемпотентно (в экранированной строке новых
# < нет) и обратимо на фронте (& не экранируем, чтобы не портить сущности).
_HTML_ESCAPES = (("<", "&lt;"), (">", "&gt;"))


def _safe_rich_url(url: str, is_img: bool) -> str | None:
    """URL-фильтр rich-пути (tasks.md 1.2а): javascript:/data: — нейтрализованы
    ЦЕЛИКОМ (в отличие от legacy-исключения data:image/ в sanitize.py —
    rich-изображение ссылается только на галерейные /images/{id}, NFR-34)."""
    if url.lower().lstrip().startswith("data:"):
        return None
    return _safe_url(url, is_img=is_img)


def escape_block_text(text: str) -> str:
    """Текст блока → безопасный текст: теги нейтрализованы как текст."""
    for char, entity in _HTML_ESCAPES:
        text = text.replace(char, entity)
    return text


# Инлайн-разметка диалекта (design §1: текст + **b**, *i*, `code`,
# [link](url), ![img](src){width=N}); фильтруются URL и width. URL-группа
# допускает ОДИН уровень скобок (javascript:alert(1) режется целиком, без
# остаточной скобки в тексте).
#
# SECURITY-ИНВАРИАНТ (review-001-4.1 #2): строка-кандидат блока-изображения,
# чей URL содержит скобки (`![a](javascript:alert(1))`), НЕ матчится
# rich_blocks._IMAGE_LINE_RE — уходит в legacy-passthrough БЕЗ rich-фильтра
# URL. Это осознанная граница, а не дыра: инвариант M-4 запрещает фильтровать
# legacy-сегменты (sanitize_rich(legacy) == sanitize_html(legacy), тест
# зафиксирован), а защита = ТОЧНАЯ идентичность зеркальных regex бэка и
# фронта: фронтовый block-parser.js IMAGE_LINE_RE — дословное зеркало, такой
# сегмент рендерится как ТЕКСТ (textContent/createElement — не исполняется,
# safeUrl — второй слой). Менять один из двух regex БЕЗ синхронного зеркала
# и дифтеста (fixture URL-со-скобками в test_rich_blocks/test_rich_editor)
# НЕЛЬЗЯ.
_URL_GROUP = r"((?:[^()\s]|\([^()]*\))*)"
_IMAGE_INLINE_RE = re.compile(
    r"!\[([^\]]*)\]" + r"\(" + _URL_GROUP + r"\)(?:\{width=(\d+)\})?"
)
_LINK_INLINE_RE = re.compile(r"\[([^\]]*)\]" + r"\(" + _URL_GROUP + r"\)")


def _filter_image_widths(match: "re.Match[str]") -> str:
    alt, src, width = match.group(1), match.group(2), match.group(3)
    safe_src = _safe_rich_url(src, is_img=True)
    if safe_src is None:
        # javascript:/data: и прочие схемы — нейтрализованы: URL вырезан
        return f"![{alt}]()"
    safe = f"![{alt}]({safe_src})"
    if width is not None:
        candidate = int(width)
        if WIDTH_MIN <= candidate <= WIDTH_MAX:
            safe += f"{{width={candidate}}}"
        # вне whitelist — атрибут отбрасывается (1.2б), изображение остается
    return safe


def _filter_link_urls(match: "re.Match[str]") -> str:
    text, url = match.group(1), match.group(2)
    safe_url = _safe_url(url, is_img=False)
    if safe_url is None:
        return f"[{text}]()"  # схема вырезана, текст ссылки остается
    return f"[{text}]({safe_url})"


def sanitize_inline(text: str) -> str:
    """Инлайн-текст блока: URL-фильтр ссылок/изображений + нейтрализация
    HTML-векторов (теги → текст)."""
    text = _IMAGE_INLINE_RE.sub(_filter_image_widths, text)
    text = _LINK_INLINE_RE.sub(_filter_link_urls, text)
    return escape_block_text(text)


def sanitize_block(node: dict) -> dict:
    """Рекурсивная санитизация узла дерева (1.2г): whitelist атрибутов,
    URL-фильтр и нейтрализация HTML-векторов на любой глубине вложенности."""
    kind = node["type"]
    if kind == "text":
        return {"type": "text", "text": sanitize_inline(node["text"])}
    if kind == "table":
        return {
            "type": "table",
            "header": [sanitize_inline(cell) for cell in node["header"]],
            "align": list(node["align"]),
            "rows": [[sanitize_inline(cell) for cell in row] for row in node["rows"]],
        }
    if kind == "code":
        # Код-блок: буквальный текст (вектор <script> — текст без исполнения),
        # URL-фильтр к коду не применяется (это не разметка ссылок).
        return {
            "type": "code",
            "lang": escape_block_text(node["lang"]),
            "code": escape_block_text(node["code"]),
        }
    if kind == "image":
        safe_src = _safe_rich_url(node["src"], is_img=True)
        sanitized: dict = {
            "type": "image",
            "alt": sanitize_inline(node["alt"]),
            "src": safe_src if safe_src is not None else "",
            "width": None,
        }
        width = node.get("width")
        if safe_src is not None and width is not None and WIDTH_MIN <= width <= WIDTH_MAX:
            sanitized["width"] = width
        return sanitized
    if kind == "callout":
        callout_type = node["callout_type"]
        if callout_type not in CALLOUT_TYPES:
            callout_type = "info"  # whitelist 1.2б: иное значение → info
        return {
            "type": "callout",
            "callout_type": callout_type,
            "children": [sanitize_block(child) for child in node["children"]],
        }
    if kind == "aside":
        return {
            "type": "aside",
            "children": [sanitize_block(child) for child in node["children"]],
        }
    if kind == "spoiler":
        return {
            "type": "spoiler",
            "title": sanitize_inline(node["title"]),
            "children": [sanitize_block(child) for child in node["children"]],
        }
    if kind == "columns":
        return {
            "type": "columns",
            "columns": [
                [sanitize_block(child) for child in column]
                for column in node["columns"]
            ],
        }
    # Неизвестный тип (не должен случаться): вернуть как текст — безопасно
    return {"type": "text", "text": sanitize_inline(str(node))}


def sanitize(content: str) -> str:
    """Санитизация контента страницы НА ЗАПИСИ (шов wiki.py 1.3).

    - Контент без блоков диалекта (legacy) — passthrough к ``sanitize_html``
      БЕЗ изменений (инвариант M-4: ``sanitize_rich(legacy) ==
      sanitize_html(legacy)``);
    - смешанный/rich-контент — по сегментам: legacy-текст между блоками —
      тот же ``sanitize_html``; блоки диалекта — ``sanitize_block`` +
      каноническая сериализация.
    """
    if not content:
        return sanitize_html(content)
    nodes = parse(content)
    if not any(node["type"] != "text" for node in nodes):
        # Только legacy-текст(ы): длина текста не менялась разбором —
        # толерантный парс lossless, поэтому это ровно старый путь.
        return sanitize_html(content)
    parts: list[str] = []
    for node in nodes:
        if node["type"] == "text":
            parts.append(sanitize_html(node["text"]))
        else:
            parts.append(serialize_nodes([sanitize_block(node)]))
    return "\n".join(parts)
