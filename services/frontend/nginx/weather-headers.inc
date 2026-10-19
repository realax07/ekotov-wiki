# Заголовки weather-ответов (change weather-service; design §5).
# Security-заголовки server-уровня (NFR-7) повторяем: add_header внутри
# location наследуется с перекрытием — без повтора в weather-локациях
# пропадут (урок search-headers.inc / images-headers.inc / videos-headers.inc).
add_header X-Service "weather" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
