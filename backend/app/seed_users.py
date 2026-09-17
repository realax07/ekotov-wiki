"""Seed-скрипт заведения пользователей (tasks.md 1.3, NFR-4/NFR-7).

Заведение учеток владельца и жены при развертывании: логины фиксированы
(owner, wife — плейсхолдеры), пароли Заказчик вводит интерактивно при запуске
— в репозиторий и в отчет реальные пароли не попадают (NFR-5, NFR-7).

Запуск (из каталога backend/, DB_PATH и SECRET_KEY — из окружения, как у
приложения; локально: `DB_PATH=/tmp/app.db SECRET_KEY=x python -m app.seed_users`).

Хеширование — bcrypt (hashpw/checkpw, sdd.md: «bcrypt или argon2»): стандарт,
минимальная поверхность, хеш-строка вида `$2b$12$...` хранится в users.password_hash.

Идемпотентность: уже существующий логин — сообщение и пропуск (не crash, не дубль);
повторный запуск безопасен.
"""

import getpass
import sqlite3
import sys

import bcrypt

from app.db import get_connection, init_db

# Логины-плейсхолдеры (sdd.md: «регистрации нет: 2 учетки заводятся seed'ом»,
# NFR-4: ровно 2 пользователя — владелец и жена).
USERS = [
    ("owner", "владелец"),
    ("wife", "жена"),
]


def hash_password(password: str) -> str:
    """Открытый пароль -> bcrypt-хеш (не хранится и не логируется)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def read_password(login: str) -> str:
    """Пароль с терминала без эха (getpass), с повтором для защиты от опечатки."""
    prompt = f"Пароль для '{login}': "
    while True:
        password = getpass.getpass(prompt)
        if not password:
            print("  Пароль не может быть пустым, повторите ввод.")
            continue
        repeat = getpass.getpass(f"Повторите пароль для '{login}': ")
        if password != repeat:
            print("  Пароли не совпадают, повторите ввод.")
            continue
        return password


def seed_user(login: str, description: str, password: str) -> str:
    """Создает пользователя; существующий логин не трогает. Возвращает статус."""
    conn = get_connection()
    try:
        try:
            conn.execute(
                "INSERT INTO users (login, password_hash) VALUES (?, ?)",
                (login, hash_password(password)),
            )
            conn.commit()
            return "created"
        except sqlite3.IntegrityError:
            return "exists"
    finally:
        conn.close()


def main() -> int:
    print(f"Заведение пользователей (логины фиксированы: {', '.join(u[0] for u in USERS)}).")
    for login, description in USERS:
        password = read_password(login)
        status = seed_user(login, description, password)
        if status == "created":
            print(f"  Пользователь '{login}' ({description}) создан.")
        else:
            print(f"  Пользователь '{login}' уже существует — пропущен (не изменен).")
    return 0


if __name__ == "__main__":
    init_db()  # схема должна существовать; идемпотентно (задача 1.2)
    sys.exit(main())
