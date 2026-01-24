from sawari.core.jsparser import parse_javascript


def test_parse_simple_javascript():
    """Test parsing simple JavaScript code"""
    code = "const x = 5;"
    language, root_node = parse_javascript(code)

    assert root_node is not None
    assert root_node.type == 'program'
    assert language is not None


def test_parse_function():
    """Test parsing a JavaScript function"""
    code = """
    function greet(name) {
        return "Hello " + name;
    }
    """
    language, root_node = parse_javascript(code)

    assert root_node.type == 'program'
    assert len(root_node.children) > 0


def test_parse_empty_code():
    """Test parsing empty JavaScript code"""
    code = ""
    language, root_node = parse_javascript(code)

    assert root_node.type == 'program'
    assert len(root_node.children) == 0


def test_parse_with_comments():
    """Test parsing JavaScript with comments"""
    code = """
    // This is a comment
    const x = 5;
    /* Multi-line
       comment */
    """
    language, root_node = parse_javascript(code)

    assert root_node.type == 'program'


def test_parse_template_string():
    """Test parsing template strings"""
    code = "const url = `https://example.com/${path}`;"
    language, root_node = parse_javascript(code)

    assert root_node.type == 'program'
    assert len(root_node.children) > 0
