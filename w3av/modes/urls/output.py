"""
Output formatting and route parameter conversion.

Handles final URL formatting, route parameter conversion, and HTML detection.
"""
import re

from .filters import clean_unbalanced_brackets, is_junk_url


def convert_route_params(text, placeholder='FUZZ'):
    """
    Converts route parameters to template syntax.
    Handles: :id -> {id}, [param] -> {param}
    Returns (original_text, converted_text, has_params).

    Examples:
        '/users/:id' -> ('/users/:id', '/users/{id}', True)
        'archives/vendor-list-v[VERSION].json' -> ('archives/vendor-list-v[VERSION].json', 'archives/vendor-list-v{VERSION}.json', True)
        '/blog/:slug/comments/:commentId' -> ('/blog/:slug/comments/:commentId', '/blog/{slug}/comments/{commentId}', True)
        '/static/path' -> ('/static/path', '/static/path', False)
        'https://user:pass@host' -> ('https://user:pass@host', 'https://user:pass@host', False)  # Don't match auth colons
    """
    has_params = False
    converted = text

    # Check if this looks like a URL with authentication (contains ://...@)
    # If so, skip route param conversion entirely to avoid matching auth colons
    if re.search(r'://[^/]*@', text):
        # Has URL authentication, don't convert route params
        # because we might accidentally match username:password
        pass
    else:
        # No authentication, safe to match route params
        # Match : followed by identifier, but only when preceded by /
        # This catches /api/:id but not plain user:password
        route_param_pattern = r'/:([a-zA-Z_][a-zA-Z0-9_]*)'
        if re.search(route_param_pattern, converted):
            converted = re.sub(route_param_pattern, r'/{\1}', converted)
            has_params = True

    # Match bracket parameters like [VERSION], [ID], [param]
    bracket_param_pattern = r'\[([a-zA-Z_][a-zA-Z0-9_]*)\]'
    if re.search(bracket_param_pattern, converted):
        converted = re.sub(bracket_param_pattern, r'{\1}', converted)
        has_params = True

    return (text, converted, has_params)


def is_html_content(text):
    """
    Detect if the input is HTML content.
    Checks for common HTML patterns at the start of the content.
    """
    if not text:
        return False

    text_stripped = text.strip()
    if not text_stripped:
        return False

    # Check for common HTML indicators
    html_indicators = [
        '<!DOCTYPE html',
        '<!doctype html',
        '<html',
        '<HTML',
        '<head',
        '<HEAD',
        '<body',
        '<BODY',
    ]

    text_lower = text_stripped[:200].lower()

    # Check for DOCTYPE or html/head/body tags near the start
    for indicator in html_indicators:
        if indicator.lower() in text_lower:
            return True

    # Check if it starts with <script> or <html-like> tags
    if text_stripped.startswith('<') and '>' in text_stripped[:100]:
        # Has opening tag structure
        first_tag_end = text_stripped.find('>')
        if first_tag_end > 0:
            first_tag = text_stripped[:first_tag_end + 1]
            # Check if it looks like an HTML tag (not just a comparison operator)
            if '<script' in first_tag.lower() or first_tag.count('<') == 1:
                return True

    return False


def format_output(url_entries, include_templates, placeholder, mime_types=None):
    """
    Formats final output based on template inclusion flag.

    Parameters:
    - url_entries: List of URL entry dictionaries
    - include_templates: Whether to include templated URLs with {var} syntax
    - placeholder: Placeholder string (default: 'FUZZ')
    - mime_types: Optional set of MIME types for junk filtering

    Returns:
    - List of deduplicated, filtered URLs
    """
    results = []

    for entry in url_entries:
        # Filter out useless entries (bare FUZZ with no resolved value)
        if entry.get('placeholder') == placeholder and not entry.get('resolved'):
            continue

        if include_templates:
            # Include ALL URLs: static URLs, original template syntax, AND placeholder versions
            original = clean_unbalanced_brackets(entry.get('original', ''))
            placeholder_val = clean_unbalanced_brackets(entry.get('placeholder', ''))

            if entry.get('has_template', False):
                # Has template - add BOTH original ({x} syntax) AND placeholder (FUZZ) version
                if original and not is_junk_url(original, placeholder, mime_types) and original not in results:
                    results.append(original)
                if placeholder_val and not is_junk_url(placeholder_val, placeholder, mime_types) and placeholder_val not in results and placeholder_val != original:
                    results.append(placeholder_val)
            else:
                # Static URL - just add it once
                if placeholder_val and not is_junk_url(placeholder_val, placeholder, mime_types) and placeholder_val not in results:
                    results.append(placeholder_val)
        else:
            # Only include static URLs or resolved placeholder versions (no {x} syntax)
            if not entry.get('has_template', False):
                # Static URL - use as-is
                output = clean_unbalanced_brackets(entry.get('resolved', entry.get('original', '')))
                if output and not is_junk_url(output, placeholder, mime_types) and output not in results:
                    results.append(output)
            else:
                # Has template - use placeholder version (with FUZZ), NOT original (with {})
                placeholder_val = clean_unbalanced_brackets(entry.get('placeholder', ''))

                # Only include if we successfully replaced template markers
                if placeholder_val and '{' not in placeholder_val and not is_junk_url(placeholder_val, placeholder, mime_types) and placeholder_val not in results:
                    results.append(placeholder_val)

    return results
