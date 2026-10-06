# Заголовки images-ответов (задача 1.4 add-gallery-service; design §1/§4).
# Security-заголовки server-уровня (NFR-7) повторяем: add_header внутри
# location наследуется с перекрытием — без повтора в images-локациях
# пропадут (урок search-headers.inc, задача 1.3).
add_header X-Service "images" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
