#!/usr/env/bin python3
import sys


def main():
    if sys.version_info < (3, 6):
        print("weav requires Python 3.6 or higher")
        sys.exit(1)

    from weav.core.argparser import parse_arguments
    from weav.core.jsparser import parse_javascript
    from weav.core.output import write_output
    from weav.modes.urls import get_urls
    from weav.modes.tree import get_syntax_tree
    from weav.modes.strings import get_strings
    from weav.modes.inspect import inspect_nodes

    args = parse_arguments()
    root_node = parse_javascript(args.javascript)

    if args.mode == 'urls':
        result = get_urls(
            root_node,
            args.placeholder,
            args.include_templates,
            args.verbose
        )
    elif args.mode == 'tree':
        result = get_syntax_tree(
            root_node,
            args.tab_space,
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

    write_output(args.output, result)


if __name__ == '__main__':
    main()
