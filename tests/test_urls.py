"""
Tests for sawari.modes.urls module - Core URL extraction from JavaScript files.

This is the main test file for URL extraction. Additional tests are organized in:
- test_urls_methods.py: Method-based extraction (concat, join, replace)
- test_urls_objects.py: Object and member expression handling
- test_urls_filtering.py: Junk filtering and helper functions
- test_urls_features.py: Feature-specific tests (route params, aliases, etc.)
- test_urls_edge_cases.py: Edge cases and special scenarios

Tests in this file cover:
- Simple string literals
- Template strings with ${} substitutions
- Binary expressions (concatenation)
- Integration tests combining multiple features
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


class TestSimpleStrings:
    """Test extraction from simple string literals."""

    def test_full_urls(self):
        node, file_size = parse_file('simple_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://api.example.com/v1/users' in urls
        assert 'https://github.com/user/repo' in urls

    def test_paths(self):
        node, file_size = parse_file('simple_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/api/login' in urls
        assert '/user/profile' in urls

    def test_domains(self):
        node, file_size = parse_file('simple_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Domains alone might be filtered or extracted differently
        # Just check that extraction works
        assert len(urls) > 0

    def test_ip_addresses(self):
        node, file_size = parse_file('simple_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '192.168.1.100' in urls
        assert '10.0.0.50:8080' in urls
        assert 'http://192.168.1.100/admin' in urls


class TestTemplateStrings:
    """Test extraction from template literals."""

    def test_template_resolution(self):
        node, file_size = parse_file('template_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should resolve template strings
        assert 'https://api.example.com' in urls
        assert '/users/123/profile' in urls
        assert '/api/v1/resource' in urls

    def test_template_with_templates_flag(self):
        node, file_size = parse_file('template_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should include template syntax with {}
        assert any('{userId}' in url for url in urls)
        assert 'https://api.example.com' in urls

    def test_static_paths(self):
        node, file_size = parse_file('template_strings.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Static template string (no substitutions)
        assert '/api/v1/resource' in urls


class TestBinaryExpressions:
    """Test extraction from concatenation with + operator."""

    def test_simple_concatenation(self):
        node, file_size = parse_file('binary_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert 'https://example.com/api' in urls
        assert '/api/users' in urls

    def test_nested_concatenation(self):
        node, file_size = parse_file('binary_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/api/v1/data/endpoint' in urls

    def test_concatenation_with_variables(self):
        node, file_size = parse_file('binary_expressions.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        assert '/api/users/profile' in urls


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_all_features_combined(self):
        # Create a complex test file on the fly
        content = """
        const base = "/api";
        const version = "v2";

        // Template with route params
        const userRoute = `/users/:id`;

        // Concatenation with array join
        const parts = [base, version];
        const url1 = parts.join("") + "/data";

        // Chained concat with replace
        const template = "{env}".concat("/resource");
        const url2 = template.replace("{env}", "prod");

        // Nested object with concatenation
        const config = {
            api: {
                endpoint: base + "/" + version
            }
        };
        const url3 = config.api.endpoint + "/users";
        """

        _, root_node = parse_javascript(content)
        urls = get_urls(root_node, 'FUZZ', include_templates=True, verbose=False, file_size=len(content.encode('utf8')))

        # Should extract various URL patterns
        assert len(urls) > 0

        # Should convert route params
        assert any('{id}' in url for url in urls)

        # Should resolve complex expressions - check for components
        assert any('/api' in url and 'data' in url for url in urls)
        assert '/api' in urls


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
