"""Роутер GET /api/weather — оркестрация кэша и провайдера
(change weather-service, design §4, §6).

Логика чтения (design §4):
1. кэш свежий (< 60 мин) → отдать из кэша, провайдер НЕ вызывается;
2. кэш истек/нет → запрос провайдеру (§3); успех — обновить кэш,
   stale: false;
3. провайдер недоступен/невалиден → устаревший кэш со stale: true
   (файл не трогается);
4. кэша нет И провайдер недоступен → 503 {"error": "weather_unavailable"}
   (честная ошибка; кэш-файл не создается; nginx intercept off — ответ
   доходит до клиента без подмены, design §5).

Обновление при истекшем TTL — под asyncio.Lock: два одновременных
запроса инициируют одно обновление, второй дожидается и получает
свежий результат (ревью №1 O1; повторная проверка кэша под локом).
Сбой записи кэша ответ не меняет: лог + отдать полученное от
провайдера (ревью №1 O2).
"""

import asyncio
import logging

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app import cache, provider

logger = logging.getLogger("weather.routes")

router = APIRouter()

# Одно обновление за раз (ревью №1 O1). Создание на импорте допустимо:
# asyncio.Lock не привязывается к циклу до первого использования.
_refresh_lock = asyncio.Lock()


def _respond(payload: dict, stale: bool) -> dict:
    """Полезная нагрузка контракта design §6: fetched_at + stale + данные."""
    return {
        "fetched_at": payload["fetched_at"],
        "stale": stale,
        "today": payload["today"],
        "days": payload["days"],
    }


@router.get("/api/weather")
async def get_weather():
    """API погоды (контракт design §6; сессия проверена middleware).

    Без аннотации ответа: успешная ветка возвращает dict (контракт §6),
    деградация — JSONResponse 503; Union-аннотация не валидируется
    Pydantic'ом как response_model (и не нужна — контракт фиксируют тесты).
    """
    ua = provider.user_agent()

    cached = cache.read()
    if cached is not None and cache.is_fresh(cached):
        return _respond(cached, stale=False)

    async with _refresh_lock:
        # Повторная проверка под локом: пока ждали, сосед мог обновить.
        cached = cache.read()
        if cached is not None and cache.is_fresh(cached):
            return _respond(cached, stale=False)

        try:
            data = await provider.fetch(ua)
        except provider.ProviderError as exc:
            logger.warning("provider unavailable: %s", exc)
            if cached is not None:
                # Управляемая деградация: максимум доступного — устаревший
                # кэш с флагом (файл НЕ перезаписывается).
                return _respond(cached, stale=True)
            return JSONResponse(
                status_code=503,
                content={"error": "weather_unavailable"},
                headers={"Retry-After": "60"},
            )

        try:
            cache.write(data)
        except OSError as exc:
            # Сбой записи кэша ответ не меняет (ревью №1 O2).
            logger.warning("cache write failed: %s", exc)

        return _respond(data, stale=False)
