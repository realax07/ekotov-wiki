# TC-UIP-113 — UPDATE TC-UI-010: инверсия has-fast на столбце (в дополнение к TC-UIP-101)

- **Change:** add-ui-polish-r8
- **Источник:** board Requirement «Подсветка fast line» / FR-87; impact §Волна 2.1: verdict **update** на `tests/web/test_fastline_ui.py::test_fast_task_create_and_highlight` (TC-UI-010, **строка 42**); CHK-P12-1 (покрытие update-ассертов кейсом TC-UIP-101 — этот файл — исполняемая инструкция для qa_automation)
- **Тип:** НФТ / update-сьют | **Приоритет:** Must
- **Маркер:** update-сьют — указание qa_automation; прогон 3.1 после правки (Прогон R2, первым в fastline-блоке)
- **Предусловия:** merge-ветка с волной 2.1 (правка board.css §5.2 — удалено правило `.board-column.has-fast`); fast line свободна; nginx-стенд
- **UPDATE — что именно меняется в существующем тесте:**

| # | Было (TC-UI-010) | Станет (после FR-87) |
|---|---|---|
| 1 | Строка 42: `assert "has-fast" in todo.get_attribute("class")` | **ЗАМЕНИТЬ на ОБРАТНЫЙ:** `assert "has-fast" not in todo.get_attribute("class")` |
| 2 | Строка 43: `assert "task-card-fast" in fast_card.get_attribute("class")` | **Без изменений** |
| 3 | Docstring строк 28–29 («столбец подсвечен») | **ПЕРЕПИСАТЬ:** «подсветка только плитки `.task-card-fast`; столбец не красится (FR-87)» |
| 4 | Бейдж + first-in-column | **Без изменений** (TC-UI-018 `test_final_path_autoarchive_and_fast_release`, ассерт `task-card-fast` строка 233 — keep, не трогается) |

- **Шаги:**
  1. Применить правки к test_fast_task_create_and_highlight.
  2. Прогнать сьют test_fastline_ui.py: TC-UI-010 (обновленный) + TC-UI-011 (keep, вторая fast 409).
  3. Кросс-проверка: TC-UI-018 не требует правок и зелен (ассертит только плитку).
- **Ожидаемый результат:** шаг 2 — обновленный TC-UI-010 зелен: столбец `[data-status="todo"]` без `has-fast`, плитка с `task-card-fast`; TC-UI-011 зелен без правок; шаг 3 — TC-UI-018 зелен; ни один локатор не переименован (ОГР-28).
