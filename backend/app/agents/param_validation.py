"""Minimal, scope-limited JSON Schema validator for query_templates.params_schema.

Covers exactly what the seeded templates use: type, minimum, maximum,
minLength, enum, required, additionalProperties. Not a general JSON
Schema implementation — if a future template needs richer features
(patterns, formats, oneOf, ...), reach for the `jsonschema` package
instead of extending this by hand.
"""
from typing import Any

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def validate_params(params: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Returns human-readable error strings; empty list means valid."""
    errors: list[str] = []
    properties: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    additional_ok: bool = schema.get("additionalProperties", True)

    for name in required:
        if name not in params:
            errors.append(f"missing required parameter '{name}'")

    if not additional_ok:
        for name in params:
            if name not in properties:
                errors.append(f"unexpected parameter '{name}'")

    for name, value in params.items():
        prop = properties.get(name)
        if prop is None:
            continue  # already reported above if additionalProperties disallows it

        expected_type = prop.get("type")
        check = _TYPE_CHECKS.get(expected_type)
        if check is not None and not check(value):
            errors.append(f"parameter '{name}' must be of type {expected_type}")
            continue  # further checks assume the right type

        if expected_type in ("integer", "number"):
            minimum = prop.get("minimum")
            maximum = prop.get("maximum")
            if minimum is not None and value < minimum:
                errors.append(f"parameter '{name}' must be >= {minimum}")
            if maximum is not None and value > maximum:
                errors.append(f"parameter '{name}' must be <= {maximum}")

        if expected_type == "string":
            min_length = prop.get("minLength")
            if min_length is not None and len(value) < min_length:
                errors.append(f"parameter '{name}' must be at least {min_length} characters")

        enum = prop.get("enum")
        if enum is not None and value not in enum:
            errors.append(f"parameter '{name}' must be one of {enum}")

    return errors
