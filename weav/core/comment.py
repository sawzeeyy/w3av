def process_comments_status(node):
    node_text = node.text.decode('UTF-8')
    comment_removed = False

    if node_text.startswith('/*'):
        comment_removed = True
        node_text = node_text.strip('/*/')

    while node_text.startswith('//'):
        comment_removed = True
        node_text = node_text[2:].strip()

    return node_text, comment_removed
