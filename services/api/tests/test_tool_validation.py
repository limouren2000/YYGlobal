import pytest

from app.agent.tools import validate_arguments


def test_number_arguments_accept_int_and_float_but_reject_bool():
    schema = {
        "type": "object",
        "properties": {"gpa": {"type": "number"}, "budget": {"type": "number"}},
        "required": ["gpa", "budget"],
        "additionalProperties": False,
    }

    validate_arguments(schema, {"gpa": 3.8, "budget": 50000})

    with pytest.raises(ValueError, match="gpa 类型应为 number"):
        validate_arguments(schema, {"gpa": True, "budget": 50000})


def test_array_items_are_recursively_validated():
    schema = {
        "type": "object",
        "properties": {"program_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["program_ids"],
        "additionalProperties": False,
    }

    validate_arguments(schema, {"program_ids": ["p1", "p2"]})

    with pytest.raises(ValueError, match=r"program_ids\[1\] 类型应为 string"):
        validate_arguments(schema, {"program_ids": ["p1", 123]})
    with pytest.raises(ValueError, match=r"program_ids\[1\] 类型应为 string"):
        validate_arguments(schema, {"program_ids": ["p1", True]})


def test_required_and_additional_properties_validation_are_preserved():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    }

    with pytest.raises(ValueError, match="缺少必填工具参数"):
        validate_arguments(schema, {})
    with pytest.raises(ValueError, match="包含未声明工具参数"):
        validate_arguments(schema, {"name": "YYGlobal", "unknown": "value"})


def test_nested_object_validation_uses_field_paths():
    schema = {
        "type": "object",
        "properties": {
            "preferences": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
                "additionalProperties": False,
            }
        },
        "required": ["preferences"],
        "additionalProperties": False,
    }

    validate_arguments(schema, {"preferences": {"city": "Singapore"}})

    with pytest.raises(ValueError, match="preferences.city 类型应为 string"):
        validate_arguments(schema, {"preferences": {"city": 123}})
    with pytest.raises(ValueError, match="preferences 包含未声明字段"):
        validate_arguments(schema, {"preferences": {"city": "Singapore", "region": "Asia"}})
