"""Санитизация HTML для wiki-контента (change add-wiki, tasks.md 2.2;
design.md §4; NFR-31, ОГР-8).

Собственный sanitizer на html.parser stdlib — БЕЗ внешних библиотек
(bleach/lxml запрещены принципом продукта, ОГР-8).

Правила (design.md §4 дословно):
- Whitelist тегов = тулбар редактора (FR-110): h1 h2 h3 p br b strong i em u
  ul ol li blockquote pre code a img table thead tbody tr th td + структурные
  div span (перенос из contenteditable).
- Whitelist атрибутов: a[href, title], img[src, alt, width — только целое],
  td/th[colspan, rowspan]; все прочие атрибуты снимаются — в т.ч. любые
  on*, style, class, id.
- URL-фильтр: a[href], img[src] — только http:, https: и относительные;
  javascript:, data: (кроме data:image/ для img) и прочие схемы вырезаются
  вместе с атрибутом.
- Запрещенные теги: script/style вырезаются С СОДЕРЖИМЫМ; остальные
  (iframe, object, form, ...) — разворачиваются (содержимое остается,
  тег и его атрибуты — нет).

Место применения — на записи (POST/PUT/revert, app/wiki.py): в БД лежит
только чистый HTML. Функция sanitize_html(html: str) -> str — единая точка
входа; чистый текст без разметки проходит без искажений.
"""

import html as _html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

# Whitelist тегов (design.md §4).
ALLOWED_TAGS = frozenset(
    {
        "h1", "h2", "h3", "p", "br", "b", "strong", "i", "em", "u",
        "ul", "ol", "li", "blockquote", "pre", "code", "a", "img",
        "table", "thead", "tbody", "tr", "th", "td", "div", "span",
    }
)

# Пустые элементы: закрывающий тег не ожидается и не эмитится.
VOID_TAGS = frozenset({"br", "img"})

# Теги, вырезаемые вместе с содержимым (design.md §4); прочие запрещенные
# теги разворачиваются — содержимое остается, тег нет.
DROP_CONTENT_TAGS = frozenset({"script", "style"})

# Whitelist атрибутов (design.md §4 + возврат живой приемки 2026-10-11:
# img width — масштаб изображений как в Confluence); все прочие — снимаются.
ALLOWED_ATTRS: dict[str, tuple[str, ...]] = {
    "a": ("href", "title"),
    "img": ("src", "alt", "width"),
    "td": ("colspan", "rowspan"),
    "th": ("colspan", "rowspan"),
    # P12 rich-блоки (design.md §1–§2): словарь data-атрибутов div'ов.
    # Значения валидируются по словарю (_safe_block_attr), невалидное
    # значение → атрибут снимается → блок деградирует в контент (NFR-39).
    "div": ("data-block", "data-block-part", "data-title", "data-lang"),
}

# ---------------------------------------------------------------------
# P12 rich-блоки: словарь блоков (design.md §1 — единственный источник
# истины; продублирован в frontend/static/js/wiki/rich/model.js, тест
# согласования — tests/api/test_sanitize.py).
# ---------------------------------------------------------------------

# div[data-block] — тип rich-блока.
DATA_BLOCK_VALUES = frozenset({"spoiler", "code", "tabs"})
# div[data-block-part] — часть блока (тело спойлера / вкладка табов).
DATA_BLOCK_PART_VALUES = frozenset({"body", "tab"})
# div[data-lang] — язык код-блока.
DATA_LANG_VALUES = frozenset({"python", "js", "bash", "json", "sql", "plain"})

# data-атрибуты div'ов, проходящие whitelist (значения — по словарям выше;
# data-title — произвольный текст, экранируется при эмите).
BLOCK_DATA_ATTRS: tuple[str, ...] = (
    "data-block",
    "data-block-part",
    "data-title",
    "data-lang",
)

# Глубина вложенности блоков (design.md §2/§6): div[data-block] глубже —
# unwrap (содержимое остается, виджет не строится).
MAX_BLOCK_DEPTH = 5

# Структурные теги таблицы (для запрета table-in-table, design.md §2/F3).
_TABLE_TAGS = frozenset({"table", "thead", "tbody", "tr", "td", "th"})


def _safe_block_attr(name: str, value: str | None) -> str | None:
    """Валидация значений data-атрибутов блоков (design.md §2). None —
    атрибут снять (блок деградирует в контент, NFR-39)."""
    if value is None:
        return None
    if name == "data-block":
        return value if value in DATA_BLOCK_VALUES else None
    if name == "data-block-part":
        return value if value in DATA_BLOCK_PART_VALUES else None
    if name == "data-lang":
        return value if value in DATA_LANG_VALUES else None
    return value  # data-title — произвольный текст (экранируется при эмите)

# img[width]: только целое число (возврат живой приемки 2026-10-11 —
# масштаб изображений). Все, что не целое (дробное, отрицательное, мусор),
# — атрибут снимается, в духе URL-проверок.
_WIDTH_RE = re.compile(r"^\d+$")


def _safe_width(value: str | None) -> str | None:
    """img[width]: только целое (плюс — уже покрыт ^\\d+$). None — снять."""
    if value is None:
        return None
    candidate = value.strip()
    if not _WIDTH_RE.fullmatch(candidate):
        return None
    return candidate

# Разрешенные схемы URL (design.md §4): http/https/относительные;
# data: — только data:image/ (для img). Прочее (javascript:, vbscript:)
# режется вместе с атрибутом.
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

# Управляющие символы и пробелы вырезаются перед разбором схемы:
# браузеры игнорируют их внутри URL («java\tscript:» и т.п.).
_URL_JUNK_RE = re.compile(r"[\x00-\x20\x7f]+")


def _safe_url(value: str | None, is_img: bool) -> str | None:
    """URL-фильтр (design.md §4). None — атрибут вырезать целиком.

    javascript:/vbscript:/прочие схемы запрещены всегда; data:image/ —
    разрешен только для img[src] (по ТЗ задачи 2.2); http/https и
    относительные URL — проходят.
    """
    if value is None:
        return None
    url = value.strip()
    if not url:
        return None
    collapsed = _URL_JUNK_RE.sub("", url)
    lowered = collapsed.lower()
    if lowered.startswith("data:"):
        return url if is_img and lowered.startswith("data:image/") else None
    scheme = urlparse(lowered).scheme
    if scheme and scheme not in _ALLOWED_URL_SCHEMES:
        return None
    return url


class _Sanitizer(HTMLParser):
    """Потоковый фильтр: rebuild разрешенных тегов, unwrap прочих.

    Контексты (P12, design.md §2):
    - ``_block_depth`` — счетчик открытых div[data-block]; глубина больше
      MAX_BLOCK_DEPTH → блок-div разворачивается (содержимое остается);
    - ``_code_depth`` — внутри div[data-block="code"] разрешены только
      pre/code и текст (остальные теги unwrap'ятся);
    - ``_nested_table`` — таблица внутри td/th целиком разворачивается:
      структурные теги table/thead/tbody/tr/td/th не эмитятся, текст
      ячеек сохраняется, ячейки разделяются <br> (запрет table-in-table).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        # Открытые разрешенные теги: (тег, роль) — роль: None | 'block'
        # (div[data-block]) | 'code' (код-блок); параллельно закрывается.
        self._stack: list[tuple[str, str | None]] = []
        self._skip_tag: str | None = None  # активный script/style
        self._skip_depth = 0
        self._block_depth = 0
        self._code_depth = 0
        self._nested_table = 0
        self._nt_cells_seen = 0  # ячеек вложенной таблицы уже начато

    # -- контексты ---------------------------------------------------------

    def _inside_cell(self) -> bool:
        """Открыт ли сейчас td/th (для запрета table-in-table)."""
        return any(tag in ("td", "th") for tag, _role in self._stack)

    def _in_nested_table(self) -> bool:
        return self._nested_table > 0

    # -- теги ------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        if self._skip_tag is not None:
            # Вложенные одноименные теги внутри script/style — счетчик
            # глубины, содержимое режется до парного закрытия.
            if tag == self._skip_tag:
                self._skip_depth += 1
            return
        if tag in DROP_CONTENT_TAGS:
            self._skip_tag = tag
            self._skip_depth = 1
            return

        # Код-блок: разрешены только pre/code и текст (design.md §2).
        if self._code_depth > 0 and tag not in ("pre", "code"):
            return  # unwrap — текст останется, разметка кода смывается

        # Вложенная таблица: структурные теги не эмитятся, текст ячеек
        # сохраняется, ячейки разделяются <br> (design.md §2, находка F3).
        if self._in_nested_table():
            if tag == "table":
                self._nested_table += 1
                return
            if tag in _TABLE_TAGS:
                if tag in ("td", "th"):
                    if self._nt_cells_seen:
                        self._out.append("<br>")
                    self._nt_cells_seen += 1
                return
        elif tag == "table" and self._inside_cell():
            # Перед содержимым вложенной таблицы, идущим после текста
            # ячейки, — разделитель <br> (текст ячейки не слипается).
            if self._out and not self._out[-1].endswith(">"):
                self._out.append("<br>")
            self._nested_table += 1
            self._nt_cells_seen = 0
            return

        if tag in ALLOWED_TAGS:
            is_block_div = False
            is_code_block = False
            if tag == "div" and self._has_block_type(attrs):
                # Глубина блоков: лимит MAX_BLOCK_DEPTH, глубже — unwrap
                # (design.md §2/§6).
                if self._block_depth >= MAX_BLOCK_DEPTH:
                    return
                is_block_div = True
                is_code_block = self._block_type(attrs) == "code"
            self._out.append(self._render_start(tag, attrs))
            if tag not in VOID_TAGS:
                role = "code" if is_code_block else ("block" if is_block_div else None)
                self._stack.append((tag, role))
                if is_block_div:
                    self._block_depth += 1
                if is_code_block:
                    self._code_depth += 1
        # Прочие запрещенные теги — unwrap: сам тег не эмитится,
        # содержимое обрабатывается дальше как обычно.

    def handle_endtag(self, tag):
        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth <= 0:
                    self._skip_tag = None
            return

        # Конец вложенной таблицы: структурные теги не эмитятся (см.
        # handle_starttag — table-in-table режется, design.md §2).
        if self._in_nested_table() and tag in _TABLE_TAGS:
            if tag == "table":
                self._nested_table -= 1
            return

        # Закрываем только реально открытые разрешенные теги; закрывающий
        # тег без открывающего — игнорируется (висячие </b> не эмитятся).
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            if not any(open_tag == tag for open_tag, _role in self._stack):
                return
            while self._stack:
                open_tag, role = self._stack.pop()
                self._out.append(f"</{open_tag}>")
                if role == "block":
                    self._block_depth -= 1
                if role == "code":
                    self._code_depth -= 1
                if open_tag == tag:
                    break

    def handle_startendtag(self, tag, attrs):
        """Самозакрытый синтаксис <tag/>: для void — один тег, для прочих —
        открытая+закрытая пара (в HTML </b> после <b/> обязателен)."""
        if tag in DROP_CONTENT_TAGS:
            return  # <script/> — содержимого нет, режется целиком
        before = len(self._stack)
        self.handle_starttag(tag, attrs)
        if len(self._stack) > before:
            # starttag открыл тег — закрываем его здесь же
            open_tag, role = self._stack.pop()
            self._out.append(f"</{open_tag}>")
            if role == "block":
                self._block_depth -= 1
            if role == "code":
                self._code_depth -= 1

    # -- данные и сущности -----------------------------------------------

    def handle_data(self, data):
        if self._skip_tag is not None:
            return  # содержимое script/style не проходит
        self._out.append(_html.escape(data, quote=False))

    # -- блоки --------------------------------------------------------------

    @staticmethod
    def _block_type(attrs: list[tuple[str, str | None]]) -> str | None:
        for name, value in attrs:
            if name == "data-block":
                return _safe_block_attr(name, value)
        return None

    def _has_block_type(self, attrs: list[tuple[str, str | None]]) -> bool:
        return self._block_type(attrs) is not None

    # -- сборка ------------------------------------------------------------

    def _render_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        parts = [tag]
        allowed = ALLOWED_ATTRS.get(tag, ())
        for name, value in attrs:
            if name not in allowed:
                continue  # on*, style, class, id и прочие — снимаются
            if name in BLOCK_DATA_ATTRS:
                value = _safe_block_attr(name, value)
                if value is None:
                    continue  # невалидное значение словаря — атрибут снят
            if name in ("href", "src"):
                value = _safe_url(value, is_img=(tag == "img"))
                if value is None:
                    continue  # запрещенная схема — атрибут вырезан
            if name == "width" and tag == "img":
                value = _safe_width(value)
                if value is None:
                    continue  # нецелое — атрибут снят (возврат приемки)
            parts.append(f'{name}="{_html.escape(value or "", quote=True)}"')
        return "<" + " ".join(parts) + ">"

    def result(self) -> str:
        self.close()
        # Незакрытые к концу входа разрешенные теги дозакрываются —
        # на выходе сбалансированная разметка.
        while self._stack:
            self._out.append(f"</{self._stack.pop()}>")
        return "".join(self._out)


def sanitize_html(html: str) -> str:
    """Санитизация HTML-контента wiki (design.md §4): whitelist тегов и
    атрибутов, URL-фильтр, script/style с содержимым, прочие запрещенные
    теги — unwrap. Возвращает безопасную строку (пустой вход — пустой выход)."""
    if not html:
        return ""
    parser = _Sanitizer()
    parser.feed(html)
    return parser.result()
