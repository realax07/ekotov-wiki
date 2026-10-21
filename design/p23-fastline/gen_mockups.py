#!/usr/bin/env python3
"""Генератор HTML-мокапов P23 «Фастлайн» (дизайн-фаза, волна 1).

6 страниц = 2 варианта отделения зоны × 3 состояния:
  variant-{a,b}-empty.html  — пустой фастлайн (без подсказок)
  variant-{a,b}-tasks.html  — 3 fast-задачи в столбцах
  variant-{a,b}-dnd.html    — кадр DnD: обычная задача летит В фастлайн
Рендер PNG — render.py (playwright, 1440×900).
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
             if assigned else '<em class="task-card-unassigned">Unassigned</em><span>·</span><span>{}</span>'.format(creator))
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


def fl_column(title, cards_html, done=False, drop=False, empty_pad=False):
    cls = "board-column board-column-done" if done else "board-column"
    if drop:
        cls += " drop-target"
    body = cards_html if cards_html else '<div class="fastline-empty-col"></div>' if empty_pad else ''
    return (f'<section class="{cls}"><h2 class="board-column-title">{title}</h2>'
            f'<div class="board-column-cards">{body}</div></section>')


def column(title, cards_html, done=False):
    cls = "board-column board-column-done" if done else "board-column"
    return (f'<section class="{cls}"><h2 class="board-column-title">{title}</h2>'
            f'<div class="board-column-cards">{cards_html}</div></section>')


def fastline(variant, cols, count, note=""):
    return f"""<section class="fastline fastline-{variant}" aria-label="Фастлайн">
  <header class="fastline-head">
    <span class="fastline-kicker">Fast line</span>
    <h2 class="fastline-title">Фастлайн</h2>
    <span class="fastline-count">{count}</span>
    <span class="fastline-note">{note}</span>
  </header>
  <div class="fastline-board">
  {cols}
  </div>
</section>"""


PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>P23 — Фастлайн — вариант {vname} — {sname}</title>
<link rel="stylesheet" href="p23-base.css">
</head>
<body class="app-shell">
{sidebar}
<main class="content">
  <h1 class="page-title">Доска</h1>
  <p class="mock-sub">Мокап P23 · вариант {vname}: {vdesc} · состояние: {sname}</p>
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

# ------------------------------------------------------------- содержимое
# Обычные (не-fast) задачи основного канбана — БЕЗ fast-бейджа, fast-таски
# только в фастлайне (требование заявки).
BOARD_TODO = (
    card("Прогнать регресс e2e перед релизом", "medium", "Средний", "QA", "до 23.10", "Тестов", "Админ")
    + card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ")
)
BOARD_PROGRESS = (
    card("Миграция ES-индекса задач", "medium", "Средний", "Бэкенд", "до 27.10", "Иванов", "Админ")
    + card("Чистка устаревших снапшотов галереи", "low", "Низкий", "Галерея", "—", "Петров", "Заказчик")
)
BOARD_DONE = card("Включить rate-limit на /api/login", "medium", "Средний", "Безопасность", "выполнено 18.10", "Иванов", "Админ")

FAST_COLS_TASKS = (
    fl_column("Ожидает", card("Перенести домен wiki на новый DNS", "high", "Высокий", "Инфра", "до 22.10", "Заказчик", "Заказчик", fast=True))
    + fl_column("В работе",
                card("Заблокировать доступ к админке извне", "high", "Высокий", "Безопасность", "до 21.10", "Иванов", "Заказчик", fast=True)
                + card("Срочный фикс: падение /api/board", "medium", "Средний", "Бэкенд", "до 20.10", "Петров", "Заказчик", fast=True))
    + fl_column("Выполнено", card("Продлить VPS до 2027", "low", "Низкий", "Инфра", "выполнено 19.10", "Админ", "Заказчик", fast=True), done=True)
)

FL_COLS_EMPTY = (
    fl_column("Ожидает", "", empty_pad=True)
    + fl_column("В работе", "", empty_pad=True)
    + fl_column("Выполнено", "", empty_pad=True, done=True)
)

# DnD-кадр: обычная задача «Обновить сертификат мониторинга» перетаскивается
# из основного канбана В столбец «Ожидает» фастлайна (зона-приемник голубым).
DND_BOARD_TODO = (
    card("Прогнать регресс e2e перед релизом", "medium", "Средний", "QA", "до 23.10", "Тестов", "Админ")
    + card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ", extra_cls="drag-ghost")
)
DND_COLS = (
    fl_column("Ожидает",
              card("Обновить сертификат мониторинга", "high", "Высокий", "Инфра", "до 21.10", "", "Админ", extra_cls="drag-flying"),
              drop=True)
    + fl_column("В работе", "", empty_pad=True)
    + fl_column("Выполнено", "", empty_pad=True, done=True)
)

DND_NOTE = """<p class="frame-note">
  <span><b>Кадр DnD:</b> обычная задача тянется из канбана в «Ожидает» фастлайна —
  зона-приемник подсвечивается голубым пунктиром (цвет зоны, не терракота канбана),</span>
  <span>карточка в полете — полупрозрачная с тенью; исходная в канбане — drag-ghost (наклон 3°, 35%).</span>
  <span>Обратное направление (из фастлайна в канбан) — тем же механизмом, приемник канбана подсвечивается терракотой как сейчас.</span>
</p>"""

VARIANTS = {
    "a": dict(vname="А", vdesc="подложка (голубой тинт) + заголовок «Фастлайн»",
              note="таски фастлайна живут только здесь"),
    "b": dict(vname="Б", vdesc="рамка-контейнер с голубой верхней кромкой",
              note="быстрая линия · 3 столбца"),
}

STATES = {
    "empty": dict(
        sname="пустой фастлайн (подсказок нет)",
        fastline=lambda v: fastline(v, FL_COLS_EMPTY, "пусто", VARIANTS[v]["note"]),
        board=(column("Ожидает", BOARD_TODO) + column("В работе", BOARD_PROGRESS) + column("Выполнено", BOARD_DONE, done=True)),
        extra="",
    ),
    "tasks": dict(
        sname="3 fast-задачи в столбцах",
        fastline=lambda v: fastline(v, FAST_COLS_TASKS, "3 задачи", VARIANTS[v]["note"]),
        board=(column("Ожидает", BOARD_TODO) + column("В работе", BOARD_PROGRESS) + column("Выполнено", BOARD_DONE, done=True)),
        extra="",
    ),
    "dnd": dict(
        sname="перетаскивание в фастлайн",
        fastline=lambda v: fastline(v, DND_COLS, "1 + перетаскивание", VARIANTS[v]["note"]),
        board=(column("Ожидает", DND_BOARD_TODO) + column("В работе", BOARD_PROGRESS) + column("Выполнено", BOARD_DONE, done=True)),
        extra=DND_NOTE,
    ),
}


def main():
    for v, vdata in VARIANTS.items():
        for s, sdata in STATES.items():
            html = PAGE.format(
                vname=vdata["vname"], sname=sdata["sname"], vdesc=vdata["vdesc"],
                sidebar=SIDEBAR,
                fastline_html=sdata["fastline"](v),
                board_html=sdata["board"],
                extra=sdata["extra"],
            )
            out = HERE / f"variant-{v}-{s}.html"
            out.write_text(html, encoding="utf-8")
            print("written", out.name)


if __name__ == "__main__":
    main()
