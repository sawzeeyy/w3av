import argparse
import sys
import textwrap

from importlib.metadata import version as pkg_version


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f'error: {message}\n')

        if 'mode' in message:
            self.print_help()
        else:
            cmd_args = sys.argv[1:]
            if cmd_args:
                subcommand_name = cmd_args[0]
                if self._subparsers is not None:
                    subcommand_choices = self._subparsers._actions[-1].choices
                    if subcommand_name in subcommand_choices:
                        subcommand_parser = subcommand_choices[subcommand_name]
                        subcommand_parser.print_help()
                    else:
                        self.print_help()
                else:
                    self.print_help()
        self.exit(1)

    def print_help(self, file=None):
        super().print_help(file)

        cmd_examples = textwrap.dedent('''
        Examples:
            weav urls main.js
            weav urls --input main.js
            weav tree main.js --only-named
            weav strings main.js --min 3
            weav inspect main.js --types string template_string
            weav query --input main.js --query '(string) @str' --trim
            cat main.js | weav urls --include-templates
        ''')
        print(cmd_examples)


class ArgumentDefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action):
        # For --output, always show '(default: stdout)'
        if action.dest == 'output':
            help_str = action.help or ''
            return f'{help_str} (default: stdout)'
        return super()._get_help_string(action)


def add_subparser_with_common_args(subparsers, mode, description):
    new_parser = subparsers.add_parser(
        mode,
        description=description,
        help=description,
        formatter_class=ArgumentDefaultsHelpFormatter
    )
    new_parser._optionals.title = 'Options'

    # Create mutually exclusive group for input
    input_group = new_parser.add_mutually_exclusive_group()
    input_group.add_argument(
        'input_file',
        nargs='?',
        type=argparse.FileType('r'),
        metavar='FILE',
        help='JavaScript file; supports pipeline input from stdin'
    )
    input_group.add_argument(
        '--input',
        type=argparse.FileType('r'),
        metavar='FILE',
        help='JavaScript file; supports pipeline input from stdin'
    )

    new_parser.add_argument(
        '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        metavar='FILE',
        help='Output file name'
    )
    return new_parser


def parse_arguments():
    prog = 'weav'
    desc = 'extract URLs, strings, and more from JavaScript code'
    __version__ = pkg_version(prog)
    parser = ArgumentParser(prog=prog, description=f'{prog} - {desc}')
    parser.add_argument('-v', '--version', action='version',
                        version=f'{prog} {__version__}')
    parser._optionals.title = 'Options'
    subparsers = parser.add_subparsers(title='Modes', dest='mode')

    # URLs
    parser_urls = add_subparser_with_common_args(
        subparsers,
        'urls',
        'Get urls in JavaScript file'
    )
    parser_urls.add_argument(
        '--placeholder',
        type=str,
        default='FUZZ',
        metavar='STR',
        help='Placeholder for expressions, templates, or variables'
    )
    parser_urls.add_argument(
        '--include-templates',
        action='store_true',
        help='Include URLs containing a template or variable'
    )
    parser_urls.add_argument(
        '--verbose',
        action='store_true',
        help='Print urls as soon as they are discovered'
    )
    parser_urls.add_argument(
        '--max-nodes',
        type=int,
        default=1000000,
        metavar='N',
        help='Maximum number of AST nodes to visit'
    )
    parser_urls.add_argument(
        '--max-file-size',
        type=float,
        default=1.0,
        metavar='MB',
        help='Max file size in MB for symbol resolution'
    )

    # Tree
    parser_tree = add_subparser_with_common_args(
        subparsers,
        'tree',
        'Print JavaScript syntax tree'
    )
    parser_tree.add_argument(
        '--indent',
        type=int,
        default=2,
        metavar='N',
        help='Number of space used for formatting'
    )
    parser_tree.add_argument(
        '--only-named',
        action='store_true',
        help='Print only named nodes'
    )
    parser_tree.add_argument(
        '--include-text',
        action='store_true',
        help='Print the node text alongside the syntax tree'
    )
    parser_tree.add_argument(
        '--parse-comments',
        action='store_true',
        help='Parse comment or comment blocks'
    )

    # Strings
    parser_strings = add_subparser_with_common_args(
        subparsers,
        'strings',
        'Get strings in JavaScript file'
    )
    parser_strings.add_argument(
        '--min',
        type=int,
        metavar='N',
        help='Minimum length of a string'
    )
    parser_strings.add_argument(
        '--max',
        type=int,
        metavar='N',
        help='Maximum length of a string'
    )
    parser_strings.add_argument(
        '--include-error',
        action='store_true',
        help='Inlcude ERROR nodes'
    )

    # Inspect
    parser_inspect = add_subparser_with_common_args(
        subparsers,
        'inspect',
        'Inspect JavaScript syntax tree'
    )
    parser_inspect.add_argument(
        '--get-types',
        action='store_true',
        help='Print all JavaScript node types and exit'
    )
    parser_inspect.add_argument(
        '--types',
        type=str,
        nargs='*',
        metavar='STR',
        help='Filter list of node types to inspect'
    )

    # Query
    parser_query = add_subparser_with_common_args(
        subparsers,
        'query',
        'Query JavaScript syntax tree'
    )
    parser_query.add_argument(
        '--query',
        type=str,
        metavar='STR',
        help='Tree sitter query'
    )
    parser_query.add_argument(
        '--unique',
        action='store_true',
        help='Get only unique capttures'
    )
    parser_query.add_argument(
        '--trim',
        action='store_true',
        help='Decode node texts and removed leading or trailing characters'
    )

    # Parse arguments
    args = parser.parse_args()

    # Print help if mode is not specified
    if args.mode is None:
        parser.print_help()
        sys.exit(0)

    # Allow --get-types in inspect mode without input
    if args.mode == 'inspect' and getattr(args, 'get_types', False):
        args.javascript = ''
    else:
        # Validate input parameter - check both positional and --input
        input_file = args.input if args.input else args.input_file

        if input_file:
            args.javascript = input_file.read()
        elif not sys.stdin.isatty():
            args.javascript = sys.stdin.read()
        else:
            parser.error('No input was provided and there was none from stdin')

        # Exit if input is empty
        if len(args.javascript.strip()) <= 0:
            sys.exit(1)

    # Validate query parameter
    if args.mode == 'query':
        if args.query is None:
            parser.error('argument --query: is required but not provided')
        if len(args.query.strip()) == 0:
            parser.error('argument --query: expected a non empty string')

    # Validate min and max parameter in strings mode
    if args.mode == 'strings':
        if args.min is not None and args.min < 1:
            parser.error("Minimum length must be at least 1")

        if args.max is not None and args.max < 1:
            parser.error("Maximum length must be at least 1")

        if args.min is not None and args.max is not None:
            if args.min >= args.max:
                parser.error("Minimum length must be less than Maximum length")

    # Disable writing to stdout if verbose is enabled in urls mode
    # since urls are printed as they are found
    if args.mode == 'urls' and args.verbose and args.output == sys.stdout:
        args.output = None

    return args
