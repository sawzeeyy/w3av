"""
URL filtering and cleaning functions.

Handles junk URL detection, bracket balancing, and placeholder consolidation.
"""
import re

from .config import load_mime_types, get_custom_extensions
from sawari.core.url_utils import is_filename_pattern

# Pre-compiled regex patterns at module level for performance
# These patterns are used repeatedly in is_junk_url() - compiling once saves time

_MIME_TYPE_PREFIX_PATTERN = re.compile(r'^(application|text|image|audio|video|font|multipart)/')
_STANDALONE_PROTOCOL_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://?$')
_PROPERTY_PATH_PATTERN = re.compile(r'^[a-z]+\.[a-z]+\.[a-z.]+$', re.IGNORECASE)
_GENERIC_SINGLE_PARAM_PATTERN = re.compile(r'^/\{[^}]+\}$')

# Date format patterns (yyyy/mm/dd, dd/mm/yyyy, mm/dd/yyyy variants)
_DATE_YMD_PATTERN = re.compile(
    r'^/+(yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})[/-]'
    r'(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-]'
    r'(dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})/?$',
    re.IGNORECASE
)
_DATE_DMY_PATTERN = re.compile(
    r'^/+(dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-]'
    r'(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-]'
    r'(yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$',
    re.IGNORECASE
)
_DATE_MDY_PATTERN = re.compile(
    r'^/+(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-]'
    r'(dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-]'
    r'(yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$',
    re.IGNORECASE
)
_TIME_FORMAT_PATTERN = re.compile(
    r'^/+(hh|HH|h|H|\{hh\}|\{HH\}|\{h\}|\{H\}):'
    r'(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})'
    r'(:(ss|SS|s|S|\{ss\}|\{SS\}|\{s\}|\{S\}))?/?$',
    re.IGNORECASE
)

# IANA timezone pattern
_TIMEZONE_PATTERN = re.compile(
    r'^(Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific|Etc|US|Canada|Mexico|Brazil|Chile)/'
    r'[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)?(\|.+)?$'
)

# Standalone date formats (without leading slash)
_STANDALONE_DATE_PATTERN = re.compile(
    r'^(yyyy|YYYY|yy|YY|mm|MM|m|M|dd|DD|d|D)[/\-]'
    r'(yyyy|YYYY|yy|YY|mm|MM|m|M|dd|DD|d|D)[/\-]'
    r'(yyyy|YYYY|yy|YY|mm|MM|m|M|dd|DD|d|D)$',
    re.IGNORECASE
)

# Regex backreference pattern
_REGEX_BACKREFERENCE_PATTERN = re.compile(r'\$\d')

# Alphanumeric content check
_HAS_ALPHANUMERIC_PATTERN = re.compile(r'[a-zA-Z0-9]')

# CSS unit pattern (placeholder-independent part, we combine with placeholder at check time)
_CSS_UNITS = ('px', 'em', 'rem', '%', 'vh', 'vw', 'vmin', 'vmax', 'ch', 'ex', 'pt', 'pc', 'in', 'cm', 'mm', 'deg', 'rad', 'turn', 's', 'ms')

# JavaScript API patterns (pre-compiled list)
_JS_API_PATTERNS = [
    re.compile(r'^(Function|Object|Array|String|Number|Boolean|Symbol|Map|Set|WeakMap|WeakSet|Promise|Proxy|Reflect)\.'),
    re.compile(r'^(moment|Immutable|Redux|React|Vue|Angular)\.'),
    re.compile(r'\.prototype\.'),
    re.compile(r'\.(bind|call|apply|toString|valueOf)\s*$'),
]

# Pre-computed sets for O(1) exact match lookups
_JUNK_EXACT_MATCHES = frozenset({
    'http://', 'https://', '//', 'https:', 'http:',
    'http://localhost', 'http://a', 'http://test/path',
    './', '/?', '/', '#',
})

# Fast prefix checks (tuple for startswith)
_JUNK_PREFIXES = (
    'http://www.w3.org/',  # W3C/XML namespaces
)


def clean_unbalanced_brackets(text):
    """
    Removes trailing unbalanced brackets/parentheses from URLs.

    Uses balanced brackets algorithm to detect mismatched closing brackets.
    Example: 'https://github.com/repo)' -> 'https://github.com/repo'
    """
    if not text or not isinstance(text, str):
        return text

    brackets = {'(': ')', '[': ']', '{': '}'}
    closing = set(brackets.values())
    stack = []
    valid_length = len(text)

    for i, char in enumerate(text):
        if char in brackets:
            stack.append((char, i))
        elif char in closing:
            if stack and brackets[stack[-1][0]] == char:
                stack.pop()
            else:
                # Unbalanced closing bracket - truncate here
                valid_length = i
                break

    return text[:valid_length]


def clean_trailing_sentence_punctuation(text):
    """
    Removes trailing sentence punctuation from URLs that is likely not part of the URL.

    A trailing period/comma is removed when it appears to be sentence punctuation:
    - After a path ending with / (e.g., 'http://example.com/path/.')
    - After a fragment (e.g., 'http://example.com/#section.')
    - After common non-extension endings (numbers, hyphens)

    Does NOT remove period if it looks like a file extension:
    - 'http://example.com/file.html' - keeps .html
    - 'http://example.com/LICENSE-2.0' - keeps as-is (no trailing period)
    """
    if not text or not isinstance(text, str):
        return text

    # Only process if ends with sentence punctuation
    if not text.endswith(('.', ',')):
        return text

    # Remove trailing punctuation
    cleaned = text.rstrip('.,')

    # If the cleaned URL ends with / or # or ), the punctuation was definitely sentence-level
    if cleaned.endswith(('/', '#', ')')):
        return cleaned

    # If the last segment (after last /) doesn't look like a file with extension, strip it
    # e.g., "LICENSE-2.0." -> "LICENSE-2.0" (the . was punctuation, not extension)
    last_slash = cleaned.rfind('/')
    if last_slash >= 0:
        last_segment = cleaned[last_slash + 1:]
        # If there's no dot in the last segment, the trailing dot was punctuation
        if '.' not in last_segment:
            return cleaned
        # If there's a dot but it's part of a version number (e.g., 2.0), strip trailing punct
        # Check if what's after the last dot in segment is not a typical extension
        last_dot = last_segment.rfind('.')
        if last_dot >= 0:
            potential_ext = last_segment[last_dot + 1:]
            # Common extensions are 2-4 chars, alphanumeric
            if not (2 <= len(potential_ext) <= 4 and potential_ext.isalnum()):
                return cleaned

    return cleaned


def is_junk_url(text, placeholder='FUZZ', mime_types=None):
    """
    Filters out non-URL strings that shouldn't be in results.

    Rejects:
    - MIME types
    - Incomplete protocols (http://, https://, //)
    - Property paths (action.target.name, util.promisify.custom)
    - W3C namespace URIs
    - Single-parameter paths (/{t}, /{a})
    - Generic test URLs
    - Date/time format placeholders
    - IANA timezone identifiers
    """
    if not text or not isinstance(text, str):
        return True

    # Fast path: very short strings unlikely to be URLs
    text_len = len(text)
    if text_len < 2:
        return True

    # Fast path: exact match check (O(1) hash lookup)
    if text in _JUNK_EXACT_MATCHES:
        return True

    # Fast path: prefix check
    if text.startswith(_JUNK_PREFIXES):
        return True

    # Load MIME types if not provided (cached after first call)
    if mime_types is None:
        mime_types = load_mime_types()

    # MIME types (exact match or with parameters)
    base_mime = text.split(';')[0].split(',')[0].strip()
    if base_mime in mime_types:
        return True

    # Starts with MIME type pattern
    if _MIME_TYPE_PREFIX_PATTERN.match(text):
        return True

    # Any standalone protocol (protocol:// with nothing after, e.g., file://, ftp://)
    if _STANDALONE_PROTOCOL_PATTERN.match(text):
        return True

    # Protocol + only placeholder (no actual domain/path info)
    # Matches: https://FUZZ, https://FUZZ/, http://FUZZ, http://FUZZ/
    # But NOT template variables like https://{domain} which are meaningful
    if text == f'https://{placeholder}' or text == f'https://{placeholder}/' or \
       text == f'http://{placeholder}' or text == f'http://{placeholder}/':
        return True

    # Property paths (word.word.word without slashes)
    # BUT exclude legitimate filenames with valid extensions
    if _PROPERTY_PATH_PATTERN.match(text) and '/' not in text:
        # Check if it's a valid filename first
        if not is_filename_pattern(text, get_custom_extensions()):
            return True

    # Generic single-parameter paths
    if _GENERIC_SINGLE_PARAM_PATTERN.match(text):  # /{t}, /{a}, /{n.pathname}
        return True

    # Too generic paths (placeholder-dependent, must check at runtime)
    if text in (f'/{placeholder}', f'//{placeholder}'):
        return True

    # Paths that are only placeholders separated by slashes (no actual path info)
    # Examples: FUZZ/FUZZ, FUZZ/FUZZ/FUZZ/FUZZ/FUZZ
    if re.match(f'^{re.escape(placeholder)}(/{re.escape(placeholder)})+$', text):
        return True

    # Date/time format placeholders (no actual value)
    # Examples: /yyyy/mm/dd/, /YYYY/MM/DD/, /yyyy-mm-dd/, /dd/mm/yyyy/
    # Also catches template versions: /yyyy/{mm}/{dd}/, /{yyyy}/{mm}/{dd}/
    if _DATE_YMD_PATTERN.match(text):
        return True
    if _DATE_DMY_PATTERN.match(text):
        return True
    if _DATE_MDY_PATTERN.match(text):
        return True
    # Time format placeholders: /hh:mm:ss/, /HH:MM/, /{hh}:{mm}/, etc.
    if _TIME_FORMAT_PATTERN.match(text):
        return True

    # IANA timezone identifiers and timezone data strings (from libraries like moment-timezone)
    # Matches both clean identifiers (Europe/London) and data entries (Africa/Abidjan|LMT GMT|...)
    # Also covers nested timezones (America/Argentina/Buenos_Aires) and legacy aliases (US/Eastern)
    if _TIMEZONE_PATTERN.match(text):
        return True

    # Standalone date format patterns (without leading slash)
    # Examples: MM/DD/YYYY, DD/MM/YYYY, YYYY/MM/DD, YYYY-MM-DD
    if _STANDALONE_DATE_PATTERN.match(text):
        return True

    # Regex replacement patterns (e.g., (/$1)?$2, $1/$2)
    # These contain $ followed by digits which are regex backreferences
    if _REGEX_BACKREFERENCE_PATTERN.search(text):
        return True

    # CSS unit patterns (e.g., FUZZpx, FUZZ%, FUZZem, FUZZrem, FUZZvh, FUZZvw)
    # These come from template strings like `${value}px`
    # Use string operations instead of regex for speed
    if text.startswith(placeholder) and text[len(placeholder):] in _CSS_UNITS:
        return True

    # Non-meaningful placeholder strings
    # After stripping the placeholder, if only symbols remain (no alphanumeric chars), it's junk
    # Examples: ^FUZZ$ -> ^$, /*FUZZ*FUZZ -> /**, /?([^\/]+)? -> /?([^\/]+)?
    stripped = text.replace(placeholder, '')
    if stripped and not _HAS_ALPHANUMERIC_PATTERN.search(stripped):
        return True

    # JavaScript standard library patterns (not URLs)
    # Matches: Function.prototype.bind, Object.prototype.hasOwnProperty, etc.
    if any(pattern.search(text) for pattern in _JS_API_PATTERNS):
        return True

    # Incomplete strings ending with unclosed quotes or parentheses
    # These are concatenation artifacts from template expansion
    text_stripped = text.rstrip()
    if text_stripped.endswith(("'", '"', '(')):
        return True

    # Strings containing quote characters mid-string (likely error messages, not URLs)
    # But allow: URLs, template expressions starting with {, and paths
    if len(text) > 3:
        inner_text = text[1:-1]
        if ("'" in inner_text or '"' in inner_text):
            # Allow if it's a valid URL starting pattern or template expression
            if not text.startswith(('http://', 'https://', '/', './', '../', '{')):
                return True

    return False


def consolidate_adjacent_placeholders(text, placeholder='FUZZ'):
    """
    Consolidates adjacent placeholders into a single placeholder.

    Example: 'FUZZFUZZ' -> 'FUZZ', '/spaces/FUZZFUZZ' -> '/spaces/FUZZ'

    This handles cases where adjacent template expressions like {t}{i}
    get replaced to become FUZZFUZZ without separators.
    """
    if not text or placeholder not in text:
        return text

    # Replace 2+ consecutive placeholders with single placeholder
    pattern = f'({re.escape(placeholder)}){{2,}}'
    return re.sub(pattern, placeholder, text)
