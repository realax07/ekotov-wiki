# Решение Заказчика: релиз add-microservices-full принят, пакет архивируется

## Контекст

Пакет `add-microservices-full` (Флоу 1) — все 13 задач закрыты (2.1–2.4
приняты: review-008/009 approve + протоколы приемки acceptance-protocol-2.3/2.4;
2.5 — RUNBOOK 7a2e7a0 + map.md/sdd.md r13 ПМ-проходом). Прод с
2026-10-05 13:35 UTC работает на матричном стеке p12-rc1
(app + frontend + search + backup) на :10443; поиск обслуживается
отдельным сервисом `services/search` (read-only профиль, X-Service: search).

## Что решено

1. Релиз ПРИНЯТ Заказчиком; окно наблюдения пройдено без инцидентов.
2. Пакет `add-microservices-full` архивируется штатным порядком
   (openspec archive по правилам, MODIFIED-дельта deploy — по контракту
   полной замены; финальный PR с [change-id] маркером).
3. Эксплуатация: прод — compose-проект `ekotov-wiki-par` на :10443;
   вторая среда :10444 гасится `stop nginx` (НЕ `down -v` — том продовой);
   откат релиза — `deploy/2.4-switch.sh rollback`; systemd-юнит —
   исторический резерв v1.

## Последствия

- approval_ref для archive/release-действий пакета: `2026-10-05-release-microservices-full`.
- Правки ядра, всплывшие при релизе (см. BACKLOG фабрики): ложный критерий
  смоука без сессии, ro/maунт + uid в бэкап-трассах, release-log журнал —
  переносятся в эталон фабрики отдельным [chore]-циклом.

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-release-microservices-full",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-microservices-full",
    "phase": "release"
  },
  "action": "release",
  "commit": "44426bf",
  "source": "Заказчик, Telegram DM 2026-10-05: «Релиз принят» (ответ на финальный статус пакета: 13/13 задач, прод на матричном стеке, развилка ОВ-1/ОВ-2)"
}
```
