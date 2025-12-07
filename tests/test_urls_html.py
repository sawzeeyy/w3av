"""
Tests for HTML URL extraction integration in urls.py
"""

import pytest
from pathlib import Path
from weav.core.jsparser import parse_javascript
from weav.modes.urls import get_urls


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'html'


def parse_js_file(filename):
    """Helper to parse JavaScript from fixture file."""
    filepath = FIXTURES_DIR / filename
    code = filepath.read_text()
    return parse_javascript(code)


class TestHtmlInStrings:
    """Test HTML URL extraction from string literals."""

    def test_simple_html_anchor(self):
        """Extract href from anchor tag in string."""
        _, root = parse_js_file('simple_anchor.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/users' in urls

    def test_html_img_src(self):
        """Extract src from img tag."""
        js = '''const widget = '<img src="https://cdn.example.com/logo.png">';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'https://cdn.example.com/logo.png' in urls

    def test_multiple_html_tags(self):
        """Extract URLs from multiple HTML tags."""
        _, root = parse_js_file('multiple_tags.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/v1' in urls
        assert '/icon.png' in urls
        assert '/style.css' in urls

    def test_html_form_action(self):
        """Extract action from form tag."""
        js = '''const form = '<form action="/submit"><button formaction="/preview">Preview</button></form>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/submit' in urls
        assert '/preview' in urls

    def test_html_video_urls(self):
        """Extract URLs from video elements."""
        js = '''const video = '<video src="/clip.mp4" poster="/thumb.jpg"><source src="/clip.webm"></video>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/clip.mp4' in urls
        assert '/thumb.jpg' in urls
        assert '/clip.webm' in urls


class TestHtmlInTemplateStrings:
    """Test HTML URL extraction from template literals."""

    def test_template_string_with_html(self):
        """Extract URLs from HTML in template string."""
        js = '''const page = `<a href="/dashboard">Dashboard</a>`;'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/dashboard' in urls

    def test_full_html_page_template(self):
        """Extract URLs from complete HTML page."""
        js = '''
const page = `
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="/css/style.css">
    <script src="/js/app.js"></script>
</head>
<body>
    <a href="/home">Home</a>
    <img src="/logo.png">
</body>
</html>
`;
'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/css/style.css' in urls
        assert '/js/app.js' in urls
        assert '/home' in urls
        assert '/logo.png' in urls


class TestHtmlSrcset:
    """Test srcset attribute parsing."""

    def test_srcset_single_image(self):
        """Extract URL from srcset with single image."""
        js = '''const img = '<img srcset="image.jpg 1x">';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'image.jpg' in urls

    def test_srcset_multiple_images(self):
        """Extract all URLs from srcset with multiple images."""
        _, root = parse_js_file('srcset.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'thumb.jpg' in urls
        assert 'medium.jpg' in urls
        assert 'large.jpg' in urls


class TestHtmlDataAttributes:
    """Test data-* attribute extraction."""

    def test_data_src_attribute(self):
        """Extract URL from data-src (lazy loading)."""
        js = '''const img = '<img data-src="/images/lazy.jpg">';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/images/lazy.jpg' in urls

    def test_data_url_attribute(self):
        """Extract URL from data-url attribute."""
        js = '''const elem = '<div data-url="https://example.com/data"></div>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'https://example.com/data' in urls

    def test_data_href_attribute(self):
        """Extract URL from data-href attribute."""
        js = '''const link = '<span data-href="/profile">Profile</span>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/profile' in urls

    def test_multiple_data_attributes(self):
        """Extract URLs from multiple data attributes."""
        _, root = parse_js_file('data_attributes.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/main.jpg' in urls
        assert 'https://fallback.com/image.png' in urls


class TestHtmlInTemplateStrings:
    """Test HTML URL extraction from template string literals."""

    def test_template_string_with_html(self):
        """Extract URLs from HTML in template string."""
        _, root = parse_js_file('template_string.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/dashboard' in urls

    def test_template_string_full_page(self):
        """Extract URLs from complete HTML page in template string."""
        _, root = parse_js_file('template_full_page.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/styles.css' in urls
        assert '/home' in urls
        assert '/app.js' in urls


class TestInlineScripts:
    """Test extraction of URLs from inline JavaScript in HTML."""

    def test_inline_script_with_url(self):
        """Extract URL from inline script tag."""
        js = '''const html = '<script>const url = "/api/data";</script>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/data' in urls

    def test_inline_script_with_fetch(self):
        """Extract URL from fetch call in inline script."""
        js = '''const html = '<script>fetch("/api/users");</script>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/users' in urls

    def test_inline_script_with_multiple_urls(self):
        """Extract multiple URLs from inline script."""
        _, root = parse_js_file('inline_script.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/data' in urls
        assert 'https://analytics.com/track' in urls
        assert '/redirect' in urls

    def test_inline_script_with_template_literal(self):
        """Extract URL from template literal in inline script."""
        js = '''const html = '<script>const url = `/api/${id}`;</script>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        # Should extract template with placeholder
        assert any('/api/' in url for url in urls)

    def test_multiple_inline_scripts(self):
        """Extract URLs from multiple inline script tags."""
        js = '''
const html = `
<script>const url1 = "/api/first";</script>
<script>const url2 = "/api/second";</script>
`;
'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/first' in urls
        assert '/api/second' in urls

    def test_mixed_inline_and_external_scripts(self):
        """Extract URLs from both inline and external scripts."""
        _, root = parse_js_file('mixed_scripts.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/external.js' in urls
        assert '/api/inline' in urls


class TestHtmlAndJavaScriptCombined:
    """Test extraction from both HTML and JavaScript in the same file."""

    def test_nested_structures(self):
        """Extract URLs from nested objects containing HTML."""
        _, root = parse_js_file('nested_structures.js')
        urls = get_urls(root, 'FUZZ', False, False)
        # HTML template URLs
        assert '/api/resource' in urls
        assert 'image.png' in urls
        assert 'lazy.png' in urls
        # Array URLs
        assert '/path1' in urls
        assert '/path2' in urls

    def test_full_integration(self):
        """Extract URLs from both HTML attributes and inline scripts."""
        _, root = parse_js_file('full_page.js')
        urls = get_urls(root, 'FUZZ', False, False)

        # HTML attributes
        assert '/styles/main.css' in urls
        assert '/vendor.js' in urls
        assert '/dashboard' in urls
        assert 'logo.jpg' in urls
        assert 'logo-sm.jpg' in urls
        assert 'logo-lg.jpg' in urls
        assert '/api/submit' in urls
        assert '/api/preview' in urls
        assert 'https://cdn.example.com/data' in urls

        # Inline JavaScript
        assert '/api/analytics' in urls
        assert 'https://external.com/track' in urls
        assert '/redirect' in urls

    def test_nested_html_structures(self):
        """Extract URLs from nested HTML structures."""
        _, root = parse_js_file('nested_html_structures.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/home' in urls
        assert '/about' in urls
        assert '/hero.jpg' in urls
        assert '/api/config' in urls
        assert 'https://cdn.example.com' in urls


class TestHtmlParserOptions:
    """Test different HTML parser backends."""

    def test_with_lxml_parser(self):
        """Extract URLs using lxml parser (default)."""
        js = '''const html = '<a href="/api">API</a>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False, html_parser='lxml')
        assert '/api' in urls

    def test_with_builtin_parser(self):
        """Extract URLs using built-in html.parser."""
        js = '''const html = '<a href="/api">API</a>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False, html_parser='html.parser')
        assert '/api' in urls

    def test_with_html5lib_parser(self):
        """Extract URLs using html5lib parser."""
        js = '''const html = '<a href="/api">API</a>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False, html_parser='html5lib')
        assert '/api' in urls

    def test_with_html5_parser(self):
        """Extract URLs using html5-parser."""
        js = '''const html = '<a href="/api">API</a>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False, html_parser='html5-parser')
        assert '/api' in urls


class TestHtmlEdgeCases:
    """Test edge cases in HTML processing."""

    def test_malformed_html(self):
        """Handle malformed HTML gracefully."""
        _, root = parse_js_file('malformed.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/valid' in urls
        assert 'image.jpg' in urls

    def test_empty_html_string(self):
        """Handle empty HTML string."""
        _, root = parse_js_file('empty_strings.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert urls == []

    def test_html_without_urls(self):
        """Handle HTML without any URLs."""
        js = '''const html = '<div>Text content</div>';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert urls == []

    def test_skip_javascript_protocol(self):
        """Skip javascript: protocol URLs."""
        _, root = parse_js_file('skip_protocols.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'javascript:void(0)' not in urls
        assert 'mailto:test@example.com' not in urls
        assert 'tel:+1234567890' not in urls
        assert '/valid' in urls

    def test_skip_data_uris(self):
        """Skip data: URIs."""
        js = '''const html = '<img src="data:image/png;base64,...">';'''
        _, root = parse_javascript(js)
        urls = get_urls(root, 'FUZZ', False, False)
        assert not any('data:' in url for url in urls)

    def test_skip_fragment_only(self):
        """Skip fragment-only URLs."""
        _, root = parse_js_file('fragments.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '#section' not in urls
        # But page with fragment should still extract the page part
        assert any('/page' in url for url in urls)

    def test_mixed_quotes_in_html(self):
        """Handle mixed quotes in HTML attributes."""
        _, root = parse_js_file('mixed_quotes.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/api/users' in urls
        assert '/api/posts' in urls


class TestCitationElements:
    """Test URL extraction from citation HTML elements."""

    def test_blockquote_cite(self):
        """Extract cite URL from blockquote."""
        _, root = parse_js_file('citation_elements.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert 'https://source.com/article' in urls

    def test_q_cite(self):
        """Extract cite URL from q element."""
        _, root = parse_js_file('citation_elements.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/local/source' in urls

    def test_ins_cite(self):
        """Extract cite URL from ins element."""
        _, root = parse_js_file('citation_elements.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/changelog#v2' in urls

    def test_del_cite(self):
        """Extract cite URL from del element."""
        _, root = parse_js_file('citation_elements.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/changelog#v1' in urls


class TestObjectAndEmbed:
    """Test URL extraction from object and embed elements."""

    def test_object_data(self):
        """Extract data URL from object element."""
        _, root = parse_js_file('object_embed.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/media/video.mp4' in urls

    def test_object_codebase(self):
        """Extract codebase URL from object element."""
        _, root = parse_js_file('object_embed.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/plugins/' in urls

    def test_embed_src(self):
        """Extract src URL from embed element."""
        _, root = parse_js_file('object_embed.js')
        urls = get_urls(root, 'FUZZ', False, False)
        assert '/flash/player.swf' in urls
