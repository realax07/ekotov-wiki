"""P20 волна 0: сужения IR-01/IR-07 в scripts/impact_rules.json (Д-Б1/Д-Б2).

Change add-p20-contracts, задачи 0.1/0.2 (design §5, arch-review-001).

Инварианты волны 0 (до волн с якорями/контрактами сервисов):
1. IR-01 when[].path сужен до ^services/[^/]+/openapi\\.json$ — yaml-якорь
   services/<svc>/openapi.yaml (например новый services/video/openapi.yaml)
   НЕ триггерит правило (ложный DENY «перегенерируй contracts/openapi.json»
   устранен), машиночитаемая спека services/<svc>/openapi.json — триггерит
   как прежде (guard консервируется).
2. IR-07 when[].path сужен до ^contracts/openapi\\.json$ — новый сервисный
   контракт contracts/openapi-<svc>.json (PR заморозки волны 2–4) и ОГР-31
   PR сервисов (код сервиса + перегенерация контракта того же сервиса) НЕ
   триггерят правило; ядерный contracts/openapi.json — триггерит (guard).
3. Гейт не ослаблен: IR-01 на M services/search/openapi.json без
   перегенерации ядра — DENY прежний (exists-guard: contracts/openapi.json
   есть в HEAD продуктового репо).

Симуляции — синтетические диффы через PR_CHANGED_FILES-конвенцию
(pr_validate.check_impact_rules) и CLI-прогон scripts/pr_validate.py,
как в критериях приемки tasks 0.1/0.2.

Трассировка: TC-P20-001…TC-P20-009 (change add-p20-contracts, FR-140,
ОВ-5/ОВ-6; design add-p20-contracts §5).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "scripts" / "impact_rules.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pr_validate  # noqa: E402


def F(st, path):
    return (st, path)


def _rules():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def _rule(rules, rule_id):
    return next(r for r in rules["rules"] if r["id"] == rule_id)


# --------------------------------------------------------------------------
# TC-P20-001..002: сужения when[].path зафиксированы декларативно
# --------------------------------------------------------------------------

def test_p20_rules_json_valid_and_narrowed():
    """TC-P20-001: rules.json валиден; IR-01 → ^services/[^/]+/openapi\\.json$,
    IR-07 → ^contracts/openapi\\.json$ (Д-Б1/Д-Б2, design §5); require не тронуты."""
    data = _rules()
    assert _rule(data, "IR-01")["when"] == [{"path": r"^services/[^/]+/openapi\.json$"}]
    assert _rule(data, "IR-07")["when"] == [{"path": r"^contracts/openapi\.json$"}]
    # require-требования не менялись (обе сужения — только when)
    assert _rule(data, "IR-01")["require"][0]["path"] == r"^contracts/openapi\.json$"
    assert _rule(data, "IR-07")["require"][0]["path"] == r"^contracts/openapi\.json$"
    # content_when IR-07 сохранен (structural-маркеры патча — как было)
    assert _rule(data, "IR-07")["content_when"][0]["path"] == "contracts/"


def test_p20_gate_not_weakened_ir01_openapi_json_still_denies():
    """TC-P20-002: guard жив — M services/<svc>/openapi.json без ядерного
    контракта в диффе → DENY IR-01 (exists-guard: contracts/openapi.json в HEAD)."""
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [F("M", "services/search/openapi.json")])
    assert len(errs) == 1 and "IR-01" in errs[0]
    assert "contracts/openapi.json" in errs[0]


# --------------------------------------------------------------------------
# TC-P20-003..005: симуляции приемки tasks 0.1/0.2 (DENY нет)
# --------------------------------------------------------------------------

def test_p20_ir01_yaml_anchor_new_service_no_deny():
    """TC-P20-003 (tasks 0.1): новый yaml-якорь services/video/openapi.yaml
    в диффе — DENY нет (до сужения IR-01 давал ложный DENY)."""
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [F("A", "services/video/openapi.yaml")])
    assert errs == []


def test_p20_ir07_service_contract_freeze_pr_no_deny():
    """TC-P20-004 (tasks 0.2): PR заморозки — новый contracts/openapi-video.json
    без ядерного контракта в диффе — DENY нет (до сужения IR-07 — DENY)."""
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [F("A", "contracts/openapi-video.json")])
    assert errs == []


def test_p20_ir07_ogr31_service_pr_no_deny():
    """TC-P20-005 (tasks 0.2): ОГР-31 PR сервиса — код videos.py + контракт
    того же сервиса — DENY нет (ядерный контракт в диффе не появляется)."""
    errs = pr_validate.check_impact_rules(
        REPO_ROOT, [F("A", "services/video/app/videos.py"),
                    F("A", "contracts/openapi-video.json")])
    assert errs == []


# --------------------------------------------------------------------------
# TC-P20-006..009: CLI-симуляции python3 scripts/pr_validate.py .
# (PR_CHANGED_FILES-конвенция, критерий приемки tasks 0.1/0.2)
# --------------------------------------------------------------------------

def _run_validate(env_files: str | None) -> str:
    env = dict(os.environ)
    env.pop("GITHUB_EVENT_PATH", None)  # CLI-режим, не CI-событие
    env.pop("PR_BODY", None)            # pr_body-требования SKIP без контекста
    if env_files is None:
        env.pop("PR_CHANGED_FILES", None)  # чистый HEAD: fallback git-дифф
    else:
        env["PR_CHANGED_FILES"] = env_files
    proc = subprocess.run(
        [sys.executable, "scripts/pr_validate.py", ".", "--id", "add-p20-contracts"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)
    return proc.stdout + proc.stderr


def test_p20_cli_sim_new_yaml_anchor_no_deny():
    """TC-P20-006: CLI-симуляция «новый services/video/openapi.yaml» —
    в выводе нет J58-DENY по IR-01 (задача 0.1)."""
    out = _run_validate("A\tservices/video/openapi.yaml\n")
    assert "J58: правило IR-01" not in out


def test_p20_cli_sim_service_contract_no_deny():
    """TC-P20-007: CLI-симуляция «новый contracts/openapi-video.json» —
    в выводе нет J58-DENY по IR-07 (задача 0.2)."""
    out = _run_validate("A\tcontracts/openapi-video.json\n")
    assert "J58: правило IR-07" not in out


def test_p20_cli_sim_ogr31_pr_no_deny():
    """TC-P20-008: CLI-симуляция ОГР-31 (videos.py + openapi-video.json) —
    DENY нет по IR-01/IR-07 (задача 0.2)."""
    out = _run_validate(
        "A\tservices/video/app/videos.py\nA\tcontracts/openapi-video.json\n")
    assert "J58: правило IR-" not in out


def test_p20_cli_clean_head_no_deny():
    """TC-P20-009: прогон на чистом HEAD (fallback git-диффа, tasks 0.1/0.2) —
    в выводе нет J58-DENY (контракт search в диффе волны триггеров не дает)."""
    out = _run_validate(None)
    assert "J58: правило IR-" not in out
