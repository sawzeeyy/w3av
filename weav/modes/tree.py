from weav.core.jsparser import parse_javascript
from weav.core.comment import process_comments_status


def traverse_node(
    node, indent, is_named, include_text, parse_comments, level=0
):
    global syntax_tree

    field_name = node.parent.field_name_for_child(
        node.parent.children.index(node)) if node.parent else None
    text = f'{" " * indent * level}'
    text = text if field_name is None else f'{text}{field_name}: '
    text += f'{node.type} '
    text += f'({node.start_point.row}, {node.start_point.column}) - '
    text += f'({node.end_point.row}, {node.end_point.column})'
    text = f'{text} => {node.text}' if include_text else text
    syntax_tree.append(text)

    if node.type == 'comment' and parse_comments:
        process_comments(node, indent, is_named, include_text, level)

    level += 1
    node_children = node.named_children if is_named else node.children

    for child in node_children:
        traverse_node(
            child,
            indent,
            is_named,
            include_text,
            parse_comments,
            level
        )


def process_comments(node, indent, is_named, include_text, level):
    node_text, comment_removed = process_comments_status(node)

    if comment_removed:
        comment_node = parse_javascript(node_text)
        traverse_node(
            comment_node,
            indent,
            is_named,
            include_text,
            True,
            level
        )


def get_syntax_tree(node, indent, is_named, include_text, parse_comments):
    global syntax_tree

    syntax_tree = []
    traverse_node(node, indent, is_named, include_text, parse_comments)

    return syntax_tree
