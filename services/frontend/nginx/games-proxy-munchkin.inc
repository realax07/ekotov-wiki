# Прокси СТАНДАЛОН-манчкина (2026-11-16, решение Заказчика «вынести манчкина
# отдельным сервисом»): контейнер munchkin на сети ekotov-wiki-par_default,
# node server.mjs (HOST=0.0.0.0 PORT=8080), БЕЗ published-портов — трафик
# только из сети через nginx. СО СРЕЗАННЫМ ПРЕФИКСОМ (games-proxy.inc-стиль):
# сервис отдает корень / и /api/lobbies сам; браузер видит /games/munchkin/… —
# network.js вычисляет базу API из location.pathname (фикс f6713c4),
# поэтому оба режима (прямой и через прокси) работают.
#
# Хаб game-portal после переключения держит рефлексный дубль манчкина
# (порт 4387, без трафика) — лобби ЕДИНЫЕ на стендалоне; дубль гасится
# пересозданием game-portal без munchkin в старт-цикле (по желанию).
#
# $upstream_munchkin — анти-stale-DNS паритет games-proxy.inc (resolver
# 127.0.0.11 в server-блоке).
set $upstream_munchkin http://munchkin:8080;
