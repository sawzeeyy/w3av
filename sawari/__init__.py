"""
sawari - Extract URLs, strings, and more from JavaScript code.

This module provides convenient high-level functions for common extraction tasks.

Example usage:
    from sawari import extract_urls, extract_strings

    # Extract URLs from JavaScript code
    urls = extract_urls(js_code, include_templates=True)

    # Extract strings from JavaScript code
    strings = extract_strings(js_code, min_length=5)
"""

from sawari.core.jsparser import parse_javascript
from sawari.modes.urls import get_urls
from sawari.modes.strings import get_strings
from sawari.modes.query import query_nodes


def extract_urls(
    code: str,
    placeholder: str = 'FUZZ',
    include_templates: bool = False,
    verbose: bool = False,
    max_nodes: int = 1000000,
    max_file_size_mb: float = 1.0,
    html_parser: str = 'lxml',
    skip_symbols: bool = False,
    skip_aliases: bool = False,
    context: dict = None,
    context_policy: str = 'merge',
    extensions: str = None,
) -> list[str]:
    """
    Extract URLs, API endpoints, and paths from JavaScript code.

    Parameters:
        code: JavaScript source code as a string
        placeholder: String for unknown values (default: 'FUZZ')
        include_templates: Include URLs containing templates/variables
        verbose: Print URLs as discovered
        max_nodes: Maximum AST nodes to visit
        max_file_size_mb: Skip symbol resolution for larger files
        html_parser: HTML parser backend ('lxml', 'html.parser', 'html5lib')
        skip_symbols: Disable variable resolution
        skip_aliases: Use raw variable names instead of semantic aliases
        context: Dict of known variable values
        context_policy: How to handle context ('merge', 'override', 'only')
        extensions: Comma-separated custom file extensions

    Returns:
        List of unique URLs and paths found in the code

    Example:
        >>> from sawari import extract_urls
        >>> code = 'const url = "https://api.example.com/users";'
        >>> extract_urls(code)
        ['https://api.example.com/users']
    """
    source_code, root_node = parse_javascript(code)

    return get_urls(
        node=root_node,
        placeholder=placeholder,
        include_templates=include_templates,
        verbose=verbose,
        file_size=len(code),
        max_nodes=max_nodes,
        max_file_size_mb=max_file_size_mb,
        html_parser=html_parser,
        skip_symbols=skip_symbols,
        skip_aliases=skip_aliases,
        context=context,
        context_policy=context_policy,
        source_text=code,
        extensions=extensions,
    )


def extract_strings(
    code: str,
    min_length: int = None,
    max_length: int = None,
    include_errors: bool = False,
) -> list[str]:
    """
    Extract string literals from JavaScript code.

    Parameters:
        code: JavaScript source code as a string
        min_length: Minimum string length to include
        max_length: Maximum string length to include
        include_errors: Include strings from ERROR nodes (malformed code)

    Returns:
        List of unique strings found in the code

    Example:
        >>> from sawari import extract_strings
        >>> code = 'const msg = "hello world";'
        >>> extract_strings(code)
        ['hello world']
    """
    source_code, root_node = parse_javascript(code)

    return get_strings(
        node=root_node,
        min=min_length,
        max=max_length,
        include_error=include_errors,
    )


def query(
    code: str,
    query_pattern: str,
    unique: bool = True,
    trim: bool = True,
) -> list[str]:
    """
    Query JavaScript AST using tree-sitter query syntax.

    Parameters:
        code: JavaScript source code as a string
        query_pattern: Tree-sitter query pattern (S-expression)
        unique: Return only unique matches
        trim: Strip quotes and whitespace from results

    Returns:
        List of matched node texts

    Example:
        >>> from sawari import query
        >>> code = 'const x = 1; const y = 2;'
        >>> query(code, '(variable_declarator name: (identifier) @name)')
        ['x', 'y']
    """
    language, root_node = parse_javascript(code)

    return query_nodes(
        language=language,
        node=root_node,
        query=query_pattern,
        only_unique=unique,
        trim_enabled=trim,
    )


__all__ = [
    'extract_urls',
    'extract_strings',
    'query',
    'parse_javascript',
]
