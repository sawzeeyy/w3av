import sys


def query_nodes(language, node, query, only_unique, trim_enabled):
    if len(query) < 1:
        sys.exit(0)

    result_text = []
    result_set = set()

    try:
        query_result = language.query(query)
        captures = query_result.captures(node)
    except Exception as e:
        print(f'error: {e}')
        sys.exit(0)

    for capture in captures:
        capture_text = capture[0].text.decode()

        if trim_enabled:
            capture_text = capture[0].text.decode().strip('\'"\n ')

        if only_unique and capture_text in result_set:
            continue

        result_text.append(capture_text)

    return result_text
