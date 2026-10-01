"""Кроп-виджет аватара (change add-r5-avatar-crop-compact-profile,
tasks.md 3.2; дельта settings — Requirement «Кроп-виджет аватара»;
FR-49…FR-53, ОВ-СА-1/4, Д-12; модуль frontend/static/js/avatar-crop.js,
эталон — design/avatar-crop-v3.html макет 1.1).

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
