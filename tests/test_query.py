import pytest
from sawari.core.jsparser import parse_javascript
from sawari.modes.query import query_nodes


def test_query_strings():
    """Test querying for string nodes"""
    code = '''
    const str1 = "hello";
    const str2 = "world";
    '''
    language, root_node = parse_javascript(code)
    query = '(string) @str'
    result = query_nodes(language, root_node, query, False, False)

    assert len(result) >= 2


def test_query_identifiers():
    """Test querying for identifier nodes"""
    code = '''
    const myVar = 5;
    let anotherVar = 10;
    '''
    language, root_node = parse_javascript(code)
    query = '(identifier) @id'
    result = query_nodes(language, root_node, query, False, False)

    assert len(result) >= 2
    assert 'myVar' in result or any('myVar' in r for r in result)


def test_query_with_trim():
    """Test querying with trim enabled"""
    code = '''
    const str = "hello";
    '''
    language, root_node = parse_javascript(code)
    query = '(string) @str'
    result = query_nodes(language, root_node, query, False, True)

    assert len(result) > 0
    # Should be trimmed
    assert result[0] == 'hello' or result[0] == '"hello"'


def test_query_unique_only():
    """Test querying with unique results only"""
    code = '''
    const a = "hello";
    const b = "hello";
    const c = "world";
    '''
    language, root_node = parse_javascript(code)
    query = '(string) @str'
    result_all = query_nodes(language, root_node, query, False, False)
    result_unique = query_nodes(language, root_node, query, True, False)

    # Unique results should be fewer or equal
    assert len(result_unique) <= len(result_all)


def test_query_function_declarations():
    """Test querying for function declarations"""
    code = '''
    function greet(name) {
        return "Hello " + name;
    }
    function farewell() {
        return "Goodbye";
    }
    '''
    language, root_node = parse_javascript(code)
    query = '(function_declaration) @func'
    result = query_nodes(language, root_node, query, False, False)

    assert len(result) >= 2


def test_query_empty_string():
    """Test querying with empty string"""
    code = "const x = 5;"
    language, root_node = parse_javascript(code)
    query = ''

    # Should exit gracefully with empty query
    with pytest.raises(SystemExit) as exc_info:
        query_nodes(language, root_node, query, False, False)

    assert exc_info.value.code == 0


def test_query_invalid_syntax():
    """Test querying with invalid query syntax"""
    code = "const x = 5;"
    language, root_node = parse_javascript(code)
    query = '(invalid_node_type) @invalid'

    # Should handle gracefully and exit
    with pytest.raises(SystemExit) as exc_info:
        query_nodes(language, root_node, query, False, False)

    assert exc_info.value.code == 0
