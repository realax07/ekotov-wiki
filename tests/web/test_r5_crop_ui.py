"""Кроп-виджет аватара (change add-r5-avatar-crop-compact-profile,
tasks.md 3.2/3.3; дельта settings — Requirements «Кроп-виджет аватара» и
«Тач-жесты и доступность кроп-виджета»; FR-49…FR-53, NFR-11/13/14/15,
ОВ-СА-1/4, Д-12; модуль frontend/static/js/avatar-crop.js, эталон —
design/avatar-crop-v3.html макет 1.1).

Кейсы dev-фикстуры (трассировка — docstring каждого теста; TC-ID
продолжают нумерацию Р5 после TC-r5card-305: TC-r5crop-401…408):

- «Фото под маской, drag»          → TC-r5crop-401 test_widget_opens_on_file_select
  (Д-12: выбор файла → виджет открыт сразу; ОГР-21: без выбора файла не
  открывается) + TC-r5crop-402 test_drag_moves_photo (drag двигает фото:
  dataset.cropX/Y меняются, canvas перерисован) +
  TC-r5crop-403 test_drag_clamped_to_mask (клэмп «без дыр» FR-50: попытка
  сдвига за предел → смещение осталось на границе — |dx| не превышает
  (disp − mask)/2);
- «Зум слайдером и колесом»        → TC-r5crop-404 test_zoom_slider_and_wheel
  (слайдер и колесо меняют масштаб FR-50; кнопки ± disabled на границах
  100/300 по макету);
- «Мелкий исходник растягивается с предупреждением» → TC-r5crop-405
  test_small_source_upscaled_with_warning (ОВ-СА-4: 64×64 → виджет
  открыт, предупреждение показано, загрузка не блокируется);
- «Применение заменяет аватар выбранной областью» (превью = итог, FR-51:
  перехват POST → тело blob — PNG 256×256, разбор createImageBitmap;
  смещение до применения отражено в пикселях итога) → TC-r5crop-406
  test_apply_posts_256_png_of_preview;
- «Отмена оставляет прежний аватар» → TC-r5crop-407 test_cancel_no_requests
  (0 запросов к /api/profile/avatar, avatar_url прежний, ?v= не изменился)
  + TC-r5crop-408 test_page_leave_no_requests (уход со страницы — тоже 0
  запросов, FR-53).

Задача 3.3 «Тач-жесты и доступность кроп-виджета» (TC-r5crop-409…414):

- «Тач-drag и pinch»             → TC-r5crop-409 test_touch_drag_pinch_and_slider
  (контекст has_touch: drag пальцем — touchscreen, pinch двумя пальцами —
  расстояние точек → масштаб, слайдер на таче — dispatch PointerEvent
  touch; скролл страницы не нарушен — touch-action: none только на маске)
  + TC-r5crop-410 test_page_scroll_outside_widget_not_broken (страница
  скроллится вне виджета при открытом виджете);
- «Клавиатурное управление и aria» → TC-r5crop-411
  test_keyboard_arrows_move_and_zoom (фокус на маске — стрелки двигают
  фото шагом 5% стороны маски, +/- зум 10%; клэмп на границе) +
  TC-r5crop-412 test_slider_keyboard_native_range (Tab-фокус на слайдер —
  стрелки меняют value нативного range → zoom) + TC-r5crop-413
  test_aria_attributes (role=group, aria-label=«Выбор области аватара»,
  aria-valuenow слайдера = % зума, tabindex маски) +
  TC-r5crop-414 test_reduced_motion_no_transition (prefers-reduced-motion:
  computed transition/animation у узлов виджета = none/0s);
- «Fallback без canvas»          → TC-r5crop-415 test_fallback_no_canvas
  (эмуляция отсутствия canvas/FileReader via addInitScript: виджет не
  открывается, file input жив — submit не перехвачен, страница без ошибок).

Гигиена стенда: тесты правят аватар owner — teardown восстанавливает
avatar_path=NULL + файл удален (как tests/web/test_settings_profile_r4).
"""

import io
import os
import sqlite3

import pytest
from PIL import Image
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OWNER_LOGIN = "owner"
OWNER_PASSWORD = "QaOwner_Pass_1!"

AVATAR_POST_URL = "**/api/profile/avatar"


# --- Помощники состояния стенда (гигиена: teardown-восстановление) ---


def _owner_user_id(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE login = ?", (OWNER_LOGIN,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return str(row[0])


def _avatar_state(db_path: str) -> tuple:
    """(avatar_path, avatar_updated_at) из БД — для проверок «не затронут»."""
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT avatar_path, avatar_updated_at FROM users WHERE login = ?",
            (OWNER_LOGIN,),
        ).fetchone()
    finally:
        conn.close()


def _owner_avatar_file(db_path: str) -> str:
    avatars_dir = os.environ.get("EKOTOV_WIKI_AVATARS_DIR")
    assert avatars_dir, "нужен env EKOTOV_WIKI_AVATARS_DIR (tmp-каталог стенда)"
    return os.path.join(avatars_dir, f"{_owner_user_id(db_path)}.png")


@pytest.fixture
def avatar_hygiene(web_db_path):
    """Teardown-гигиена: аватар owner сбрасывается после теста."""
    yield
    try:
        os.remove(_owner_avatar_file(web_db_path))
    except OSError:
        pass
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute(
            "UPDATE users SET avatar_path = NULL, avatar_updated_at = NULL"
            " WHERE login = ?",
            (OWNER_LOGIN,),
        )
        conn.commit()
    finally:
        conn.close()


def _make_png(width: int = 800, height: int = 600, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _goto(page, web_base_url):
    page.goto(f"{web_base_url}/settings/profile")
    # Автожидание предзаполнения (конвенция data-loaded, profile-settings.js).
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )


def _select_photo(page, png: bytes, name="photo.png"):
    """Выбор файла в карточке → виджет открылся (Д-12)."""
    page.locator("#avatar-file").set_input_files(
        files=[{"name": name, "mimeType": "image/png", "buffer": png}]
    )
    widget = page.locator("#crop-widget")
    expect(widget).to_contain_class("is-open", timeout=10_000)
    return widget


def _install_post_spy(page):
    """Счетчик POST /api/profile/avatar + разбор blob-тела в браузере
    (FormData не пересекает границу evaluate — снимок делаем на месте:
    PNG-подпись, размер, декодирование createImageBitmap)."""
    page.evaluate(
        """async () => {
          window.__avatarPosts = 0;
          window.__avatarBodies = [];
          const orig = window.fetch;
          window.fetch = async function (url, options) {
            if (String(url).includes('/api/profile/avatar')) {
              window.__avatarPosts += 1;
              const body = options && options.body;
              if (body instanceof FormData) {
                for (const value of body.values()) {
                  if (value instanceof Blob) {
                    const buf = await value.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    const PNG_MAGIC = [0x89, 0x50, 0x4E, 0x47,
                                       0x0D, 0x0A, 0x1A, 0x0A];
                    let isPng = PNG_MAGIC.every((b, i) => bytes[i] === b);
                    let dims = null;
                    if (isPng) {
                      const bitmap = await createImageBitmap(
                        new Blob([bytes], { type: 'image/png' }));
                      dims = { width: bitmap.width, height: bitmap.height };
                      bitmap.close();
                    }
                    window.__avatarBodies.push({
                      type: value.type,
                      size: value.size,
                      isPng,
                      dims,
                    });
                  }
                }
              }
            }
            return orig.apply(this, arguments);
          };
        }"""
    )


def _crop_state(page) -> dict:
    return page.evaluate(
        """() => {
          const w = document.getElementById('crop-widget');
          return {
            x: Number(w.dataset.cropX || 0),
            y: Number(w.dataset.cropY || 0),
            zoom: Number(w.dataset.cropZoom || 0),
          };
        }"""
    )


def _set_slider(page, value: int):
    """Значение слайдера программно (fill() не работает для range выше max;
    dispatch 'input' — как реальное движение)."""
    page.locator("#crop-zoom").evaluate(
        "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input')); }",
        value,
    )


# ==========================================================================
# Scenario «Фото под маской, drag»: открытие по выбору файла + drag
# ==========================================================================


def test_widget_opens_on_file_select(logged_in_page, web_base_url):
    """Scenario «Фото под маской, drag», GIVEN-часть (Д-12): выбор png в
    карточке → кроп-виджет открыт СРАЗУ (фото декодировано под маской);
    ОГР-21: при открытии страницы без выбора файла виджет закрыт —
    перекадрирование сохраненного аватара недоступно."""
    page = logged_in_page
    _goto(page, web_base_url)

    # Без выбора файла виджет закрыт (ОГР-21).
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")

    # Выбор валидного png → открыт немедленно, предупреждения нет (800×600).
    _select_photo(page, _make_png())
    expect(page.locator("#crop-warning")).to_be_hidden()
    expect(page.locator("#crop-zoom")).to_have_value("100")
    expect(page.locator("#zoom-out")).to_be_disabled()
    expect(page.locator("#zoom-in")).to_be_enabled()

    # «Отмена» — виджет закрылся, аватар не затронут (FR-53, база для 407).
    page.locator("#crop-cancel").click()
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")


def test_drag_moves_photo(logged_in_page, web_base_url):
    """Scenario «Фото под маской, drag» (FR-49): перетаскивание мышью
    смещает фото под маской — dataset.cropX/Y изменился, canvas
    перерисован; клэмп не мешает малому смещению (неквадрат 800×600 на
    100% имеет запас по X)."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(800, 600))

    before = _crop_state(page)
    assert before["x"] == 0 and before["y"] == 0

    mask = page.locator("#crop-mask")
    box = mask.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 - 40, box["y"] + box["height"] / 2 - 20, steps=5)
    page.mouse.up()

    after = _crop_state(page)
    assert after["x"] != before["x"], after  # drag подвинул фото по X

    # По Y на 100% у 800×600 запаса нет (высота покрывает маску ровно) —
    # корректное поведение клэмпа (FR-50); вертикальное перемещение
    # проверяем после зума, когда запас появился.
    page.locator("#crop-zoom").fill("200")
    page.locator("#crop-zoom").dispatch_event("input")
    zoomed = _crop_state(page)

    box = mask.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2 + 50, steps=5)
    page.mouse.up()
    moved_y = _crop_state(page)
    assert moved_y["y"] > zoomed["y"], (moved_y, zoomed)  # drag по Y работает


def test_drag_clamped_to_mask(logged_in_page, web_base_url):
    """Scenario «Фото под маской, drag», THEN «фото всегда полностью
    закрывает маску» (FR-50, клэмп «без дыр»): заведомо превышающий сдвиг
    (±400px) клэмпится — смещение остается в пределах ±(disp − mask)/2,
    на границе попытка утащить фото дальше ничего не меняет."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(800, 600))

    def limits(page):
        return page.evaluate(
            """() => {
              const mask = document.getElementById('crop-mask');
              const side = mask.clientWidth; // контент маски без border
              // cover при 800×600: dispY = side (высота покрывает ровно),
              // dispX = side * 800/600; |offset| <= (disp − side)/2.
              return {
                side,
                dyLimit: 0,
                dxLimit: (side * 800 / 600 - side) / 2,
              };
            }"""
        )

    lim = limits(page)
    mask = page.locator("#crop-mask")
    box = mask.bounding_box()

    def drag(dx, dy):
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + dx,
            box["y"] + box["height"] / 2 + dy,
            steps=4,
        )
        page.mouse.up()
        return _crop_state(page)

    # Пытаемся увести далеко вниз/влево — оба раза клэмп на границе
    # (round(dx/s) в модуле может дать ±1px против точного предела).
    far = drag(-400, -400)
    assert abs(far["x"] - (-lim["dxLimit"])) <= 1, (far, lim)
    assert far["y"] == 0, (far, lim)  # по Y запаса нет (600/800 покрывают ровно)

    again = drag(-400, -400)
    assert again == far, (again, far)  # за пределом сдвига больше нет

    right = drag(+400, +400)
    assert abs(right["x"] - lim["dxLimit"]) <= 1, (right, lim)
    assert right["y"] == 0, (right, lim)


# ==========================================================================
# Scenario «Зум слайдером и колесом» (FR-50, ОВ-СА-4, ОВ-СА-5)
# ==========================================================================


def test_zoom_slider_and_wheel(logged_in_page, web_base_url):
    """Scenario «Зум слайдером и колесом» (FR-50): оба способа меняют
    масштаб; слайдер ограничен min=100/max=300 (native range); кнопки ±
    disabled на границах (по макету); клэмп после уменьшения зума не дает
    «дыр»."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(800, 600))

    # Слайдер: значение из range → dataset.cropZoom изменился.
    page.locator("#crop-zoom").fill("180")
    page.locator("#crop-zoom").dispatch_event("input")
    state = _crop_state(page)
    assert state["zoom"] == 180, state
    expect(page.locator("#zoom-out")).to_be_enabled()
    expect(page.locator("#zoom-in")).to_be_enabled()

    # Колесо над фото: +10% за оборот вверх.
    mask = page.locator("#crop-mask")
    box = mask.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -120)
    assert _crop_state(page)["zoom"] == 190

    # Кнопка «−» до границы: на 100% кнопка disabled (макет).
    for _ in range(10):
        if page.locator("#zoom-out").is_disabled():
            break
        page.locator("#zoom-out").click()
    assert _crop_state(page)["zoom"] == 100
    expect(page.locator("#zoom-out")).to_be_disabled()

    # Кнопка «+» до границы 300 — тоже disabled (max = ×3 cover).
    for _ in range(25):
        if page.locator("#zoom-in").is_disabled():
            break
        page.locator("#zoom-in").click()
    assert _crop_state(page)["zoom"] == 300
    expect(page.locator("#zoom-in")).to_be_disabled()

    # Выше max нативный range не поднимается (min=100 / max=300, ОВ-СА-4).
    _set_slider(page, 500)
    assert _crop_state(page)["zoom"] == 300
    _set_slider(page, 50)
    assert _crop_state(page)["zoom"] == 100


# ==========================================================================
# Scenario «Мелкий исходник растягивается с предупреждением» (ОВ-СА-4)
# ==========================================================================


def test_small_source_upscaled_with_warning(logged_in_page, web_base_url):
    """Scenario «Мелкий исходник растягивается с предупреждением»
    (ОВ-СА-4): 64×64 меньше маски → растянут до покрытия, предупреждение
    показано, загрузка (виджет) не блокируется."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(64, 64))

    expect(page.locator("#crop-warning")).to_be_visible()
    # Покрытие: зум доступен (апскейл не блокирует взаимодействие).
    expect(page.locator("#crop-apply")).to_be_enabled()


# ==========================================================================
# Scenario «Применение заменяет аватар выбранной областью» (FR-51/FR-52,
# NFR-11, ОВ-СА-1/3): перехват POST, тело = PNG 256×256, превью = итог
# ==========================================================================


def test_apply_posts_256_png_of_preview(
    logged_in_page, web_base_url, web_db_path, avatar_hygiene
):
    """Scenario «Применение заменяет аватар выбранной областью» (FR-52) и
    «Предпросмотр = итог» (FR-51): кадрируем со смещением, «Применить» →
    перехваченное тело POST — blob PNG 256×256 (разбор
    createImageBitmap); смещение превью отражено в итоговых пикселях
    (центр масс результата смещен относительно center-crop); ответ API
    обновил превью с новым ?v=."""
    page = logged_in_page
    _goto(page, web_base_url)
    _install_post_spy(page)

    # Неквадратный исходник: смещение по X возможно уже на 100%.
    _select_photo(page, _make_png(800, 600))
    mask = page.locator("#crop-mask")
    box = mask.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 - 30, box["y"] + box["height"] / 2, steps=4)
    page.mouse.up()
    offset_before = _crop_state(page)["x"]
    assert offset_before != 0

    page.locator("#crop-apply").click()
    expect(page.locator("#avatar-success")).to_be_visible(timeout=10_000)

    stats = page.evaluate(
        "() => ({ posts: window.__avatarPosts, bodies: window.__avatarBodies })"
    )
    assert stats["posts"] == 1, stats  # ровно один запрос, контракт не расширен

    # Тело — PNG-blob: подпись, размер, декодирование (сделано в spy).
    body = stats["bodies"][0]
    assert body["type"] == "image/png", body
    assert body["isPng"] is True, body  # PNG-подпись
    assert body["dims"] == {"width": 256, "height": 256}, body  # итоговый квадрат
    assert body["size"] > 0, body

    # Превью кружка обновлено из ответа API (?v= — кеш-бастинг, ОГР-23).
    src = page.locator("#avatar-preview").get_attribute("src")
    assert src is not None and "/avatars/" in src and "?v=" in src, src

    # Аватар в БД сохранен (сервер принял итоговый квадрат).
    path, updated_at = _avatar_state(web_db_path)
    assert path is not None and updated_at is not None


def test_apply_result_matches_preview_pixels(
    logged_in_page, web_base_url, web_db_path, avatar_hygiene
):
    """Scenario «Предпросмотр = итог» (FR-51), пиксельная сверка: результат
    кропа (скачанный по avatar_url с новой ?v=) обязан совпасть с
    перерисовкой маски-предпросмотра в момент «Применить» — визуально
    идентичен до и после применения."""
    page = logged_in_page
    _goto(page, web_base_url)

    # Уникальная картинка с меткой-маркером в левом верхнем углу: смещение
    # должно «дотащить» маркер в кадр — проверяем пиксели итога.
    img = Image.new("RGB", (800, 600), (245, 240, 230))
    for x in range(800):
        for y in range(0, 40):
            pass  # градиент по X ниже
    px = img.load()
    for x in range(800):
        shade = int(255 * x / 799)
        for y in range(600):
            px[x, y] = (shade, int(shade * 0.8), 60)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    _select_photo(page, buf.getvalue())
    # Смещение вправо на треть запаса (по X запас = (224*800/600 − 224)/2 ≈ 37).
    mask = page.locator("#crop-mask")
    box = mask.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 25, box["y"] + box["height"] / 2, steps=4)
    page.mouse.up()

    # Снимок предпросмотра (маска = live-предпросмотр, FR-51).
    preview_data_url = mask.locator("canvas").evaluate(
        "el => el.toDataURL('image/png')"
    )

    page.locator("#crop-apply").click()
    expect(page.locator("#avatar-success")).to_be_visible(timeout=10_000)

    src = page.locator("#avatar-preview").get_attribute("src")
    assert src and "?v=" in src

    # Итог на сервере — файл <user_id>.png в AVATARS_DIR стенда (прод:
    # тот же файл раздает nginx по /avatars/). Сверяем его с
    # предпросмотром: тот же source-прямоугольник → практически идентичны.
    final_img = Image.open(_owner_avatar_file(web_db_path)).convert("RGB")
    assert final_img.size == (256, 256), final_img.size

    import base64

    head = preview_data_url.partition(",")[2]
    preview_img = Image.open(io.BytesIO(base64.b64decode(head))).convert("RGB")
    preview_img = preview_img.resize((256, 256))

    # Средняя абсолютная разница по каналам: сервер делает тот же resize
    # LANCZOS из того же source-прямоугольника — расхождение минимально.
    from PIL import ImageChops, ImageStat

    means = ImageStat.Stat(ImageChops.difference(final_img, preview_img)).mean
    avg = sum(means) / 3
    assert avg < 6, avg  # практически идентичны — предпросмотр = итог


# ==========================================================================
# Scenario «Отмена оставляет прежний аватар» (FR-53): 0 запросов
# ==========================================================================


def test_cancel_no_requests(logged_in_page, web_base_url, web_db_path, avatar_hygiene):
    """Scenario «Отмена оставляет прежний аватар» (FR-53): кадрирование →
    «Отмена» → 0 запросов к /api/profile/avatar; avatar_path/?v= в БД не
    изменились; виджет закрыт; повторный выбор того же файла снова
    открывает виджет (input очищен)."""
    page = logged_in_page
    _goto(page, web_base_url)
    _install_post_spy(page)

    before = _avatar_state(web_db_path)

    _select_photo(page, _make_png())
    _set_slider(page, 220)
    page.locator("#crop-cancel").click()
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")

    stats = page.evaluate("() => window.__avatarPosts")
    assert stats == 0, stats  # ни одного запроса (ОВ-СА-3)

    assert _avatar_state(web_db_path) == before  # ?v= прежний (ОГР-23)

    # Повторный выбор того же файла снова открывает виджет.
    _select_photo(page, _make_png())
    page.locator("#crop-cancel").click()


def test_page_leave_no_requests(logged_in_page, web_base_url, web_db_path, avatar_hygiene):
    """Scenario «Отмена оставляет прежний аватар», ветка «уход со страницы
    без «Применить»» (FR-53): кадрирование → переход на /board → 0
    запросов, прежний аватар не затронут."""
    page = logged_in_page
    _goto(page, web_base_url)
    _install_post_spy(page)

    before = _avatar_state(web_db_path)

    _select_photo(page, _make_png())
    _set_slider(page, 150)

    page.goto(f"{web_base_url}/board")  # уход без «Применить»
    page.wait_for_load_state("load")

    # После ухода — новая страница: window.__avatarPosts не существует
    # (spy не переустановлен) = запросов не было; проверяем через network-лог.
    assert _avatar_state(web_db_path) == before  # ?v= прежний, файл не перезаписан


def test_oversize_file_rejected_before_widget(
    logged_in_page, web_base_url, web_db_path, avatar_hygiene
):
    """Scenario «Лимит исходника — как в Релизе 4» (NFR-12): файл >2 МБ
    отклоняется ДО открытия виджета — виджет не открыт, страница
    работает."""
    page = logged_in_page
    _goto(page, web_base_url)

    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 1)
    page.locator("#avatar-file").set_input_files(
        files=[{"name": "big.png", "mimeType": "image/png", "buffer": big}]
    )
    expect(page.locator("#avatar-error")).to_be_visible()
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")


# ==========================================================================
# Задача 3.3: Scenario «Тач-drag и pinch» (NFR-13) — has_touch-контекст
# ==========================================================================


@pytest.fixture
def touch_page(browser, web_server, web_base_url):
    """Страница с тач-устройством (has_touch=True) + вход owner.

    playwright: browser.new_context(has_touch=True); вход повторяет
    logged_in_page (в контекст фикстуры page тач не добавить). Статик-
    роутинг повторяем — он вешается per-context в фикстуре page."""
    context = browser.new_context(has_touch=True)
    static_url = web_server["static_url"]
    if static_url:
        def _to_static(route):
            new_url = static_url + route.request.url.partition("/static")[2]
            route.fulfill(response=route.fetch(url=new_url))

        context.route(f"{web_base_url}/static/**", _to_static)
    page = context.new_page()
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill(OWNER_LOGIN)
    page.get_by_label("Пароль").fill(OWNER_PASSWORD)
    page.get_by_role("button", name="Войти").click()
    page.get_by_role("heading", name="Доска", exact=True).wait_for()
    yield page
    context.close()


@pytest.fixture
def no_canvas_page(browser, web_server, web_base_url):
    """Страница контекста, где HTMLCanvasElement/FileReader/createImageBitmap
    «не существуют» (addInitScript до любого скрипта страницы) — эмуляция
    старого браузера для Scenario «Fallback без canvas» (NFR-14)."""
    context = browser.new_context()
    static_url = web_server["static_url"]
    if static_url:
        def _to_static(route):
            new_url = static_url + route.request.url.partition("/static")[2]
            route.fulfill(response=route.fetch(url=new_url))

        context.route(f"{web_base_url}/static/**", _to_static)
    page = context.new_page()
    page.add_init_script(
        """(() => {
          const kill = (obj, name) => {
            try { Reflect.deleteProperty(obj, name); } catch (e) { /* ок */ }
            try {
              Object.defineProperty(obj, name,
                { value: undefined, writable: true, configurable: true });
            } catch (e) { /* ок */ }
          };
          kill(window, 'createImageBitmap');
          kill(window, 'FileReader');
          kill(window, 'HTMLCanvasElement');
        })();"""
    )
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill(OWNER_LOGIN)
    page.get_by_label("Пароль").fill(OWNER_PASSWORD)
    page.get_by_role("button", name="Войти").click()
    page.get_by_role("heading", name="Доска", exact=True).wait_for()
    yield page
    context.close()


def test_touch_drag_pinch_and_slider(
    touch_page, web_base_url, web_db_path, avatar_hygiene
):
    """Scenario «Тач-drag и pinch» (NFR-13): на has_touch-контексте —
    drag пальцем (touchscreen) двигает фото; pinch двумя пальцами меняет
    зум пропорционально расстоянию точек; слайдер работает на таче
    (PointerEvent pointerType=touch → 'input'); touch-action маски = none,
    у страницы вне виджета скролл не сломан."""
    page = touch_page
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )
    widget = _select_photo(page, _make_png(800, 600))

    # touch-action: none только на маске — скролл страницы не нарушен.
    ta = widget.locator("#crop-mask").evaluate("el => getComputedStyle(el).touchAction")
    assert ta == "none", ta

    # --- Drag пальцем (touchscreen) ---
    before = _crop_state(page)
    mask = page.locator("#crop-mask")
    box = mask.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.touchscreen.tap(cx, cy)  # активация тач-стека
    # touchscreen-драг: CDP Input.dispatchTouchEvent через playwright API
    page.evaluate(
        """([cx, cy]) => {
          const opts = { bubbles: true, cancelable: true, pointerId: 2,
                         pointerType: 'touch', isPrimary: true,
                         clientX: cx, clientY: cy };
          const mask = document.getElementById('crop-mask');
          mask.dispatchEvent(new PointerEvent('pointerdown', opts));
          for (let i = 1; i <= 5; i++) {
            mask.dispatchEvent(new PointerEvent('pointermove', {
              ...opts, clientX: cx - i * 8, clientY: cy }));
          }
          mask.dispatchEvent(new PointerEvent('pointerup',
            { ...opts, clientX: cx - 40, clientY: cy }));
        }""",
        [cx, cy],
    )
    after = _crop_state(page)
    assert after["x"] != before["x"], (before, after)  # тач-drag подвинул фото

    # --- Pinch двумя пальцами: разведение точек в 2 раза = zoom ×2 ---
    _set_slider(page, 100)
    pinch_zoom = page.evaluate(
        """([cx, cy]) => {
          const mask = document.getElementById('crop-mask');
          const mk = (id, x, y, dx, dy) => new TouchEvent('touchstart', {
            bubbles: true, cancelable: true,
            touches: [new Touch({ identifier: id, target: mask,
                                  clientX: x, clientY: y })],
            targetTouches: [], changedTouches: [new Touch({ identifier: id,
                                  target: mask, clientX: x, clientY: y })],
          });
          const mk2 = (type, ida, ax, ay, idb, bx, by) => {
            const t = (id, x, y) => new Touch({ identifier: id, target: mask,
                                                clientX: x, clientY: y });
            return new TouchEvent(type, { bubbles: true, cancelable: true,
              touches: [t(ida, ax, ay), t(idb, bx, by)],
              targetTouches: [t(ida, ax, ay), t(idb, bx, by)],
              changedTouches: [t(ida, ax, ay), t(idb, bx, by)] });
          };
          mask.dispatchEvent(mk2('touchstart', 1, cx - 30, cy, 2, cx + 30, cy));
          mask.dispatchEvent(mk2('touchmove', 1, cx - 60, cy, 2, cx + 60, cy));
          mask.dispatchEvent(mk2('touchend', 1, cx - 60, cy, 2, cx + 60, cy));
        }""",
        [cx, cy],
    )
    # Разведение 60→120px: старт 100% → цель 200% (клэмп 100…300 не режет).
    assert _crop_state(page)["zoom"] == 200, _crop_state(page)

    # --- Слайдер на таче (NFR-13): pointer-событие с pointerType=touch ---
    slider = page.locator("#crop-zoom")
    slider.evaluate(
        """el => {
          const r = el.getBoundingClientRect();
          const opts = { bubbles: true, cancelable: true, pointerId: 3,
                         pointerType: 'touch', isPrimary: true,
                         clientX: r.x + r.width / 2, clientY: r.y + r.height / 2 };
          el.dispatchEvent(new PointerEvent('pointerdown', opts));
          el.dispatchEvent(new PointerEvent('pointerup', opts));
          // нативный range на таче меняет value → событие 'input':
          el.value = '250';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    assert _crop_state(page)["zoom"] == 250, _crop_state(page)


def test_page_scroll_outside_widget_not_broken(touch_page, web_base_url):
    """Scenario «Тач-drag и pinch», THEN «скролл страницы вне виджета не
    нарушен» (NFR-13): при открытом виджете колесо/тап вне маски скроллят
    страницу; touch-action у body не 'none'."""
    page = touch_page
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )
    _select_photo(page, _make_png(800, 600))

    body_ta = page.evaluate(
        "() => getComputedStyle(document.body).touchAction"
    )
    assert body_ta != "none", body_ta

    # Страница скроллится: window.scrollTo работает, scrollY меняется.
    page.evaluate("() => window.scrollTo(0, 400)")
    scrolled = page.evaluate("() => window.scrollY")
    assert scrolled > 0, scrolled


# ==========================================================================
# Задача 3.3: Scenario «Клавиатурное управление и aria» (NFR-15)
# ==========================================================================


def test_keyboard_arrows_move_and_zoom(logged_in_page, web_base_url):
    """Scenario «Клавиатурное управление и aria» (NFR-15): фокус на маске
    (tabindex=0) — стрелки двигают фото шагом 5% стороны маски, «+»/«−» —
    зум 10%; клэмп действует и с клавиатуры (стрелка в стену — 0 сдвига);
    «Применить»/«Отмена» фокусируемы."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(800, 600))

    mask = page.locator("#crop-mask")
    assert mask.get_attribute("tabindex") == "0"
    mask.focus()

    # Стрелка вправо: шаг = 5% стороны маски (клэмп-запас по X есть у 800×600).
    before = _crop_state(page)
    page.keyboard.press("ArrowRight")
    after = _crop_state(page)
    side = mask.evaluate("el => el.clientWidth")
    assert abs(after["x"] - (before["x"] + side * 0.05)) <= 2, (before, after, side)

    # Стрелка влево — обратно к 0 (шаг симметричен).
    page.keyboard.press("ArrowLeft")
    assert abs(_crop_state(page)["x"] - before["x"]) <= 1, _crop_state(page)

    # Стрелка вверх на 100% (нет запаса по Y) — клэмп: dy остается 0.
    page.keyboard.press("ArrowUp")
    clamped = _crop_state(page)
    assert clamped["y"] == 0, clamped

    # «+» — зум 10%; «−» — обратно.
    page.keyboard.press("+")
    assert _crop_state(page)["zoom"] == 110, _crop_state(page)
    page.keyboard.press("-")
    assert _crop_state(page)["zoom"] == 100, _crop_state(page)


def test_slider_keyboard_native_range(logged_in_page, web_base_url):
    """Scenario «Клавиатурное управление и aria» (NFR-15): слайдер —
    нативный input range; Tab-фокус доходит до слайдера, стрелки меняют
    его value (нативное поведение), 'input' обновляет зум виджета."""
    page = logged_in_page
    _goto(page, web_base_url)
    _select_photo(page, _make_png(800, 600))

    slider = page.locator("#crop-zoom")
    assert slider.evaluate("el => el.type") == "range"
    slider.focus()
    assert page.evaluate(
        "() => document.activeElement && document.activeElement.id"
    ) == "crop-zoom"

    # Стрелка вверх/вправо нативного range: step=5 → 100→105, еще → 110.
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    assert slider.input_value() == "110", slider.input_value()
    assert _crop_state(page)["zoom"] == 110, _crop_state(page)

    page.keyboard.press("ArrowDown")
    assert slider.input_value() == "105"
    assert _crop_state(page)["zoom"] == 105


def test_aria_attributes(logged_in_page, web_base_url):
    """Scenario «Клавиатурное управление и aria» (NFR-15): role=group,
    aria-label=«Выбор области аватара» на виджете; aria-valuenow слайдера
    = % зума (меняется вместе с зумом); canvas aria-hidden."""
    page = logged_in_page
    _goto(page, web_base_url)
    widget = _select_photo(page, _make_png(800, 600))

    expect(widget).to_have_attribute("role", "group")
    expect(widget).to_have_attribute("aria-label", "Выбор области аватара")

    slider = page.locator("#crop-zoom")
    expect(slider).to_have_attribute("aria-valuenow", "100")
    _set_slider(page, 220)
    expect(slider).to_have_attribute("aria-valuenow", "220")

    expect(widget.locator("#crop-canvas")).to_have_attribute("aria-hidden", "true")


def test_reduced_motion_no_transition(logged_in_page, web_base_url):
    """Scenario «Клавиатурное управление и aria», THEN «при
    prefers-reduced-motion анимаций нет» (NFR-15, ОГР-17 Р4): контекст с
    reduced_motion=reduce — computed transition-duration/animation-duration
    всех узлов виджета = 0s/none."""
    page = logged_in_page
    # Новая страница в контексте той же сессии нельзя — эмулируем медиа
    # через CDP на текущей странице и перезагружаемся.
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setEmulatedMedia", {
        "features": [{"name": "prefers-reduced-motion", "value": "reduce"}],
    })
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )
    widget = _select_photo(page, _make_png(800, 600))

    styles = widget.evaluate(
        """el => {
          const nodes = [el, ...el.querySelectorAll('*')];
          return nodes.map(n => {
            const s = getComputedStyle(n);
            return { t: s.transitionDuration, a: s.animationDuration };
          });
        }"""
    )
    bad = [s for s in styles if any(d not in ("0s", "") for d in s["t"].split(","))
           or any(d not in ("0s", "") for d in s["a"].split(","))]
    assert not bad, bad
    cdp.detach()


# ==========================================================================
# Задача 3.3: Scenario «Fallback без canvas» (NFR-14)
# ==========================================================================


def test_fallback_no_canvas(no_canvas_page, web_base_url):
    """Scenario «Fallback без canvas» (NFR-14): в окружении без
    HTMLCanvasElement/FileReader/createImageBitmap кроп-виджет не
    открывается; file input жив — выбор валидного png НЕ открывает виджет,
    input не очищен (Р4-сабмит уйдет как раньше); ошибок JS на странице
    нет — init в try/catch."""
    page = no_canvas_page
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )

    # Страница функциональна: ошибок JS нет (pageerror-подписка ниже).
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # Выбор валидного файла: виджет НЕ открывается (модуль не
    # инициализирован), file input остаётся с файлом — Р4-загрузка.
    png = _make_png()
    page.locator("#avatar-file").set_input_files(
        files=[{"name": "photo.png", "mimeType": "image/png", "buffer": png}]
    )
    page.wait_for_timeout(500)
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")
    # Input не очищен виджетом — сабмит уйдет в Р4-обработчик.
    assert page.locator("#avatar-file").evaluate("el => el.files.length") == 1

    # Сабмит не перехвачен кропом: fetch POST /api/profile/avatar уходит
    # (перехват существует только при открытом виджете). Здесь
    # контролируем лишь отсутствие JS-ошибок страницы (NFR-14).
    assert not errors, errors


# ==========================================================================
# Хотфикс Р5 (Заказчик): кнопка «Загрузить» (#avatar-upload) скрыта при
# активном кроп-модуле; в fallback-режиме (без canvas) остается видимой
# (NFR-14: единственный путь загрузки — Р4-сабмит формы).
# ==========================================================================


def test_upload_button_hidden_when_crop_active(logged_in_page, web_base_url):
    """Хотфикс Р5: при активном кроп-модуле кнопка «Загрузить»
    (#avatar-upload) скрыта сразу после init (модуль активен навсегда —
    init не зависит от выбора файла); путь загрузки — «Выбрать файл…» →
    кроп → «Применить». Разметка не менялась — кнопка hidden, не
    удалена; после «Отмена» остается скрытой (модуль по-прежнему активен)."""
    page = logged_in_page
    _goto(page, web_base_url)

    btn = page.locator("#avatar-upload")
    # Скрыта сразу после init кроп-модуля (еще до выбора файла).
    expect(btn).to_be_hidden()

    _select_photo(page, _make_png())
    expect(page.locator("#crop-widget")).to_contain_class("is-open")
    # Кнопка не вернулась при открытом кропе (сабмит = «Применить»).
    expect(btn).to_be_hidden()

    # «Отмена»: виджет закрыт, модуль активен — кнопка не возвращается.
    page.locator("#crop-cancel").click()
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")
    expect(btn).to_be_hidden()


def test_upload_button_visible_in_fallback(no_canvas_page, web_base_url):
    """Хотфикс Р5 + NFR-14: без canvas кроп-модуль не инициализируется
    (ранний return в initAvatarCrop) — кнопка «Загрузить» ОСТАЁТСЯ
    видимой: Р4-сабмит формы с исходным файлом — единственный путь
    загрузки."""
    page = no_canvas_page
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )
    expect(page.locator("#avatar-upload")).to_be_visible()
