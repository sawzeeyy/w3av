from sawari.core.jsparser import parse_javascript
from sawari.modes.inspect import inspect_nodes


def test_inspect_get_types():
    """Test getting all node types"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, True, None)

    assert len(result) > 0
    assert isinstance(result, list)
    # Should contain common JavaScript node types
    assert 'identifier' in result
    assert 'string' in result


def test_inspect_all_nodes():
    """Test inspecting all nodes without type filter"""
    code = '''
    const str = "hello";
    const num = 42;
    '''
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, None)

    assert len(result) > 0


def test_inspect_with_type_filter():
    """Test inspecting nodes with type filter"""
    code = '''
    const str1 = "hello";
    const str2 = "world";
    const num = 42;
    '''
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, ['string'])

    assert len(result) >= 2


def test_inspect_multiple_types():
    """Test inspecting nodes with multiple type filters"""
    code = '''
    const myVar = "hello";
    let anotherVar = 42;
    '''
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, ['string', 'number'])

    assert len(result) > 0


def test_inspect_empty_types():
    """Test inspecting nodes with empty type filter"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, [])

    # Empty filter should inspect all nodes
    assert len(result) > 0


def test_inspect_nonexistent_type():
    """Test inspecting with nonexistent node type"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, ['nonexistent_type'])

    # Should return empty list
    assert len(result) == 0


def test_inspect_no_duplicates():
    """Test that inspect doesn't return duplicates"""
    code = '''
    const a = "hello";
    const b = "hello";
    const c = "hello";
    '''
    _, root_node = parse_javascript(code)
    result = inspect_nodes(root_node, False, ['string'])

    # Should only have unique values
    hello_count = result.count('hello')
    assert hello_count == 1
