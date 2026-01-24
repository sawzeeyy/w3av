"""
Main URL extraction orchestration.

Provides the main get_urls() function that coordinates all extraction passes.
"""
import sys

from sawari.core.jsparser import parse_javascript
from sawari.core.html import extract_urls_from_html, extract_inline_scripts_from_html
from sawari.core.context import populate_symbol_tables, should_skip_pass1

from .config import load_mime_types, set_custom_extensions
from .output import format_output, is_html_content
from .symbols import build_symbol_table
from .traversal import traverse_node


def get_urls(node, placeholder, include_templates, verbose, file_size=0, max_nodes=1000000,
             max_file_size_mb=1.0, html_parser='lxml', skip_symbols=False, skip_aliases=False,
             context=None, context_policy='merge', source_text=None, extensions=None):
    """
    Main function - orchestrates the two-pass extraction.

    Parameters:
    - node: Root AST node from tree-sitter (can be None if source_text is HTML)
    - placeholder: String for unknown values (default: "FUZZ")
    - include_templates: Whether to include templated URLs
    - verbose: Print URLs as discovered
    - file_size: Size of input file in bytes (for optimization)
    - max_nodes: Maximum number of AST nodes to visit (default: 1,000,000)
    - max_file_size_mb: Max file size in MB for symbol/alias resolution (default: 1.0)
    - html_parser: HTML parser backend to use (default: 'lxml')
    - skip_symbols: Skip symbol resolution entirely (default: False)
    - skip_aliases: Skip semantic alias extraction (default: False)
    - context: Parsed context dictionary (external variable definitions)
    - context_policy: How to handle context/file collisions ('merge', 'override', 'only')
    - source_text: Original source text (for HTML detection)
    - extensions: Comma-separated string of custom file extensions

    Note: Large files (>max_file_size_mb) automatically skip both symbols and aliases.
          Context forces symbol resolution even for large files.
          If source_text is HTML, will extract from HTML attributes and inline scripts.

    Returns:
    - List of URLs
    """
    # Check if input is HTML content
    if source_text and is_html_content(source_text):
        result = []

        # Extract URLs from HTML attributes
        html_urls = extract_urls_from_html(source_text, placeholder=placeholder, html_parser=html_parser)
        if html_urls:
            result.extend([entry.get('resolved', entry.get('url', '')) for entry in html_urls if entry.get('resolved') or entry.get('url')])

        # Extract and parse inline JavaScript
        inline_scripts = extract_inline_scripts_from_html(source_text, html_parser=html_parser)
        for script_code in inline_scripts:
            try:
                _, script_root_node = parse_javascript(script_code)
                # Recursively call get_urls on the inline script
                script_urls = get_urls(
                    script_root_node,
                    placeholder,
                    include_templates,
                    verbose,
                    len(script_code),
                    max_nodes,
                    max_file_size_mb,
                    html_parser,
                    skip_symbols,
                    skip_aliases,
                    context,
                    context_policy,
                    source_text=None,  # Don't re-check HTML for inline scripts
                    extensions=extensions
                )
                if script_urls:
                    result.extend(script_urls)
            except Exception:
                # Skip scripts that fail to parse
                pass

        # Remove duplicates while preserving order
        seen = set()
        unique_result = []
        for url in result:
            if url not in seen:
                seen.add(url)
                unique_result.append(url)

        return unique_result

    # Initialize state for this extraction
    url_entries = []
    symbol_table = {}
    object_table = {}
    array_table = {}
    alias_table = {}  # Track semantic aliases for variable names
    seen_urls = set()
    node_visit_count = [0]
    max_nodes_limit = max_nodes
    mime_types = load_mime_types()
    html_parser_backend = html_parser

    # Parse and normalize custom file extensions
    set_custom_extensions(extensions or '')

    # Pre-populate tables from context if provided
    context_provided = context is not None and context
    if context_provided:
        populate_symbol_tables(context, symbol_table, object_table, array_table)
        if verbose:
            sys.stderr.write(f'Loaded {len(context)} context variable(s).\n')

    # For large files (>max_file_size_mb), skip symbol table building and semantic aliases to avoid hanging
    # Also skip if user explicitly requested via --skip-symbols or --skip-aliases
    # UNLESS context is provided - then we force symbol resolution
    file_size_mb = file_size / (1024 * 1024)
    is_large_file = file_size_mb > max_file_size_mb

    # Context overrides large file optimization
    force_symbol_resolution = context_provided

    skip_symbols = skip_symbols or (is_large_file and not force_symbol_resolution)
    skip_aliases = skip_aliases or is_large_file
    disable_semantic_aliases = skip_aliases  # Control semantic alias extraction

    if verbose:
        if is_large_file and not force_symbol_resolution:
            sys.stderr.write(f'Large file ({file_size_mb:.1f}MB): Skipping symbol resolution and semantic aliases for faster processing.\n')
        elif is_large_file and force_symbol_resolution:
            sys.stderr.write(f'Large file ({file_size_mb:.1f}MB): Context provided, forcing symbol resolution.\n')
        else:
            if skip_symbols:
                sys.stderr.write('Skipping symbol resolution (--skip-symbols flag).\n')
            if skip_aliases:
                sys.stderr.write('Skipping semantic aliases (--skip-aliases flag).\n')

    # Pass 1: Build symbol table (skip for large files, or if user requested, or if policy is 'only')
    skip_pass1 = skip_symbols or (context_provided and should_skip_pass1(context_policy))

    if not skip_pass1:
        build_symbol_table(
            node, placeholder, symbol_table, object_table, array_table,
            alias_table, context, context_policy, node_visit_count, max_nodes_limit
        )

    # Reset node visit count for pass 2
    node_visit_count[0] = 0

    # Pass 2: Extract URLs
    traverse_node(
        node, placeholder, verbose, url_entries, seen_urls,
        symbol_table, object_table, array_table, alias_table,
        mime_types, html_parser_backend, disable_semantic_aliases,
        node_visit_count, max_nodes_limit
    )

    # Format and return
    return format_output(url_entries, include_templates, placeholder, mime_types)
