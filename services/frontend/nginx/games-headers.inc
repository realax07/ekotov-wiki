# Заголовки ответов game-portal (P26). Security-заголовки server-уровня
# (NFR-7) повторяем: add_header внутри location наследуется с перекрытием —
# без повтора в /games-локациях пропадут (урок search-headers.inc /
# weather-headers.inc / videos-headers.inc).
add_header X-Service "games" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options SAMEORIGIN always; # хаб фреймит игры сам (iframe #game-frame), DENY запрещает и same-origin
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
