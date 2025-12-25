from w3av.core.jsparser import parse_javascript
from w3av.modes.strings import get_strings


def test_get_strings_basic():
    """Test extracting strings from JavaScript"""
    code = '''
    const str1 = "hello";
    const str2 = 'world';
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, None, None, False)

    assert 'hello' in result
    assert 'world' in result


def test_get_strings_with_min_length():
    """Test filtering strings by minimum length"""
    code = '''
    const a = "hi";
    const b = "hello";
    const c = "world";
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, 5, None, False)

    assert 'hi' not in result
    assert 'hello' in result
    assert 'world' in result


def test_get_strings_with_max_length():
    """Test filtering strings by maximum length"""
    code = '''
    const a = "hi";
    const b = "hello";
    const c = "world";
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, None, 3, False)

    assert 'hi' in result
    assert 'hello' not in result
    assert 'world' not in result


def test_get_strings_with_min_and_max():
    """Test filtering strings with both min and max length"""
    code = '''
    const a = "hi";
    const b = "hello";
    const c = "world";
    const d = "verylongstring";
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, 4, 6, False)

    assert 'hi' not in result
    assert 'hello' in result
    assert 'world' in result
    assert 'verylongstring' not in result


def test_get_strings_template_strings():
    """Test extracting template strings"""
    code = '''
    const url = `https://example.com`;
    const path = `/${id}`;
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, None, None, False)

    assert 'https://example.com' in result or '`https://example.com`' in result


def test_get_strings_no_duplicates():
    """Test that duplicate strings are not returned"""
    code = '''
    const a = "hello";
    const b = "hello";
    const c = "hello";
    '''
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, None, None, False)

    # Count occurrences of "hello"
    hello_count = result.count('hello')
    assert hello_count == 1


def test_get_strings_empty_code():
    """Test extracting strings from empty code"""
    code = ""
    _, root_node = parse_javascript(code)
    result = get_strings(root_node, None, None, False)

    assert len(result) == 0
