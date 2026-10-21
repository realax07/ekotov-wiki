#!/usr/bin/env python3
"""Генератор HTML-мокапов P23 v2 — вариант А под ограничение Заказчика:
в фастлайне ТОЛЬКО 1 задача одновременно (до выполнения).

5 страниц (только утвержденный вариант A, счетчик убран):
  v2-empty        — пустой фастлайн: полная зона, 3 пустых столбца, без подсказок
  v2-busy         — занято: 1 fast-карта в «В работе», остальные столбцы пусты
  v2-blocked      — занято + попытка вставить вторую: disabled-кнопка + чип-запрет
  v2-dnd-move     — DnD: единственная fast-карта переносится между столбцами
                    (голубой пунктир-приемник)
  v2-dnd-blocked  — DnD: обычная задача тянется в занятый фастлайн — запрет
                    (красный пунктир + знак запрета)
Рендер PNG — render_v2.py (playwright, 1440×900).
"""
from pathlib import Path

HERE = Path(__file__).parent

# ---------------------------------------------------------------- каркас
SIDEBAR = """
<aside class="sidebar">
  <nav class="sidebar-nav">
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M2 7h20M6 3v4" fill="none" stroke="currentColor" stroke-width="2"/></svg>Мониторинг</a>
    <a href="#" class="nav-item active"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 9h18M9 9v12" fill="none" stroke="currentColor" stroke-width="2"/></svg>Доска</a>
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.5 15.5l5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Поиск</a>
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5V5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>Wiki</a>
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="9.5" r="1.6" fill="currentColor"/><path d="M4.5 17.5l5-5.5 4 4.5 3-3 3 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>Галерея</a>
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 9.2l5 2.8-5 2.8V9.2z" fill="currentColor"/></svg>Видео</a>
    <a href="#" class="nav-item"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Погода</a>
  </nav>
  <div class="sidebar-footer"><button type="button" class="logout-button">Выйти</button></div>
</aside>"""

PRIO = {
    "high": ('priority-high', '#9c3524', 'M6 1.5 L10.5 8.5 H1.5 Z'),
    "medium": ('priority-medium', '#8a5a1e', None),
    "low": ('priority-low', '#5f6f34', 'M6 10.5 L1.5 3.5 H10.5 Z'),
}


def prio_badge(level, label):
    cls, color, tri = PRIO[level]
    if tri:
        icon = f'<svg class="prio-icon" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="{tri}" fill="{color}"/></svg>'
    else:
        icon = ('<svg class="prio-icon" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
                '<path d="M2 4.2h8M2 7.8h8" stroke="%s" stroke-width="2" stroke-linecap="round" fill="none"/></svg>' % color)
    return (f'<span class="task-priority-badge {cls}">{icon}{label}</span>')


def card(title, prio, prio_label, cat, due, assigned, creator, fast=False, extra_cls=""):
    fast_badge = '<span class="task-fast-badge">Fast</span>' if fast else ''
    fast_cls = ' task-card-fast' if fast else ''
    users = (f'<span>{assigned}</span><span>·</span><span>{creator}</span>'
             if assigned else f'<em class="task-card-unassigned">Unassigned</em><span>·</span><span>{creator}</span>')
    return f"""<article class="task-card task-priority-{prio}{fast_cls} {extra_cls}">
  <div class="task-card-header">
    <h3 class="task-card-title">{title}</h3>{fast_badge}
  </div>
  <div class="task-card-meta">
    <span class="task-category">{cat}</span>
    {prio_badge(prio, prio_label)}
    <span>{due}</span>
  </div>
  <div class="task-card-users">{users}</div>
</article>"""


def fl_column(title, cards_html, done=False, cls_extra=""):
    cls = "board-column board-column-done" if done else "board-column"
    if cls_extra:
        cls += f" {cls_extra}"
    body = cards_html if cards_html else '<div class="fastline-empty-col"></div>'
    return (f'<section class="{cls}"><h2 class="board-column-title">{title}</h2>'
            f'<div class="board-column-cards">{body}</div></section>')


def column(title, cards_html, done=False):
    cls = "board-column board-column-done" if done else "board-column"
    return (f'<section class="{cls}"><h2 class="board-column-title">{title}</h2>'
            f'<div class="board-column-cards">{cards_html}</div></section>')


FORBIDDEN_BADGE = ('<span class="drop-forbidden-badge" aria-hidden="true">'
                   '<svg viewBox="0 0 24 24" width="28" height="28">'
                   '<circle cx="12" cy="12" r="9.5" fill="#fffdf9" stroke="#9c3524" stroke-width="2"/>'
                   '<path d="M5.8 5.8l12.4 12.4" stroke="#9c3524" stroke-width="2"/></svg></span>')

# Единственная fast-задача (одна на весь фастлайн во всех кадрах)
FAST_TASK = dict(title="Перенести домен wiki на новый DNS", prio="high", prio_label="Высокий",
                 cat="Инфра", due="до 22.10", assigned="Заказчик", creator="Заказчик")

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>P23 v2 — Фастлайн — вариант А — {sname}</title>
<link rel="stylesheet" href="p23-base.css">
<link rel="stylesheet" href="p23-v2.css">
</head>
<body class="app-shell">
{sidebar}
<main class="content">
  <h1 class="page-title">Доска</h1>
  <p class="mock-sub">Мокап P23 v2 · вариант А (подложка + заголовок) · ограничение: 1 задача в фастлайне · состояние: {sname}</p>
  <p><button type="button" id="create-task-button">Создать задачу</button></p>
{fastline_html}
<hr class="board-sep">
<div id="board" class="board">
{board_html}
</div>
{extra}
</main>
</body>
</html>
"""

# ------------------------------------------------------------- канбан (общий)
BOARD = (column("Ожидает",
                card("Прогнать регресс e2e перед релизом", "medium", "Средний", "QA", "до 23.10", "Тестов", "Админ")
                + card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ"))
         + column("В работе",
                  card("Миграция ES-индекса задач", "medium", "Средний", "Бэкенд", "до 27.10", "Иванов", "Админ")
                  + card("Чистка устаревших снапшотов галереи", "low", "Низкий", "Галерея", "—", "Петров", "Заказчик"))
         + column("Выполнено",
                  card("Включить rate-limit на /api/login", "medium", "Средний", "Безопасность", "выполнено 18.10", "Иванов", "Админ"), done=True))


def fastline(cols, head_extra=""):
    """Шапка БЕЗ счетчика (решение ОВ-2: счетчик убрать)."""
    return f"""<section class="fastline fastline-a" aria-label="Фастлайн">
  <header class="fastline-head">
    <h2 class="fastline-title">FASTLINE</h2>
    {head_extra}
    <span class="fastline-note">одна задача за раз — 3 столбца = этапы одной fast-задачи</span>
  </header>
  <div class="fastline-board">
  {cols}
  </div>
</section>"""


def fast_card(**kw):
    d = dict(FAST_TASK)
    extra_cls = kw.pop("extra_cls", "")
    d.update(kw)
    return card(d["title"], d["prio"], d["prio_label"], d["cat"], d["due"],
                d["assigned"], d["creator"], fast=True, extra_cls=extra_cls)


# ------------------------------------------------------------- состояния
STATES = {}

STATES["empty"] = dict(
    sname="пустой фастлайн (подсказок нет, счетчика нет)",
    fastline=fastline(
        fl_column("Ожидает", "") + fl_column("В работе", "") + fl_column("Выполнено", "", done=True)),
    board=BOARD, extra="")

STATES["busy"] = dict(
    sname="занято — одна fast-задача на весь фастлайн",
    fastline=fastline(
        fl_column("Ожидает", "")
        + fl_column("В работе", fast_card())
        + fl_column("Выполнено", "", done=True)),
    board=BOARD, extra="""<p class="frame-note">
  <span><b>Занято:</b> во всем фастлайне — одна fast-задача; столбцы «Ожидает» → «В работе» → «Выполнено» — этапы её жизненного цикла.</span>
  <span>Новая fast-задача не вставляется, пока текущая не выполнена (выполненная покидает фастлайн).</span>
</p>""")

BLOCKED_HEAD = """<button type="button" class="fastline-add" disabled aria-disabled="true">+ Fast-задача</button>
    <span class="fastline-blocked-hint"><svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M5.8 5.8l12.4 12.4" stroke="currentColor" stroke-width="2.5"/></svg>В фастлайне уже есть задача — выполните текущую</span>"""

STATES["blocked"] = dict(
    sname="блокировка — вторую fast-задачу вставить нельзя",
    fastline=fastline(
        fl_column("Ожидает", "")
        + fl_column("В работе", fast_card())
        + fl_column("Выполнено", "", done=True),
        head_extra=BLOCKED_HEAD),
    board=BOARD, extra="""<p class="frame-note">
  <span><b>Блокировка:</b> пока в фастлайне есть задача, кнопка «+ Fast-задача» disabled (курсор not-allowed),</span>
  <span>рядом чип-запрет в error-цветах сайта: «В фастлайне уже есть задача — выполните текущую».</span>
  <span>Кнопка активна (голубая рамка) только при пустом фастлайне — кадр v2-empty.</span>
</p>""")

DND_MOVE_NOTE = """<p class="frame-note">
  <span><b>DnD (разрешено):</b> единственная fast-карта переносится между тремя столбцами фастлайна —</span>
  <span>зона-приемник подсвечивается голубым пунктиром (цвет зоны, не терракота канбана);</span>
  <span>карточка в полете — полупрозрачная с тенью, исходная — drag-ghost (наклон 3°, 35%). Ограничение «1 задача» при этом не нарушается.</span>
</p>"""

STATES["dnd-move"] = dict(
    sname="DnD — перенос единственной fast-карты между столбцами",
    fastline=fastline(
        fl_column("Ожидает", "")
        + fl_column("В работе", fast_card(extra_cls="drag-ghost"))
        + fl_column("Выполнено", fast_card(extra_cls="drag-flying"), done=True, cls_extra="drop-target")),
    board=BOARD, extra=DND_MOVE_NOTE)

DND_BLOCKED_BOARD = (column("Ожидает",
                            card("Прогнать регресс e2e перед релизом", "medium", "Средний", "QA", "до 23.10", "Тестов", "Админ")
                            + card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ", extra_cls="drag-ghost"))
                     + column("В работе",
                              card("Миграция ES-индекса задач", "medium", "Средний", "Бэкенд", "до 27.10", "Иванов", "Админ")
                              + card("Чистка устаревших снапшотов галереи", "low", "Низкий", "Галерея", "—", "Петров", "Заказчик"))
                     + column("Выполнено",
                              card("Включить rate-limit на /api/login", "medium", "Средний", "Безопасность", "выполнено 18.10", "Иванов", "Админ"), done=True))

DND_BLOCKED_NOTE = """<p class="frame-note">
  <span><b>DnD (запрещено):</b> обычная задача тянется из канбана в занятый фастлайн — вставка второй задачи невозможна:</span>
  <span>колонка-«приемник» отвечает красным пунктиром и знаком запрета (вместо голубого пунктира пустого фастлайна);</span>
  <span>курсор — not-allowed. Обычные задачи по-прежнему свободно ходят по основному канбану (терракотовый drop-target без изменений).</span>
</p>"""

STATES["dnd-blocked"] = dict(
    sname="DnD — обычная задача в занятый фастлайн: запрет",
    fastline=fastline(
        fl_column("Ожидает",
                  card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ", extra_cls="drag-flying")
                  + FORBIDDEN_BADGE, cls_extra="drop-forbidden")
        + fl_column("В работе", fast_card())
        + fl_column("Выполнено", "", done=True)),
    board=DND_BLOCKED_BOARD, extra=DND_BLOCKED_NOTE)


def main():
    for s, sdata in STATES.items():
        html = PAGE.format(
            sname=sdata["sname"], sidebar=SIDEBAR,
            fastline_html=sdata["fastline"], board_html=sdata["board"], extra=sdata["extra"])
        out = HERE / f"v2-{s}.html"
        out.write_text(html, encoding="utf-8")
        print("written", out.name)


if __name__ == "__main__":
    main()
