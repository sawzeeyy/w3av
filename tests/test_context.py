import pytest
import tempfile
import os
import json

from sawari.core.context import (
    parse_context_input,
    populate_symbol_tables,
    should_skip_pass1,
    should_use_file_value,
    validate_policy,
    ContextPolicy
)

"""
Tests for context parsing and policy handling.
"""


class TestParseContextInput:
    """Tests for parse_context_input function."""

    def test_parse_json_string(self):
        """Should parse valid JSON string."""
        input_str = '{"BASE_URL":"https://api.example.com","CDN":"https://cdn.com"}'
        result = parse_context_input(input_str)
        assert result == {
            "BASE_URL": "https://api.example.com",
            "CDN": "https://cdn.com"
        }

    def test_parse_key_value_comma_separated(self):
        """Should parse comma-separated KEY=VALUE pairs."""
        input_str = 'BASE_URL=https://api.example.com,CDN=https://cdn.com'
        result = parse_context_input(input_str)
        assert result == {
            "BASE_URL": "https://api.example.com",
            "CDN": "https://cdn.com"
        }

    def test_parse_key_value_space_separated(self):
        """Should parse space-separated KEY=VALUE pairs."""
        input_str = 'BASE_URL=https://api.example.com CDN=https://cdn.com'
        result = parse_context_input(input_str)
        assert result == {
            "BASE_URL": "https://api.example.com",
            "CDN": "https://cdn.com"
        }

    def test_parse_single_key_value(self):
        """Should parse single KEY=VALUE pair."""
        input_str = 'BASE_URL=https://api.example.com'
        result = parse_context_input(input_str)
        assert result == {"BASE_URL": "https://api.example.com"}

    def test_parse_json_file(self):
        """Should read and parse JSON from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"BASE_URL": "https://api.example.com"}, f)
            temp_file = f.name

        try:
            result = parse_context_input(temp_file)
            assert result == {"BASE_URL": "https://api.example.com"}
        finally:
            os.unlink(temp_file)

    def test_parse_nested_json(self):
        """Should parse nested JSON objects."""
        input_str = '{"config":{"api":{"base":"https://api.example.com"}}}'
        result = parse_context_input(input_str)
        assert result == {
            "config": {
                "api": {
                    "base": "https://api.example.com"
                }
            }
        }

    def test_empty_input_raises_error(self):
        """Should raise ValueError for empty input."""
        with pytest.raises(ValueError, match="Context input cannot be empty"):
            parse_context_input("")

    def test_whitespace_only_raises_error(self):
        """Should raise ValueError for whitespace-only input."""
        with pytest.raises(ValueError, match="Context input cannot be empty"):
            parse_context_input("   ")

    def test_invalid_key_value_format_raises_error(self):
        """Should raise ValueError for invalid KEY=VALUE format."""
        with pytest.raises(ValueError, match="Invalid context format"):
            parse_context_input("INVALID_FORMAT")

    def test_json_array_raises_error(self):
        """Should raise ValueError for JSON array (must be object)."""
        with pytest.raises(ValueError, match="must be an object"):
            parse_context_input('["value1", "value2"]')

    def test_invalid_json_file_raises_error(self):
        """Should raise ValueError for file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')
            temp_file = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON in context file"):
                parse_context_input(temp_file)
        finally:
            os.unlink(temp_file)

    def test_empty_key_raises_error(self):
        """Should raise ValueError for empty key in KEY=VALUE."""
        with pytest.raises(ValueError, match="Empty key"):
            parse_context_input("=value")


class TestPopulateSymbolTables:
    """Tests for populate_symbol_tables function."""

    def test_populate_scalar_values(self):
        """Should populate symbol_table with scalar values."""
        context = {
            "BASE_URL": "https://api.example.com",
            "VERSION": "v2"
        }
        symbol_table = {}
        object_table = {}
        array_table = {}

        populate_symbol_tables(context, symbol_table, object_table, array_table)

        assert symbol_table == {
            "BASE_URL": ["https://api.example.com"],
            "VERSION": ["v2"]
        }
        assert object_table == {}
        assert array_table == {}

    def test_populate_nested_objects(self):
        """Should populate object_table with nested objects."""
        context = {
            "config": {
                "api": {
                    "base": "https://api.example.com"
                }
            }
        }
        symbol_table = {}
        object_table = {}
        array_table = {}

        populate_symbol_tables(context, symbol_table, object_table, array_table)

        assert symbol_table == {}
        assert "config" in object_table
        assert object_table["config"]["api"]["base"] == "https://api.example.com"
        assert array_table == {}

    def test_populate_arrays(self):
        """Should populate array_table with arrays."""
        context = {
            "urls": ["https://example.com", "https://api.example.com"]
        }
        symbol_table = {}
        object_table = {}
        array_table = {}

        populate_symbol_tables(context, symbol_table, object_table, array_table)

        assert symbol_table == {}
        assert object_table == {}
        assert array_table == {
            "urls": ["https://example.com", "https://api.example.com"]
        }

    def test_populate_mixed_types(self):
        """Should correctly categorize mixed types."""
        context = {
            "BASE_URL": "https://api.example.com",
            "config": {"key": "value"},
            "urls": ["url1", "url2"]
        }
        symbol_table = {}
        object_table = {}
        array_table = {}

        populate_symbol_tables(context, symbol_table, object_table, array_table)

        assert symbol_table == {"BASE_URL": ["https://api.example.com"]}
        assert "config" in object_table
        assert "urls" in array_table

    def test_converts_numbers_to_strings(self):
        """Should convert numeric values to strings."""
        context = {
            "PORT": 8080,
            "TIMEOUT": 30.5,
            "ENABLED": True
        }
        symbol_table = {}
        object_table = {}
        array_table = {}

        populate_symbol_tables(context, symbol_table, object_table, array_table)

        assert symbol_table == {
            "PORT": ["8080"],
            "TIMEOUT": ["30.5"],
            "ENABLED": ["True"]
        }


class TestContextPolicy:
    """Tests for context policy functions."""

    def test_should_skip_pass1_only_policy(self):
        """Should skip Pass 1 for 'only' policy."""
        assert should_skip_pass1(ContextPolicy.ONLY) is True

    def test_should_not_skip_pass1_merge_policy(self):
        """Should not skip Pass 1 for 'merge' policy."""
        assert should_skip_pass1(ContextPolicy.MERGE) is False

    def test_should_not_skip_pass1_override_policy(self):
        """Should not skip Pass 1 for 'override' policy."""
        assert should_skip_pass1(ContextPolicy.OVERRIDE) is False

    def test_should_use_file_value_merge_always(self):
        """Merge policy should always use file value."""
        context = {"BASE_URL": "https://api.example.com"}
        assert should_use_file_value("BASE_URL", context, ContextPolicy.MERGE) is True
        assert should_use_file_value("OTHER", context, ContextPolicy.MERGE) is True

    def test_should_use_file_value_override_only_if_not_in_context(self):
        """Override policy should only use file value if not in context."""
        context = {"BASE_URL": "https://api.example.com"}
        assert should_use_file_value("BASE_URL", context, ContextPolicy.OVERRIDE) is False
        assert should_use_file_value("OTHER", context, ContextPolicy.OVERRIDE) is True

    def test_should_use_file_value_only_never(self):
        """Only policy should never use file value."""
        context = {"BASE_URL": "https://api.example.com"}
        assert should_use_file_value("BASE_URL", context, ContextPolicy.ONLY) is False
        assert should_use_file_value("OTHER", context, ContextPolicy.ONLY) is False

    def test_validate_policy_valid_values(self):
        """Should accept valid policy values."""
        assert validate_policy("merge") == "merge"
        assert validate_policy("override") == "override"
        assert validate_policy("only") == "only"

    def test_validate_policy_invalid_value(self):
        """Should raise ValueError for invalid policy."""
        with pytest.raises(ValueError, match="Invalid context policy"):
            validate_policy("invalid")
