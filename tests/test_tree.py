from sawari.core.jsparser import parse_javascript
from sawari.modes.tree import get_syntax_tree


def test_get_syntax_tree_basic():
    """Test getting syntax tree from JavaScript"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result = get_syntax_tree(root_node, 2, False, False, False)

    assert len(result) > 0
    assert 'program' in result[0]


def test_get_syntax_tree_with_indent():
    """Test syntax tree with custom indentation"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result_indent_2 = get_syntax_tree(root_node, 2, False, False, False)
    result_indent_4 = get_syntax_tree(root_node, 4, False, False, False)

    assert len(result_indent_2) > 0
    assert len(result_indent_4) > 0


def test_get_syntax_tree_only_named():
    """Test syntax tree with only named nodes"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result_all = get_syntax_tree(root_node, 2, False, False, False)
    result_named = get_syntax_tree(root_node, 2, True, False, False)

    # Named nodes should be fewer than all nodes
    assert len(result_named) <= len(result_all)


def test_get_syntax_tree_with_text():
    """Test syntax tree including node text"""
    code = "const x = 5;"
    _, root_node = parse_javascript(code)
    result = get_syntax_tree(root_node, 2, False, True, False)

    assert len(result) > 0
    # Should contain '=>' separator for text
    assert any('=>' in line for line in result)


def test_get_syntax_tree_nested_structure():
    """Test syntax tree for nested structures"""
    code = """
    function greet(name) {
        return "Hello " + name;
    }
    """
    _, root_node = parse_javascript(code)
    result = get_syntax_tree(root_node, 2, False, False, False)

    assert len(result) > 1
    assert 'program' in result[0]


def test_get_syntax_tree_empty_code():
    """Test syntax tree for empty code"""
    code = ""
    _, root_node = parse_javascript(code)
    result = get_syntax_tree(root_node, 2, False, False, False)

    assert len(result) >= 1  # At least the program node
    assert 'program' in result[0]
