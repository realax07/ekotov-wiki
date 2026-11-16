"""Схемная валидация по замороженному контракту (add-p20-contracts, волна 5,
задача 5.2; design add-p20-contracts §3, FR-138, ОВ-1б).

Хелпер — КОПИЯ одного файла для всех 4 сервисов (design §3): отличается
только имя контракта в CONTRACT_PATH. Загружает
contracts/openapi-<svc>.json из корня репозитория
(services/<svc>/tests/x.py → parents[3] = корень), валидирует
Draft7Validator'ом с резолвом $ref на корень замороженного файла.
Валидаторы кэшируются по канонической форме схемы — построение
происходит один раз на схему (NFR-46: стоимость валидации словаря по
готовой схеме — микросекунды).

validate_response(path, method, status, payload):
- маршрут/метод, отсутствующие в спеке, — AssertionError (это и есть
  ловушка дрейфа на уровне тестов; второй уровень защиты пакета:
  гейт IR-08…IR-12 — поверхность, схемная валидация — payloads);
- статус, не описанный для маршрута, — AssertionError;
- у ответа нет application/json-схемы (или схема пустая `{}` —
  «что угодно») — payload возвращается без изменений, валидировать
  нечего (бинарные отдачи file/preview);
- payload не соответствует схеме — AssertionError с маршрутом и
  несовпавшим полем (сценарий «Дрейф поля ответа ловится тестом»).

Трассировка: FR-138, ОВ-1б, NFR-46.
"""

import json
from pathlib import Path

from jsonschema import Draft7Validator

# Замороженный контракт — из корня репозитория.
CONTRACT_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "openapi-video.json"
)

CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

# Кэш валидаторов по канонической форме схемы ответа (схемы — одинаковые
# объекты CONTRACT'а на каждый вызов; валидатор строится один раз).
_VALIDATORS: dict[str, Draft7Validator] = {}

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _json_path(error) -> str:
    """JSON-путь несовпавшего фрагмента (для сообщения о дрейфе)."""
    parts = [str(p) for p in error.absolute_path]
    if not parts:
        return "$"
    return "$" + "".join(
        f".{p}" if p.isidentifier() else f"[{p}]" for p in parts
    )


def _dereference(schema):
    """Резолв локальных $ref ("#/components/schemas/X") на корень
    замороженного файла. В контрактах пакета $ref — только внутренние
    JSON-указатели на components.schemas (export-скрипты); рекурсивная
    подстановка дает самодостаточную схему для Draft7Validator.
    """
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            node = CONTRACT
            for part in ref[2:].split("/"):
                node = node[part.replace("~1", "/").replace("~0", "~")]
            return _dereference(node)
        return {k: _dereference(v) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_dereference(item) for item in schema]
    return schema


def _validator_for(schema) -> Draft7Validator:
    """Draft7Validator схемы ответа с $ref-резолвом на корень контракта."""
    resolved = _dereference(schema)
    key = json.dumps(resolved, sort_keys=True)
    validator = _VALIDATORS.get(key)
    if validator is None:
        validator = Draft7Validator(resolved)
        _VALIDATORS[key] = validator
    return validator


def validate_response(path: str, method: str, status: int, payload):
    """Валидация payload ответа по схеме из замороженного контракта.

    Несоответствие — AssertionError с маршрутом и несовпавшим полем.
    """
    method = method.lower()
    assert method in _HTTP_METHODS, f"не HTTP-метод: {method!r}"
    op = CONTRACT.get("paths", {}).get(path, {}).get(method)
    if op is None:
        raise AssertionError(
            f"{method.upper()} {path}: маршрут отсутствует в контракте "
            f"({CONTRACT_PATH.name}) — дрейф поверхности?"
        )
    responses = op.get("responses", {})
    response = responses.get(str(status))
    if response is None:
        raise AssertionError(
            f"{method.upper()} {path}: статус {status} не описан в "
            f"контракте ({sorted(responses)}) — дрейф статусов?"
        )
    media = (response.get("content") or {}).get("application/json")
    schema = (media or {}).get("schema")
    if not schema:
        return payload  # схемы нет (пустая `{}`) — валидировать нечего
    errors = sorted(_validator_for(schema).iter_errors(payload), key=_json_path)
    if not errors:
        return payload
    err = errors[0]
    raise AssertionError(
        f"{method.upper()} {path} [{status}]: payload не соответствует "
        f"контракту {CONTRACT_PATH.name}; поле {_json_path(err)}: "
        f"{err.message}"
    )
