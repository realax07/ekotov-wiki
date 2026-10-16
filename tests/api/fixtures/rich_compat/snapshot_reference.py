"""Генерация эталонных снепшотов регресс-набора rich_compat (tasks.md 1.7а).

Эталон снимается ДО волны 2 (design §5): «рендер» фиксированного набора
существующих страниц = sanitize_rich(content) — то, что записывается и
рендерится клиенту по существующим правилам. Скрипт запускается один раз
при снятии эталона; тест test_render_compat.py сверяет текущий вывод
с зафиксированными .render.txt.

Запуск (из корня репозитория):
  python3 tests/api/fixtures/rich_compat/snapshot_reference.py --rewrite
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..", "..", "..", "..", "backend")
sys.path.insert(0, BACKEND)

from app.rich_blocks import content_has_blocks, parse  # noqa: E402
from app.sanitize import sanitize_html  # noqa: E402
from app.sanitize_rich import sanitize  # noqa: E402

# case7_mixed содержит валидный rich-блок — не legacy; остальное — legacy-набор
MIXED_CASE = "case7_mixed"


def main() -> None:
    rewrite = "--rewrite" in sys.argv
    names = sorted(
        f[:-len(".content.txt")]
        for f in os.listdir(HERE)
        if f.endswith(".content.txt")
    )
    for name in names:
        with open(os.path.join(HERE, name + ".content.txt"), encoding="utf-8") as fh:
            content = fh.read()
        reference = sanitize(content)
        snapshot = os.path.join(HERE, name + ".render.txt")
        if rewrite or not os.path.exists(snapshot):
            with open(snapshot, "w", encoding="utf-8") as fh:
                fh.write(reference)
            print(f"снят эталон: {name} ({len(reference)} симв.)")
        else:
            with open(snapshot, encoding="utf-8") as fh:
                current = fh.read()
            print(
                f"{name}: {'СОВПАДАЕТ' if current == reference else 'РАСХОЖДЕНИЕ'}"
            )
        if name != MIXED_CASE:
            assert not content_has_blocks(content), f"{name} ожидался legacy"
            assert reference == sanitize_html(content), f"{name}: инвариант M-4"
    print("готово:", len(names), "кейсов")


if __name__ == "__main__":
    main()
