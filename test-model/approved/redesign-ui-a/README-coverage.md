# README-coverage: кейсы redesign-ui-a

11 кейсов TC-ui-a-001…011 — по одному на каждый Requirement дельты
(11/11), сценарии дельты (29) распределены внутри кейсов своего
Requirement. Трассировка «кейс → автотест»:

| Кейс | Requirement (дельта) | Автопокрытие (HEAD ff5a12d) |
|---|---|---|
| TC-ui-a-001 | accessibility NFR-41 (2 scen) | test_tc_redesign_001 |
| TC-ui-a-002 | accessibility NFR-42 (2 scen) | test_tc_redesign_002 (cyan→gold) |
| TC-ui-a-003 | board FR-132 (2 scen) | test_tc_redesign_007/008/009, test_r3_vis_ui (TC-vis-101), test_bug004, test_board_fastline, test_coverage_fastline |
| TC-ui-a-004 | design-tokens FR-128 (4 scen) | test_tc_redesign_010/011, TC-GAL-122 (test_qa21_gallery_design) |
| TC-ui-a-005 | design-tokens FR-129 (2 scen) | test_tc_redesign_012 (cyan→gold), test_r6_tag_combobox_ui, test_p12_nav_icons_favicon_r8 |
| TC-ui-a-006 | design-tokens FR-130 (3 scen) | test_tc_redesign_013, test_tc_redesign_030 (LED) |
| TC-ui-a-007 | gallery FR-125 (3 scen) | test_tc_redesign_016/017, TC-GAL-122-live (:18443 — контур regress-final) |
| TC-ui-a-008 | navigation ADDED (3 scen) | test_tc_redesign_010 (light-блок), test_tc_redesign_023 (#theme-toggle 44px); «localStorage недоступен» — ручное (QA §3) |
| TC-ui-a-009 | video-ui FR-126 (2 scen) | test_tc_redesign_030, video-сьюты tests/web |
| TC-ui-a-010 | wiki FR-123 (4 scen) | test_tc_redesign_034/035, test_p15_wiki_tree |
| TC-ui-a-011 | wiki FR-124 (2 scen) | test_tc_redesign_033/036, test_p15_wiki_* |

Известный фон: средовые :18443-кейсы (QA-отчет §2.2) — закрываются
каноническим контуром `scripts/qa_stand_up.sh` на regress-final
(impact/redesign-ui-a.md Д1).
