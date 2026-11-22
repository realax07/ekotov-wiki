# Утверждение кейсов redesign-ui-a (2026-11-22)

11 кейсов TC-ui-a-001…011 (по Requirement дельты, 29 Scenario внутри).
Независимое ревью qa_case_reviewer: «одобрить»
(test-model/reviews/redesign-ui-a/review-001.md — 0 blocker / 0 major /
2 minor, исправлений не требуется).

Проверка по условиям утверждения:
- автопокрытие — тесты уже существуют на HEAD (test_redesign_console.py
  36/36 + сьюты волны правок sdd §4), прогон 2 QA: 412 passed, 0 дельтовых
  фейлов (docs/qa/qa-redesign-ui-a.md);
- tests/api — единственное изменение: существующий test_qa21_gallery_design.py
  (TC-GAL-122 whitelist на токены A); новых API-кейсов нет;
- средовые :18443-кейсы классифицированы (QA §2.2), закрываются контуром
  regress-final.
