from tree_sitter_languages import get_parser


def parse_javascript(code):
    parser = get_parser('javascript')
    tree = parser.parse(bytes(code, 'utf8'))
    root_node = tree.root_node

    return root_node
