"""Пакет weather-сервиса ekotov-wiki (change weather-service, P18 «Погода»).

Структура — паритет services/video/app: db (сессии), middleware (сессионный),
provider (клиент Open-Meteo), wmo (таблицы WMO/румбов), cache (кэш-файл в
томе), routes (GET /api/weather), main (точка входа). БД у сервиса НЕТ
(граница PLAN): единственное состояние — кэш-файл в томе weather-cache;
SELECT sessions — чтение общей БД ядра (ro-маунт, паритет search).
"""
