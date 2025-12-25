import pytest

from w3av.core.html import (
    extract_urls_from_html,
    extract_inline_scripts_from_html,
    is_url_pattern,
    is_path_pattern
)

"""
Tests for HTML URL extraction and inline script extraction.
"""


class TestIsUrlPattern:
    """Tests for is_url_pattern helper function."""

    def test_protocol_urls(self):
        assert is_url_pattern('http://example.com')
        assert is_url_pattern('https://example.com')
        assert is_url_pattern('ftp://files.example.com')
        assert is_url_pattern('ws://socket.example.com')
        assert is_url_pattern('wss://secure-socket.example.com')

    def test_protocol_relative(self):
        assert is_url_pattern('//cdn.example.com')
        assert is_url_pattern('//api.github.com/users')

    def test_common_prefixes(self):
        assert is_url_pattern('www.example.com')
        assert is_url_pattern('api.github.com')
        assert is_url_pattern('cdn.cloudflare.com')

    def test_ip_addresses(self):
        assert is_url_pattern('192.168.1.1')
        assert is_url_pattern('10.0.0.1:8080')
        assert is_url_pattern('127.0.0.1/api')

    def test_domain_patterns(self):
        assert is_url_pattern('example.com/path')
        assert is_url_pattern('api.example.com')
        assert is_url_pattern('sub.domain.example.com')

    def test_rejects_false_positives(self):
        assert not is_url_pattern('user.name')
        assert not is_url_pattern('object.property')
        assert not is_url_pattern('mr.flatpickr')


class TestIsPathPattern:
    """Tests for is_path_pattern helper function."""

    def test_absolute_paths(self):
        assert is_path_pattern('/api/users')
        assert is_path_pattern('/profile')
        assert is_path_pattern('/path/to/file.js')

    def test_paths_with_query_strings(self):
        assert is_path_pattern('/cgraphql?q=SessionDataQuery')
        assert is_path_pattern('/api?key=value&other=123')

    def test_paths_with_fragments(self):
        assert is_path_pattern('/page#section')
        assert is_path_pattern('/docs#getting-started')

    def test_relative_paths(self):
        assert is_path_pattern('./file.js')
        assert is_path_pattern('../parent/file.js')

    def test_api_paths(self):
        assert is_path_pattern('api/users')
        assert is_path_pattern('v1/endpoint')

    def test_rejects_protocol_relative(self):
        assert not is_path_pattern('//cdn.example.com')

    def test_rejects_too_short(self):
        assert not is_path_pattern('/e')
        assert not is_path_pattern('/a')


class TestExtractUrlsFromHtml:
    """Tests for extract_urls_from_html function."""

    def test_basic_anchor_tag(self):
        html = '<a href="/api/users">Users</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/api/users'

    def test_multiple_urls(self):
        html = '''
        <div>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <img src="https://example.com/image.png">
        </div>
        '''
        urls = extract_urls_from_html(html)
        assert len(urls) == 3
        originals = [u['original'] for u in urls]
        assert '/page1' in originals
        assert '/page2' in originals
        assert 'https://example.com/image.png' in originals

    def test_script_src_attribute(self):
        html = '<script src="/static/js/app.js"></script>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/static/js/app.js'

    def test_img_src_attribute(self):
        html = '<img src="https://cdn.example.com/logo.png" alt="Logo">'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == 'https://cdn.example.com/logo.png'

    def test_link_href_attribute(self):
        html = '<link href="/css/styles.css" rel="stylesheet">'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/css/styles.css'

    def test_form_action_attribute(self):
        html = '<form action="/submit" method="post"></form>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/submit'

    def test_video_multiple_attributes(self):
        html = '<video src="/video.mp4" poster="/poster.jpg"></video>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 2
        originals = [u['original'] for u in urls]
        assert '/video.mp4' in originals
        assert '/poster.jpg' in originals

    def test_srcset_parsing(self):
        html = '<img srcset="small.jpg 100w, large.jpg 200w">'
        urls = extract_urls_from_html(html)
        assert len(urls) == 2
        originals = [u['original'] for u in urls]
        assert 'small.jpg' in originals
        assert 'large.jpg' in originals

    def test_data_attributes(self):
        html = '''
        <div data-src="/lazy-load.jpg" data-url="/api/endpoint"></div>
        '''
        urls = extract_urls_from_html(html)
        assert len(urls) == 2
        originals = [u['original'] for u in urls]
        assert '/lazy-load.jpg' in originals
        assert '/api/endpoint' in originals

    def test_skip_fragments(self):
        html = '<a href="#section">Skip</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 0

    def test_skip_javascript_protocol(self):
        html = '<a href="javascript:void(0)">Click</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 0

    def test_skip_data_uris(self):
        html = '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==">'
        urls = extract_urls_from_html(html)
        assert len(urls) == 0

    def test_blockquote_cite(self):
        html = '<blockquote cite="/source">Quote</blockquote>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/source'

    def test_button_formaction(self):
        html = '<button formaction="/override">Submit</button>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0]['original'] == '/override'

    def test_object_data_and_codebase(self):
        html = '<object data="/app.swf" codebase="/base/"></object>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 2
        originals = [u['original'] for u in urls]
        assert '/app.swf' in originals
        assert '/base/' in originals

    def test_malformed_html(self):
        html = '<a href="/path"'  # Missing closing >
        urls = extract_urls_from_html(html)
        # Should not crash, BeautifulSoup handles it
        assert isinstance(urls, list)

    def test_mixed_html_and_text(self):
        html = '''
        Some text
        <a href="/link1">Link</a>
        More text
        <img src="/image.png">
        '''
        urls = extract_urls_from_html(html)
        assert len(urls) == 2

    def test_entry_structure(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html)
        assert len(urls) == 1
        entry = urls[0]
        assert 'original' in entry
        assert 'placeholder' in entry
        assert 'resolved' in entry
        assert 'has_template' in entry
        assert entry['has_template'] is False


class TestExtractInlineScriptsFromHtml:
    """Tests for extract_inline_scripts_from_html function."""

    def test_single_inline_script(self):
        html = '''
        <script>
            const apiUrl = "/api/data";
        </script>
        '''
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 1
        assert 'const apiUrl = "/api/data";' in scripts[0]

    def test_multiple_inline_scripts(self):
        html = '''
        <script>const x = 1;</script>
        <script>const y = 2;</script>
        '''
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 2

    def test_skip_external_scripts(self):
        html = '''
        <script src="/external.js"></script>
        <script>const inline = true;</script>
        '''
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 1
        assert 'const inline = true;' in scripts[0]

    def test_mixed_inline_and_external(self):
        html = '''
        <script>const a = 1;</script>
        <script src="/external1.js"></script>
        <script>const b = 2;</script>
        <script src="/external2.js"></script>
        '''
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 2

    def test_complex_javascript(self):
        html = '''
        <script>
            fetch("https://api.example.com/data")
                .then(res => res.json())
                .then(data => console.log(data));
        </script>
        '''
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 1
        assert 'fetch("https://api.example.com/data")' in scripts[0]

    def test_empty_script_tag(self):
        html = '<script></script>'
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 0

    def test_script_with_only_whitespace(self):
        html = '<script>   \n\t  </script>'
        scripts = extract_inline_scripts_from_html(html)
        assert len(scripts) == 0


class TestHtmlParserOptions:
    """Tests for different HTML parser backends."""

    def test_lxml_parser(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html, html_parser='lxml')
        assert len(urls) == 1
        assert urls[0]['original'] == '/test'

    def test_html_parser_builtin(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html, html_parser='html.parser')
        assert len(urls) == 1
        assert urls[0]['original'] == '/test'

    def test_html5lib_parser(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html, html_parser='html5lib')
        assert len(urls) == 1
        assert urls[0]['original'] == '/test'

    def test_html5_parser(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html, html_parser='html5-parser')
        assert len(urls) == 1
        assert urls[0]['original'] == '/test'

    def test_invalid_parser_fallback(self):
        html = '<a href="/test">Test</a>'
        # Should fallback to html.parser
        urls = extract_urls_from_html(html, html_parser='invalid_parser')
        assert len(urls) == 1
        assert urls[0]['original'] == '/test'


class TestPlaceholderParameter:
    """Tests for custom placeholder parameter."""

    def test_custom_placeholder(self):
        html = '<a href="/test">Test</a>'
        urls = extract_urls_from_html(html, placeholder='CUSTOM')
        assert len(urls) == 1
        # Placeholder doesn't affect static URLs
        assert urls[0]['placeholder'] == '/test'


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_full_html_page(self):
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <link href="/css/styles.css" rel="stylesheet">
            <script src="/js/analytics.js"></script>
        </head>
        <body>
            <a href="/page1">Page 1</a>
            <img src="https://cdn.example.com/image.png">
            <script>
                const apiUrl = "/api/data";
                fetch("https://analytics.example.com/track");
            </script>
        </body>
        </html>
        '''
        urls = extract_urls_from_html(html)
        scripts = extract_inline_scripts_from_html(html)

        # Should extract all URLs from attributes
        originals = [u['original'] for u in urls]
        assert '/css/styles.css' in originals
        assert '/js/analytics.js' in originals
        assert '/page1' in originals
        assert 'https://cdn.example.com/image.png' in originals

        # Should extract inline script
        assert len(scripts) == 1
        assert 'const apiUrl = "/api/data";' in scripts[0]

    def test_nested_structures(self):
        html = '''
        <div>
            <div>
                <a href="/nested1">
                    <img src="/nested-img.png">
                </a>
            </div>
        </div>
        '''
        urls = extract_urls_from_html(html)
        originals = [u['original'] for u in urls]
        assert '/nested1' in originals
        assert '/nested-img.png' in originals
