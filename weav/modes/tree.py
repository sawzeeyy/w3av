from core.jsparser import parse_javascript
from core.comment import process_comments_status


def traverse_node(
        node, tab_space, is_named, include_text, parse_comments, level=0):
    global syntax_tree

    text = f"{' ' * tab_space * level} {node.type} "
    text += f"{node.start_point}, {node.end_point}"
    text = f'{text} - {node.text}' if include_text else text
    syntax_tree.append(text)

    if node.type == 'comment' and parse_comments:
        process_comments(node, tab_space, is_named, include_text, level)

    level += 1
    node_children = node.named_children if is_named else node.children

    for child in node_children:
        traverse_node(
            child,
            tab_space,
            is_named,
            include_text,
            parse_comments,
            level
        )


def process_comments(node, tab_space, is_named, include_text, level):
    node_text, comment_removed = process_comments_status(node)

    if comment_removed:
        comment_node = parse_javascript(node_text)
        traverse_node(
            comment_node,
            tab_space,
            is_named,
            include_text,
            True,
            level
        )


def get_syntax_tree(node, tab_space, is_named, include_text, parse_comments):
    global syntax_tree

    syntax_tree = []
    traverse_node(node, tab_space, is_named, include_text, parse_comments)

    return syntax_tree
