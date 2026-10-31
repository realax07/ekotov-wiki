# autotest-coverage Specification

## Purpose
TBD - created by archiving change coverage-backfill-1. Update Purpose after archive.

## Requirements

### Requirement: Автотест-покрытие утвержденных Must-кейсов

Каждый утвержденный кейс (`test-model/approved/`) приоритета MUST из
разрывов отчета qa-cleanup-1026 (раздел «(г)») MUST иметь автотест в
репозитории с TC-ID маркером в docstring и зеленым прогоном на стенде.
Автотесты MUST NOT изменять прод-код. Кейс Should из списков разрывов
SHOULD быть покрыт автотестом или Should-решением в coverage-отчете.

#### Scenario: Группа p12-rich-tools покрыта

- **GIVEN** кейсы TC-rich-001…039 утверждены (test-model/approved/p12-rich-tools/)
- **WHEN** qa-инвентаризация сверяет TC-ID из approved с маркерами в tests/
- **THEN** каждый кейс группы найден автотестом с тем же TC-ID (Should —
  автотестом или Should-решением в coverage-отчете)

#### Scenario: Группа p23-fastline покрыта

- **GIVEN** кейсы TC-p23-109…121 утверждены (test-model/approved/p23-fastline/)
- **WHEN** qa-инвентаризация сверяет маркеры TC-p23 в tests/
- **THEN** кейсы 109…121 покрыты (116 Should — автотестом или
  Should-решением); существующее покрытие 101…108 не деградировало

#### Scenario: Группа weather-service покрыта

- **GIVEN** Must-кейсы TC-weather-001, 005–008, 015–019, 023, 025 утверждены
- **WHEN** qa-инвентаризация сверяет маркеры TC-weather
- **THEN** каждый перечисленный кейс найден автотестом с тем же TC-ID

#### Scenario: Группа add-responsive-mobile покрыта

- **GIVEN** кейсы TC-P14-101…110 утверждены
  (test-model/approved/add-responsive-mobile/)
- **WHEN** qa-инвентаризация сверяет маркеры TC-P14 в tests/
- **THEN** каждый кейс группы найден автотестом (Should-кейсы 106/107/108 —
  автотестом или Should-решением в coverage-отчете)

#### Scenario: Группа add-ui-polish-r8 покрыта

- **GIVEN** Must-кейсы TC-P12G-003/008/009/010/011, TC-P12N-005/008/009,
  TC-UIP-102/107/114 утверждены
- **WHEN** qa-инвентаризация сверяет маркеры в tests/ и services/*/tests/
- **THEN** каждый перечисленный кейс найден автотестом с тем же TC-ID

#### Scenario: Прод-код не меняется автотестами

- **GIVEN** change coverage-backfill-1 реализован полностью
- **WHEN** проверяется диф пакета
- **THEN** изменения — только тесты (tests/, services/*/tests/),
  test-model/reports/ и пакет change; прод-код (backend/, services/*/app,
  frontend/, deploy/) не изменен

#### Scenario: Трассировка маркеров воспроизводима

- **GIVEN** все задачи tasks.md групп A–E закрыты
- **WHEN** прогоняется инвентаризация TC-ID (approved vs tests/)
- **THEN** разрывы раздела «(г)» REPORT-qa-cleanup.md пусты; отчет
  coverage-backfill-1 фиксирует карту покрытия и Should-решения
