"""
URL pattern detection utilities.

Shared functions for detecting URLs and paths in various contexts.
Used by both the HTML parser and JavaScript string extraction.
"""

import re


def is_url_pattern(text):
    """
    Detects if text is a URL with protocol or common indicators.

    Matches:
    - Protocol URLs: http://, ftp://, custom:// (RFC 3986 URI schemes)
    - Protocol-relative: //example.com
    - Common prefixes: www., api., cdn.
    - Domain-only patterns: example.com, api.github.com
    - IP addresses: 192.168.1.1, 10.0.0.1, 127.0.0.1
    - IP with protocol: http://192.168.1.1, https://10.0.0.1:8080
    """
    if not text or not isinstance(text, str):
        return False

    # Protocol URLs
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', text):
        return True

    # Protocol-relative
    if text.startswith('//'):
        return True

    # Common prefixes
    if re.match(r'^(www\.|api\.|cdn\.)', text, re.IGNORECASE):
        return True

    # IP addresses (with optional port)
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?(/|$)', text):
        return True

    # Domain patterns (at least one dot, valid TLD-like structure)
    # Require either: a known TLD, a slash after domain, or port number
    # Reject: single-word domains, Vue directives, object properties
    if re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', text):  # Has TLD
        return True
    if re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+/', text):  # Has path after domain
        return True

    # Reject common false positives
    if re.match(r'^[a-z]+\.[a-z]+$', text, re.IGNORECASE):
        # Simple word.word (like mr.flatpickr, user.firstname)
        return False

    return False


def is_path_pattern(text):
    """
    Detects if text is a file system path or API endpoint.

    Matches:
    - Absolute paths: /api/users, /profile (minimum 2 chars after /)
    - Paths with query strings: /cgraphql?q=SessionDataQuery
    - Paths with fragments: /page#section
    - Relative paths: ./file, ../dir
    - API paths: api/users, v1/endpoint

    Rejects:
    - Single word with trailing slash: mrFlatpickr/
    - Protocol-relative URLs: //cdn.example.com (handled by is_url_pattern)
    - Very short paths: /e (too generic)
    """
    if not text or not isinstance(text, str):
        return False

    # Reject protocol-relative URLs
    if text.startswith('//'):
        return False

    # Absolute paths (minimum 2 chars after /, allowing query/fragment)
    # Match: /path, /path/more, /path?query, /path#hash, /path?q#h
    if re.match(r'^/[a-zA-Z0-9_-]{2,}', text):
        return True

    # Relative paths
    if re.match(r'^\.\.?/', text):
        return True

    # API paths (word/word pattern)
    if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*/[a-zA-Z0-9]', text):
        return True

    return False
