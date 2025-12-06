import sys
from tree_sitter import Query, QueryCursor


def query_nodes(language, node, query, only_unique, trim_enabled):
    if len(query) < 1:
        sys.exit(0)

    result_text = []
    result_set = set()

    try:
        query_obj = Query(language, query)
        cursor = QueryCursor(query_obj)
        captures_dict = cursor.captures(node)

        # Flatten all captures from all capture names
        all_captures = []
        for capture_nodes in captures_dict.values():
            all_captures.extend(capture_nodes)

    except Exception as e:
        print(f'error: {e}')
        sys.exit(0)

    for capture_node in all_captures:
        capture_text = capture_node.text.decode()

        if trim_enabled:
            capture_text = capture_text.strip('\'"\n ')

        if only_unique and capture_text in result_set:
            continue

        result_text.append(capture_text)
        result_set.add(capture_text)

    return result_text
