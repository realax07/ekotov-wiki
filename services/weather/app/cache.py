"""Кэш weather-сервиса: файл в томе weather-cache, TTL 60 минут
(change weather-service, design §4).

- Файл — env EKOTOV_WEATHER_CACHE_PATH, дефолт /data/cache/weather.json
  (compose: том weather-cache:/data/cache). Полезная нагрузка ответа
  (design §6 БЕЗ stale) + fetched_at.
- Атомарная запись: tmp-файл + os.replace — читатели никогда не видят
  полуфайл; fsync перед replace (переживает пересоздание контейнера).
- Чтение: битый JSON/нечитаемый файл → None (кэш «нет»; данные НЕ
  теряются — файл не затирается чтением).
- TTL: 60 минут от fetched_at (ISO с offset; наивное значение трактуется
  как UTC — старые записи не «вечны»).
- Сбой записи (том переполнен/ro) — наверх отдаётся OSError; routes
  логирует и отвечает как при успехе (кэш-файл остается прежним,
  ревью №1 O2). Здесь НЕ глотается, чтобы тесты могли проверить ветку.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("weather.cache")

DEFAULT_CACHE_PATH = "/data/cache/weather.json"

# TTL кэша (spec «Кэш 60 минут»).
CACHE_TTL_SECONDS = 60 * 60


def path() -> str:
    """Путь кэш-файла (env EKOTOV_WEATHER_CACHE_PATH, дефолт design §2)."""
    return os.environ.get("EKOTOV_WEATHER_CACHE_PATH") or DEFAULT_CACHE_PATH


def read() -> dict | None:
    """Кэш-файл как dict или None (нет файла / битый JSON / нечитаем).

    None = «кэша нет» для routes (битый JSON приравнивается к пустому
    кэшу — файл при этом НЕ затирается).
    """
    try:
        with open(path(), encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.info("cache read miss (%s)", exc)
        return None
    return payload if isinstance(payload, dict) else None


def write(payload: dict) -> None:
    """Атомарная запись кэша (tmp + os.replace, fsync)."""
    target = path()
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = f"{target}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)


def is_fresh(payload: dict, now: datetime | None = None) -> bool:
    """Кэш моложе TTL (60 мин)? fetched_at — ISO с offset."""
    try:
        fetched = datetime.fromisoformat(payload["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    age = (current - fetched).total_seconds()
    return 0 <= age < CACHE_TTL_SECONDS
