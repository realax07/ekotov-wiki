# Решение Заказчика: fix gallery escalations (Э-3/Э-4)

## decision-record

```decision-record
{
  "schema": "decision-record/1",
  "decision_id": "2026-10-05-gallery-fix-escalations",
  "date": "2026-10-05",
  "actor": "Заказчик (Егор Котов, Telegram DM)",
  "quote": "по gallery - чини все",
  "scope": {"project": "wiki", "change_id": "add-gallery-service", "phase": 1},
  "action": "dev_task",
  "approves": "закрыть эскалации Э-3/Э-4 сервисными дельтами в пакете add-gallery-service: (Э-3) список GET /api/images возвращает теги изображения; (Э-4) GET /api/auth/me отдает id пользователя; фронтенд gallery.js переходит на прямые данные",
  "artifacts": ["services/images/**", "backend/app/auth.py", "frontend/static/js/gallery.js", "tests/services images units"]
}
```

Слово Заказчика в чате 2026-10-05 ~22:20 UTC: «по gallery - чини все» — в ответ на доклад эскалаций Э-3 (API списка без тегов) и Э-4 (/api/auth/me без id). Трактовка: закрыть обе эскалации полноценными дельтами сервиса/ядра в рамках пакета add-gallery-service (Флоу 1), не упрощением мокапа.
