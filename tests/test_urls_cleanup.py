"""
Tests for URL cleanup utilities.

Covers:
- Trailing sentence punctuation cleanup
- Adjacent placeholder consolidation
- JavaScript escape sequence decoding
"""

import os
import pytest

from w3av.core.jsparser import parse_javascript
from w3av.modes.urls import (
    get_urls,
    clean_trailing_sentence_punctuation,
    consolidate_adjacent_placeholders,
    is_junk_url,
)


# Path to test fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'urls')


def parse_file(filename):
    """Helper to parse a JavaScript file from fixtures."""
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    _, root_node = parse_javascript(content)
    return root_node, len(content.encode('utf8'))


class TestTrailingSentencePunctuation:
    """Test trailing sentence punctuation cleanup."""

    def test_trailing_period_after_slash(self):
        """Period after path ending with / should be removed."""
        assert clean_trailing_sentence_punctuation('http://example.com/path/.') == 'http://example.com/path/'
        assert clean_trailing_sentence_punctuation('https://example.com/api/.') == 'https://example.com/api/'

    def test_trailing_period_after_fragment(self):
        """Period after fragment should be removed."""
        assert clean_trailing_sentence_punctuation('http://example.com/#section.') == 'http://example.com/#section'

    def test_trailing_comma_removed(self):
        """Trailing comma should be removed."""
        assert clean_trailing_sentence_punctuation('http://example.com/path,') == 'http://example.com/path'
        assert clean_trailing_sentence_punctuation('http://example.com/api/,') == 'http://example.com/api/'

    def test_file_extension_preserved(self):
        """Valid file extensions should NOT be removed."""
        assert clean_trailing_sentence_punctuation('http://example.com/file.html') == 'http://example.com/file.html'
        assert clean_trailing_sentence_punctuation('http://example.com/script.js') == 'http://example.com/script.js'
        assert clean_trailing_sentence_punctuation('http://example.com/style.css') == 'http://example.com/style.css'

    def test_version_number_preserved(self):
        """Version numbers like LICENSE-2.0 should be preserved."""
        assert clean_trailing_sentence_punctuation('http://example.com/LICENSE-2.0') == 'http://example.com/LICENSE-2.0'

    def test_edge_cases(self):
        """Edge cases should be handled gracefully."""
        assert clean_trailing_sentence_punctuation('') == ''
        assert clean_trailing_sentence_punctuation(None) == None
        assert clean_trailing_sentence_punctuation('no-punctuation') == 'no-punctuation'


class TestAdjacentPlaceholders:
    """Test handling of adjacent template expressions without separators."""

    def test_adjacent_template_expressions(self):
        node, file_size = parse_file('adjacent_placeholders.js')
        urls = get_urls(node, 'FUZZ', include_templates=True, verbose=False, file_size=file_size)

        # Should consolidate adjacent placeholders
        assert 'FUZZ/spaces/FUZZ' in urls
        assert '{prefix}/spaces/{key}{suffix ? `/${suffix}` : ""}' in urls

        # Should NOT include pure placeholder paths (filtered as junk)
        assert 'FUZZ/FUZZ' not in urls
        assert 'FUZZ/FUZZ/FUZZ/FUZZ/FUZZ' not in urls

    def test_consolidate_adjacent_placeholders_function(self):
        # Test the helper function directly
        assert consolidate_adjacent_placeholders('FUZZFUZZ', 'FUZZ') == 'FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/FUZZFUZZ', 'FUZZ') == 'FUZZ/FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/spaces/FUZZFUZZ', 'FUZZ') == 'FUZZ/spaces/FUZZ'
        assert consolidate_adjacent_placeholders('FUZZ/FUZZ/FUZZ/FUZZ/FUZZFUZZ', 'FUZZ') == 'FUZZ/FUZZ/FUZZ/FUZZ/FUZZ'

        # Test with custom placeholder
        assert consolidate_adjacent_placeholders('CUSTOMCUSTOM', 'CUSTOM') == 'CUSTOM'
        assert consolidate_adjacent_placeholders('CUSTOM/api/CUSTOMCUSTOM', 'CUSTOM') == 'CUSTOM/api/CUSTOM'


class TestEscapeSequences:
    """Test JavaScript escape sequence decoding in URLs."""

    def test_escape_sequences_in_urls(self):
        """Test that various JavaScript escape sequences are decoded in extracted URLs."""
        node, file_size = parse_file('escape_sequences.js')
        urls = get_urls(node, 'FUZZ', include_templates=False, verbose=False, file_size=file_size)

        # All escaped equals signs should be decoded to '='
        assert '/api/example?param1=value1' in urls
        assert '/api/example?param2=value2' in urls
        assert '/api/example?param3=value3' in urls
        assert '/api/example?param4=value4' in urls
        assert '/api/test?a=1&b=2&c=d' in urls
        assert '/api/endpoint?key=val' in urls

        # Escaped versions should NOT be in output
        assert '/api/example?param1\\x3dvalue1' not in urls
        assert '/api/example?param2\\u003dvalue2' not in urls
        assert '/api/example?param3\\u{003D}value3' not in urls
        assert '/api/example?param4\\075value4' not in urls

    def test_junk_filtering_pure_placeholders(self):
        # Pure placeholder paths should be junk
        assert is_junk_url('FUZZ/FUZZ', 'FUZZ') == True
        assert is_junk_url('FUZZ/FUZZ/FUZZ', 'FUZZ') == True
        assert is_junk_url('FUZZ/FUZZ/FUZZ/FUZZ/FUZZ', 'FUZZ') == True

        # Paths with actual content should NOT be junk
        assert is_junk_url('FUZZ/spaces/FUZZ', 'FUZZ') == False
        assert is_junk_url('/api/FUZZ/users', 'FUZZ') == False
        assert is_junk_url('FUZZ/api/v2', 'FUZZ') == False

        # Custom placeholder
        assert is_junk_url('CUSTOM/CUSTOM', 'CUSTOM') == True
        assert is_junk_url('CUSTOM/api/CUSTOM', 'CUSTOM') == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
