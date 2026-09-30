/* Авто-высота textarea (Р5 polish, прод-репорт Заказчика; зона: доска).
 *
 * Проблема: «Описание» (task-form) и «Новый комментарий» (comment-body)
 * были слишком высокими по умолчанию (rows=3/2 при фактическом рендере),
 * курсор оказывался «в середине пустоты».
 *
 * Решение (согласовано с Заказчиком: без рамок, поля остаются с нижней
 * линией — pixel-consistent V3 4.2 не затрагивается):
 * - старт ~2 строки (≈52px; задает CSS min-height у .auto-textarea —
 *   атрибут rows из разметки больше не влияет: height управляется JS);
 * - рост по вводу: input → height:auto → scrollHeight (прямой биндинг
 *   на элементы — их ровно два и они статичны в board.html);
 * - потолок ~10 строк (CSS max-height + overflow-y:auto — JS ничего
 *   не режет, скролл включает браузер);
 * - курсор в НАЧАЛЕ при фокусе (setSelectionRange(0,0), если пользователь
 *   сам не поставил курсор: проверка selectionStart/End — click/tab не
 *   ломаем, пустое поле только сдвигаем из дефолтного «в конце»);
 * - сброс высоты при очистке значения: height возвращает к старту
 *   (resetTextareaHeight; вызывается из task-form.js при clearTaskForm/
 *   fillTaskForm и после отправки комментария).
 *
 * Подсказка — placeholder ВНУТРИ поля («Описание задачи…», «Новый
 * комментарий…»), компактный внешний label над полем остается (доступность
 * не деградирует: label связан с полем и прежде). Логика сохранения
 * (collectTaskForm, submitComment) не задействована — только визуал.
 */
"use strict";

var MAX_HEIGHT = 260; /* ~10 строк × ~26px (font+line-height) + паддинги */

export function autoresize(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, MAX_HEIGHT) + "px";
}

export function resetTextareaHeight(textarea) {
  /* height:auto вернет стартовую высоту из CSS (min-height ~2 строки). */
  textarea.style.height = "";
}

export function initAutoTextareas() {
  ["task-description", "comment-body"].forEach(function (id) {
    var textarea = document.getElementById(id);
    if (!textarea) {
      return;
    }
    textarea.classList.add("auto-textarea");

    textarea.addEventListener("input", function () {
      autoresize(textarea);
    });

    /* Курсор в начале пустого поля (прод-репорт: «курсор в середине
     * пустоты»). Только если пользователь курсор сам не ставил. */
    textarea.addEventListener("focus", function () {
      if (
        textarea.value === "" &&
        textarea.selectionStart === 0 &&
        textarea.selectionEnd === 0
      ) {
        textarea.setSelectionRange(0, 0);
      }
    });

    autoresize(textarea);
  });
}
