# Ревью test-модели: add-netdata-monitoring (impact, чеклист, approved-кейсы)

- **Дата:** 2026-10-05
- **Ревьюер:** независимый code_reviewer (review-003-2.1, deleg-14246228188a432f — содержательная верификация REPORT-2.1, тест-файла и трассировок, вердикт approve 5ddd133) + ПМ-проход оформления по прецеденту R6 (ccacc7b: машина не проводит qa_review поверх approved/ без new/ — DENY зафиксирован в релизном журнале)
- **Reviewer-Delegation:** deleg-14246228188a432f
- **Предмет:** test-model/impact/add-netdata-monitoring.md, test-model/checklists/add-netdata-monitoring.md, test-model/approved/add-netdata-monitoring/TC-ADD-201…206.md

## Вердикт: **ОДОБРИТЬ** (6 кейсов, impact + чеклист)

**Вердикт: approve.**

## Обоснование

1. **Impact-анализ согласован с фактами цикла:** дельта (deploy MODIFIED — netdata в матрице + nginx /netdata; monitoring/navigation ADDED; ядро не затронуто) описана верно; вердикт «keep весь регресс, revalidate живых метрик на 2.2» подтвержден REPORT-2.1 (web 171p/1s, api 201p/9s/2xf — оба стеновых 413, квалифицированы в §3, ревьюером review-003 проверено на согласованность чисел).
2. **Чеклист полон по дельте:** CHK-ADD-1…5 (monitoring: компоуз-паритет, непубликация, basic auth 301/401/200, NFR-19, живые метрики), CHK-ADD-6…8 (navigation: ролевая видимость, мокап, target=_blank), CHK-ADD-9…11 (деплой-смоук). Два docker-зависимых пункта (CHK-ADD-5, CHK-ADD-10) честно помечены частичным покрытием с переносом на 2.2 (E-2.1a) — совпадает с реестром компенсаций REPORT-2.1 §1/§3.1.
3. **Кейсы approved воспроизводимы:** TC-ADD-201…203 — маркеры на фактически исполненные web-проверки (tests/web/test_qa21_netdata_sidebar_ui.py, 171p/1s, verified review-003); TC-ADD-204 — смоук 301/401/200 REPORT-2.1 §3 (10/10); TC-ADD-205 — design_validator APPROVE (review-001-design, мета deleg_0b722e1e); TC-ADD-206 — security-заголовки/изоляция из того же смоука. Все ссылаются на CHK-ID чеклиста — трассировка замкнута.
4. **Мелочи, не влияющие на вердикт:** токен-литералы в тесте (minor-5 review-003) — в бэклоге; live-метрики — 2.2.
