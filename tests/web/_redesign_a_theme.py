"""Общий хелпер визуальных сьютов направления A (redesign-ui-a).

Тема: headless chromium имеет prefers-color-scheme: light, анти-FOUC
инициализатор включает светлую тему. Визуальные ассерты канона A — на dark:
пишем theme=dark в localStorage (явный выбор приоритетен, ОВ-2) и снимаем
атрибут; NFR-41 «обе темы» проверяется в test_redesign_console TC-001.
"""


def force_dark_theme(request):
    for name in ("logged_in_page", "page"):
        if name in request.fixturenames:
            p = request.getfixturevalue(name)
            p.evaluate(
                "() => { try { localStorage.setItem('theme', 'dark'); } catch (e) {}"
                " document.documentElement.removeAttribute('data-theme'); }"
            )
            # live-переход цвета (--speed-fast 160ms) при смене темы на уже
            # загруженной странице — ждем конечный кадр, иначе ассерты ловят
            # промежуточный цвет (урок test_qa21_netdata: rgb 80% перехода).
            p.wait_for_timeout(250)
            return
