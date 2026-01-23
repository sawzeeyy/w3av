"""
Tests for URL filtering and junk detection.

This is the main filtering test file. Additional tests are organized in:
- test_urls_cleanup.py: Trailing punctuation, placeholders, escape sequences
- test_urls_junk_patterns.py: Specific junk pattern filtering

Covers:
- Junk URL filtering (MIME types, protocols, property paths, etc.)
- Helper functions (clean_unbalanced_brackets, is_junk_url, etc.)
"""

import os
import pytest
import tree_sitter_javascript

from tree_sitter import Parser, Language
from w3av.core.jsparser import parse_javascript
from w3av.modes.urls import (
    get_urls,
    clean_unbalanced_brackets,
    is_junk_url,
    convert_route_params,
    is_url_pattern,
    is_path_pattern,
    decode_js_string,
    extract_string_value
)


# Path to test fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'urls')


def parse_file(filename):
    """Helper to parse a JavaScript file from fixtures."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    _, root_node = parse_javascript(content)
    return root_node, len(content.encode('utf8'))


class TestJunkFiltering:
    """Test junk URL filtering."""

    def test_mime_types_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # MIME types should be filtered out
        assert 'application/json' not in urls
        assert 'text/html' not in urls
        assert 'image/png' not in urls
        assert 'multipart/form-data' not in urls

    def test_incomplete_protocols_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Incomplete protocols should be filtered out
        assert 'https://' not in urls
        assert '//' not in urls
        assert 'http:' not in urls

    def test_property_paths_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Property paths should be filtered out
        assert 'action.target.value' not in urls
        assert 'util.promisify.custom' not in urls
        assert 'user.profile.name' not in urls

    def test_w3c_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # W3C namespaces should be filtered out
        assert 'http://www.w3.org/2000/svg' not in urls

    def test_generic_paths_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Generic paths should be filtered out
        assert '/{t}' not in urls
        assert '//FUZZ' not in urls
        assert './' not in urls

    def test_test_urls_filtered(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Test URLs should be filtered out
        assert 'http://localhost' not in urls
        assert 'http://a' not in urls

    def test_unbalanced_brackets_cleaned(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Unbalanced brackets should be cleaned
        assert 'https://github.com/apollographql/invariant-packages' in urls
        # Should NOT have trailing )
        assert 'https://github.com/apollographql/invariant-packages)' not in urls

    def test_valid_urls_kept(self):
        node, file_size = parse_file('junk_filtering.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Valid URLs should be kept
        assert 'https://api.example.com/users' in urls
        assert '/api/v2/users' in urls
        # Domain-only might be filtered, check that we have valid URLs
        assert len(urls) > 0

    def test_date_format_placeholders_filtered(self):
        """Test that date/time format placeholders are filtered out."""
        js_code = """
        // These should be FILTERED (pure date format placeholders)
        const fmt1 = "/yyyy/mm/dd/";
        const fmt2 = "/yyyy-mm-dd/";
        const fmt3 = "/dd/mm/yyyy/";
        const fmt4 = "/YYYY/MM/DD/";
        const fmt5 = "/mm/dd/yyyy/";
        const fmt6 = "/hh:mm:ss/";
        const fmt7 = "/HH:MM/";

        // These should be KEPT (valid URLs with date patterns)
        const url1 = "/api/yyyy/mm/dd/posts";
        const url2 = "/archive/yyyy/mm/dd";
        const url3 = "https://example.com/yyyy/mm/dd/data";
        const url4 = "/blog/yyyy-mm-dd/article";
        const url5 = "/yyyy/mm/dd/index.html";
        const url6 = "/api/v1/yyyy/mm/dd";
        const url7 = "/api/2024/12/07/posts";
        """

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))

        urls = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False
        )

        # Date format placeholders should be filtered
        assert '/yyyy/mm/dd/' not in urls
        assert '/yyyy-mm-dd/' not in urls
        assert '/dd/mm/yyyy/' not in urls
        assert '/YYYY/MM/DD/' not in urls
        assert '/mm/dd/yyyy/' not in urls
        assert '/hh:mm:ss/' not in urls
        assert '/HH:MM/' not in urls

        # Valid URLs containing date patterns should be kept
        assert '/api/yyyy/mm/dd/posts' in urls
        assert '/archive/yyyy/mm/dd' in urls
        assert 'https://example.com/yyyy/mm/dd/data' in urls
        assert '/blog/yyyy-mm-dd/article' in urls
        assert '/yyyy/mm/dd/index.html' in urls
        assert '/api/v1/yyyy/mm/dd' in urls
        assert '/api/2024/12/07/posts' in urls

    def test_timezone_identifiers_filtered(self):
        """Test that IANA timezone identifiers are filtered out."""
        js_code = """
        // These should be FILTERED (timezone identifiers)
        const tz1 = "Europe/Bucharest";
        const tz2 = "America/New_York";
        const tz3 = "Asia/Tokyo";
        const tz4 = "Pacific/Auckland";
        const tz5 = "Africa/Cairo";

        // These should be KEPT (valid URLs containing similar patterns)
        const url1 = "https://example.com/Europe/Bucharest/weather";
        const url2 = "/api/Europe/data";
        const url3 = "https://cdn.example.com/assets/America/config.js";
        """

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))

        urls = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False
        )

        # Timezone identifiers should be filtered
        assert 'Europe/Bucharest' not in urls
        assert 'America/New_York' not in urls
        assert 'Asia/Tokyo' not in urls
        assert 'Pacific/Auckland' not in urls
        assert 'Africa/Cairo' not in urls

        # Valid URLs with similar patterns should be kept
        assert 'https://example.com/Europe/Bucharest/weather' in urls
        assert '/api/Europe/data' in urls
        assert 'https://cdn.example.com/assets/America/config.js' in urls

    def test_filename_extraction(self):
        """Test that legitimate filenames with valid extensions are extracted."""
        js_code = """
        // These should be EXTRACTED (valid filenames)
        const file1 = "config.json";
        const file2 = "jquery.min.js";
        const file3 = "bootstrap.bundle.min.css";
        const file4 = "archive.tar.gz";
        const file5 = "my-document_v2.pdf";
        const file6 = "a1.js";  // short but has number
        const file7 = "styles.css";
        const file8 = "image.png";

        // These should be FILTERED (property access patterns)
        const prop1 = "window.location";
        const prop2 = "user.name";
        const prop3 = "a.b";  // too short
        const prop4 = "object.property.value";

        // These should be EXTRACTED (paths with filenames)
        const path1 = "/assets/styles.css";
        const path2 = "./config.json";
        const path3 = "https://cdn.example.com/lib/jquery.min.js";
        """

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))

        urls = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False
        )

        # Valid filenames should be extracted
        assert 'config.json' in urls
        assert 'jquery.min.js' in urls
        assert 'bootstrap.bundle.min.css' in urls
        assert 'archive.tar.gz' in urls
        assert 'my-document_v2.pdf' in urls
        assert 'a1.js' in urls
        assert 'styles.css' in urls
        assert 'image.png' in urls

        # Property access patterns should be filtered
        assert 'window.location' not in urls
        assert 'user.name' not in urls
        assert 'a.b' not in urls
        assert 'object.property.value' not in urls

        # Paths with filenames should be extracted
        assert '/assets/styles.css' in urls
        assert './config.json' in urls
        assert 'https://cdn.example.com/lib/jquery.min.js' in urls


class TestHelperFunctions:
    """Test individual helper functions directly."""

    def test_clean_unbalanced_brackets(self):
        # Trailing unbalanced closing brackets
        assert clean_unbalanced_brackets('https://example.com)') == 'https://example.com'
        assert clean_unbalanced_brackets('https://example.com]') == 'https://example.com'
        assert clean_unbalanced_brackets('https://example.com}') == 'https://example.com'

        # Balanced brackets (should not change)
        assert clean_unbalanced_brackets('https://example.com/(path)') == 'https://example.com/(path)'
        assert clean_unbalanced_brackets('https://example.com/[data]') == 'https://example.com/[data]'

        # Multiple trailing unbalanced
        assert clean_unbalanced_brackets('https://example.com))') == 'https://example.com'

        # Edge cases
        assert clean_unbalanced_brackets('') == ''
        assert clean_unbalanced_brackets(None) == None

    def test_is_junk_url(self):
        # MIME types
        assert is_junk_url('application/json') == True
        assert is_junk_url('text/html') == True
        assert is_junk_url('image/png') == True

        # Incomplete protocols
        assert is_junk_url('https://') == True
        assert is_junk_url('//') == True
        assert is_junk_url('http:') == True

        # Property paths
        assert is_junk_url('action.target.value') == True
        assert is_junk_url('util.promisify.custom') == True

        # W3C namespaces
        assert is_junk_url('http://www.w3.org/2000/svg') == True

        # Generic paths
        assert is_junk_url('/{t}') == True
        assert is_junk_url('//FUZZ') == True

        # Valid URLs (should return False)
        assert is_junk_url('https://api.example.com/users') == False
        assert is_junk_url('/api/v2/users') == False
        # Note: domain-only strings like 'api.github.com' may be filtered
        # depending on validation rules

    def test_convert_route_params(self):
        # Colon-style route params
        original, converted, has_params = convert_route_params('/users/:id')
        assert converted == '/users/{id}'
        assert has_params == True

        # Bracket-style params
        original, converted, has_params = convert_route_params('archives/v[VERSION].json')
        assert converted == 'archives/v{VERSION}.json'
        assert has_params == True

        # Mixed params
        original, converted, has_params = convert_route_params('/users/:userId/posts/[ID]')
        assert converted == '/users/{userId}/posts/{ID}'
        assert has_params == True

        # No params
        original, converted, has_params = convert_route_params('/static/path')
        assert converted == '/static/path'
        assert has_params == False

    def test_convert_route_params_with_authentication(self):
        """Test that route param conversion doesn't affect URL authentication."""

        # GitHub URL with token - colon should NOT be treated as route param
        original, converted, has_params = convert_route_params('https://user:ghp_token123@github.com/repo.git')
        assert original == 'https://user:ghp_token123@github.com/repo.git'
        assert converted == 'https://user:ghp_token123@github.com/repo.git'
        assert has_params == False

        # HTTP basic auth
        original, converted, has_params = convert_route_params('https://admin:password@example.com/api')
        assert original == 'https://admin:password@example.com/api'
        assert converted == 'https://admin:password@example.com/api'
        assert has_params == False

        # FTP with credentials
        original, converted, has_params = convert_route_params('ftp://user:pass@ftp.example.com/file.zip')
        assert original == 'ftp://user:pass@ftp.example.com/file.zip'
        assert converted == 'ftp://user:pass@ftp.example.com/file.zip'
        assert has_params == False

    def test_decode_js_string(self):
        """Test JavaScript escape sequence decoding."""

        # Hex escapes (\xHH)
        assert decode_js_string('param1\\x3dvalue') == 'param1=value'
        assert decode_js_string('\\x41\\x42\\x43') == 'ABC'
        assert decode_js_string('test\\x20space') == 'test space'

        # Unicode escapes (\uHHHH)
        assert decode_js_string('param\\u003dvalue') == 'param=value'
        assert decode_js_string('\\u0041\\u0042\\u0043') == 'ABC'
        assert decode_js_string('hello\\u0020world') == 'hello world'

        # Unicode code points (\u{HHHHHH})
        assert decode_js_string('param\\u{003D}value') == 'param=value'
        assert decode_js_string('param\\u{00003D}value') == 'param=value'
        assert decode_js_string('\\u{1F600}') == '😀'

        # Octal escapes (\OOO)
        assert decode_js_string('param\\075value') == 'param=value'
        assert decode_js_string('\\101\\102\\103') == 'ABC'
        assert decode_js_string('test\\040space') == 'test space'

        # Standard escapes
        assert decode_js_string('line1\\nline2') == 'line1\nline2'
        assert decode_js_string('tab\\there') == 'tab\there'
        assert decode_js_string('carriage\\rreturn') == 'carriage\rreturn'
        assert decode_js_string('back\\bspace') == 'back\bspace'
        assert decode_js_string('form\\ffeed') == 'form\ffeed'
        assert decode_js_string('vertical\\vtab') == 'vertical\vtab'
        assert decode_js_string("quote\\'test") == "quote'test"
        assert decode_js_string('quote\\"test') == 'quote"test'
        assert decode_js_string('back\\\\slash') == 'back\\slash'
        assert decode_js_string('null\\0char') == 'null\0char'

        # Mixed escapes
        assert decode_js_string('\\x3d\\u003d\\075') == '==='
        assert decode_js_string('param1\\x3dval1&param2\\u003dval2') == 'param1=val1&param2=val2'

        # No escapes
        assert decode_js_string('normal text') == 'normal text'
        assert decode_js_string('') == ''

    def test_extract_string_value_with_escapes(self):
        """Test that extract_string_value properly decodes escape sequences."""

        # Create simple test strings and parse them
        test_cases = [
            ('"/api/test\\x3dparam"', '/api/test=param'),
            ('"/api/test\\u003dparam"', '/api/test=param'),
            ('"/api/test\\075param"', '/api/test=param'),
            ('"/path\\nwith\\nnewlines"', '/path\nwith\nnewlines'),
        ]

        for js_code, expected in test_cases:
            _, root = parse_javascript(f'const x = {js_code}')
            # Find the string node
            string_node = None
            def find_string(node):
                nonlocal string_node
                if node.type == 'string':
                    string_node = node
                    return
                for child in node.children:
                    find_string(child)
            find_string(root)

            if string_node:
                result = extract_string_value(string_node)
                assert result == expected, f"Expected {expected}, got {result}"

    def test_is_url_pattern(self):
        # Protocol URLs
        assert is_url_pattern('https://example.com') == True
        assert is_url_pattern('http://localhost') == True
        assert is_url_pattern('ftp://files.example.com') == True

        # Protocol-relative
        assert is_url_pattern('//cdn.example.com') == True

        # Common prefixes
        assert is_url_pattern('www.example.com') == True
        assert is_url_pattern('api.github.com') == True
        assert is_url_pattern('cdn.jsdelivr.net') == True

        # IP addresses
        assert is_url_pattern('192.168.1.1') == True
        assert is_url_pattern('10.0.0.1:8080') == True

        # Not URLs
        assert is_url_pattern('hello.world') == False  # Simple word.word
        assert is_url_pattern('user.name') == False

    def test_is_path_pattern(self):
        # Absolute paths
        assert is_path_pattern('/api/users') == True
        assert is_path_pattern('/profile') == True

        # Relative paths
        assert is_path_pattern('./file') == True
        assert is_path_pattern('../dir') == True

        # API paths
        assert is_path_pattern('api/users') == True
        assert is_path_pattern('v1/endpoint') == True

        # Not paths
        assert is_path_pattern('//cdn.example.com') == False  # Protocol-relative
        assert is_path_pattern('/e') == False  # Too short


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
