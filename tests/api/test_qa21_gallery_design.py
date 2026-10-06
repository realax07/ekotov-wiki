"""QA 2.1 add-gallery-service — design_validator (TC-GAL-122, статическая часть).

Проверяет токенную дисциплину дельты gallery (design §0 п.4, FR-86): значения
берутся из CSS-переменных app.css :root (paper/ink/clay, Georgia display,
радиусы 6/10px, focus-ring), НЕ зашиты литералами в gallery.css/gallery.js;
мокапы 1.1 существуют (design/gallery-grid.html, gallery-lightbox.html,
gallery-upload.html).

Динамическая часть (Computed Styles живой страницы, hover/focus-состояния,
сверка компоновки построчно) — SKIPPED: сетка/лайтбокс не отрисовываются из-за
BUG-008 (gallery.js SyntaxError, тест-модель/bugs/); вердикт design_validator —
ПОСЛЕ фикса BUG-008 (переводится в автопрогон этим же файлом + ручной проход
по мокапам). Итоговый вердикт approve/return — зона СА (review-NNN-design),
QA фиксирует факты.
"""

import os
import re

import pytest

pytestmark = [pytest.mark.api, pytest.mark.must]

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tc_gal_122_tokens_from_css_vars_not_hardcoded():
    """TC-GAL-122 (шаг 2, токены V3 «Бумага»): gallery.css использует только
    var(--token) — 0 hex/rgb-литералов цветов; gallery.js — 0 цветовых
    литералов; токены paper/ink/clay/Georgia/radius/focus-ring определены
    в app.css :root."""
    css = open(os.path.join(REPO, "frontend/static/css/gallery.css")).read()
    # Цветовые литералы в gallery.css (вне комментариев): hex / rgb() / rgba().
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hex_literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    rgb_literals = re.findall(r"rgba?\([^)]*\)", body)
    assert not hex_literals, f"gallery.css: зашиты hex-цвета: {hex_literals[:5]}"
    # rgba(): в цветовой системе V3 полупрозрачные тени/оверлеи выражаются
    # rgba() и в эталонных файлах (app.css: --shadow-modal/--focus-ring,
    # board.css) — допустимый класс (заводские rgba НЕ новые цвета, а alpha
    # вариантов paper/ink). Сверяем с эталонным набором значений app.css:
    # допустимы rgba от 61,54,48 (ink-900) и 255,253,249 (paper) — те же
    # базовые цвета, что в токенах; иные base-цвета = отход от токенов.
    allowed_bases = {("61", "54", "48"), ("255", "253", "249"), ("168", "67", "44")}
    for m in rgb_literals:
        parts = re.findall(r"[\d.]+", m)
        base = tuple(p.split(".")[0] for p in parts[:3])
        assert base in allowed_bases, (
            f"gallery.css: rgba вне токенных базовых цветов V3: {m} (base={base})"
        )
    # Токены используются.
    assert len(re.findall(r"var\(--", body)) >= 50, "токены почти не используются?"

    js = open(os.path.join(REPO, "frontend/static/js/gallery.js")).read()
    js_hex = re.findall(r"#[0-9a-fA-F]{6}\b", js)
    js_rgb = re.findall(r"rgba?\(", js)
    assert not js_hex and not js_rgb, f"gallery.js: цветовые литералы {js_hex[:3]}{js_rgb[:3]}"

    root = open(os.path.join(REPO, "frontend/static/css/app.css")).read()
    for token in ("--font-family-display: Georgia", "--radius-field: 6px",
                  "--radius-card: 10px", "--focus-ring:"):
        assert token in root, f"app.css :root: нет {token}"

    # Мокапы 1.1 на месте (сверка компоновки — после фикса BUG-008).
    for mock in ("gallery-grid.html", "gallery-lightbox.html", "gallery-upload.html"):
        assert os.path.isfile(os.path.join(REPO, "design", mock)), mock


def test_tc_gal_122_live_computed_styles_and_states():
    """TC-GAL-122 (шаги 1, 3–6): Computed Styles живой страницы (токены не
    хардкод), hover/focus-visible, подсветка «мой голос», ошибки 422, пункт
    сайдбара — ТРЕБУЕТ отрисованную сетку/лайтбокс."""
    pytest.skip(
        "BUG-008: gallery.js SyntaxError — /gallery не отрисовывается;"
        " динамический design_validator после фикса (BUG-008 блокер)"
    )
