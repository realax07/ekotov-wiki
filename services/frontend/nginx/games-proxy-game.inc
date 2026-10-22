# Прокси game-portal (P26) — СТРАНИЦЫ ИГР /games/<id>/… БЕЗ вырезания
# префикса (фикс БАГ-5, code-reviews/chore-p26-games/review-002.md).
#
# Проблема: server.mjs роутит игровые пути НАТИВНО (regex
# ^\/games\/([^/]+)(\/.*)?$) и сам отдает файлы из папки игры —
# вырезание префикса (games-proxy.inc) превращало /games/vice/ в /vice/
# → «Не найдено» 404, игры из хаба не открывались.
#
# Здесь префикс УХОДИТ КАК ЕСТЬ: proxy_pass собирает URL из
# $request_uri (исходный URI с аргументами, без рерайта). Относительные
# ассеты страниц игр (style.css, app.js) браузер резолвит в
# /games/<id>/style.css → попадают в ЭТОТ ЖЕ regex-локейшн
# (ekotov-wiki.conf: ^/games/(munchkin|vice|poker|tanks|durak)(/|$)) →
# бэкенд раздает их из папки игры по match[2]. sub_filter НЕ нужен:
# страницы игр используют относительные пути (абсолютных href="/…" нет),
# а переписывание здесь только навредило бы.
#
# Переменная $upstream_games — паритет games-proxy.inc: proxy_pass с
# переменной переразрешается через resolver server-блока (127.0.0.11),
# старт nginx без game-portal безопасен.
set $upstream_games http://game-portal:8080;

proxy_pass $upstream_games$request_uri;

proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
