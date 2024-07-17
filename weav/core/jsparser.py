import tree_sitter_javascript
from tree_sitter import Language, Parser


def parse_javascript(code):
    JS_LANGUAGE = Language(tree_sitter_javascript.language())
    parser = Parser(JS_LANGUAGE)
    tree = parser.parse(bytes(code, 'utf8'))
    root_node = tree.root_node

    return JS_LANGUAGE, root_node
