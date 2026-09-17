"""Конфигурация приложения — только из переменных окружения.

Секреты и пути (SECRET_KEY, DB_PATH) дефолтов в коде не имеют:
отсутствующая переменная = ошибка старта с понятным сообщением (NFR-5, правило 3 dev-промпта).
Загрузка .env — средствами uvicorn (`uvicorn --env-file .env`) или systemd EnvironmentFile (задача 1.4).
"""

import os


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Обязательная переменная окружения {name} не задана "
            f"(см. .env.example; локально: uvicorn --env-file .env)"
        )
    return value


class Settings:
    def __init__(self) -> None:
        self.db_path: str = _require("DB_PATH")
        self.secret_key: str = _require("SECRET_KEY")


settings = Settings()
