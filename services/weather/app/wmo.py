"""Таблицы преобразований weather-сервиса (design §3).

- WMO weather_code → (русское описание, ключ иконки). Иконки рисует
  фронтенд (inline-SVG по ключу); в API-контракте (design §6) ключа нет —
  только code/description, фронтенд держит СВОЮ компактную карту
  code→иконка (контракт §6 не расширяется).
- Румбы: градусы (0–360) → русские румбы С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ (шаг 45°).
"""

# WMO weather interpretation codes (WW) — открытая таблица Open-Meteo
# (документация провайдера). Ключ иконки — подмножество
# {sun, sun-cloud, cloud, fog, rain, snow, storm}.
WMO_DESCRIPTIONS: dict[int, tuple[str, str]] = {
    0: ("Ясно", "sun"),
    1: ("Преимущественно ясно", "sun-cloud"),
    2: ("Переменная облачность", "sun-cloud"),
    3: ("Пасмурно", "cloud"),
    45: ("Туман", "fog"),
    48: ("Туман, изморозь", "fog"),
    51: ("Лёгкая морось", "rain"),
    53: ("Морось", "rain"),
    55: ("Сильная морось", "rain"),
    56: ("Ледяная морось", "rain"),
    57: ("Сильная ледяная морось", "rain"),
    61: ("Небольшой дождь", "rain"),
    63: ("Дождь", "rain"),
    65: ("Сильный дождь", "rain"),
    66: ("Ледяной дождь", "rain"),
    67: ("Сильный ледяной дождь", "rain"),
    71: ("Небольшой снег", "snow"),
    73: ("Снег", "snow"),
    75: ("Сильный снег", "snow"),
    77: ("Снежные зёрна", "snow"),
    80: ("Небольшой ливень", "rain"),
    81: ("Ливень", "rain"),
    82: ("Сильный ливень", "rain"),
    85: ("Небольшой снегопад", "snow"),
    86: ("Сильный снегопад", "snow"),
    95: ("Гроза", "storm"),
    96: ("Гроза с градом", "storm"),
    99: ("Сильная гроза с градом", "storm"),
}

# Дефолт для неизвестного кода — «Пасмурно»/облако (не ломает карточку).
WMO_DEFAULT = ("Пасмурно", "cloud")

# Русские румбы по 45°, начиная с севера по часовой стрелке.
WIND_RUMBS = ("С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ")


def describe(code) -> tuple[str, str]:
    """(описание, ключ иконки) по WMO-коду; None/неизвестный — дефолт."""
    if code is None:
        return WMO_DEFAULT
    try:
        return WMO_DESCRIPTIONS.get(int(code), WMO_DEFAULT)
    except (TypeError, ValueError):
        return WMO_DEFAULT


def rumb(degrees) -> str | None:
    """Русский румб по градусам (45°-сектора, округление к ближайшему).

    None/нечисло → None (фронтенд покажет прочерк — деградация метрики).
    """
    if degrees is None:
        return None
    try:
        value = float(degrees)
    except (TypeError, ValueError):
        return None
    index = int(round(value / 45.0)) % 8
    return WIND_RUMBS[index]
