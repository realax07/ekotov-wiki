"""BUG-013: отступы признаков в окне просмотра задачи (r8-polish приемка).

Трассировка: TC-view-110 (BUG-013-регресс к домену view-модалки,
test-model/bugs/BUG-013-task-view-attrs-edge-padding.md; нумерация
продолжает test_view_modal_r4.py TC-view-101…109).

Мокап-арбитр design/polish-ticket-modal.html: сетка признаков .attr-grid и
карточки .attr живут ВНУТРИ .modal-body с его паддингами — горизонтальные
отступы признаков равны отступам остального содержимого окна (--space-4).
Дефект (BUG-013): карточки признаков прижаты к краю окна.

Computed-styles ассерты (мокап):
- .task-view-body  padding = var(--space-2) var(--space-4) = 16px 32px;
- .task-view .attr-grid — БЕЗ собственного паддинга (0px), левый/правый
  край сетки совпадает с контентом .task-view-body (паддинг тела, ±1px);
- .task-view .attr padding = var(--space-1) var(--space-2) = 8px 16px.

BUG-015 (повторная приемка r8-polish-2): старый dl#task-detail-attrs
(скрытый носитель данных контракта TC-UI-009/ОГР-28) НЕ отображается
в окне рядом с attr-grid — паттерн sr-only в board.css:
- .task-view-attrs: position:absolute; width/height 1px; clip rect(0 0 0 0)
  (computed по паттерну; НЕ display:none — текст attrs читается e2e);
- attr-grid при этом ВИДИМ (единственный видимый носитель признаков).
Мутационная проверка (снять sr-only → ассерты красные) — в отчете
фикс-цикла BUG-015.

Среда: автостенд tests/web (conftest), маркер web.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OVERLAY = "#task-detail-overlay"


def _create_task(web_owner_session, web_base_url, web_cleanup_created, title):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": title,
            "description": "Описание задачи BUG-013",
            "priority": "high",
            "category": "Дом",
            "due_date": "2026-12-31",
            "tags": ["bug013"],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    return task_id


def test_view_attrs_padding_matches_mockup(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """BUG-013: отступы признаков окна просмотра — по мокапу.

    .task-view-body несет паддинг мокапа .modal-body (16px 32px);
    .attr-grid не имеет собственного горизонтального паддинга и стоит
    в контенте тела (ее края = края контента тела, ±1px); карточки
    .attr — паддинг мокапа 8px 16px. Признаки НЕ прижаты к краю окна:
    горизонтальный отступ сетки признаков = отступу описания/тегов.
    """
    page = board_page
    _create_task(
        web_owner_session, web_base_url, web_cleanup_created, "QAT-bug013-pad"
    )
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    page.get_by_role("article").filter(has_text="QAT-bug013-pad").click()
    expect(page.locator(OVERLAY)).to_be_visible()
    # Рендер тела асинхронен (GET /api/tasks/{id}) — ждем сетку признаков.
    expect(page.locator(f"{OVERLAY} .attr-grid")).to_be_visible()

    # BUG-015: старый dl#task-detail-attrs — скрытый носитель данных
    # (контракт TC-UI-009/ОГР-28), sr-only-паттерн board.css: 1px-box,
    # clip rect(0 0 0 0); видимые признаки окна — ТОЛЬКО attr-grid.
    bug015 = page.evaluate(
        """() => {
          const modal = document.querySelector(
            "#task-detail-overlay .modal");
          const dl = modal.querySelector("#task-detail-attrs");
          const grid = modal.querySelector(".attr-grid");
          const cs = getComputedStyle(dl);
          const round = (n) => Math.round(n * 10) / 10;
          const r = dl.getBoundingClientRect();
          return {
            position: cs.position,
            width: round(r.width),
            height: round(r.height),
            clip: cs.clip,
            display: cs.display,
            visibility: cs.visibility,
            dlText: dl.textContent.length,
            gridVisible: !!(grid.offsetWidth || grid.offsetHeight),
          };
        }"""
    )
    assert bug015["display"] != "none", bug015  # текст attrs читаем (TC-UI-009)
    assert bug015["position"] == "absolute", bug015
    assert bug015["width"] <= 1 and bug015["height"] <= 1, bug015
    assert bug015["clip"] == "rect(0px, 0px, 0px, 0px)", bug015
    assert bug015["dlText"] > 0, bug015  # носитель не пуст (ОГР-28)
    assert bug015["gridVisible"], bug015  # attr-grid единственный видимый

    styles = page.evaluate(
        """() => {
          const modal = document.querySelector(
            "#task-detail-overlay .modal");
          const body = modal.querySelector(".task-view-body");
          const grid = modal.querySelector(".attr-grid");
          const attr = modal.querySelector(".attr");
          const desc = modal.querySelector(".task-view-desc");
          const round = (n) => Math.round(n * 10) / 10;
          const br = body.getBoundingClientRect();
          const gr = grid.getBoundingClientRect();
          const dr = desc.getBoundingClientRect();
          return {
            bodyPadding: getComputedStyle(body).padding,
            gridPadding: getComputedStyle(grid).padding,
            attrPadding: getComputedStyle(attr).padding,
            gridInsetLeft: round(gr.x - br.x),
            gridInsetRight: round(br.right - gr.right),
            descGridDelta: round(Math.abs(dr.x - gr.x)),
          };
        }"""
    )

    # Мокап .modal-body: padding var(--space-2) var(--space-4).
    assert styles["bodyPadding"] == "16px 32px", styles
    # Сетка признаков — без собственного паддинга (карточки .attr несут
    # свой внутренний отступ мокапа).
    assert styles["gridPadding"] == "0px", styles
    # Мокап .attr: padding var(--space-1) var(--space-2).
    assert styles["attrPadding"] == "8px 16px", styles
    # Признаки НЕ прижаты к краю: сетка внутри паддинга тела (32px),
    # левый/правый край совпадает с остальным содержимым (±1px).
    assert styles["gridInsetLeft"] >= 31, styles
    assert styles["gridInsetRight"] >= 31, styles
    assert styles["descGridDelta"] <= 1, styles
