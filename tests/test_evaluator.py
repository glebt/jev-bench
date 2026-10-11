from pathlib import Path

from eval import build_prompt, discover_schemas, load_schema, validate_json


class TestSchemaLoading:
    def test_load_simple_schema(self):
        schema = load_schema(Path("schemas/simple.json"))
        assert schema["title"] == "Simple Person"
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert schema["required"] == ["name", "age", "email"]

    def test_load_nested_schema(self):
        schema = load_schema(Path("schemas/nested.json"))
        assert schema["title"] == "Company with Employees"
        assert "company" in schema["properties"]
        assert "employees" in schema["properties"]

    def test_load_complex_schema(self):
        schema = load_schema(Path("schemas/complex.json"))
        assert schema["title"] == "E-Commerce Order"
        assert "order_id" in schema["properties"]
        assert "customer" in schema["properties"]
        assert "items" in schema["properties"]


class TestPromptBuilding:
    def test_build_prompt_contains_schema(self):
        schema = load_schema(Path("schemas/simple.json"))
        prompt = build_prompt(schema, "test")
        assert "Simple Person" in prompt
        assert "name" in prompt
        assert "JSON Output:" in prompt


class TestSchemaDiscovery:
    def test_discover_schemas(self):
        test_cases = discover_schemas()
        assert len(test_cases) == 3
        names = {tc.name for tc in test_cases}
        assert names == {"simple", "nested", "complex"}


class TestValidation:
    def test_valid_json_passes(self):
        schema = load_schema(Path("schemas/simple.json"))
        valid_json = '{"name": "John", "age": 30, "email": "john@example.com"}'
        is_valid, errors, parsed = validate_json(valid_json, schema)
        assert is_valid is True
        assert errors == []
        assert parsed["name"] == "John"

    def test_invalid_json_fails(self):
        schema = load_schema(Path("schemas/simple.json"))
        invalid_json = '{"name": "John", "age": "thirty", "email": "john@example.com"}'
        is_valid, errors, _parsed = validate_json(invalid_json, schema)
        assert is_valid is False
        assert len(errors) > 0

    def test_missing_required_field_fails(self):
        schema = load_schema(Path("schemas/simple.json"))
        missing_field = '{"name": "John", "age": 30}'
        is_valid, errors, _parsed = validate_json(missing_field, schema)
        assert is_valid is False
        assert "email" in str(errors)

    def test_malformed_json_fails(self):
        schema = load_schema(Path("schemas/simple.json"))
        malformed = '{"name": "John", "age": 30,}'
        is_valid, errors, _parsed = validate_json(malformed, schema)
        assert is_valid is False
        assert "Invalid JSON" in str(errors)

