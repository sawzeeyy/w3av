"""
Tests for junk URL pattern filtering.

Covers:
- Standalone protocols
- Regex backreferences
- CSS unit patterns
- Non-meaningful placeholders
- JavaScript API patterns
- Standalone date formats
- Query string only
- Unclosed quotes and parentheses
- Prose with quotes
- Enhanced timezone filtering
"""

import pytest

from sawari.modes.urls import is_junk_url


class TestStandaloneProtocols:
    """Test filtering of standalone protocols."""

    def test_standalone_protocols_filtered(self):
        """Standalone protocols without content should be filtered."""
        assert is_junk_url('file://') == True
        assert is_junk_url('ftp://') == True
        assert is_junk_url('ws://') == True
        assert is_junk_url('wss://') == True
        assert is_junk_url('blob://') == True
        assert is_junk_url('chrome://') == True

    def test_protocols_with_content_kept(self):
        """Protocols with actual content should NOT be filtered."""
        assert is_junk_url('file:///path/to/file') == False
        assert is_junk_url('ftp://example.com/file.zip') == False
        assert is_junk_url('ws://example.com/socket') == False


class TestRegexBackreferences:
    """Test filtering of regex replacement patterns."""

    def test_backreferences_filtered(self):
        """Strings with regex backreferences ($1, $2) should be filtered."""
        assert is_junk_url('(/$1)?$2') == True
        assert is_junk_url('$1/$2') == True
        assert is_junk_url('/path/$1/data') == True
        assert is_junk_url('prefix$1suffix') == True

    def test_dollar_without_digit_kept(self):
        """Dollar signs not followed by digits should be kept."""
        assert is_junk_url('/api/price/$amount') == False
        assert is_junk_url('/shop/$category/items') == False


class TestCSSUnitPatterns:
    """Test filtering of CSS unit patterns."""

    def test_css_units_filtered(self):
        """Placeholder followed by CSS unit should be filtered."""
        assert is_junk_url('FUZZpx', 'FUZZ') == True
        assert is_junk_url('FUZZ%', 'FUZZ') == True
        assert is_junk_url('FUZZem', 'FUZZ') == True
        assert is_junk_url('FUZZrem', 'FUZZ') == True
        assert is_junk_url('FUZZvh', 'FUZZ') == True
        assert is_junk_url('FUZZvw', 'FUZZ') == True
        assert is_junk_url('FUZZdeg', 'FUZZ') == True
        assert is_junk_url('FUZZms', 'FUZZ') == True

    def test_valid_paths_with_similar_endings_kept(self):
        """Valid paths that happen to end similarly should be kept."""
        assert is_junk_url('/api/FUZZpixels', 'FUZZ') == False
        assert is_junk_url('/path/to/FUZZembed', 'FUZZ') == False


class TestNonMeaningfulPlaceholders:
    """Test filtering of strings that become only symbols after placeholder removal."""

    def test_symbols_only_filtered(self):
        """Strings with only symbols after removing placeholder should be filtered."""
        assert is_junk_url('^FUZZ$', 'FUZZ') == True
        assert is_junk_url('/*FUZZ*/', 'FUZZ') == True
        assert is_junk_url('FUZZ?', 'FUZZ') == True
        assert is_junk_url('[FUZZ]', 'FUZZ') == True

    def test_alphanumeric_content_kept(self):
        """Strings with alphanumeric content after placeholder removal should be kept."""
        assert is_junk_url('/api/FUZZ/users', 'FUZZ') == False
        assert is_junk_url('FUZZ/data', 'FUZZ') == False
        assert is_junk_url('prefix-FUZZ-suffix', 'FUZZ') == False


class TestJSAPIPatterns:
    """Test filtering of JavaScript API patterns."""

    def test_js_builtin_prototypes_filtered(self):
        """JavaScript built-in prototype patterns should be filtered."""
        assert is_junk_url('Function.prototype.bind') == True
        assert is_junk_url('Object.prototype.hasOwnProperty') == True
        assert is_junk_url('Array.prototype.slice') == True
        assert is_junk_url('String.prototype.split') == True

    def test_js_library_patterns_filtered(self):
        """Common JS library patterns should be filtered."""
        assert is_junk_url('React.Component') == True
        assert is_junk_url('Vue.component') == True
        assert is_junk_url('moment.locale') == True

    def test_similar_looking_urls_kept(self):
        """URLs that look similar but are valid should be kept."""
        assert is_junk_url('https://api.example.com/Function/data') == False
        assert is_junk_url('/api/Object/details') == False


class TestStandaloneDateFormats:
    """Test filtering of standalone date format patterns."""

    def test_date_formats_filtered(self):
        """Standalone date format patterns should be filtered."""
        assert is_junk_url('MM/DD/YYYY') == True
        assert is_junk_url('DD/MM/YYYY') == True
        assert is_junk_url('YYYY/MM/DD') == True
        assert is_junk_url('YYYY-MM-DD') == True
        assert is_junk_url('mm/dd/yy') == True

    def test_date_patterns_in_paths_kept(self):
        """Date patterns within valid paths should be kept."""
        assert is_junk_url('/api/YYYY/MM/DD/posts') == False
        assert is_junk_url('/archive/2024/12/07') == False


class TestQueryStringOnly:
    """Test filtering of query-string-only patterns."""

    def test_query_only_filtered(self):
        """Query string without path should be filtered."""
        assert is_junk_url('/?') == True

    def test_valid_query_strings_kept(self):
        """Valid paths with query strings should be kept."""
        assert is_junk_url('/?query=value') == False
        assert is_junk_url('/api?param=1') == False


class TestUnclosedQuotesAndParens:
    """Test filtering of strings with unclosed quotes or parentheses."""

    def test_trailing_quote_filtered(self):
        """Strings ending with unclosed quote should be filtered."""
        assert is_junk_url("/path/to/file'") == True
        assert is_junk_url('/api/endpoint"') == True

    def test_trailing_paren_filtered(self):
        """Strings ending with unclosed parenthesis should be filtered."""
        assert is_junk_url('/api/call(') == True

    def test_balanced_quotes_kept(self):
        """Strings with balanced or no quotes should be kept."""
        assert is_junk_url('/api/endpoint') == False
        assert is_junk_url('/path/to/file') == False


class TestQuotesMidString:
    """Test filtering of prose/error messages with quotes inside."""

    def test_prose_with_quotes_filtered(self):
        """Error messages or prose containing quotes should be filtered."""
        assert is_junk_url("Cannot read property 'foo' of undefined") == True
        assert is_junk_url('Expected "value" to be defined') == True

    def test_urls_with_quotes_in_query_kept(self):
        """Valid URLs should be kept even with special chars."""
        assert is_junk_url('https://example.com/search?q=test') == False
        assert is_junk_url('/api/data') == False


class TestEnhancedTimezoneFilter:
    """Test enhanced timezone filtering including nested and data formats."""

    def test_nested_timezones_filtered(self):
        """Nested timezone identifiers should be filtered."""
        assert is_junk_url('America/Argentina/Buenos_Aires') == True
        assert is_junk_url('America/Indiana/Indianapolis') == True
        assert is_junk_url('America/Kentucky/Louisville') == True

    def test_legacy_timezone_aliases_filtered(self):
        """Legacy timezone aliases should be filtered."""
        assert is_junk_url('US/Eastern') == True
        assert is_junk_url('US/Pacific') == True
        assert is_junk_url('Canada/Eastern') == True
        assert is_junk_url('Etc/GMT+5') == True

    def test_timezone_data_with_pipe_filtered(self):
        """Timezone data strings with pipe separators should be filtered."""
        assert is_junk_url('Africa/Abidjan|LMT GMT|') == True
        assert is_junk_url('Europe/London|GMT BST|') == True

    def test_urls_with_timezone_like_paths_kept(self):
        """Valid URLs containing timezone-like patterns should be kept."""
        assert is_junk_url('https://example.com/America/New_York/weather') == False
        assert is_junk_url('/api/timezones/Europe/London') == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
