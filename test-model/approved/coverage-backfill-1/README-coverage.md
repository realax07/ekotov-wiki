# Покрытие coverage-backfill-1 — трассировка к утвержденным кейсам

Утвержденные кейсы живут в пакетах-источниках (approval-делегирование
Заказчика 2026-10-24, APPROVAL.md в каждом пакете). Здесь — карта групп на
исходные каталоги кейсов. Автотесты: tests/web/test_coverage_*.py
(docstring содержит маркер пакета и исходный TC-ID).

| Группа | Источник кейсов (approved) | Кейсы | Автотесты | Статус |
|---|---|---|---|---|
| A.01–A.39 | test-model/approved/p12-rich-tools/ | TC-rich-001…039 | test_coverage_rich_tools.py, test_coverage_rich_tools_security.py | 39/39 |
| B.01–B.13 | test-model/approved/p23-fastline/ | TC-p23-109…121 | test_coverage_fastline.py | 13/13 |
| C.01–C.12 | test-model/approved/weather-service/ | TC-weather-001, 005–008, 015–019, 023, 025 | test_coverage_weather.py | 11 автотестов + 1 skip (TC-weather-019 — docker-стенд) |
| D.01–D.10 | test-model/approved/add-responsive-mobile/ | TC-P14-101…110 | test_coverage_p14_mobile.py | 9 автотестов + 1 manual (TC-P14-110 — живая приемка на проде) |
| E.01–E.11 | test-model/approved/add-ui-polish-r8/ | TC-P12G-003/008–011, P12N-005/008/009, UIP-102/107/114 | test_coverage_uip.py | 11/11 |

Попутные находки волны (баг-репорты): test-model/bugs/BUG-022…024
(rich: панель таблиц, redo спойлера, диалог «Ссылка»).
