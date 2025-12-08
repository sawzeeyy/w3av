from bs4 import BeautifulSoup
from weav.core.url_utils import is_url_pattern, is_path_pattern, is_filename_pattern

"""
HTML parsing utilities for extracting URLs from HTML markup and inline JavaScript.

This module provides functions to:
- Extract URLs from HTML attributes (href, src, action, etc.)
- Extract inline JavaScript code from <script> tags
- Extract legitimate filenames with valid extensions (e.g., image.jpg, script.js)
- Support multiple HTML parser backends (lxml, html.parser, html5lib, html5-parser)
"""


def extract_urls_from_html(html_string, placeholder='FUZZ', html_parser='lxml'):
    """
    Parse HTML and extract URLs from common attributes.

    Args:
        html_string: String containing HTML markup
        placeholder: String for unknown values (default: 'FUZZ')
        html_parser: Parser backend for BeautifulSoup (default: 'lxml')
                    Options: 'lxml', 'html.parser', 'html5lib', 'html5-parser'

    Returns:
        List of entry dictionaries with URL information

    Extracts from:
        - <a href="...">
        - <link href="...">
        - <base href="...">
        - <area href="...">
        - <img src="...">
        - <script src="...">
        - <iframe src="...">
        - <embed src="...">
        - <source src="...">
        - <track src="...">
        - <video src="..." poster="...">
        - <audio src="...">
        - <input src="...">
        - <form action="...">
        - <button formaction="...">
        - <object data="..." codebase="...">
        - <blockquote cite="...">
        - <q cite="...">
        - <ins cite="...">
        - <del cite="...">
        - <use href="..." xlink:href="...">
        - <img srcset="..."> (responsive images)
        - data-src, data-url, data-href (lazy loading patterns)
    """
    entries = []

    try:
        # Parse HTML with specified parser, fallback to html.parser if parser unavailable
        try:
            soup = BeautifulSoup(html_string, html_parser)
        except Exception:
            # Fallback to built-in parser if specified parser not available
            soup = BeautifulSoup(html_string, 'html.parser')

        # Define attribute mappings: tag -> attributes (can be list for multiple attrs)
        url_extractors = [
            ('a', ['href']),
            ('link', ['href']),
            ('base', ['href']),
            ('area', ['href']),
            ('img', ['src', 'srcset', 'data-src']),
            ('script', ['src', 'data-src']),
            ('form', ['action']),
            ('button', ['formaction']),
            ('iframe', ['src', 'data-src']),
            ('video', ['src', 'poster', 'data-src']),
            ('audio', ['src', 'data-src']),
            ('source', ['src', 'srcset']),
            ('track', ['src']),
            ('embed', ['src']),
            ('input', ['src']),
            ('object', ['data', 'codebase']),
            ('blockquote', ['cite']),
            ('q', ['cite']),
            ('ins', ['cite']),
            ('del', ['cite']),
            ('use', ['href', 'xlink:href']),
        ]

        # Also check for common data attributes on any tag
        data_attrs = ['data-url', 'data-href', 'data-src']

        # Extract URLs from each tag type
        for tag_name, attr_names in url_extractors:
            for tag in soup.find_all(tag_name):
                for attr_name in attr_names:
                    url = tag.get(attr_name)
                    if url and url.strip():
                        # Handle srcset (multiple URLs separated by commas)
                        if attr_name == 'srcset':
                            # srcset format: "url1 1x, url2 2x" or "url1 100w, url2 200w"
                            urls = [u.strip().split()[0] for u in url.split(',')]
                        else:
                            urls = [url.strip()]

                        for u in urls:
                            # Skip common non-URLs
                            if u.startswith('#') or u.startswith('javascript:') or u.startswith('data:'):
                                continue

                            # Check if it's a URL/path pattern
                            # is_path_pattern() now includes is_filename_pattern() check
                            if is_url_pattern(u) or is_path_pattern(u):
                                entry = {
                                    'original': u,
                                    'placeholder': u,
                                    'resolved': u,
                                    'has_template': False
                                }
                                entries.append(entry)

        # Extract from data-* attributes on all tags
        for tag in soup.find_all(True):  # True matches all tags
            for data_attr in data_attrs:
                url = tag.get(data_attr)
                if url and url.strip():
                    url = url.strip()

                    # Skip common non-URLs
                    if url.startswith('#') or url.startswith('javascript:') or url.startswith('data:'):
                        continue

                    # Check if it's a URL/path pattern
                    # is_path_pattern() now includes is_filename_pattern() check
                    if is_url_pattern(url) or is_path_pattern(url):
                        entry = {
                            'original': url,
                            'placeholder': url,
                            'resolved': url,
                            'has_template': False
                        }
                        entries.append(entry)

    except Exception:
        # If HTML parsing fails, silently skip
        # (avoid breaking extraction for malformed HTML)
        pass

    return entries


def extract_inline_scripts_from_html(html_string, html_parser='lxml'):
    """
    Extract inline JavaScript code from <script> tags.

    Args:
        html_string: String containing HTML markup
        html_parser: Parser backend for BeautifulSoup (default: 'lxml')
                    Options: 'lxml', 'html.parser', 'html5lib', 'html5-parser'

    Returns:
        List of JavaScript code strings to be parsed with tree-sitter
    """
    inline_scripts = []

    try:
        # Parse HTML with specified parser, fallback to html.parser if parser unavailable
        try:
            soup = BeautifulSoup(html_string, html_parser)
        except Exception:
            # Fallback to built-in parser if specified parser not available
            soup = BeautifulSoup(html_string, 'html.parser')

        # Extract inline JavaScript from <script> tags (without src attribute)
        for script_tag in soup.find_all('script'):
            # Only process inline scripts (no src attribute)
            if not script_tag.get('src') and script_tag.string:
                js_code = script_tag.string.strip()
                if js_code:
                    inline_scripts.append(js_code)

    except Exception:
        # If HTML parsing fails, silently skip
        pass

    return inline_scripts
