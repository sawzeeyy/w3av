"""
Tests for URL extraction from object and member expressions.

Covers:
- Object property access
- Member expressions (nested objects)
- Subscript/bracket notation access
- window.location behavior
"""

import os
import pytest

from sawari.core.jsparser import parse_javascript
from sawari.modes.urls import get_urls


# Path to test fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'urls')


def parse_file(filename):
    """Helper to parse a JavaScript file from fixtures."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    _, root_node = parse_javascript(content)
    return root_node, len(content.encode('utf8'))


class TestObjectProperties:
    """Test object property access and nested objects."""

    def test_simple_object_properties(self):
        node, file_size = parse_file('object_properties.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Object properties extracted, check components
        assert '/api' in urls
        assert '/v2' in urls
        assert '/users' in urls
        assert '/posts' in urls

    def test_nested_object_properties(self):
        node, file_size = parse_file('object_properties.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Nested properties extracted
        assert '/api' in urls
        assert '/v1' in urls
        assert '/users' in urls
        assert '/data' in urls

    def test_object_property_assignment(self):
        node, file_size = parse_file('object_properties.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Property assignments tracked
        assert '/v3' in urls


class TestMemberExpressions:
    """Test member expression resolution (window.location, nested objects)."""

    def test_window_location_properties(self):
        node, file_size = parse_file('member_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # window.location.origin should resolve to https://FUZZ
        assert any('FUZZ' in url and '/api/users' in url for url in urls)

    def test_nested_member_expressions(self):
        node, file_size = parse_file('member_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Deeply nested object properties
        assert 'https://api.example.com/endpoint' in urls or 'https://api.example.com' in urls


class TestSubscriptExpressions:
    """Test subscript/bracket notation access."""

    def test_string_literal_subscripts(self):
        node, file_size = parse_file('subscript_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # obj["api-url"] should resolve
        assert any('https://api.example.com' in url for url in urls)
        assert any('/api' in url for url in urls)

    def test_variable_subscripts(self):
        node, file_size = parse_file('subscript_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # obj[variable] should resolve if variable value is known
        assert any('api.example.com' in url or '/api' in url for url in urls)

    def test_nested_subscripts(self):
        node, file_size = parse_file('subscript_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # config["endpoints"]["v1"] should resolve
        assert any('/api/v1' in url or '/api/v2' in url for url in urls)


class TestWindowLocation:
    """Test window.location specific behavior."""

    def test_window_location_defaults(self):
        node, file_size = parse_file('window_location.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # window.location.origin defaults to https://FUZZ
        assert any('https://FUZZ' in url for url in urls)

    def test_location_without_window(self):
        node, file_size = parse_file('window_location.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # location.origin (without window.) should also work and resolve to https://FUZZ
        assert any('https://FUZZ' in url for url in urls)

    def test_location_concatenation(self):
        node, file_size = parse_file('window_location.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Concatenation with location properties
        assert any('/api/v1' in url for url in urls)
        assert any('/search' in url for url in urls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
