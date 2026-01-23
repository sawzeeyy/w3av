"""
URL filtering and cleaning functions.

Handles junk URL detection, bracket balancing, and placeholder consolidation.
"""
import re

from .config import load_mime_types, get_custom_extensions
from w3av.core.url_utils import is_filename_pattern


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

    # Load MIME types if not provided
    if mime_types is None:
        mime_types = load_mime_types()

    # MIME types (exact match or with parameters)
    base_mime = text.split(';')[0].split(',')[0].strip()
    if base_mime in mime_types:
        return True

    # Starts with MIME type pattern
    if re.match(r'^(application|text|image|audio|video|font|multipart)/', text):
        return True

    # Incomplete protocols only
    if text in ['http://', 'https://', '//', 'https:', 'http:']:
        return True

    # Protocol + only placeholder (no actual domain/path info)
    # Matches: https://FUZZ, https://FUZZ/, http://FUZZ, http://FUZZ/
    # But NOT template variables like https://{domain} which are meaningful
    if text == f'https://{placeholder}' or text == f'https://{placeholder}/' or \
       text == f'http://{placeholder}' or text == f'http://{placeholder}/':
        return True

    # Property paths (word.word.word without slashes)
    # BUT exclude legitimate filenames with valid extensions
    if re.match(r'^[a-z]+\.[a-z]+\.[a-z.]+$', text, re.IGNORECASE) and '/' not in text:
        # Check if it's a valid filename first
        if not is_filename_pattern(text, get_custom_extensions()):
            return True

    # W3C/XML namespaces
    if text.startswith('http://www.w3.org/'):
        return True

    # Generic single-parameter paths
    if re.match(r'^/\{[^}]+\}$', text):  # /{t}, /{a}, /{n.pathname}
        return True

    # Generic localhost/test URLs
    if text in ['http://localhost', 'http://a', 'http://test/path']:
        return True

    # Too generic paths
    if text in ['./', f'/{placeholder}', f'//{placeholder}']:
        return True

    # Paths that are only placeholders separated by slashes (no actual path info)
    # Examples: FUZZ/FUZZ, FUZZ/FUZZ/FUZZ/FUZZ/FUZZ
    if re.match(f'^{re.escape(placeholder)}(/{re.escape(placeholder)})+$', text):
        return True

    # Date/time format placeholders (no actual value)
    # Examples: /yyyy/mm/dd/, /YYYY/MM/DD/, /yyyy-mm-dd/, /dd/mm/yyyy/
    # Also catches template versions: /yyyy/{mm}/{dd}/, /{yyyy}/{mm}/{dd}/
    if re.match(r'^/+(yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})[/-](mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})/?$', text, re.IGNORECASE):
        return True
    if re.match(r'^/+(dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-](mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$', text, re.IGNORECASE):
        return True
    if re.match(r'^/+(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-](yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$', text, re.IGNORECASE):
        return True
    # Time format placeholders: /hh:mm:ss/, /HH:MM/, /{hh}:{mm}/, etc.
    if re.match(r'^/+(hh|HH|h|H|\{hh\}|\{HH\}|\{h\}|\{H\}):(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})(:(ss|SS|s|S|\{ss\}|\{SS\}|\{s\}|\{S\}))?/?$', text, re.IGNORECASE):
        return True

    # IANA timezone identifiers and timezone data strings (from libraries like moment-timezone)
    # Matches both clean identifiers (Europe/London) and data entries (Africa/Abidjan|LMT GMT|...)
    # Also covers nested timezones (America/Argentina/Buenos_Aires) and legacy aliases (US/Eastern)
    if re.match(r'^(Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific|Etc|US|Canada|Mexico|Brazil|Chile)/[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)?(\|.+)?$', text):
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
