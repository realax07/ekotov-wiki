# Заголовки video-ответов (задача 1.4 video-hosting; design §1/§6).
# Security-заголовки server-уровня (NFR-7) повторяем: add_header внутри
# location наследуется с перекрытием — без повтора в video-локациях
# пропадут (урок search-headers.inc / images-headers.inc).
add_header X-Service "video" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
