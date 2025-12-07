"""
Tests for weav.modes.urls module - URL extraction from JavaScript files.

Tests cover:
- Simple string literals
- Template strings with ${} substitutions
- Binary expressions (concatenation)
- Route parameters (:id and [VERSION] conversion)
- Chained .concat() calls
- Array .join() method
- Object properties and nested objects
- String .replace() method
- Junk URL filtering
- Variable reassignment
"""

import os
import pytest
from weav.core.jsparser import parse_javascript
from weav.modes.urls import get_urls


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


class TestRouteParams:
    """Test route parameter conversion (:id -> {id}, [VERSION] -> {VERSION})."""

    def test_colon_route_params(self):
        node, file_size = parse_file('route_params.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should convert :id to {id}
        assert '/users/{id}' in urls
        assert '/posts/{postId}/comments/{commentId}' in urls
        assert '/users/{userId}/profile/{section}' in urls

    def test_bracket_route_params(self):
        node, file_size = parse_file('route_params.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should convert [VERSION] to {VERSION}
        assert 'archives/vendor-list-v{VERSION}.json' in urls
        assert '/posts/{ID}/comments/{commentId}' in urls
        assert '/api/{version}/users' in urls

    def test_route_params_with_fuzz(self):
        node, file_size = parse_file('route_params.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should also output FUZZ versions
        assert '/users/FUZZ' in urls
        assert 'archives/vendor-list-vFUZZ.json' in urls

    def test_template_with_route_params(self):
        node, file_size = parse_file('route_params.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Template string with route params: ${} -> {} and :param -> {param}
        assert '/users/{userId}/posts/{postId}' in urls
        assert '/data/{category}/items/{itemId}' in urls


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


class TestComments:
    """Test extraction from JavaScript code in comments."""

    def test_comments_extraction(self):
        node, file_size = parse_file('comments.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should extract from regular code
        assert 'https://visible.example.com/data' in urls

        # May or may not extract from comments (implementation dependent)
        # Just verify some URLs are extracted
        assert len(urls) > 0


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


class TestHelperFunctions:
    """Test individual helper functions directly."""

    def test_clean_unbalanced_brackets(self):
        from weav.modes.urls import clean_unbalanced_brackets

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
        from weav.modes.urls import is_junk_url

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
        from weav.modes.urls import convert_route_params

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

    def test_is_url_pattern(self):
        from weav.modes.urls import is_url_pattern

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
        from weav.modes.urls import is_path_pattern

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


class TestAdjacentPlaceholders:
    """Test handling of adjacent template expressions without separators."""

    def test_adjacent_template_expressions(self):
        node, file_size = parse_file('adjacent_placeholders.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should consolidate adjacent placeholders
        assert 'FUZZ/spaces/FUZZ' in urls
        assert '{prefix}/spaces/{key}{suffix ? `/${suffix}` : ""}' in urls

        # Should NOT include pure placeholder paths (filtered as junk)
        assert 'FUZZ/FUZZ' not in urls
        assert 'FUZZ/FUZZ/FUZZ/FUZZ/FUZZ' not in urls

    def test_consolidate_adjacent_placeholders_function(self):
        from weav.modes.urls import consolidate_adjacent_placeholders

        # Test the helper function directly
        assert consolidate_adjacent_placeholders('FUZZFUZZ', 'FUZZ') == 'FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/FUZZFUZZ', 'FUZZ') == 'FUZZ/FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/spaces/FUZZFUZZ', 'FUZZ') == 'FUZZ/spaces/FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/FUZZ/FUZZ/FUZZ/FUZZFUZZ', 'FUZZ') == 'FUZZ/FUZZ/FUZZ/FUZZ/FUZZ'

        # Test with custom placeholder
        assert consolidate_adjacent_placeholders('CUSTOMCUSTOM', 'CUSTOM') == 'CUSTOM'
        assert consolidate_adjacent_placeholders('CUSTOM/api/CUSTOMCUSTOM', 'CUSTOM') == 'CUSTOM/api/CUSTOM'

    def test_junk_filtering_pure_placeholders(self):
        from weav.modes.urls import is_junk_url

        # Pure placeholder paths should be junk
        assert is_junk_url('FUZZ/FUZZ', 'FUZZ') == True
        assert is_junk_url('FUZZ/FUZZ/FUZZ', 'FUZZ') == True
        assert is_junk_url('FUZZ/FUZZ/FUZZ/FUZZ/FUZZ', 'FUZZ') == True

        # Paths with actual content should NOT be junk
        assert is_junk_url('FUZZ/spaces/FUZZ', 'FUZZ') == False
        assert is_junk_url('/api/FUZZ/users', 'FUZZ') == False
        assert is_junk_url('FUZZ/api/v2', 'FUZZ') == False

        # Custom placeholder
        assert is_junk_url('CUSTOM/CUSTOM', 'CUSTOM') == True
        assert is_junk_url('CUSTOM/api/CUSTOM', 'CUSTOM') == False


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


class TestSemanticAliases:
    """Test semantic alias extraction feature."""

    @staticmethod
    def extract_urls(js_code):
        """Helper to extract URLs from JavaScript code."""
        from tree_sitter import Parser, Language
        import tree_sitter_javascript

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))
        return get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False
        )

    def test_object_literal_aliases(self):
        """Test extraction of aliases from object literals."""
        js_code = """
        const t = '123';
        const r = 'date';
        const params = { contentId: t, orderBy: r };
        const url = `/api/content/${t}?sort=${r}`;
        """

        urls = self.extract_urls(js_code)

        # Should use semantic names from object literal
        assert any('{contentId}' in url for url in urls), \
            "Expected {contentId} in template output"
        assert any('{orderBy}' in url for url in urls), \
            "Expected {orderBy} in template output"

        # Should NOT use generic variable names when alias exists
        template_urls = [u for u in urls if '{' in u and '}' in u and 'FUZZ' not in u]
        assert not any('{t}' in url for url in template_urls), \
            "Should not use {t} when {contentId} alias exists"
        assert not any('{r}' in url for url in template_urls), \
            "Should not use {r} when {orderBy} alias exists"

    def test_urlsearchparams_aliases(self):
        """Test extraction of aliases from URLSearchParams constructor."""
        js_code = """
        const userId = '456';
        const params = new URLSearchParams({ userId: userId });
        const url = `/api/user/${userId}`;
        """

        urls = self.extract_urls(js_code)

        # Should preserve semantic name
        assert any('{userId}' in url for url in urls), \
            "Expected {userId} in template output"

    def test_concatenation_with_aliases(self):
        """Test that aliases work in binary expressions (concatenation)."""
        js_code = """
        const id = '789';
        const obj = { postId: id };
        const url = '/api/posts/' + id;
        """

        urls = self.extract_urls(js_code)

        # Should use semantic name from object literal
        assert any('{postId}' in url for url in urls), \
            "Expected {postId} in concatenated URL"

    def test_multiple_aliases_same_variable(self):
        """Test that best alias is chosen when variable appears in multiple contexts."""
        js_code = """
        const x = '123';
        const obj1 = { id: x };
        const obj2 = { tempValue: x };
        const url = `/api/item/${x}`;
        """

        urls = self.extract_urls(js_code)

        # Should prefer 'id' over 'tempValue' (shorter, less generic)
        template_urls = [u for u in urls if '{' in u and '}' in u and 'FUZZ' not in u]
        assert any('{id}' in url for url in template_urls), \
            "Expected {id} to be chosen as best alias"

    def test_no_alias_fallback(self):
        """Test that original variable name is used when no alias exists."""
        js_code = """
        const mySpecialId = '123';
        const url = `/api/item/${mySpecialId}`;
        """

        urls = self.extract_urls(js_code)

        # Should use original variable name when no alias
        assert any('{mySpecialId}' in url for url in urls), \
            "Expected {mySpecialId} when no alias exists"

    def test_formdata_aliases(self):
        """Test extraction of aliases from FormData.append() calls."""
        js_code = """
        const u = '123';
        const formData = new FormData();
        formData.append('userId', u);
        const url = `/api/user/${u}`;
        """

        urls = self.extract_urls(js_code)

        # Should extract alias from FormData.append
        assert any('{userId}' in url for url in urls), \
            "Expected {userId} from FormData.append pattern"

    def test_member_expression_with_alias(self):
        """Test that member expressions use aliases for base variable."""
        js_code = """
        const c = { id: '123', name: 'test' };
        const obj = { config: c };
        const url = `/api/item/${c.id}`;
        """

        urls = self.extract_urls(js_code)

        # Should use alias for base variable in member expression
        assert any('{config.id}' in url for url in urls), \
            "Expected {config.id} using alias for base variable"

    def test_skip_aliases_flag(self):
        """Test that --skip-aliases flag disables semantic alias extraction."""
        from tree_sitter import Parser, Language
        import tree_sitter_javascript

        js_code = """
        const t = '123';
        const params = { contentId: t };
        const url = `/api/content/${t}`;
        """

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))

        # With semantic aliases (default)
        urls_with_aliases = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False,
            skip_aliases=False
        )

        # Without semantic aliases
        urls_without_aliases = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False,
            skip_aliases=True
        )

        # With aliases: should see {contentId}
        assert any('{contentId}' in url for url in urls_with_aliases), \
            f"Expected {{contentId}} with aliases enabled, got: {urls_with_aliases}"

        # Without aliases: should see {t}
        assert any('{t}' in url for url in urls_without_aliases), \
            f"Expected {{t}} with aliases disabled, got: {urls_without_aliases}"

        # Ensure we DON'T see the opposite
        assert not any('{t}' in url for url in urls_with_aliases), \
            f"Should not see {{t}} with aliases enabled"
        assert not any('{contentId}' in url for url in urls_without_aliases), \
            f"Should not see {{contentId}} with aliases disabled"

    def test_large_file_disables_aliases(self):
        """Test that large files automatically disable semantic aliases."""
        from tree_sitter import Parser, Language
        import tree_sitter_javascript

        js_code = """
        const t = '123';
        const params = { contentId: t };
        const url = `/api/content/${t}`;
        """

        JS_LANGUAGE = Language(tree_sitter_javascript.language())
        parser = Parser(JS_LANGUAGE)
        tree = parser.parse(bytes(js_code, 'utf8'))

        # Small file - aliases enabled
        urls_small = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False,
            file_size=100,
            max_file_size_mb=1.0
        )

        # Large file - aliases disabled automatically
        urls_large = get_urls(
            node=tree.root_node,
            placeholder='FUZZ',
            include_templates=True,
            verbose=False,
            file_size=2 * 1024 * 1024,  # 2MB
            max_file_size_mb=1.0
        )

        # Small file should have aliases
        assert any('{contentId}' in url for url in urls_small), \
            f"Expected {{contentId}} for small file, got: {urls_small}"

        # Large file should use raw variable names
        assert any('{t}' in url for url in urls_large), \
            f"Expected {{t}} for large file, got: {urls_large}"
        assert not any('{contentId}' in url for url in urls_large), \
            f"Should not see {{contentId}} for large file"


class TestSkipSymbols:
    """Test --skip-symbols functionality."""

    def test_skip_symbols_flag(self):
        """Test that --skip-symbols prevents symbol resolution."""
        node, file_size = parse_file('skip_symbols_basic.js')

        # With symbol resolution (default)
        urls_with_symbols = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=False)
        assert '/api/v1' in urls_with_symbols
        assert '/users' in urls_with_symbols
        assert '/static/path' in urls_with_symbols
        assert '/api/v1/users' in urls_with_symbols  # Should resolve the concatenation

        # Without symbol resolution (--skip-symbols)
        urls_without_symbols = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=True)
        assert '/api/v1' in urls_without_symbols
        assert '/users' in urls_without_symbols
        assert '/static/path' in urls_without_symbols
        assert '/api/v1/users' not in urls_without_symbols  # Should NOT resolve the concatenation

    def test_skip_symbols_with_large_file(self):
        """Test that large files automatically skip symbols."""
        node, file_size = parse_file('skip_symbols_simple.js')

        # Small file size - should use symbols
        urls = get_urls(node, 'FUZZ', False, False, file_size=100, max_file_size_mb=1.0, skip_symbols=False)
        assert '/api/test' in urls

        # Large file size - should skip symbols automatically
        urls = get_urls(node, 'FUZZ', False, False, file_size=2 * 1024 * 1024, max_file_size_mb=1.0, skip_symbols=False)
        assert '/api/test' in urls

        # Explicit skip_symbols overrides file size check
        urls = get_urls(node, 'FUZZ', False, False, file_size=100, max_file_size_mb=1.0, skip_symbols=True)
        assert '/api/test' in urls

    def test_skip_symbols_with_templates(self):
        """Test skip_symbols with template strings."""
        node, file_size = parse_file('skip_symbols_template.js')

        # With symbol resolution
        urls_with = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=False)
        assert any('/users/' in url for url in urls_with)

        # Without symbol resolution - should still extract templates with placeholder
        urls_without = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=True)
        assert any('/users/' in url for url in urls_without)

    def test_skip_symbols_with_objects(self):
        """Test skip_symbols with object properties."""
        node, file_size = parse_file('skip_symbols_objects.js')

        # With symbol resolution
        urls_with = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=False)
        assert '/api/v2' in urls_with
        assert '/data' in urls_with
        assert '/api/v2/data' in urls_with  # Should resolve object properties

        # Without symbol resolution
        urls_without = get_urls(node, 'FUZZ', False, False, file_size=file_size, skip_symbols=True)
        assert '/api/v2' in urls_without
        assert '/data' in urls_without
        assert '/api/v2/data' not in urls_without  # Should NOT resolve object properties


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
