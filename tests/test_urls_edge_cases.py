"""
Tests for edge cases and special scenarios in URL extraction.

Covers:
- Edge cases and unusual input
- Large file optimization
- Special characters and mixed quotes
- Unknown variables handling
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


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_result(self):
        # File with no URLs
        content = "const x = 123; const y = 'hello';"
        _, root_node = parse_javascript(content)
        urls = get_urls(root_node, 'FUZZ', include_templates=False, verbose=False, file_size=len(content.encode('utf8')))

        assert len(urls) == 0

    def test_verbose_mode(self):
        # Verbose mode should still filter junk
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=True, file_size=file_size)

        # MIME types should still be filtered in verbose mode
        assert 'application/json' not in urls
        assert 'text/html' not in urls

    def test_include_templates_flag(self):
        node, file_size = parse_file('template_strings.js')

        # Without templates flag
        urls_no_templates = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # With templates flag
        urls_with_templates = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # With templates should have more (or equal) results
        assert len(urls_with_templates) >= len(urls_no_templates)

    def test_custom_placeholder(self):
        node, file_size = parse_file('binary_expressions.js')
        urls = get_urls(node, 'CUSTOM', include_templates=True, verbose=False, file_size=file_size)

        # Should use custom placeholder
        assert any('CUSTOM' in url for url in urls)


class TestEdgeCases2:
    """Test additional edge cases and special scenarios."""

    def test_multiple_urls_in_string(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should extract multiple URLs from one string
        assert 'https://api.example.com/v1/users' in urls
        assert 'https://backup.example.com/v2/users' in urls

    def test_embedded_url_in_error(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should extract URL from error message
        assert 'https://database.example.com/api' in urls

    def test_protocol_relative_urls(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Protocol-relative URLs should be extracted
        assert '//cdn.example.com/static/app.js' in urls
        assert '//resources.example.com/images' in urls

    def test_empty_string_concatenation(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Empty strings shouldn't break extraction
        assert 'https://example.com' in urls

    def test_special_characters_in_urls(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # URLs with query params and fragments
        assert any('example.com/search' in url for url in urls)
        assert any('example.com/page' in url for url in urls)

    def test_mixed_quotes(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Different quote types should all work
        assert 'https://example.com/single-quotes' in urls
        assert 'https://example.com/double-quotes' in urls
        assert 'https://example.com/backticks' in urls

    def test_unknown_variables(self):
        node, file_size = parse_file('edge_cases.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Unknown variables should become FUZZ
        assert any('FUZZ' in url and '/api/users' in url for url in urls)
        assert any('/api' in url and 'FUZZ' in url for url in urls)


class TestLargeFileOptimization:
    """Test behavior with large files."""

    def test_large_file_detection(self):
        # Simulate large file (>1MB)
        large_content = "const url = '/api/users';\n" * 50000  # ~1MB
        _, root_node = parse_javascript(large_content)

        # Should still extract URLs even without symbol table
        urls = get_urls(root_node, 'FUZZ', include_templates=False, verbose=False, file_size=len(large_content.encode('utf8')))

        assert '/api/users' in urls
        assert len(urls) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
