# TC-ADD-201: Ссылка «Мониторинг» видна только Product manager

- **Источник:** navigation FR-78; QA 2.1(a); CHK-ADD-6
- **Предусловие:** живой стенд, сессия owner (роль Product manager)
- **Шаги:** открыть любую страницу функционала; инспекция sidebar-footer
- **Ожидание:** пункт «Мониторинг» присутствует, href=/netdata/, target=_blank, rel=noopener
- **Покрытие:** tests/web/test_qa21_netdata_sidebar_ui.py::test_owner_sees_monitoring_link
- **Вердикт QA:** PASS (REPORT-2.1 §2)
