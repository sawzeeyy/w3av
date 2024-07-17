from weav.core.jsparser import parse_javascript
from weav.core.comment import remove_comment_delimiter


def traverse_node(node, types):
    global result_text, result_set

    if types is None or node.type in types:
        node_text = node.text.decode('UTF-8')
        node_text = node_text.strip('\'"')

        if node_text in result_set:
            return

        result_text.append(node_text)
        result_set.add(node_text)

    if node.type == 'comment':
        process_comments(node, types)

    for child in node.named_children:
        traverse_node(child, types)


def process_comments(node, types):
    node_text, comment_removed = remove_comment_delimiter(node.text.decode())

    if node_text is not None and comment_removed:
        comment_node = parse_javascript(node_text)[1]
        traverse_node(comment_node, types)


def inspect_nodes(node, get_types, types):
    with open('./config/nodetypes.txt', 'r') as file:
        all_nodetypes = [x.strip() for x in file.readlines()]

    if get_types:
        return all_nodetypes

    global result_text, result_set

    result_text = []
    result_set = set()

    types = None if types is None or len(types) == 0 else set(types)
    traverse_node(node, types)

    return result_text
