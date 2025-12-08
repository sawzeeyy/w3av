import re
import importlib.resources

"""
URL pattern detection utilities.

Shared functions for detecting URLs and paths in various contexts.
Used by both the HTML parser and JavaScript string extraction.
"""


# Cache for file extensions
_file_extensions = None


def load_file_extensions():
    """
    Loads valid file extensions from config/file-extensions.txt.
    Returns a set of extensions (without dots).
    Cached after first load.
    """
    global _file_extensions

    if _file_extensions is not None:
        return _file_extensions

    extensions = set()
    with importlib.resources.files('weav.config').joinpath('file-extensions.txt').open('r') as file:
        for line in file:
            ext = line.strip()
            if ext:
                extensions.add(ext.lower())

    _file_extensions = extensions
    return _file_extensions


def is_filename_pattern(text):
    """
    Detects if text is a legitimate filename with a valid extension.

    Matches:
    - Simple filenames: config.json, styles.css, image.png
    - Complex filenames: my-file.tar.gz, document_v2.pdf
    - Filenames with multiple dots: jquery.min.js, bootstrap.bundle.min.css

    Rejects:
    - Too generic: single letter before extension (a.js, x.pdf)
    - Property access: object.property, window.location
    - No extension: just_a_word
    - Timezone-like: Europe/Bucharest (handled elsewhere)
    """
    if not text or not isinstance(text, str):
        return False

    # Must not contain path separators (those are paths, not filenames)
    if '/' in text or '\\' in text:
        return False

    # Must have at least one dot
    if '.' not in text:
        return False

    # Get the extension (everything after the last dot)
    parts = text.rsplit('.', 1)
    if len(parts) != 2:
        return False

    basename, extension = parts

    # Reject if basename is too short (likely property access like 'a.b')
    # Allow at least 2 characters or common single-char prefixes with numbers
    if len(basename) < 2 and not re.match(r'^[a-zA-Z]\d+$', basename):
        return False

    # Check if extension is valid
    extensions = load_file_extensions()

    # Handle compound extensions like .tar.gz
    # Check both the final extension and the compound extension
    if extension.lower() in extensions:
        return True

    # Check for compound extensions (e.g., tar.gz, min.js)
    if '.' in basename:
        compound_ext = basename.split('.')[-1] + '.' + extension
        if compound_ext.lower() in extensions:
            return True

    return False


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
    - Filenames: config.json, styles.css, image.png
    - URLs with query strings: example.com?query=value

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

    # Check if it's a legitimate filename with valid extension
    if is_filename_pattern(text):
        return True

    # If it has query parameters, check the base part
    # This handles cases like: /path?query, path?query, domain.com?query
    if '?' in text:
        # Extract base (before ?)
        base = text.split('?')[0]
        if not base:
            return False
        # Check if base is a valid URL or path
        # For query params, we're more lenient - just need something before the ?
        if base.startswith('/'):
            return True  # Any path with query is valid
        elif '/' in base:
            return True  # Paths like 'api/users?query'
        elif '.' in base:
            return True  # Domains like 'example.com?query'
        # Single word before ? (like 'ABC?query') - check if it looks URL-like
        # Allow it if it has other URL indicators in the full text
        return len(base) >= 2  # Minimum length for base part

    # Absolute paths (minimum 2 chars after /)
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
