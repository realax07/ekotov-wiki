"""Санитизация HTML для wiki-контента (change add-wiki, tasks.md 2.2;
design.md §4; NFR-31, ОГР-8).

Собственный sanitizer на html.parser stdlib — БЕЗ внешних библиотек
(bleach/lxml запрещены принципом продукта, ОГР-8).

Правила (design.md §4 дословно):
- Whitelist тегов = тулбар редактора (FR-110): h1 h2 h3 p br b strong i em u
  ul ol li blockquote pre code a img table thead tbody tr th td + структурные
  div span (перенос из contenteditable).
- Whitelist атрибутов: a[href, title], img[src, alt], td/th[colspan, rowspan];
  все прочие атрибуты снимаются — в т.ч. любые on*, style, class, id.
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

# Whitelist атрибутов (design.md §4); все прочие — снимаются.
ALLOWED_ATTRS: dict[str, tuple[str, ...]] = {
    "a": ("href", "title"),
    "img": ("src", "alt"),
    "td": ("colspan", "rowspan"),
    "th": ("colspan", "rowspan"),
}

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
    """Потоковый фильтр: rebuild разрешенных тегов, unwrap прочих."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._stack: list[str] = []  # открытые разрешенные теги
        self._skip_tag: str | None = None  # активный script/style
        self._skip_depth = 0

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
        if tag in ALLOWED_TAGS:
            self._out.append(self._render_start(tag, attrs))
            if tag not in VOID_TAGS:
                self._stack.append(tag)
        # Прочие запрещенные теги — unwrap: сам тег не эмитится,
        # содержимое обрабатывается дальше как обычно.

    def handle_endtag(self, tag):
        if self._skip_tag is not None:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth <= 0:
                    self._skip_tag = None
            return
        # Закрываем только реально открытые разрешенные теги; закрывающий
        # тег без открывающего — игнорируется (висячие </b> не эмитятся).
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS and tag in self._stack:
            while self._stack:
                top = self._stack.pop()
                self._out.append(f"</{top}>")
                if top == tag:
                    break

    def handle_startendtag(self, tag, attrs):
        """Самозакрытый синтаксис <tag/>: для void — один тег, для прочих —
        открытая+закрытая пара (в HTML </b> после <b/> обязателен)."""
        if self._skip_tag is not None:
            return
        if tag in DROP_CONTENT_TAGS:
            return  # <script/> — содержимого нет, режется целиком
        if tag in ALLOWED_TAGS:
            self._out.append(self._render_start(tag, attrs))
            if tag not in VOID_TAGS:
                self._out.append(f"</{tag}>")

    # -- данные и сущности -----------------------------------------------

    def handle_data(self, data):
        if self._skip_tag is not None:
            return  # содержимое script/style не проходит
        self._out.append(_html.escape(data, quote=False))

    # -- сборка ------------------------------------------------------------

    def _render_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        parts = [tag]
        allowed = ALLOWED_ATTRS.get(tag, ())
        for name, value in attrs:
            if name not in allowed:
                continue  # on*, style, class, id и прочие — снимаются
            if name in ("href", "src"):
                value = _safe_url(value, is_img=(tag == "img"))
                if value is None:
                    continue  # запрещенная схема — атрибут вырезан
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
