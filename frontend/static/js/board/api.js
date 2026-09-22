/* Клиент REST API (P6: извлечено из board.js; ОГР-2, design.md §7):
 * данные только через API, сессионная кука — credentials: "same-origin".
 *
 * Обработка ошибок API (sdd §3): 401 → redirect /login; 422 →
 * error.details; 409 «fast line occupied» → «fast line занята»
 * (5.2); прочие (сеть/сервер) → общее сообщение.
 */
"use strict";

export function parseBody(response) {
  /* json() может отклониться асинхронно (не-JSON тело: HTML 502 от
   * nginx и т.п.) — try/catch это не ловит, поэтому .catch. */
  return response.json().catch(function () {
    return null;
  });
}

/* Единая обработка ответа API (sdd §3): 401 → /login; 422 →
 * error.details; остальное — общее сообщение. */
export function handleApiError(response, body, onError) {
  if (response.status === 401) {
    window.location.href = "/login";
    return;
  }
  /* Не-JSON тело при полученном HTTP-статусе (HTML-страница 502 и
   * т.п.) — не вводим в заблуждение «сетевой ошибкой». */
  if (!body) {
    onError("Ошибка запроса (HTTP " + response.status + ").", response, null);
    return;
  }
  if (response.status === 422) {
    var parts = [];
    if (body.error) {
      parts.push(body.error);
    }
    var details = body.details;
    /* Сервер (tasks.py install_error_handlers) отдает details
     * МАССИВОМ pydantic-ошибок ({loc, msg, type, ...}); формат
     * «объект {поле: [тексты]}» — fallback. */
    if (Array.isArray(details)) {
      details.forEach(function (item) {
        var text =
          (item.loc && item.loc.length ? item.loc.join(".") + ": " : "") +
          (item.msg || "");
        if (text) {
          parts.push(text);
        }
      });
    } else if (details && typeof details === "object") {
      Object.keys(details).forEach(function (key) {
        var value = details[key];
        var text = Array.isArray(value) ? value.join("; ") : String(value);
        parts.push(key + ": " + text);
      });
    }
    onError(
      parts.length ? parts.join(". ") : "Ошибка валидации (422).",
      response,
      body
    );
    return;
  }
  /* 409 «fast line occupied» (sdd §3.2) — человекочитаемое сообщение
   * рядом с чекбоксом fast (5.2, FR-3): форма остается открытой,
   * задача НЕ создается, пользователь может снять флаг или отменить. */
  if (response.status === 409) {
    onError(
      body && body.error === "fast line occupied"
        ? "fast line занята"
        : "Ошибка запроса (HTTP 409).",
      response,
      body
    );
    return;
  }
  onError("Ошибка запроса (HTTP " + response.status + ").", response, body);
}

/* Запрос к API: сеть (reject) → общее сообщение; HTTP-ошибка →
 * handleApiError; иначе onOk(тело). onError(message, response, body):
 * response/body передаются, когда обработчику нужен разбор ответа
 * (tasks 3.1: подсветка поля категории по details.category 422). */
export function api(path, options, onError, onOk) {
  fetch(path, Object.assign({ credentials: "same-origin" }, options))
    .then(function (response) {
      if (response.ok) {
        if (response.status === 204) {
          onOk(null);
          return;
        }
        return parseBody(response).then(function (body) {
          onOk(body);
        });
      }
      return parseBody(response).then(function (body) {
        handleApiError(response, body, onError);
      });
    })
    .catch(function () {
      onError("Сетевая ошибка. Проверьте соединение и попробуйте еще раз.");
    });
}
