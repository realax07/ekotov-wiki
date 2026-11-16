"""Карта map.md §8 «Контракты и зависимости» — файловые ссылки живы (QA-контур add-p20-contracts).

Трассировка: TC-p20-001 (FR-139, ОГР-30, Д-17, ОВ-9; критерий задачи 6.1).

FR-139 требует «ссылки на контракты-файлы существуют». На dev-волнах это
снималось разовым факт-чеком; здесь — постоянный механический гейт:
§8 содержит имена всех 5 контрактов (4 сервиса + ядро, ОВ-6) и
Retry-After (деградации), а каждый repo-путь, упомянутый в §8,
существует в репо (0 MISSING). Дрейф карты (переименование контракта,
удаление якоря/скрипта экспорта) краснит тест до merge.

Без стенда: чистые файловые ассерты от корня репо.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = REPO_ROOT / "architecture" / "map.md"

SECTION_HEADING = "## 8. Контракты и зависимости"

# Имена всех 5 контрактов в §8: 4 сервиса (FR-134…136, FR-133) + ядро (ОВ-6).
EXPECTED_CONTRACTS = (
    "contracts/openapi-search.json",
    "contracts/openapi-video.json",
    "contracts/openapi-images.json",
    "contracts/openapi-weather.json",
    "contracts/openapi.json",
)

# repo-относительный путь с расширением: в обратных кавычках или без
# (практика карты: `path` и path — оба встречаются). Без пробелов.
PATH_RE = re.compile(
    r"`?((?:contracts|services|scripts|frontend|tests|deploy|backend|"
    r"architecture|openspec)/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)`?"
)


def _section_text() -> str:
    """Текст раздела §8: от заголовка до следующего заголовка '## '."""
    lines = MAP_PATH.read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, l in enumerate(lines) if l.startswith(SECTION_HEADING)
    )
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_map_section8_contracts_named():
    """TC-p20-001 (FR-139, шаг 1–2): §8 содержит имена всех 5 контрактов
    и Retry-After (деградации — часть контракта потребителя)."""
    sec = _section_text()
    for contract in EXPECTED_CONTRACTS:
        assert contract in sec, f"карта §8: нет имени контракта {contract}"
    assert "Retry-After" in sec, "карта §8: нет Retry-After (деградации)"


def test_map_section8_referenced_files_exist():
    """TC-p20-001 (FR-139, шаг 3–4): каждый repo-путь, упомянутый в §8,
    существует (0 MISSING) — карта не ссылается на несуществующие файлы."""
    sec = _section_text()
    candidates = sorted(set(PATH_RE.findall(sec)))
    assert candidates, "карта §8: не извлечен ни один путь — сломался парсер"
    missing = [
        c for c in candidates
        if not os.path.exists(os.path.join(REPO_ROOT, c))
    ]
    assert not missing, f"карта §8 ссылается на несуществующие файлы: {missing}"
