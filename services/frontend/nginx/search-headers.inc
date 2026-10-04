# Заголовки search-ответов (задача 1.3; spec services «Маршрутизация nginx»:
# заголовок X-Service: search в ответе). add_header внутри location
# наследуется с перекрытием — security-заголовки server-уровня (NFR-7)
# повторяем, иначе в search-локациях пропадут.
add_header X-Service "search" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
