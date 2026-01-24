"""
AST traversal and URL entry management (Pass 2).

Handles traversing the AST to extract URLs and managing the URL entry collection.
"""
import re

from sawari.core.jsparser import parse_javascript
from sawari.core.url_utils import is_url_pattern, is_path_pattern

from .filters import clean_unbalanced_brackets, clean_trailing_sentence_punctuation, is_junk_url
from .processors import (
    process_string_literal,
    process_template_string,
    process_binary_expression,
    process_concat_call,
    process_call_expression,
)


def add_url_entry(entry, url_entries, seen_urls, verbose=False, placeholder='FUZZ', mime_types=None):
    """
    Adds entry to results, handles deduplication and lists.

    Parameters:
    - entry: Single URL entry dict or list of entries
    - url_entries: List to append entries to (mutated in place)
    - seen_urls: Set for deduplication (mutated in place)
    - verbose: Print URLs as discovered
    - placeholder: Placeholder string for unknown values
    - mime_types: Optional set of MIME types for junk filtering
    """
    if not entry:
        return

    entries = [entry] if isinstance(entry, dict) else entry

    for e in entries:
        if not isinstance(e, dict):
            continue

        # Create deduplication key
        key = (e.get('original', ''), e.get('placeholder', ''), e.get('resolved', ''))

        if key not in seen_urls:
            seen_urls.add(key)
            url_entries.append(e)

            if verbose:
                # Clean and filter before printing
                url_to_print = clean_unbalanced_brackets(e.get('placeholder', e.get('original', '')))
                url_to_print = clean_trailing_sentence_punctuation(url_to_print)
                if not is_junk_url(url_to_print, placeholder, mime_types):
                    print(f"{url_to_print}")


def process_comments(node, placeholder, verbose, url_entries, seen_urls,
                     symbol_table=None, object_table=None, array_table=None,
                     alias_table=None, mime_types=None, html_parser_backend='lxml',
                     disable_semantic_aliases=False, max_nodes_limit=1000000):
    """
    Extracts URLs from JavaScript comments and attempts to parse code within them.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}
    if alias_table is None:
        alias_table = {}

    if node.type not in ['comment', 'hash_bang_line']:
        return

    text = node.text.decode('utf8')

    # Remove comment markers
    if text.startswith('//'):
        text = text[2:].strip()
    elif text.startswith('/*') and text.endswith('*/'):
        text = text[2:-2].strip()
    elif text.startswith('#!'):
        text = text[2:].strip()

    if not text:
        return

    # Extract URLs directly from comment text using regex
    found_urls = []

    # Match full URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    found_urls.extend(re.findall(url_pattern, text))

    # Match path patterns
    path_pattern = r'(?:^|[\s,;])((?:/[a-zA-Z0-9_\-./{}:]+)|(?:\./[a-zA-Z0-9_\-./]+)|(?:\.\./[a-zA-Z0-9_\-./]+))'
    found_paths = re.findall(path_pattern, text)
    found_urls.extend(found_paths)

    # Add found URLs as entries
    for url in found_urls:
        url = url.strip()
        if url and (is_url_pattern(url) or is_path_pattern(url)):
            entry = {
                'original': url,
                'placeholder': url,
                'resolved': url,
                'has_template': False
            }
            add_url_entry(entry, url_entries, seen_urls, verbose, placeholder, mime_types)

    # Try to parse as JavaScript code (for commented-out code)
    try:
        _, comment_root = parse_javascript(text)
        # Create a simple traverse function for the comment
        node_visit_count = [0]

        def traverse_comment(n, ph, v):
            traverse_node(
                n, ph, v, url_entries, seen_urls,
                symbol_table, object_table, array_table,
                alias_table, mime_types, html_parser_backend,
                disable_semantic_aliases, node_visit_count, max_nodes_limit
            )

        traverse_comment(comment_root, placeholder, verbose)
    except:
        pass


def traverse_node(node, placeholder, verbose, url_entries, seen_urls,
                  symbol_table=None, object_table=None, array_table=None,
                  alias_table=None, mime_types=None, html_parser_backend='lxml',
                  disable_semantic_aliases=False, node_visit_count=None,
                  max_nodes_limit=1000000):
    """
    Second pass - iteratively traverses AST to extract URLs using explicit stack.

    This iterative approach eliminates recursion overhead and avoids stack overflow
    on very deep ASTs.

    Parameters:
    - node: AST node to traverse
    - placeholder: Placeholder string for unknown values
    - verbose: Print URLs as discovered
    - url_entries: List to collect URL entries
    - seen_urls: Set for deduplication
    - symbol_table: Dictionary mapping variable names to value lists
    - object_table: Dictionary mapping object names to property structures
    - array_table: Dictionary mapping array names to element lists
    - alias_table: Dictionary for semantic aliases
    - mime_types: Set of MIME types for junk filtering
    - html_parser_backend: HTML parser to use
    - disable_semantic_aliases: Whether to disable semantic alias extraction
    - node_visit_count: Mutable list [count] for tracking visits
    - max_nodes_limit: Maximum number of nodes to visit
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}
    if alias_table is None:
        alias_table = {}
    if node_visit_count is None:
        node_visit_count = [0]

    # Use explicit stack for iterative traversal
    stack = [node]

    # Create a traverse function for nested calls (e.g., processing HTML inline scripts)
    def traverse_func(n, ph, v):
        traverse_node(
            n, ph, v, url_entries, seen_urls,
            symbol_table, object_table, array_table,
            alias_table, mime_types, html_parser_backend,
            disable_semantic_aliases, node_visit_count, max_nodes_limit
        )

    while stack:
        if node_visit_count[0] > max_nodes_limit:
            break

        current_node = stack.pop()
        node_visit_count[0] += 1

        # Process current node
        result = None
        node_type = current_node.type

        if node_type == 'string':
            result = process_string_literal(
                current_node, placeholder, symbol_table, object_table, array_table,
                html_parser_backend, traverse_func
            )
        elif node_type == 'template_string':
            result = process_template_string(
                current_node, placeholder, symbol_table, object_table, array_table,
                alias_table, disable_semantic_aliases, html_parser_backend, traverse_func
            )
        elif node_type == 'binary_expression':
            result = process_binary_expression(
                current_node, placeholder, symbol_table, object_table, array_table,
                alias_table, disable_semantic_aliases
            )
        elif node_type == 'call_expression':
            # Check for .concat(), .join(), or .replace()
            func_node = current_node.child_by_field_name('function')
            if func_node and func_node.type == 'member_expression':
                prop = func_node.child_by_field_name('property')
                if prop:
                    method_name = prop.text.decode('utf8')
                    if method_name == 'concat':
                        result = process_concat_call(
                            current_node, placeholder, symbol_table, object_table, array_table,
                            alias_table, disable_semantic_aliases
                        )
                    elif method_name in ('join', 'replace'):
                        result = process_call_expression(
                            current_node, placeholder, symbol_table, object_table, array_table
                        )
        elif node_type in ('comment', 'hash_bang_line'):
            process_comments(
                current_node, placeholder, verbose, url_entries, seen_urls,
                symbol_table, object_table, array_table, alias_table,
                mime_types, html_parser_backend, disable_semantic_aliases, max_nodes_limit
            )

        if result:
            add_url_entry(result, url_entries, seen_urls, verbose, placeholder, mime_types)

        # Add children to stack (reverse for left-to-right processing order)
        stack.extend(reversed(current_node.named_children))
