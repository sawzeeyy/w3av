from core.jsparser import parse_javascript
from core.comment import process_comments_status


def traverse_node(node, min, max, include_error):
    global strings_text, strings_set

    string_nodes = {'string', 'template_string', 'string_fragment'}
    string_nodes = string_nodes | {'ERROR'} if include_error else string_nodes

    if node.type in string_nodes:
        node_text = node.text.decode('UTF-8')
        node_text = node_text.strip('\'"')

        if node_text in strings_set:
            return

        text_length = len(node_text)
        min_condition = min is None or text_length >= min
        max_condition = max is None or text_length <= max

        if min_condition and max_condition:
            strings_text.append(node_text)
            strings_set.add(node_text)

    elif node.type == 'comment':
        process_comments(node, min, max, include_error)

    for child in node.named_children:
        traverse_node(child, min, max, include_error)


def process_comments(node, min, max, include_error):
    node_text, comment_removed = process_comments_status(node)

    if comment_removed:
        comment_node = parse_javascript(node_text)
        traverse_node(comment_node, min, max, include_error)


def get_strings(node, min, max, include_error):
    global strings_text, strings_set

    strings_text = []
    strings_set = set()
    traverse_node(node, min, max, include_error)

    return strings_text
