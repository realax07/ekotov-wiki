# TC-ui-a-009: Экран «Видео» в стиле A (FR-126)

- **Change:** redesign-ui-a
- **Источник:** video-ui MODIFIED — «Экран «Видео» в стиле «Пульт» (FR-126)» / Scenario: «Список видео в визуале «Пульта»», «Функциональность видео не деградировала»
- **Тип:** визуальный | **Приоритет:** Must
- **Среда/предусловия:** video-сервис с сидом 4 статусов; страница /video; редизайн применен (токены наследуются от app.css — снимок «Пульт» удален)
- **Шаги:**
  1. Карточки: v-card-title serif, статусы LED (золото «Новое»/warning-blink/success/danger), play-overlay gold-hover, плеер-рамка (автотест `test_tc_redesign_030_video_screen_pult` + браузерная сверка QA §3: все 4 статуса различимы в обеих темах, 8 player-узлов, плейсхолдеры ph-frame/ph-no-frame ✓).
  2. Функциональность: карточки/фильтры/плеер — видео-сьюты tests/web (test_video_ui, test_video_convert_ui, test_video_rename_ui, test_video_social_ui) без правок логики.
- **Ожидаемый результат:** визуал соответствует эталону `design-forge/extra/video` (QA §4 ✓); видео-сьюты green в прогоне 2 (rest-of 32 файла зеленые).
- **Тестовые данные:** сид video (uploaded/converting/ready/error).
