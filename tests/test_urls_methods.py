"""
Tests for URL extraction from JavaScript method calls.

Covers:
- Chained .concat() calls
- Array .join() method
- String .replace() method
- Variable reassignment handling
"""

import os
import pytest

from w3av.core.jsparser import parse_javascript
from w3av.modes.urls import get_urls


# Path to test fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'urls')


def parse_file(filename):
    """Helper to parse a JavaScript file from fixtures."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    _, root_node = parse_javascript(content)
    return root_node, len(content.encode('utf8'))


class TestChainedConcat:
    """Test chained .concat() method calls."""

    def test_simple_chaining(self):
        node, file_size = parse_file('chained_concat.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://api.example.com/v2/users/profile' in urls

    def test_chaining_with_variables(self):
        node, file_size = parse_file('chained_concat.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should resolve variables in chained concat
        assert 'https://FUZZ/api/login' in urls or 'FUZZ/api/login' in urls

    def test_complex_chaining(self):
        node, file_size = parse_file('chained_concat.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://example.com/api/v1/data' in urls


class TestArrayJoin:
    """Test array .join() method."""

    def test_array_join_empty_separator(self):
        node, file_size = parse_file('array_join.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/api/v2/users' in urls

    def test_array_join_with_separator(self):
        node, file_size = parse_file('array_join.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://api.example.com/api/v1/data' in urls

    def test_array_join_with_variables(self):
        node, file_size = parse_file('array_join.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://example.com/api/v2/endpoint' in urls

    def test_array_join_in_concatenation(self):
        node, file_size = parse_file('array_join.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/users/profile/settings' in urls


class TestReplaceMethod:
    """Test string .replace() method."""

    def test_simple_replace(self):
        node, file_size = parse_file('replace_method.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/api/v2/users' in urls

    def test_replace_with_variables(self):
        node, file_size = parse_file('replace_method.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Replace creates template versions
        assert '/users/{id}/profile' in urls or '/user/{userId}' in urls
        assert '/user/456' in urls

    def test_chained_replace(self):
        node, file_size = parse_file('replace_method.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Multiple .replace() calls should work - check template version
        assert any('prod' in url or '{env}' in url for url in urls)


class TestVariableReassignment:
    """Test variable reassignment handling."""

    def test_reassignment_tracking(self):
        node, file_size = parse_file('variable_reassignment.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should track both values - components extracted
        assert '/api/users' in urls
        assert '/api/products' in urls or '/products' in urls
        assert '/api' in urls
        assert '/v2' in urls

    def test_object_property_reassignment(self):
        node, file_size = parse_file('variable_reassignment.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should track object property values - components extracted
        assert '/api' in urls
        assert '/v3' in urls
        assert '/data' in urls or '/resource' in urls


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
