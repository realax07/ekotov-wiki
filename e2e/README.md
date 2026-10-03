# e2e — сквозной сьют против compose-стенда (P11 ЭТАП 1, tasks 1.5)

Change `add-containerization` (FR-69, design §5): playwright-сьют проверяет то,
что web-стенд на `http.server` не эмулирует — поведение nginx-контейнера
(заголовки кеша статики, gzip, security-заголовки) плюс смоук авторизации и
доски против полного стек `app` + `nginx` из `deploy/compose.test.yaml`.

## Стенд

Поднимается `deploy/compose.test.yaml` (зона devops):

```bash
docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build
```

- nginx публикует `8443:10443`, TLS self-signed (клиенты e2e игнорируют
  валидацию сертификата);
- tmp-том БД — данные стенда исчезают при `down` (NFR-10);
- seeded-юзер: `owner` / пароль из `EKOTOV_WIKI_E2E_PASSWORD`
  (дефолт `QaOwner_Pass_1!` — тестовое значение кейсов, NFR-7).
  Seed выполняется вручную после подъема стенда
  (`docker compose -p wiki-test exec app python -m app.seed_users`,
  интерактивный ввод паролей — getpass; см. ниже).

## Запуск (одинаково локально и в CI)

```bash
# 1. Поднять стенд и дождаться healthy:
docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build
# 2. Схема БД (tmpfs пуста при первом up; init_db идемпотентен):
docker compose -p wiki-test exec app python -m app.db
# 3. Seed (owner/wife) — интерактивный ввод паролей (getpass, логины фиксированы;
#    seed_users.py не имеет --non-interactive — пароли вводятся с терминала):
docker compose -p wiki-test exec app python -m app.seed_users

# 4. Сьют (из корня клона; venv проекта, playwright-браузеры ставятся один раз):
pip install -r backend/requirements.txt
python -m playwright install chromium
EKOTOV_WIKI_E2E_BASE_URL=https://127.0.0.1:8443 \
  python -m pytest e2e -v

# 5. Останов:
docker compose -p wiki-test down   # tmpfs-данные исчезают
```

Без `EKOTOV_WIKI_E2E_BASE_URL` сьют пропускается (skip) — скоуп e2e осмыслен
только против стенда.

## CI

Job `e2e` в `.github/workflows/flow.yml` (tasks 1.7) гоняет этот же сьют на
каждый PR: поднимает `compose.test.yaml`, заводит seed-юзера, запускает pytest.

## Границы

- Прод-смоук НЕ заменяется: RUNBOOK §4.4 + `scripts/smoke_static.py` проверяют
  живой TLS и конфиг хоста, которых в стенде нет (design §5).
- Логин-флоу детально покрывается web-сьютом (`tests/web`, локальный стенд);
  здесь — смоук: вход seeded-юзера, доска отрисована, статика отдается nginx'ом.
