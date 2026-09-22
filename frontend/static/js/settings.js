/* Управление справочником категорий на /settings (tasks.md 2.1 пакета
 * add-r2-categories-settings; дельта settings, FR-19/FR-20 через API
 * из задач 1.1 — POST/PATCH/DELETE /api/categories). Никаких дублей
 * бэкенда: только существующие эндпоинты (sdd r2 §3.1).
 *
 * Сценарии дельты settings, покрываемые здесь:
 * - «В настройках доступно только управление категориями» (FR-25):
 *   единственные действия на странице — создать/переименовать/удалить.
 * - 409 {"error": "category in use", "details": {"tasks": N}} (Д-1):
 *   сообщение пользователю с числом задач из details.tasks.
 * - 422 (пустое имя) и 409 (дубль) — текст ошибки показывается как есть.
 * - 401 (сессия истекла): middleware не редиректит fetch — переходим на
 *   /login сами (паттерн: страница без сессии редиректится сервером).
 * Имена категорий вставляются только через textContent (XSS, как в dom.js).
 */
(function () {
  "use strict";

  var listEl = document.getElementById("category-list");
  var errorEl = document.getElementById("settings-error");
  var successEl = document.getElementById("settings-success");
  var createForm = document.getElementById("category-create-form");
  var newNameInput = document.getElementById("category-new-name");

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

  function clearMessages() {
    errorEl.hidden = true;
    successEl.hidden = true;
  }

  function request(method, url, body) {
    return fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then(function (response) {
      if (response.status === 401) {
        // Сессия истекла: страница настроек без сессии сервером редиректится.
        window.location.href = "/login";
        return new Promise(function () {}); // не резолвим — идет переход
      }
      return response
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          return { status: response.status, data: data };
        });
    });
  }

  function loadCategories() {
    return request("GET", "/api/categories").then(function (result) {
      if (result.status !== 200) {
        showError("Не удалось загрузить категории");
        return;
      }
      render(result.data.categories || []);
    });
  }

  function render(categories) {
    listEl.textContent = "";
    categories.forEach(function (category) {
      var li = document.createElement("li");
      li.className = "category-item";
      li.dataset.id = category.id;

      var nameEl = document.createElement("span");
      nameEl.className = "category-name";
      nameEl.textContent = category.name; // без innerHTML (XSS)

      var actions = document.createElement("span");
      actions.className = "category-actions";

      var renameButton = document.createElement("button");
      renameButton.type = "button";
      renameButton.className = "category-rename";
      renameButton.textContent = "Переименовать";
      renameButton.addEventListener("click", function () {
        startRename(li, category);
      });

      var deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "category-delete";
      deleteButton.textContent = "Удалить";
      deleteButton.addEventListener("click", function () {
        removeCategory(category);
      });

      actions.appendChild(renameButton);
      actions.appendChild(deleteButton);
      li.appendChild(nameEl);
      li.appendChild(actions);
      listEl.appendChild(li);
    });
  }

  function startRename(li, category) {
    // Инлайн-переименование: input с текущим именем + Сохранить/Отмена.
    var nameEl = li.querySelector(".category-name");
    var actionsEl = li.querySelector(".category-actions");
    var input = document.createElement("input");
    input.type = "text";
    input.className = "category-rename-input";
    input.value = category.name;

    var saveButton = document.createElement("button");
    saveButton.type = "button";
    saveButton.textContent = "Сохранить";
    saveButton.addEventListener("click", function () {
      var name = input.value.trim();
      if (!name) {
        showError("Имя категории не может быть пустым");
        return;
      }
      request("PATCH", "/api/categories/" + category.id, { name: name }).then(
        function (result) {
          if (result.status === 200) {
            clearMessages();
            showSuccess("Категория переименована");
            loadCategories();
          } else if (result.status === 409) {
            showError("Категория с таким именем уже существует");
          } else if (result.status === 422) {
            showError("Имя категории не может быть пустым");
          } else if (result.status === 404) {
            showError("Категория уже удалена");
            loadCategories();
          } else {
            showError("Не удалось переименовать категорию");
          }
        }
      );
    });

    var cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.textContent = "Отмена";
    cancelButton.addEventListener("click", function () {
      clearMessages();
      loadCategories();
    });

    nameEl.replaceWith(input);
    actionsEl.textContent = "";
    actionsEl.appendChild(saveButton);
    actionsEl.appendChild(cancelButton);
    input.focus();
  }

  function removeCategory(category) {
    if (!window.confirm('Удалить категорию "' + category.name + '"?')) {
      return;
    }
    request("DELETE", "/api/categories/" + category.id).then(function (result) {
      if (result.status === 200) {
        clearMessages();
        showSuccess("Категория удалена");
        loadCategories();
        return;
      }
      if (result.status === 409) {
        // Д-1: категория используется задачами — показываем число задач
        // из details.tasks (sdd r2 §3.1).
        var tasks = result.data && result.data.details ? result.data.details.tasks : undefined;
        showError(
          "Категория используется задачами (" +
            (tasks === undefined ? "число неизвестно" : tasks) +
            "). Переведите задачи на другую категорию и повторите удаление."
        );
        return;
      }
      if (result.status === 404) {
        showError("Категория уже удалена");
        loadCategories();
        return;
      }
      showError("Не удалось удалить категорию");
    });
  }

  createForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var name = newNameInput.value.trim();
    if (!name) {
      showError("Введите имя категории");
      return;
    }
    request("POST", "/api/categories", { name: name }).then(function (result) {
      if (result.status === 201) {
        newNameInput.value = "";
        clearMessages();
        showSuccess("Категория создана");
        loadCategories();
      } else if (result.status === 409) {
        showError("Категория с таким именем уже существует");
      } else if (result.status === 422) {
        showError("Имя категории не может быть пустым");
      } else {
        showError("Не удалось создать категорию");
      }
    });
  });

  loadCategories();
})();
