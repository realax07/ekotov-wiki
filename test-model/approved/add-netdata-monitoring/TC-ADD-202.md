# TC-ADD-202: Ссылка скрыта у PE (wife) и анонима

- **Источник:** navigation FR-78 (ролевая видимость); QA 2.1(a); CHK-ADD-6
- **Предусловие:** сессия PE; отдельная проба без сессии
- **Ожидание:** пункта «Мониторинг» нет в DOM у обоих; блок профиля не сломан
- **Покрытие:** tests/web/test_qa21_netdata_sidebar_ui.py::test_pe_and_anonymous_no_link
- **Вердикт QA:** PASS
