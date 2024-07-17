import re


def remove_comment_delimiter(text):
    comment_removed = False
    text = text.strip()
    current_length = len(text)
    pattern = re.compile(
        r'^\/\/'                      # Start with double slash
        r'(?:'                        # Start non-capturing group for domain/IP
        r'(?:[a-zA-Z0-9-]+\.)+'       # Domain name part
        r'[a-zA-Z]{2,}'               # TLD part
        r'|'                          # OR
        r'(?:\d{1,3}\.){3}\d{1,3}'    # IP address part
        r')'                          # End non-capturing group for domain/IP
        r'(?::\d{1,5})?'              # Optional port number
        r'(?:\/[^\s]*)?'              # Optional path
        r'$',                         # End of string
        re.VERBOSE                    # Ignore space and comments
    )

    while text.startswith('/*'):
        text = text[2:].strip()

    while text.endswith('*/'):
        text = text[:-2].strip()

    while text.startswith('//') and not pattern.match(text):
        text = text[2:].strip()

    while text.startswith('/ '):
        text = text[2:].strip()

    while text.endswith(' /'):
        text = text[:-2].strip()

    if len(text) == 0:
        text = None

    if current_length > len(text):
        comment_removed = True

    return text, comment_removed
