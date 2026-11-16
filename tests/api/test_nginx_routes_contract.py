"""nginx-контракт маршрутов (add-p20-contracts, волна 6, задача 6.2).

Парсинг location-строк services/frontend/nginx/ekotov-wiki.conf и
прокси-include'ов: ровно ожидаемые location-семейства для каждого
сервиса (пары «= точный + ^~ префикс-слэш»), named-локации деградаций
(@*_down → 503 + Retry-After), внутренний auth-стык /_video_auth и
прокси-цели (имена контейнеров/порты — по proxy_pass-переменным тех же
локаций). Правка маршрутизации без одновременной правки теста/спеки/
карты = красный тест (FR-141, ОВ-8).

Карта: architecture/map.md §8 «Контракты и зависимости».

Трассировка: TC-API-001…TC-API-004 (FR-141; правило 6 flow_check).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_PATH = (
    REPO_ROOT / "services" / "frontend" / "nginx" / "ekotov-wiki.conf"
)
NGINX_DIR = CONF_PATH.parent

# Ожидаемые /api-семейства nginx ровно, per service (design add-p20-contracts §6).
EXPECTED_API_FAMILIES = {
    "search": ("= /api/search", "^~ /api/search/",
               "= /api/suggestions", "^~ /api/suggestions/"),
    "images": ("= /api/images", "^~ /api/images/"),
    "video": ("= /api/videos", "^~ /api/videos/"),
    "weather": ("= /api/weather", "^~ /api/weather/"),
}

# Пары «прокси-переменная → контейнер:порт» per service (proxy_pass
# по переменной — анти-stale-DNS; set в <svc>-proxy.inc / conf).
EXPECTED_UPSTREAMS = {
    "search": ("$upstream_search", "search:8378"),
    "images": ("$upstream_images", "images:8379"),
    "videos": ("$upstream_videos", "video:8380"),
    "weather": ("$upstream_weather", "weather:8381"),
    "app": ("$upstream_app", "app:8377"),
}

# Named-локации деградаций + auth-стык + редирект логина.
EXPECTED_NAMED = ("@search_down", "@images_down", "@videos_down",
                  "@weather_down", "@login_redirect")


def _conf_text() -> str:
    """Текст nginx-конфа контейнера frontend (маршрутизация прода)."""
    return CONF_PATH.read_text(encoding="utf-8")


def _locations(text: str) -> list[tuple[str, str]]:
    """Все location-директивы conf'а: список пар (модификатор, путь).

    Модификатор без модификатора — "" (обычный префикс: /, /static/,
    /images/, /videos/, /games/).
    """
    found = []
    for line in text.splitlines():
        m = re.match(r"\s*location\s+(=|~|~\*|\^~)?\s*(\S+)\s*\{", line)
        if m:
            found.append((m.group(1) or "", m.group(2)))
    return found


def _api_families(locations: list[tuple[str, str]]) -> set[str]:
    """Только /api-семейства в форме «модификатор путь»."""
    return {f"{mod} {path}".strip() for mod, path in locations
            if path.startswith("/api/")}


# --------------------------------------------------------------------------
# Тесты (правило 6 flow_check: TC-API-NNN внутри docstring)
# --------------------------------------------------------------------------


def test_nginx_api_families_exact_per_service():
    """TC-API-001 (FR-141, ОВ-8): в nginx-конфе ровно ожидаемые /api-
    семейства каждого сервиса (пары «= точный + ^~ префикс») и ЛИШНИХ
    /api-локаций нет — правка маршрутизации без правки теста/карты красит."""
    locations = _locations(_conf_text())
    api = _api_families(locations)
    expected = {loc for fams in EXPECTED_API_FAMILIES.values() for loc in fams}
    assert api == expected, (
        "расхождение nginx /api-маршрутизации: лишние "
        f"{sorted(api - expected)}, отсутствуют {sorted(expected - api)}"
    )
    # Ровность per service: каждый expected задан, и ни одно семейство
    # одного сервиса не «переехало» в префикс другого.
    for svc, fams in EXPECTED_API_FAMILIES.items():
        for loc in fams:
            assert loc in api, f"{svc}: нет location «{loc}»"


def test_nginx_degradation_named_locations():
    """TC-API-002 (FR-141): named-локации деградаций @*_down присутствуют,
    дают 503 JSON с Retry-After: 5; /_video_auth (internal auth-стык) и
    /videos/ с auth_request на месте."""
    text = _conf_text()
    named = {path for _, path in _locations(text) if path.startswith("@")}
    for name in EXPECTED_NAMED:
        assert name in named, f"нет named-локации {name}"
    # Деградация: управляемый 503 + Retry-After: 5 в каждой *_down.
    for svc in ("search", "images", "videos", "weather"):
        block = re.search(
            rf"location {re.escape('@' + svc + '_down')}\s*\{{(.*?)\}}",
            text, re.S)
        assert block, f"нет блока @{svc}_down"
        body = block.group(1)
        assert "return 503" in body and 'Retry-After' in body and '"5"' in body
    # Auth-стык video (единственный server-сервер-потребитель, ОГР-30).
    assert "location = /_video_auth {" in text
    assert "auth_request /_video_auth;" in text


def test_nginx_upstream_targets_per_service():
    """TC-API-003 (FR-141): прокси-цели — имена контейнеров и порты по
    proxy_pass-переменным тех же локаций ($upstream_* в <svc>-proxy.inc,
    app — в server-блоке conf'а)."""
    conf = _conf_text()
    for svc, (var, target) in EXPECTED_UPSTREAMS.items():
        if svc == "app":
            source = conf
        else:
            source = (NGINX_DIR / f"{svc}-proxy.inc").read_text(
                encoding="utf-8")
        assert f"set {var} http://{target};" in source, (
            f"{svc}: ожидалось «set {var} http://{target};»"
        )
        assert f"proxy_pass {var};" in source or f"proxy_pass {var}" in source, (
            f"{svc}: proxy_pass не через переменную {var} (анти-stale-DNS)"
        )


def test_nginx_no_extra_api_regex_families():
    """TC-API-004 (FR-141): среди location нет regex-локаций (~/~*) на
    /api/* — API-семейства защищены ^~ (regex-проверки отключены);
    games-страницы — единственные допустимые regex-локации."""
    for mod, path in _locations(_conf_text()):
        if mod in ("~", "~*"):
            assert path.lstrip("^").startswith("/games/"), (
                f"недопустимая regex-локация вне games: {mod} {path}"
            )
        if path.startswith("/api/") and mod in ("", "~", "~*"):
            raise AssertionError(
                f"/api-локация без защиты «= точный или ^~»: {mod or ' '} {path}"
            )
