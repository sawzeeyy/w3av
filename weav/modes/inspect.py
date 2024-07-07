from core.jsparser import parse_javascript
from core.comment import process_comments_status


def traverse_node(node, types):
    global strings_text, strings_set

    if types is None or node.type in types:
        node_text = node.text.decode('UTF-8')
        node_text = node_text.strip('\'"')

        if node_text in strings_set:
            return

        strings_text.append(node_text)
        strings_set.add(node_text)

    if node.type == 'comment':
        process_comments(node, types)

    for child in node.named_children:
        traverse_node(child, types)


def process_comments(node, types):
    node_text, comment_removed = process_comments_status(node)

    if comment_removed:
        comment_node = parse_javascript(node_text)
        traverse_node(comment_node, types)


def inspect_nodes(node, get_types, types):
    with open('./config/nodetypes.txt', 'r') as file:
        all_nodetypes = [x.strip() for x in file.readlines()]

    if get_types:
        return all_nodetypes

    global strings_text, strings_set

    strings_text = []
    strings_set = set()

    types = None if types is None or len(types) == 0 else set(types)
    traverse_node(node, types)

    return strings_text
