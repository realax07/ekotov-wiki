/* Кроп-виджет аватара — /settings/profile (tasks.md 3.2 пакета
 * add-r5-avatar-crop-compact-profile; FR-49…FR-53, NFR-11, ОВ-СА-1/4,
 * Д-12/Д-13; дельта settings — Requirement «Кроп-виджет аватара»).
 *
 * Поведение по сценариям дельты:
 * - Д-12: виджет открывается СРАЗУ после выбора файла в карточке
 *   (change на #avatar-file → декодирование → .is-open). Виджет только
 *   при новой загрузке файла (ОГР-21): без выбора файла не открывается.
 * - Фото под КРУГЛОЙ маской; маска = live-предпросмотр (FR-51): <canvas
 *   id="crop-canvas"> перерисовывается на каждое перемещение/зум — ровно
 *   то, что уйдет на сервер.
 * - Drag — Pointer Events на маске (pointerdown/move/up + setPointerCapture,
 *   touch-action: none в CSS — скролл страницы не ломается).
 * - Зум — слайдер #crop-zoom (native range) и колесо мыши над маской
 *   (FR-50); шаг 10%, кнопки ± (по макету design/avatar-crop-v3.html).
 * - Пределы зума (ОВ-СА-4): min=100% — cover (фото покрывает маску),
 *   max=300% — утроенный cover; слайдер min/max = 100/300, кнопки
 *   disabled на границах (по макету).
 * - Клэмп «без дыр» (FR-50): инвариант — изображение всегда полностью
 *   закрывает маску. Смещение ограничено |dx| ≤ (dispW − mask)/2
 *   (аналогично dy), поэтому при 100% на квадратном фото сдвига нет.
 * - Мелкий исходник (ОВ-СА-4): сторона меньше маски → cover-апскейл +
 *   предупреждение #crop-warning о потере четкости; загрузка НЕ
 *   блокируется.
 * - «Применить» (FR-52/FR-54/NFR-11, ОВ-СА-1/3): canvas 256×256 →
 *   toBlob PNG → multipart POST СУЩЕСТВУЮЩЕГО /api/profile/avatar —
 *   контракт НЕ расширяется; ответ {avatar_url} с новым ?v= идет в
 *   превью кружка (ОГР-23: кеш-бастинг). 422-тексты API — как есть
 *   (дисциплина profile-settings.js), 401 → /login (сессия истекла).
 * - «Отмена»/закрытие/уход со страницы (FR-53): сброс состояния БЕЗ
 *   запросов — файл никуда не отправляется до «Применить», прежний
 *   аватар не затронут (pagehide — только локальный close).
 * - EXIF: изображение берется ПОСЛЕ декодирования браузером —
 *   createImageBitmap(file, {imageOrientation: "from-image"}).
 * - Совместимость с Р4: submit-перехват — на document (capture-фаза),
 *   ТОЛЬКО когда виджет открыт (файл уже «вOwned» виджетом, input
 *   очищен): «Загрузить» при открытом виджете = «Применить» (тот же
 *   POST итогового квадрата). Без поддержки canvas/createImageBitmap
 *   модуль не инициализируется — форма работает по-Р4 (fallback,
 *   NFR-14; полный fallback-сценарий — задача 3.3). init в try/catch —
 *   ошибка модуля не ломает страницу (NFR-14).
 *
 * Все пользовательские строки — только textContent (XSS-дисциплина).
 */
"use strict";

const MAX_FILE_BYTES = 2 * 1024 * 1024; // NFR-10/ОВ-22: те же правила, что сервер
const ALLOWED_TYPES = ["image/png", "image/jpeg"];
const ALLOWED_EXTS = [".png", ".jpg", ".jpeg"];
const ZOOM_MIN = 100; // % от cover (ОВ-СА-4: min = покрытие маски)
const ZOOM_MAX = 300; // ×3 cover
const ZOOM_STEP = 10; // кнопки ±/колесо (по макету, ОВ-СА-5)
const OUTPUT_SIZE = 256; // Д-13: итоговый квадрат

function cropSupported() {
  return (
    typeof window.createImageBitmap === "function" &&
    typeof window.FileReader !== "undefined" &&
    typeof HTMLCanvasElement !== "undefined" &&
    typeof HTMLCanvasElement.prototype.toBlob === "function"
  );
}

function declaredTypeAllowed(file) {
  if (ALLOWED_TYPES.indexOf(file.type) !== -1) {
    return true;
  }
  const name = (file.name || "").toLowerCase();
  return ALLOWED_EXTS.some((ext) => name.endsWith(ext));
}

/* Fallback-декодирование (ревью 3.2a): <img> + decode() — EXIF-ориентация
 * применяется браузером УНИВЕРСАЛЬНО (в т.ч. старыми Safari, где
 * imageOrientation у createImageBitmap не поддержан/игнорируется). */
function decodeViaImgElement(file) {
  return new Promise(function (resolve, reject) {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = function () {
      img
        .decode()
        .then(function () {
          const stage = document.createElement("canvas");
          stage.width = img.naturalWidth;
          stage.height = img.naturalHeight;
          stage.getContext("2d").drawImage(img, 0, 0);
          URL.revokeObjectURL(url);
          resolve(createImageBitmap(stage));
        })
        .catch(function (error) {
          URL.revokeObjectURL(url);
          reject(error);
        });
    };
    img.onerror = function () {
      URL.revokeObjectURL(url);
      reject(new Error("image decode failed"));
    };
    img.src = url;
  });
}

async function decodeOriented(file) {
  try {
    // EXIF: ориентация применяется при декодировании (image-orientation).
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // Старый Chromium без опции — пробуем декодировать как есть.
    try {
      return await createImageBitmap(file);
    } catch {
      // Последний рубеж (старые Safari): <img>+decode() — EXIF применён.
      return await decodeViaImgElement(file);
    }
  }
}

function initAvatarCrop() {
  const form = document.getElementById("avatar-form");
  if (!form || !cropSupported()) {
    return; // NFR-14: нет canvas/декодирования — Р4-загрузка как есть
  }

  const fileInput = document.getElementById("avatar-file");
  const widget = document.getElementById("crop-widget");
  const mask = document.getElementById("crop-mask");
  const canvas = document.getElementById("crop-canvas");
  const warning = document.getElementById("crop-warning");
  const zoomSlider = document.getElementById("crop-zoom");
  const zoomValue = document.getElementById("zoom-value");
  const zoomInBtn = document.getElementById("zoom-in");
  const zoomOutBtn = document.getElementById("zoom-out");
  const applyBtn = document.getElementById("crop-apply");
  const cancelBtn = document.getElementById("crop-cancel");
  const errorEl = document.getElementById("avatar-error");
  const successEl = document.getElementById("avatar-success");
  const preview = document.getElementById("avatar-preview");

  /* Состояние виджета; dx/dy — смещение фото в CSS-пикселях маски. */
  const state = {
    bitmap: null,
    zoom: ZOOM_MIN,
    dx: 0,
    dy: 0,
    size: 0, // сторона маски в CSS-пикселях (факт верстки)
    busy: false,
    selectToken: 0, // защита от гонки двойного выбора файла (ревью 3.2b)
  };

  function showError(text) {
    errorEl.textContent = text;
    errorEl.hidden = false;
    successEl.hidden = true;
  }

  function showSuccess(text) {
    successEl.textContent = text;
    successEl.hidden = false;
    errorEl.hidden = true;
  }

  /* --- Геометрия: cover + клэмп «без дыр» (FR-50, ОВ-СА-4) --- */

  function coverScale() {
    // Минимальный масштаб: сторона изображения не меньше диаметра маски.
    return state.size / Math.min(state.bitmap.width, state.bitmap.height);
  }

  function currentScale() {
    return (coverScale() * state.zoom) / 100;
  }

  function maxOffset(dimension) {
    const displayed = dimension * currentScale();
    return Math.max(0, (displayed - state.size) / 2);
  }

  function clampOffsets() {
    const limitX = maxOffset(state.bitmap.width);
    const limitY = maxOffset(state.bitmap.height);
    state.dx = Math.min(limitX, Math.max(-limitX, state.dx));
    state.dy = Math.min(limitY, Math.max(-limitY, state.dy));
  }

  /* --- Отрисовка: маска = live-предпросмотр (FR-51) --- */

  function render() {
    clampOffsets();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const px = Math.round(state.size * dpr);
    if (canvas.width !== px) {
      canvas.width = px;
      canvas.height = px;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#fffdf9"; // --color-bg-surface: под фото «дыр» нет по инварианту
    ctx.fillRect(0, 0, state.size, state.size);

    const s = currentScale();
    const sourceSide = state.size / s; // квадрат маски в пикселях исходника
    const sx =
      state.bitmap.width / 2 - state.dx / s - sourceSide / 2;
    const sy =
      state.bitmap.height / 2 - state.dy / s - sourceSide / 2;
    ctx.drawImage(
      state.bitmap, sx, sy, sourceSide, sourceSide, 0, 0, state.size, state.size
    );

    /* Машиночитаемое состояние (проверки клэмпa/drag, тесты). */
    widget.dataset.cropX = String(state.dx);
    widget.dataset.cropY = String(state.dy);
    widget.dataset.cropZoom = String(state.zoom);
    syncZoomControls();
  }

  function syncZoomControls() {
    zoomSlider.value = String(state.zoom);
    zoomSlider.setAttribute("aria-valuenow", String(state.zoom));
    zoomValue.textContent = state.zoom + "%";
    zoomOutBtn.disabled = state.zoom <= ZOOM_MIN;
    zoomInBtn.disabled = state.zoom >= ZOOM_MAX;
  }

  function setZoom(zoom) {
    if (!state.bitmap) {
      return;
    }
    state.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(zoom)));
    render();
  }

  /* --- Открытие/закрытие (Д-12, FR-53) --- */

  function openCrop(bitmap, token) {
    // Гонка двойного выбора (ревью 3.2b): openCrop применяется только
    // если за время decode() не начался более новый выбор файла; иначе
    // устаревший bitmap закрывается и НЕ перезаписывает актуальный.
    if (token !== state.selectToken) {
      if (bitmap && typeof bitmap.close === "function") {
        bitmap.close();
      }
      return;
    }
    if (state.bitmap && state.bitmap !== bitmap) {
      if (typeof state.bitmap.close === "function") {
        state.bitmap.close();
      }
    }
    state.bitmap = bitmap;
    state.zoom = ZOOM_MIN;
    state.dx = 0;
    state.dy = 0;
    state.size = mask.clientWidth || 224;
    // ОВ-СА-4: сторона исходника меньше маски → апскейл до cover + предупреждение.
    warning.hidden = !(
      Math.min(bitmap.width, bitmap.height) < state.size
    );
    widget.classList.add("is-open");
    render();
    mask.focus();
  }

  function closeCrop() {
    widget.classList.remove("is-open");
    if (state.bitmap) {
      state.bitmap.close();
    }
    state.bitmap = null;
    state.busy = false;
    warning.hidden = true;
    fileInput.value = ""; // повторный выбор того же файла снова даст change
  }

  /* --- Выбор файла → сразу виджет (Д-12, NFR-12) --- */

  fileInput.addEventListener("change", async function () {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      return;
    }
    // NFR-12: тип/размер отклоняются ДО открытия виджета (правила сервера).
    if (!declaredTypeAllowed(file) || file.size > MAX_FILE_BYTES) {
      showError("Файл не png/jpg или больше 2 МБ");
      return; // input НЕ очищаем — Р4-сабмит покажет 422 сервера как раньше
    }
    errorEl.hidden = true;
    // Токен актуальности: каждый новый выбор инкрементирует; decode
    // предыдущего выбора не откроет виджет поверх нового (ревью 3.2b).
    const token = ++state.selectToken;
    try {
      const bitmap = await decodeOriented(file);
      fileInput.value = ""; // файл теперь у виджета; Р4-сабмит не дублирует
      openCrop(bitmap, token);
    } catch {
      if (token === state.selectToken) {
        showError("Не удалось прочитать изображение");
      }
    }
  });

  /* --- Drag: Pointer Events (FR-49) --- */

  let drag = null;
  mask.addEventListener("pointerdown", function (event) {
    if (!state.bitmap) {
      return;
    }
    drag = { x: event.clientX, y: event.clientY };
    mask.setPointerCapture(event.pointerId);
  });
  mask.addEventListener("pointermove", function (event) {
    if (!drag || !state.bitmap) {
      return;
    }
    state.dx += event.clientX - drag.x;
    state.dy += event.clientY - drag.y;
    drag = { x: event.clientX, y: event.clientY };
    render(); // клэмп внутри — фото не уходит за маску
  });
  function endDrag() {
    drag = null;
  }
  mask.addEventListener("pointerup", endDrag);
  mask.addEventListener("pointercancel", endDrag);

  /* --- Тач (задача 3.3, NFR-13): touch-drag + pinch-to-zoom --- */

  /* touch-action: none на маске (CSS) гасит скролл/зум страницы над
   * виджетом; вне виджета скролл страницы не затронут. Drag работает и
   * пальцем — pointerdown/move покрывают touch-указатели (pointerType
   * touch). Pinch: расстояние двух активных touch-точек → зум. */
  let pinch = null; // { startDist, startZoom }
  function touchDistance(touches) {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.hypot(dx, dy);
  }
  mask.addEventListener(
    "touchstart",
    function (event) {
      if (!state.bitmap || event.touches.length !== 2) {
        pinch = null;
        return;
      }
      event.preventDefault(); // pinch над фото — зум, не зум страницы
      drag = null; // второй палец отменяет одиночный drag
      pinch = {
        startDist: touchDistance(event.touches),
        startZoom: state.zoom,
      };
    },
    { passive: false }
  );
  mask.addEventListener(
    "touchmove",
    function (event) {
      if (!pinch || !state.bitmap || event.touches.length !== 2) {
        return;
      }
      event.preventDefault();
      const dist = touchDistance(event.touches);
      if (pinch.startDist > 0) {
        // Расстояние двух точек → масштаб (NFR-13).
        setZoom(pinch.startZoom * (dist / pinch.startDist));
      }
    },
    { passive: false }
  );
  function endPinch() {
    pinch = null;
  }
  mask.addEventListener("touchend", endPinch);
  mask.addEventListener("touchcancel", endPinch);

  /* --- Клавиатура (задача 3.3, NFR-15): маска в фокусе — стрелки
   * двигают фото (шаг 5% стороны маски), +/- зум 10%; слайдер —
   * нативный input range (стрелки работают сами). --- */
  const KEY_MOVE_STEP_RATIO = 0.05; // 5% стороны маски
  mask.addEventListener("keydown", function (event) {
    if (!state.bitmap) {
      return;
    }
    const step = state.size * KEY_MOVE_STEP_RATIO;
    let handled = false;
    if (event.key === "ArrowLeft") {
      state.dx -= step;
      handled = true;
    } else if (event.key === "ArrowRight") {
      state.dx += step;
      handled = true;
    } else if (event.key === "ArrowUp") {
      state.dy -= step;
      handled = true;
    } else if (event.key === "ArrowDown") {
      state.dy += step;
      handled = true;
    } else if (event.key === "+" || event.key === "=") {
      setZoom(state.zoom + ZOOM_STEP);
      handled = true;
    } else if (event.key === "-" || event.key === "_") {
      setZoom(state.zoom - ZOOM_STEP);
      handled = true;
    }
    if (handled) {
      event.preventDefault();
      render(); // клэмп внутри — «дыр» нет и с клавиатуры
    }
  });

  /* --- Зум: слайдер + колесо + кнопки ± (FR-50, ОВ-СА-5) --- */

  zoomSlider.addEventListener("input", function () {
    state.zoom = Number(zoomSlider.value);
    render();
  });
  zoomInBtn.addEventListener("click", function () {
    setZoom(state.zoom + ZOOM_STEP);
  });
  zoomOutBtn.addEventListener("click", function () {
    setZoom(state.zoom - ZOOM_STEP);
  });
  mask.addEventListener(
    "wheel",
    function (event) {
      if (!state.bitmap) {
        return;
      }
      event.preventDefault(); // колесо над фото — зум, не скролл страницы
      setZoom(state.zoom + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    },
    { passive: false }
  );

  /* --- «Применить»: canvas 256×256 → PNG blob → POST (FR-52, ОВ-СА-1/3) --- */

  function drawOutput() {
    const out = document.createElement("canvas");
    out.width = OUTPUT_SIZE;
    out.height = OUTPUT_SIZE;
    const ctx = out.getContext("2d");
    const s = currentScale();
    const sourceSide = state.size / s;
    const sx = state.bitmap.width / 2 - state.dx / s - sourceSide / 2;
    const sy = state.bitmap.height / 2 - state.dy / s - sourceSide / 2;
    // Тот же source-прямоугольник, что в render() — предпросмотр = итог.
    ctx.drawImage(
      state.bitmap, sx, sy, sourceSide, sourceSide, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE
    );
    return out;
  }

  async function applyCrop() {
    if (!state.bitmap || state.busy) {
      return;
    }
    state.busy = true;
    applyBtn.disabled = true;
    try {
      const blob = await new Promise(function (resolve) {
        drawOutput().toBlob(resolve, "image/png");
      });
      if (!blob) {
        showError("Не удалось подготовить изображение");
        return;
      }
      const body = new FormData();
      body.append("file", blob, "avatar.png");
      const response = await fetch("/api/profile/avatar", {
        method: "POST",
        credentials: "same-origin",
        body: body,
      });
      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (response.status === 200) {
        showSuccess("Аватар загружен");
        if (data.avatar_url) {
          preview.src = data.avatar_url; // ?v= от сервера — кеш-бастинг (ОГР-23)
          preview.hidden = false;
        }
        closeCrop();
        return;
      }
      if (response.status === 422) {
        showError(
          data.error === "file too large"
            ? "Файл слишком большой (максимум 2 МБ)"
            : "Недопустимый тип файла (только png/jpg)"
        );
        return;
      }
      showError("Не удалось загрузить аватар");
    } catch {
      showError("Не удалось загрузить аватар");
    } finally {
      state.busy = false;
      applyBtn.disabled = false;
    }
  }

  applyBtn.addEventListener("click", applyCrop);

  /* Открытый виджет перехватывает сабмит «Загрузить» = «Применить»:
   * capture-фаза на document — раньше bubble-обработчика profile-settings.js
   * (тот при очищенном input показал бы «Выберите файл»). */
  document.addEventListener(
    "submit",
    function (event) {
      if (event.target !== form || !state.bitmap) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      applyCrop();
    },
    true
  );

  /* --- «Отмена»/закрытие/уход — сброс без запросов (FR-53) --- */

  cancelBtn.addEventListener("click", closeCrop);
  window.addEventListener("pagehide", function () {
    if (state.bitmap) {
      closeCrop();
    }
  });
}

try {
  initAvatarCrop();
} catch (error) {
  // NFR-14: ошибка виджета не должна ломать страницу профиля —
  // загрузка аватара остается работоспособной по-Р4.
  if (window.console && console.error) {
    console.error("avatar-crop init failed", error);
  }
}
