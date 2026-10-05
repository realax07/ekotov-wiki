# Security-заголовки netdata-ответов (задача 1.3; NFR-7). add_header ВНУТРИ
# location наследуется с перекрытием — раз в локации есть свой add_header
# (этот include), server-уровень к ней НЕ применяется и security-набор
# нужно повторить (урок Р6; паритет search-headers.inc, но без X-Service —
# ответ приходит от netdata, а не от search).
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options DENY always;
add_header Referrer-Policy same-origin always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
