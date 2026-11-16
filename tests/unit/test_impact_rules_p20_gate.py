"""P20 волна 7: негативный тест гейта дрейфа IR-08…IR-12 (Д-Б1/ОВ-5/ОВ-6).

Change add-p20-contracts, задачи 7.1/7.2 (design add-p20-contracts §5,
FR-140, ОГР-31). Гейт = декларативные правила в scripts/impact_rules.json,
исполняются существующим check_impact_rules (pr_validate.py / CI-шаг
pr_validate) — код ворот НЕ менялся.

Четыре кейса приемки задачи 7.2 + уточнение content_when:
1. фиктивный дифф «новый маршрут в services/video/app без контракта» →
   DENY с id IR-08 и hint «перегенерируй контракт»;
2. тот же дифф + изменение contracts/openapi-video.json → green (ОГР-31:
   правка + перегенерация одним PR);
3. static_v-бамп (backend/app/pages.py без декораторов) → без DENY
   (content_when по добавленной строке декоратора);
4. дифф «новый contracts/openapi-video.json» без ядерного контракта →
   без DENY (IR-07 сужен волной 0 — регресс-проверка Д-Б1);
5. правка handler'а БЕЗ новой строки декоратора → без DENY
   (осознанное сужение: гейт = поверхность, payloads — схемная
   валидация services/*/tests, design §5).

Симуляции — PR_CHANGED_FILES-конвенция (check_impact_rules) с
синтетическим патчем (monkeypatch _diff_patch — git-патч фиктивный дифф
не содержит) и CLI-прогон scripts/pr_validate.py.

Трассировка: TC-P20-010…TC-P20-015 (FR-140, ОВ-5/ОВ-6, ОГР-31, NFR-46).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "scripts" / "impact_rules.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pr_validate  # noqa: E402


def _rule(rule_id: str) -> dict:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return next(r for r in data["rules"] if r["id"] == rule_id)


# Синтетический патч «новый маршрут в video-сервисе» (форма git-патча —
# как ее читает content_when: chunks по «diff --git », заголовок — путь).
PATCH_VIDEO_NEW_ROUTE = (
    "diff --git a/services/video/app/videos.py b/services/video/app/videos.py\n"
    "--- a/services/video/app/videos.py\n"
    "+++ b/services/video/app/videos.py\n"
    "@@ -10,6 +10,8 @@ def existing():\n"
    "     return {}\n"
    "+@router.get(\"/api/videos/extra\")\n"
    "+def extra():\n"
    "+    return {}\n"
)

# Тот же файл, правка ЛОГИКИ handler'а без новой строки декоратора.
PATCH_VIDEO_HANDLER_ONLY = (
    "diff --git a/services/video/app/videos.py b/services/video/app/videos.py\n"
    "--- a/services/video/app/videos.py\n"
    "+++ b/services/video/app/videos.py\n"
    "@@ -10,6 +10,7 @@ def existing():\n"
    "-    return {}\n"
    "+    return {\"extra\": True}\n"
)

# static_v-бамп ядра: pages.py без декораторов маршрутов.
PATCH_PAGES_STATIC_V = (
    "diff --git a/backend/app/pages.py b/backend/app/pages.py\n"
    "--- a/backend/app/pages.py\n"
    "+++ b/backend/app/pages.py\n"
    "@@ -5,4 +5,4 @@\n"
    '-static_v = "p15-wiki-7"\n'
    '+static_v = "p16-contracts"\n'
)


@pytest.fixture()
def fake_patch(monkeypatch):
    """Фабрика: подменяет git-патч (_diff_patch) синтетическим диффом."""
    def _set(patch: str):
        monkeypatch.setattr(pr_validate, "_diff_patch", lambda repo: patch)
    return _set


def test_p20_gate_rules_present():
    """TC-P20-010 (задача 7.1): IR-08…IR-12 присутствуют декларативно —
    when по app-кодам сервиса/ядра, content_when — строка декоратора
    маршрута, require — контракт соответствующего сервиса/ядра."""
    decorator = r"\+\s*@(router|app)\.(get|post|put|patch|delete|api_route)"
    expected = {
        "IR-08": ("^services/video/app/", r"^contracts/openapi-video\.json$"),
        "IR-09": ("^services/images/app/", r"^contracts/openapi-images\.json$"),
        "IR-10": ("^services/weather/app/", r"^contracts/openapi-weather\.json$"),
        "IR-11": ("^services/search/app/", r"^contracts/openapi-search\.json$"),
        "IR-12": ("^backend/app/", r"^contracts/openapi\.json$"),
    }
    for rule_id, (when_path, require_path) in expected.items():
        rule = _rule(rule_id)
        assert rule["when"] == [{"path": when_path}], rule_id
        cw = rule["content_when"]
        assert len(cw) == 1 and cw[0]["regex"] == decorator, rule_id
        assert cw[0]["path"] in when_path or cw[0]["path"] == when_path.rstrip("/"), rule_id
        assert rule["require"][0]["path"] == require_path, rule_id
        assert "перегенерируй контракт" in rule["require"][0]["hint"], rule_id


def test_p20_gate_new_route_without_contract_denies(fake_patch):
    """TC-P20-011 (задача 7.2, кейс 1): новый маршрут в services/video/app
    без контракта в диффе → DENY IR-08 с hint «перегенерируй контракт»."""
    fake_patch(PATCH_VIDEO_NEW_ROUTE)
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [("M", "services/video/app/videos.py")])
    assert len(errs) == 1
    assert "IR-08" in errs[0]
    assert "перегенерируй контракт" in errs[0]
    assert "contracts/openapi-video.json" in errs[0]


def test_p20_gate_route_with_contract_green(fake_patch):
    """TC-P20-012 (задача 7.2, кейс 2): тот же дифф + перегенерированный
    contracts/openapi-video.json (ОГР-31 одним PR) → DENY нет."""
    fake_patch(PATCH_VIDEO_NEW_ROUTE)
    errs = pr_validate.check_impact_rules(
        REPO_ROOT,
        [("M", "services/video/app/videos.py"),
         ("M", "contracts/openapi-video.json")])
    assert errs == []


def test_p20_gate_static_v_bump_no_deny(fake_patch):
    """TC-P20-013 (задача 7.2, кейс 3): static_v-бамп backend/app/pages.py
    БЕЗ декораторов маршрутов → IR-12 молчит (content_when), DENY нет."""
    fake_patch(PATCH_PAGES_STATIC_V)
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [("M", "backend/app/pages.py")])
    assert errs == []


def test_p20_gate_service_contract_freeze_no_deny(fake_patch):
    """TC-P20-014 (задача 7.2, кейс 4): новый contracts/openapi-video.json
    без ядерного контракта → DENY нет (IR-07 сужен волной 0, Д-Б1)."""
    fake_patch(PATCH_VIDEO_NEW_ROUTE)  # патч значения не имеет
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [("A", "contracts/openapi-video.json")])
    assert errs == []


def test_p20_gate_handler_edit_without_decorator_no_deny(fake_patch):
    """TC-P20-015 (задача 7.2, уточнение design §5): правка логики handler'а
    без новой строки декоратора маршрута → IR-08 молчит (двухслойная
    защита: гейт = поверхность, дрейф payloads ловит схемная валидация
    services/*/tests)."""
    fake_patch(PATCH_VIDEO_HANDLER_ONLY)
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [("M", "services/video/app/videos.py")])
    assert errs == []


def _run_cli(env_files: str | None) -> str:
    env = dict(os.environ)
    env.pop("GITHUB_EVENT_PATH", None)  # CLI-режим, не CI-событие
    env.pop("PR_BODY", None)            # pr_body-требования SKIP без контекста
    if env_files is None:
        env.pop("PR_CHANGED_FILES", None)  # чистый HEAD: fallback git-дифф
    else:
        env["PR_CHANGED_FILES"] = env_files
    proc = subprocess.run(
        [sys.executable, "scripts/pr_validate.py", ".", "--id", "[chore] test"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)
    return proc.stdout + proc.stderr


def test_p20_gate_cli_clean_head_no_deny():
    """TC-P20-016 (задача 7.1, критерий приемки): CLI-прогон
    python3 scripts/pr_validate.py . --id на чистом HEAD — J58-DENY нет
    (content_when не срабатывает на пустом/нерелевантном диффе); и CLI
    PR_CHANGED_FILES-симуляция правки video-кода без патча-декоратора —
    тоже без DENY."""
    assert "J58: правило IR-" not in _run_cli(None)
    assert "J58: правило IR-" not in _run_cli("M\tservices/video/app/videos.py\n")
