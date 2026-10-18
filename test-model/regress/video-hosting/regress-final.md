# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T04:45:00+00:00
- commit: 1055ec49eb3e46b1cddab7847af480a9eda59c6a
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh2
- verdict: FAIL
- diff source: git diff main...HEAD
- changed files: 107
- suites: tests/api, tests/web, tests (маппинг J51.2-дедупом сворачивается в общий домен `tests`)
- pytest exit code: — (механический прогон не стартовал, см. «Блокер ворот»)
- Предыдущий прогон: 2416f77 (95105ef), вердикт FAIL — дефект маппинга
  (дубль домена `tests`); считается устраненным 1055ec4, но зеркало неполное.

## Блокер ворот (механический прогон, 2 попытки — детерминировано, не флак)

`python3 scripts/flowctl.py regress --change video-hosting --final` падает ДО
выбора тестов на обоих прогонах с идентичным трейсом:

```
File "scripts/flowctl.py", line 1393, in cmd_regress
    cid_problem = sc.change_id_problem(change)
AttributeError: module 'session_check' has no attribute 'change_id_problem'
```

Причина: зеркало фабрики 1055ec4 («зеркало фабрики: flowctl regress — дедуп
доменов маппинга») перенесло `cmd_regress` из ai-factory/scripts/flowctl.py
(328 insertions), но НЕ перенесло зависимость из
ai-factory/scripts/session_check.py:96 — `CHANGE_ID_RE` + `change_id_problem()`.
В wiki-зеркале scripts/session_check.py этих символов нет. Чинить зеркалом
фабрики (функция + CHANGE_ID_RE), зона scripts/ — вне зоны regress_runner.
Попутно: читающий конец ворот `pr_validate.check_regress_final` (упомянут
комментарием в cmd_regress как «та же функция на читающем конце») в wiki-
scripts/pr_validate.py тоже отсутствует — зеркало неполное с обеих сторон:
даже после починки session_check артефакт regress-final останется без
машинной валидации ворот merge.

## Фактический регресс (эквивалентный прогон, прецедент предыдущего артефакта)

Механический эквивалент при живых воротах — одиночный вызов домена `tests`
(дедуп сворачивает частичные домены в общий). Фактический прогон выполнен
покомпонентно на каноническом контуре (прецедент REPORT-regress-21 §2,
REPORT-2.1-gallery-qa §1, предыдущий regress-final):

- контур: nginx :18443 → app :8080 + search :8391 + images :8392 + video :8399
  (прод-паритет services/frontend/nginx/ekotov-wiki.conf: search/images/videos-
  локации, /videos/ c authcheck-subrequest, netdata-заглушка c basic-auth;
  видео-сервис с ffmpeg в PATH);
- БД на сессию: свежая схема (`python -m app.db`) → seed owner/wife
  (программно, bcrypt) → migrate_r4/gallery/wiki/video → справочник
  «Дом/Работа/Личное» (README-протокол внешнего стенда: автосеем внешний
  стенд не занимается; migrate_categories на пустой БД справочник НЕ создает —
  это дата-миграция из задач);
- env: EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443, EKOTOV_WIKI_DB_PATH,
  AVATARS_DIR (tmp), EKOTOV_WIKI_IMAGES_PORT/IMAGES_DIR; mime-проверка статики
  через nginx — application/javascript; интерпретатор venv (3.11/pytest 9.1).

### tests/api (через nginx) — 310 collected, ИТОГ 0 failed

- маршрутный прогон: 283 passed, 14 failed, 11 skipped, 2 xfailed (125s).
- Изолированный перепрогон 14 в канонической для них среде — все green:
  - avatar_r4/avatar_r5/gaps_r5 (16 тестов файлов, 12 упавших + смежные):
    по дизайну кейсов 2МБ-границы требуют direct-app стенд :8080 + AVATARS_DIR
    (через nginx серверный лимит 2m дает 413 раньше сервиса) — 16 passed
    (27s); при первом подъеме стенда ловится грабля env: переменная стенда
    называется AVATARS_DIR, EKOTOV_WIKI_AVATARS_DIR — только тестовое;
  - tc_gal_107: нужен env EKOTOV_WIKI_IMAGES_DIR (том сервиса) — 1 passed.
- skipped/xfailed — эталонные по tests/README (BUG-003 ×2, НФТ-рестарты).

### tests/web (через nginx) — 258 collected: 250 passed, 7 failed (663s)

Изолированный перепрогон семи упавших (2× на свежей БД; оба прогона
идентичны — ФЛАКОВ НЕТ):

- Green изолированно (2/2); в полном порядке их красит контекст:
  - test_bug014 computed_styles — известный БАГ-016 (evaluate без
    предварительного expect — элемент отсутствует в момент снятия); тест-
    дефект механики, pre-existing (файл вне диффа);
  - tc_gal_115, tc_gal_116 — в полном порядке галерею засоряет хвост
    test_p15_wiki_editor (заливает картинку редактора в галерею, original_name
    `tmp*.png` остается в БД/томе без очистки — pre-existing долг очистки,
    p15 вне диффа); изолированно 115/116 green 2/2.
- Детерминированный FAIL 2/2:
  - **test_navigation_search_ui::test_sidebar_all_pages_and_wiki_stub —
    ДИФФ-ЗОНА (файл в диффе)**: `get_by_role("heading", name="Wiki")` на
    пустой wiki-БД матчит ДВА заголовка (h1 «Wiki» + empty-state «В Wiki пока
    нет страниц») → strict violation, «Actual value: None». Локатору нужен
    exact=True/.first. Продукт работает (проба playwright: клик «Wiki» →
    /wiki, h1 на месте, 5 пунктов сайдбара). Синхронизировать в пакете — тот
    же класс, что уже снятый в ef77e26 устаревший сайдбар-ассерт;
  - **test_qa21_gallery_ui::test_tc_gal_119... — ДИФФ-ЗОНА (обновлен ef77e26)**:
    `.wiki-create` на пустой wiki-БД резолвится в ДВЕ кнопки (empty-state
    «Создать первую страницу» + тулбарная «Создать страницу») → strict
    violation; нужен `.first()`. Синхронизировать в пакете;
  - test_p12_ui_polish_r8::test_combobox_three_tags... — pre-existing
    (идентично предыдущему артефакту: красный на чистом main);
  - test_r3_profile_ui::test_profile_badge... — задокументированный
    стенд-артефакт предыдущего артефакта (strict-матчинг заголовка «Wiki»
    ловит пустую wiki-БД стенда), не регресс диффа.

Видео-сьюты ветки на контуре green: test_video_convert_ui,
test_video_social_ui, test_video_ui, test_video_wiki_isolation_ui — в числе
250 passed.

### tests/ (корень) — механический домен

- test_flowctl.py: 28 failed, 11 passed — pre-existing дрейф (идентичный
  падеж на чистом main, зафиксирован предыдущим артефактом; состав 28
  совпадает). С учетом того, что scripts/flowctl.py в диффе — после починки
  зеркала сводить счетчик с чистым main заново.
- test_walkthrough_probe.py: 1 passed.

## Итог разбора

- Продуктовых багов диффа video-hosting НЕ выявлено: видео-фича работает
  (сайдбар 5 пунктов с «Видео», /api/videos маршрутизируется через nginx,
  конвертация и социальные механики — видео-сьюты green на контуре).
- Ворота merge блокируют ДВЕ вещи, обе вне зоны regress_runner:
  1. Баг зеркала 1055ec4: scripts/session_check.py без `change_id_problem`
     (зеркало фабрики неполное; там же отсутствует `check_regress_final` в
     scripts/pr_validate.py) — механический `regress --final` не запускается;
  2. Два тест-дефекта дифф-зоны на пустой wiki-БД (TC-UI-016-сайдбар:
     heading-name без exact; TC-GAL-119: `.wiki-create` без .first) —
     детерминированы 2/2, синхронизировать в пакете.
- После устранения 1–2 перегнать `regress --final` механически.
