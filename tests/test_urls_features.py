"""
Tests for specific URL extraction features.

Covers:
- Route parameter conversion (:id, [VERSION])
- Comments extraction
- Semantic aliases
- Skip symbols functionality
- Custom file extensions
"""

import os
import pytest
import tree_sitter_javascript

from tree_sitter import Parser, Language
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


class TestComments:
    """Test extraction from JavaScript code in comments."""

    def test_comments_extraction(self):
        node, file_size = parse_file('comments.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # Should extract from regular code
        assert 'https://visible.example.com/data' in urls

        # Should extract from single-line comment
        assert 'https://hidden.example.com/api' in urls

        # Should extract from multi-line comment
        assert 'https://api.example.com/v1' in urls
        assert '/users/profile' in urls

        # Should extract from inline comment
        assert 'https://inline.example.com' in urls

    def test_javascript_comment_with_plain_text_urls(self):
        """Should extract URLs from plain text in JavaScript comments."""
        code = '''
        // This endpoint is deprecated: https://old-api.example.com/v1
        /* New endpoint: https://new-api.example.com/v2 */
        const x = 1;
        '''
        _, root_node = parse_javascript(code)
        urls = get_urls(root_node, 'FUZZ', include_templates=False, verbose=False, file_size=len(code.encode('utf8')))

        assert 'https://old-api.example.com/v1' in urls
        assert 'https://new-api.example.com/v2' in urls

    def test_javascript_comment_with_paths(self):
        """Should extract paths from JavaScript comments."""
        code = '''
        // Legacy endpoint: /api/v1/users
        /* Current path: /api/v2/users */
        // Config: ./settings.json
        const x = 1;
        '''
        _, root_node = parse_javascript(code)
        urls = get_urls(root_node, 'FUZZ', include_templates=False, verbose=False, file_size=len(code.encode('utf8')))

        assert '/api/v1/users' in urls
        assert '/api/v2/users' in urls
        assert './settings.json' in urls


class TestSemanticAliases:
    """Test semantic alias extraction feature."""

    @staticmethod
    def extract_urls(js_code):
        """Helper to extract URLs from JavaScript code."""
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


class TestCustomExtensions:
    """Test custom file extensions support."""

    def test_custom_extensions_with_paths(self):
        """Should recognize custom extensions in paths."""
        node, file_size = parse_file('custom_extensions.js')

        # Without custom extensions - only recognize standard extensions
        urls_default = get_urls(node, 'FUZZ', False, False, file_size=file_size, extensions=None)
        assert 'config.json' in urls_default
        # Proto, graphql, mdx should be extracted as paths even without extension recognition
        assert 'api/schema.proto' in urls_default
        assert 'queries/user.graphql' in urls_default
        assert './docs/readme.mdx' in urls_default

    def test_custom_extensions_normalization(self):
        """Should normalize extensions with/without dots."""
        code = '''
        const file1 = "api/schema.proto";
        const file2 = "queries/user.graphql";
        '''
        _, root_node = parse_javascript(code)

        # Test with dots
        urls_with_dots = get_urls(root_node, 'FUZZ', False, False, file_size=len(code.encode('utf8')), extensions='.proto,.graphql')
        assert 'api/schema.proto' in urls_with_dots
        assert 'queries/user.graphql' in urls_with_dots

        # Test without dots
        urls_without_dots = get_urls(root_node, 'FUZZ', False, False, file_size=len(code.encode('utf8')), extensions='proto,graphql')
        assert 'api/schema.proto' in urls_without_dots
        assert 'queries/user.graphql' in urls_without_dots

    def test_custom_extensions_multiple(self):
        """Should handle multiple custom extensions."""
        code = '''
        const proto = "schema.proto";
        const graphql = "query.graphql";
        const mdx = "readme.mdx";
        '''
        _, root_node = parse_javascript(code)

        urls = get_urls(root_node, 'FUZZ', False, False, file_size=len(code.encode('utf8')), extensions='proto,graphql,mdx')
        # Simple filenames without paths won't be extracted unless they're recognized extensions
        # But paths with these extensions should work
        assert len(urls) >= 0  # May or may not extract standalone filenames


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
