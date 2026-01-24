from sawari.core.jsparser import parse_javascript
from sawari.core.comment import remove_comment_delimiter


def traverse_node(node, min, max, include_error):
    global result_text, result_set

    string_nodes = {'string', 'template_string', 'string_fragment'}
    string_nodes = string_nodes | {'ERROR'} if include_error else string_nodes

    if node.type in string_nodes:
        node_text = node.text.decode('UTF-8')
        node_text = node_text.strip('\'"')

        if node_text in result_set:
            return

        text_length = len(node_text)
        min_condition = min is None or text_length >= min
        max_condition = max is None or text_length <= max

        if min_condition and max_condition:
            result_text.append(node_text)
            result_set.add(node_text)

    elif node.type == 'comment':
        process_comments(node, min, max, include_error)

    for child in node.named_children:
        traverse_node(child, min, max, include_error)


def process_comments(node, min, max, include_error):
    node_text, comment_removed = remove_comment_delimiter(node.text.decode())

    if node_text is not None and comment_removed:
        comment_node = parse_javascript(node_text)[1]
        traverse_node(comment_node, min, max, include_error)


def get_strings(node, min, max, include_error):
    global result_text, result_set

    result_text = []
    result_set = set()
    traverse_node(node, min, max, include_error)

    return result_text
