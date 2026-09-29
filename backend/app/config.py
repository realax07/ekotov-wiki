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
    # AVATARS_DIR — необязательная переменная окружения: дефолт — продовый
    # путь (design.md пакета §2, blocker C-1 ревью review-001, ОГР-16);
    # в тестах/локальной разработке переопределяется на tmp-каталог.
    _AVATARS_DIR_DEFAULT = "/var/lib/ekotov-wiki/avatars/"

    def __init__(self) -> None:
        self.db_path: str = _require("DB_PATH")
        self.secret_key: str = _require("SECRET_KEY")
        self.avatars_dir: str = os.environ.get("AVATARS_DIR", self._AVATARS_DIR_DEFAULT)


settings = Settings()
