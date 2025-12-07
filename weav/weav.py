#!/usr/bin/env python3
import sys

from weav.core.argparser import parse_arguments
from weav.core.jsparser import parse_javascript
from weav.core.output import write_output
from weav.modes.urls import get_urls
from weav.modes.tree import get_syntax_tree
from weav.modes.strings import get_strings
from weav.modes.inspect import inspect_nodes
from weav.modes.query import query_nodes


def main():
    if sys.version_info < (3, 6):
        print("weav requires Python 3.6 or higher")
        sys.exit(1)

    args = parse_arguments()
    language, root_node = parse_javascript(args.javascript)

    if args.mode == 'urls':
        result = get_urls(
            root_node,
            args.placeholder,
            args.include_templates,
            args.verbose,
            len(args.javascript),
            args.max_nodes,
            args.max_file_size,
            args.html_parser,
            args.skip_symbols
        )
    elif args.mode == 'tree':
        result = get_syntax_tree(
            root_node,
            args.indent,
            args.only_named,
            args.include_text,
            args.parse_comments
        )
    elif args.mode == 'strings':
        result = get_strings(
            root_node,
            args.min,
            args.max,
            args.include_error
        )
    elif args.mode == 'inspect':
        result = inspect_nodes(
            root_node,
            args.get_types,
            args.types
        )
    elif args.mode == 'query':
        result = query_nodes(
            language,
            root_node,
            args.query,
            args.unique,
            args.trim
        )

    write_output(args.output, result)


if __name__ == '__main__':
    main()
