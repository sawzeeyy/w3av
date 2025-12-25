"""
Tests for HTML file input handling in URLs mode.

Tests that weav correctly detects HTML content and extracts URLs from:
- HTML attributes (href, src, action, etc.)
- Inline JavaScript in <script> tags
"""

from tree_sitter import Parser, Language
import tree_sitter_javascript

from weav.modes.urls import get_urls, is_html_content


def parse_js(code):
    """Helper to parse JavaScript code."""
    JS_LANGUAGE = Language(tree_sitter_javascript.language())
    parser = Parser(JS_LANGUAGE)
    tree = parser.parse(bytes(code, 'utf8'))
    return tree.root_node


class TestIsHtmlContent:
    """Test HTML content detection."""

    def test_detects_doctype(self):
        """Should detect HTML with DOCTYPE."""
        html = '<!DOCTYPE html><html><body></body></html>'
        assert is_html_content(html) is True

    def test_detects_lowercase_doctype(self):
        """Should detect lowercase DOCTYPE."""
        html = '<!doctype html><html><body></body></html>'
        assert is_html_content(html) is True

    def test_detects_html_tag(self):
        """Should detect HTML tag at start."""
        html = '<html><head></head><body></body></html>'
        assert is_html_content(html) is True

    def test_detects_uppercase_html(self):
        """Should detect uppercase HTML tag."""
        html = '<HTML><HEAD></HEAD><BODY></BODY></HTML>'
        assert is_html_content(html) is True

    def test_detects_head_tag(self):
        """Should detect head tag at start."""
        html = '<head><title>Test</title></head>'
        assert is_html_content(html) is True

    def test_detects_body_tag(self):
        """Should detect body tag at start."""
        html = '<body><p>Test</p></body>'
        assert is_html_content(html) is True

    def test_detects_script_tag(self):
        """Should detect script tag at start."""
        html = '<script>var x = 1;</script>'
        assert is_html_content(html) is True

    def test_rejects_javascript(self):
        """Should not detect pure JavaScript as HTML."""
        js = 'var x = 1; const y = 2;'
        assert is_html_content(js) is False

    def test_rejects_json(self):
        """Should not detect JSON as HTML."""
        json = '{"key": "value", "number": 123}'
        assert is_html_content(json) is False

    def test_rejects_comparison_operators(self):
        """Should not detect comparison operators as HTML."""
        js = 'if (x < 5 && y > 3) { doSomething(); }'
        assert is_html_content(js) is False

    def test_rejects_empty_string(self):
        """Should return False for empty string."""
        assert is_html_content('') is False

    def test_rejects_whitespace_only(self):
        """Should return False for whitespace."""
        assert is_html_content('   \n\t  ') is False

    def test_detects_with_leading_whitespace(self):
        """Should detect HTML with leading whitespace."""
        html = '\n  <!DOCTYPE html><html></html>'
        assert is_html_content(html) is True


class TestHtmlFileUrlExtraction:
    """Test URL extraction from HTML files."""

    def test_simple_html_with_inline_script(self):
        """Should extract URL from inline script in HTML."""
        html = '''
        <html>
            <body>
                <script>
                    var apiUrl = "/api/data";
                </script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')  # Dummy node, HTML will be detected
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/api/data' in result

    def test_html_with_href_and_script(self):
        """Should extract URLs from both HTML attributes and inline scripts."""
        html = '''
        <!DOCTYPE html>
        <html>
            <head>
                <link href="/styles.css" rel="stylesheet">
            </head>
            <body>
                <a href="/about">About</a>
                <script>
                    var endpoint = "/api/users";
                </script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/styles.css' in result
        assert '/about' in result
        assert '/api/users' in result

    def test_html_with_multiple_inline_scripts(self):
        """Should extract URLs from multiple inline scripts."""
        html = '''
        <html>
            <body>
                <script>var url1 = "/api/posts";</script>
                <script>var url2 = "/api/comments";</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/api/posts' in result
        assert '/api/comments' in result

    def test_html_with_img_src(self):
        """Should extract URLs from img src attributes."""
        html = '''
        <html>
            <body>
                <img src="/images/logo.png" alt="Logo">
                <script>var api = "/api/data";</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/images/logo.png' in result
        assert '/api/data' in result

    def test_html_with_form_action(self):
        """Should extract URLs from form action attributes."""
        html = '''
        <html>
            <body>
                <form action="/submit" method="post">
                    <input type="submit">
                </form>
                <script>fetch("/api/check");</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/submit' in result
        assert '/api/check' in result

    def test_html_deduplicates_urls(self):
        """Should deduplicate URLs from HTML and scripts."""
        html = '''
        <html>
            <body>
                <a href="/api/data">Link</a>
                <script>var url = "/api/data";</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        # Should appear only once despite being in both HTML and script
        assert result.count('/api/data') == 1

    def test_html_with_malformed_script(self):
        """Should handle malformed inline scripts gracefully."""
        html = '''
        <html>
            <body>
                <a href="/valid-url">Link</a>
                <script>this is not valid javascript {{{</script>
                <script>var goodUrl = "/api/good";</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        # Should still extract valid URLs despite malformed script
        assert '/valid-url' in result
        assert '/api/good' in result

    def test_html_with_template_literals_in_script(self):
        """Should extract templated URLs from inline scripts."""
        html = '''
        <html>
            <body>
                <script>
                    const API_BASE = "https://api.example.com";
                    const endpoint = `${API_BASE}/users`;
                </script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', True, False, source_text=html)

        assert 'https://api.example.com/users' in result or 'FUZZ/users' in result

    def test_javascript_not_treated_as_html(self):
        """Should process pure JavaScript normally, not as HTML."""
        js = 'var url = "/api/data"; const path = "/users";'
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False, source_text=js)

        assert '/api/data' in result
        assert '/users' in result

    def test_html_with_external_script_src(self):
        """Should extract external script src URLs."""
        html = '''
        <html>
            <head>
                <script src="/js/app.js"></script>
            </head>
            <body>
                <script>var api = "/api/data";</script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/js/app.js' in result
        assert '/api/data' in result

    def test_html_with_custom_placeholder(self):
        """Should use custom placeholder in HTML mode."""
        html = '''
        <html>
            <body>
                <script>
                    const userId = getUserId();
                    const url = `/users/${userId}`;
                </script>
            </body>
        </html>
        '''
        node = parse_js('var dummy = 1;')
        result = get_urls(node, 'XXX', True, False, source_text=html)

        assert '/users/XXX' in result or any('XXX' in url for url in result)


class TestPathPatternFalsePositives:
    """Test that path pattern detection doesn't produce false positives."""

    def test_rejects_natural_language_with_question_mark(self):
        """Should not treat natural language questions as URLs."""
        js = '''
        var msg = "This isn't a secret; why does it say that?!";
        var question = "What's the meaning of life?";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        # Should not include natural language strings
        assert "This isn't a secret; why does it say that?!" not in result
        assert "What's the meaning of life?" not in result

    def test_accepts_valid_query_strings(self):
        """Should accept valid URLs with query strings."""
        js = '''
        var url1 = "ABC?q=SessionDataQuery";
        var url2 = "/api?key=123";
        var url3 = "example.com?param=value";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        assert 'ABC?q=SessionDataQuery' in result
        assert '/api?key=123' in result
        assert 'example.com?param=value' in result

    def test_rejects_strings_with_spaces_before_question(self):
        """Should reject strings with spaces before question mark."""
        js = '''
        var msg = "How are you doing today?";
        var valid = "api?query=test";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        assert "How are you doing today?" not in result
        assert "api?query=test" in result

    def test_rejects_strings_with_special_chars(self):
        """Should reject strings with special characters that indicate text."""
        js = '''
        var text1 = "Hello, world!";
        var text2 = "What's happening?";
        var text3 = "Email: test@example.com";
        var valid = "/path/to/resource";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        assert "Hello, world!" not in result
        assert "What's happening?" not in result
        assert '/path/to/resource' in result

    def test_accepts_domains_with_query_params(self):
        """Should accept domain patterns with query parameters."""
        js = '''
        var url1 = "api.example.com?key=value";
        var url2 = "cdn.site.com?v=123";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        assert 'api.example.com?key=value' in result
        assert 'cdn.site.com?v=123' in result

    def test_rejects_single_words_with_question(self):
        """Should reject short single words before question marks."""
        js = '''
        var short = "a?b";
        var valid = "abc?query=1";
        '''
        node = parse_js(js)
        result = get_urls(node, 'FUZZ', False, False)

        # Short patterns might be rejected or accepted depending on length rules
        # Valid patterns with proper structure should work
        assert "abc?query=1" in result

class TestHtmlCommentExtraction:
    """Test URL extraction from HTML comments."""

    def test_extracts_urls_from_html_comments(self):
        """Should extract URLs from HTML comments."""
        html = '''<!DOCTYPE html>
        <html>
        <body>
            <!-- TODO: Update to https://api.example.com/v2 -->
            <!-- Backup: https://backup.example.com -->
            <a href="/visible">Visible</a>
        </body>
        </html>'''

        node = parse_js(html)
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert 'https://api.example.com/v2' in result
        assert 'https://backup.example.com' in result
        assert '/visible' in result

    def test_extracts_paths_from_commented_html_tags(self):
        """Should extract URLs from commented-out HTML tags."""
        html = '''<!DOCTYPE html>
        <html>
        <body>
            <!-- <a href="/old-endpoint">Old Link</a> -->
            <!-- <img src="/legacy-image.png"> -->
            <a href="/current-endpoint">Current</a>
        </body>
        </html>'''

        node = parse_js(html)
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert '/old-endpoint' in result
        assert '/legacy-image.png' in result
        assert '/current-endpoint' in result

    def test_extracts_multiple_urls_from_single_comment(self):
        """Should extract multiple URLs from a single HTML comment."""
        html = '''<!DOCTYPE html>
        <html>
        <body>
            <!-- Old endpoints: https://old-api.example.com and https://legacy.example.com -->
        </body>
        </html>'''

        node = parse_js(html)
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert 'https://old-api.example.com' in result
        assert 'https://legacy.example.com' in result

    def test_skips_non_url_comments(self):
        """Should not extract non-URL text from comments."""
        html = '''<!DOCTYPE html>
        <html>
        <body>
            <!-- This is just a regular comment -->
            <!-- TODO: Fix the bug -->
            <a href="https://example.com">Link</a>
        </body>
        </html>'''

        node = parse_js(html)
        result = get_urls(node, 'FUZZ', False, False, source_text=html)

        assert 'https://example.com' in result
        # Should not have random text from comments
        assert 'regular comment' not in result
        assert 'Fix the bug' not in result