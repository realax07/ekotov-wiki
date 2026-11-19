# Прокси СТАНДАЛОН-манчкина в ОТДЕЛЬНОМ разделе сайта (2026-11-16, решение
# Заказчика «отдельный раздел + отдельный uri и порт»; репо realax07/manchkin):
# контейнер manchkin на сети ekotov-wiki-par_default, node server.mjs
# (HOST=0.0.0.0 PORT=8382), БЕЗ published-портов — трафик только из сети.
# СО СРЕЗАННЫМ ПРЕФИКСОМ (стиль games-proxy.inc): сервис отдает корень /
# и /api/lobbies сам. /games/munchkin/ (версия в составе game-portal) —
# отдельное развертывание с СВОИМ пулом лобби (lobbies in-memory).
#
# $upstream_manchkin_site — анти-stale-DNS паритет games-proxy.inc.
set $upstream_manchkin_site http://manchkin:8382;
