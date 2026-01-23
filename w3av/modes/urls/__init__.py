"""
URL extraction module for JavaScript files.

This module provides URL and path extraction from JavaScript source code,
handling template literals, variable resolution, and concatenation patterns.

Main entry point:
    get_urls(node, placeholder, include_templates, verbose, ...) -> List[str]

Example usage:
    from w3av.modes.urls import get_urls
    from w3av.core.jsparser import parse_javascript

    source_code, root_node = parse_javascript(js_content)
    urls = get_urls(root_node, 'FUZZ', include_templates=True, verbose=False)
"""

# Main extraction function
from .extractor import get_urls

# Configuration utilities
from .config import (
    load_mime_types,
    get_custom_extensions,
    set_custom_extensions,
)

# Re-export from core.url_utils for backward compatibility
from w3av.core.url_utils import is_url_pattern, is_path_pattern

# Filtering and cleaning
from .filters import (
    is_junk_url,
    clean_unbalanced_brackets,
    consolidate_adjacent_placeholders,
)

# Output formatting
from .output import (
    convert_route_params,
    format_output,
    is_html_content,
)

# String and expression resolution
from .resolvers import (
    decode_js_string,
    extract_string_value,
    resolve_member_expression,
    resolve_subscript_expression,
    resolve_join_call,
    resolve_replace_call,
    resolve_binary_expression,
)

# Alias management
from .aliases import (
    add_alias,
    get_best_alias,
    extract_local_aliases,
    extract_aliases_from_object,
    scan_for_urlsearchparams,
    scan_sibling_nodes_for_aliases,
)

# Symbol table building
from .symbols import (
    build_symbol_table,
    collect_variable_assignment,
    collect_object_assignment,
    collect_object_properties,
    collect_array_elements,
)

# Node processors
from .processors import (
    process_html_content,
    process_string_literal,
    process_template_string,
    process_binary_expression,
    process_concat_call,
    process_call_expression,
    extract_chained_parts,
)

# AST traversal
from .traversal import (
    traverse_node,
    add_url_entry,
    process_comments,
)


__all__ = [
    # Main entry point
    'get_urls',

    # Configuration
    'load_mime_types',
    'get_custom_extensions',
    'set_custom_extensions',

    # Re-exports from core.url_utils
    'is_url_pattern',
    'is_path_pattern',

    # Filtering
    'is_junk_url',
    'clean_unbalanced_brackets',
    'consolidate_adjacent_placeholders',

    # Output
    'convert_route_params',
    'format_output',
    'is_html_content',

    # Resolvers
    'decode_js_string',
    'extract_string_value',
    'resolve_member_expression',
    'resolve_subscript_expression',
    'resolve_join_call',
    'resolve_replace_call',
    'resolve_binary_expression',

    # Aliases
    'add_alias',
    'get_best_alias',
    'extract_local_aliases',
    'extract_aliases_from_object',
    'scan_for_urlsearchparams',
    'scan_sibling_nodes_for_aliases',

    # Symbols
    'build_symbol_table',
    'collect_variable_assignment',
    'collect_object_assignment',
    'collect_object_properties',
    'collect_array_elements',

    # Processors
    'process_html_content',
    'process_string_literal',
    'process_template_string',
    'process_binary_expression',
    'process_concat_call',
    'process_call_expression',
    'extract_chained_parts',

    # Traversal
    'traverse_node',
    'add_url_entry',
    'process_comments',
]
