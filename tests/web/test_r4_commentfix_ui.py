"""Регресс вёрстки блока комментариев в форме задачи (фикс прод-дефекта
Р4; дельты 4.1 + 4.2 Релиза 4).

Прод-репорт: в карточке редактирования задачи съехала вёрстка блока
добавления комментария. Корень: 4.1 перенесла #task-comments СОСЕДНИМ
элементом к form.modal внутрь .modal-overlay — flex-контейнера без
flex-wrap — и секция вставала В РЯД с формой (сжатие до ~225px, сдвиг
по вертикали), а не под ней. Фикс: #task-form и #task-comments обернуты
в .modal.task-form-sheet («лист» модалки), форма — .task-form--bare.

Ассерты — геометрические (boundingBox), не скриншоты: съезд вёрстки
больше не проходит мимо сьюта.

Нумерация продолжается за test_view_modal_r4 (TC-view-1xx):
- TC-cmt-201: комментарии в режиме редактирования — ПОД формой, той же
  ширины, без горизонтального сдвига (прод-дефект);
- TC-cmt-202: кнопка комментария — под textarea, блок не сжат;
- TC-cmt-203: в режиме создания комментариев нет (негативный, 4.1:
  блок скрыт openCreateForm).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.web, pytest.mark.must]

OVERLAY = "#task-form-overlay"
COMMENTS = "#task-comments"
COMMENT_FORM = "#comment-form"
# Допуск гео-ассертов (субпиксели + округления браузера).
EPS = 2.0


def _open_edit_form(page, title: str):
    """Создать задачу и открыть форму редактирования (доска → карточка →
    view → «Редактировать»; путь Д-9, 4.1)."""
    create_task_via_ui(page, title)
    card = page.get_by_role("article").filter(has_text=title)
    card.click()
    expect(page.locator("#task-detail-overlay")).to_be_visible()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator(OVERLAY)).to_be_visible()
    expect(page.locator(COMMENT_FORM)).to_be_visible()
    return card


def test_edit_comments_block_below_form(board_page, web_cleanup_created):
    """TC-cmt-201: блок комментариев в режиме редактирования лежит ПОД
    формой (левый край и ширина совпадают с формой), а не сбоку от нее —
    прод-дефект «съехавшей вёрстки» (секция сжималась до ~225px и
    вставала в ряд с form.modal)."""
    page = board_page
    card = _open_edit_form(page, "QAT-cmt-под-формой")
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    bb_form = page.locator("#task-form").bounding_box()
    bb_comments = page.locator(COMMENTS).bounding_box()
    assert bb_form is not None and bb_comments is not None

    # Блок ниже формы: его верх — не выше низа формы.
    assert bb_comments["y"] >= bb_form["y"] + bb_form["height"] - EPS, (
        f"блок комментариев не под формой: form.y+h={bb_form['y'] + bb_form['height']:.0f}, "
        f"comments.y={bb_comments['y']:.0f}"
    )
    # Той же ширины и на том же левом крае (в ряд с формой по X — дефект).
    assert abs(bb_comments["x"] - bb_form["x"]) <= EPS, (
        f"левые края не совпадают: form.x={bb_form['x']:.0f}, "
        f"comments.x={bb_comments['x']:.0f}"
    )
    assert abs(bb_comments["width"] - bb_form["width"]) <= EPS, (
        f"ширина блока не совпадает с формой: form.w={bb_form['width']:.0f}, "
        f"comments.w={bb_comments['width']:.0f} (дефект: сжатие до ~225px)"
    )


def test_comment_input_and_button_in_row(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-cmt-202: блок добавления комментария в форме редактирования —
    исторический вид прежнего окна деталей: кнопка «Добавить комментарий»
    ПОД textarea на всю ширину формы (не сжата), левые края textarea,
    кнопки и списка комментариев совпадают; ширина блока = ширине формы
    (дефект волны 5: секция сжималась flex-оверлеем до min-content и
    вставала сбоку)."""
    page = board_page
    title = "QAT-cmt-в-ряд"
    card = _open_edit_form(page, title)
    task_id = int(card.get_attribute("data-task-id"))
    web_cleanup_created(task_id)

    # Добавить комментарий (через UI-форму — POST /api/tasks/{id}/comments):
    # список перестает быть пустым и геометрия ряда становится измеримой.
    page.get_by_label("Новый комментарий").fill("комментарий для гео-теста")
    page.get_by_role("button", name="Добавить комментарий").click()
    expect(page.locator("#task-form-comments-list li")).to_have_count(1)

    ta = page.locator("#comment-body").bounding_box()
    btn = page.locator(f"{COMMENT_FORM} button[type=submit]").bounding_box()
    form = page.locator("#task-form").bounding_box()
    lst = page.locator("#task-form-comments-list").bounding_box()
    assert all(b is not None for b in (ta, btn, form, lst))

    # Кнопка ПОД textarea (исторический вид, столбик) и в пределах формы:
    assert btn["y"] >= ta["y"] + ta["height"] - EPS, (
        f"кнопка не под textarea: ta.y+h={ta['y'] + ta['height']:.0f}, "
        f"btn.y={btn['y']:.0f}"
    )
    assert (
        btn["x"] >= form["x"] - EPS
        and btn["x"] + btn["width"] <= form["x"] + form["width"] + EPS
    ), f"кнопка вне формы: btn.x={btn['x']:.0f} w={btn['width']:.0f}"
    # Левые края textarea/кнопки/списка выровнены (блок не уехал вбок —
    # главный симптом дефекта волны 5: секция вставала сбоку от формы):
    left = {round(b["x"]) for b in (ta, btn, lst)}
    assert len(left) == 1, f"левые края разъехались: {left}"
    # Ширина блока = ширине формы:
    assert abs(lst["width"] - form["width"]) <= EPS, (
        f"comments шириной {lst['width']:.0f} против формы {form['width']:.0f}"
    )


def test_create_mode_comments_hidden(board_page):
    """TC-cmt-203 (негативный, 4.1): в режиме СОЗДАНИЯ блока комментариев
    нет (openCreateForm скрывает); форма закрывается как прежде."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator(OVERLAY)).to_be_visible()
    assert not page.locator(COMMENTS).is_visible()
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator(OVERLAY)).to_be_hidden()


def test_comment_button_gap_below_textarea(board_page, web_cleanup_created):
    """Хотфикс Р5 (Заказчик): между textarea#comment-body и кнопкой
    «Добавить комментарий» есть вертикальный зазор (margin-top по
    8px-сетке) — кнопка не прилегает вплотную к полю. Геометрический
    ассерт: низ textarea СТРОГО выше верха кнопки."""
    page = board_page
    title = "QAT-cmt-отступ"
    card = _open_edit_form(page, title)
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    ta = page.locator("#comment-body").bounding_box()
    btn = page.locator(f"{COMMENT_FORM} button[type=submit]").bounding_box()
    assert ta is not None and btn is not None

    gap = btn["y"] - (ta["y"] + ta["height"])
    assert gap > 0, (
        f"кнопка вплотную к textarea: зазор {gap:.1f}px (ожидается > 0, "
        f"margin-top 8px)"
    )
    # Зазор соответствует 8px-сетке (не «случайные» пиксели), с допуском
    # на субпиксели/скругления браузера:
    assert 8 - EPS <= gap <= 8 + EPS, f"зазор {gap:.1f}px вместо ~8px"
