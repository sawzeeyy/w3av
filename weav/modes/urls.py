import re
import sys
import importlib.resources

from itertools import product
from weav.core.jsparser import parse_javascript
from weav.core.url_utils import is_url_pattern, is_path_pattern, is_filename_pattern
from weav.core.html import extract_urls_from_html, extract_inline_scripts_from_html
from weav.core.context import populate_symbol_tables, should_skip_pass1, should_use_file_value


# Load MIME types from config files
def load_mime_types():
    mime_types = set()

    # Load IANA official MIME types
    with importlib.resources.files('weav.config').joinpath('iana-mimetypes.txt')\
            .open('r') as file:
        mime_types.update(line.strip() for line in file if line.strip())

    # Load additional non-standard MIME types
    with importlib.resources.files('weav.config').joinpath('mimetypes.txt')\
            .open('r') as file:
        mime_types.update(line.strip() for line in file if line.strip())

    return mime_types


def clean_unbalanced_brackets(text):
    """
    Removes trailing unbalanced brackets/parentheses from URLs.

    Uses balanced brackets algorithm to detect mismatched closing brackets.
    Example: 'https://github.com/repo)' -> 'https://github.com/repo'
    """
    if not text or not isinstance(text, str):
        return text

    brackets = {'(': ')', '[': ']', '{': '}'}
    closing = set(brackets.values())
    stack = []
    valid_length = len(text)

    for i, char in enumerate(text):
        if char in brackets:
            stack.append((char, i))
        elif char in closing:
            if stack and brackets[stack[-1][0]] == char:
                stack.pop()
            else:
                # Unbalanced closing bracket - truncate here
                valid_length = i
                break

    return text[:valid_length]


def process_html_content(text, placeholder):
    """
    Helper function to extract URLs from HTML content and inline scripts.
    Returns list of URL entries or None if no URLs found.
    """
    if not text or '<' not in text or '>' not in text:
        return None

    results = []

    # Extract URLs from HTML attributes
    html_urls = extract_urls_from_html(text, placeholder=placeholder, html_parser=html_parser_backend)
    if html_urls:
        results.extend(html_urls)

    # Extract inline JavaScript from <script> tags and parse them
    inline_scripts = extract_inline_scripts_from_html(text, html_parser=html_parser_backend)
    for script_code in inline_scripts:
        # Parse the inline JavaScript to extract URLs
        try:
            _, script_root_node = parse_javascript(script_code)
            if script_root_node:
                # Traverse the inline script's AST directly
                # URLs will be added to global url_entries
                traverse_node(script_root_node, placeholder, verbose=False)
        except Exception:
            # If parsing fails, skip this inline script
            pass

    return results if results else None


def is_junk_url(text, placeholder='FUZZ'):
    """
    Filters out non-URL strings that shouldn't be in results.

    Rejects:
    - MIME types
    - Incomplete protocols (http://, https://, //)
    - Property paths (action.target.name, util.promisify.custom)
    - W3C namespace URIs
    - Single-parameter paths (/{t}, /{a})
    - Generic test URLs
    """
    if not text or not isinstance(text, str):
        return True

    # MIME types (exact match or with parameters)
    base_mime = text.split(';')[0].split(',')[0].strip()
    if base_mime in mime_types:
        return True

    # Starts with MIME type pattern
    if re.match(r'^(application|text|image|audio|video|font|multipart)/', text):
        return True

    # Incomplete protocols only
    if text in ['http://', 'https://', '//', 'https:', 'http:']:
        return True

    # Protocol + only placeholder (no actual domain/path info)
    # Matches: https://FUZZ, https://FUZZ/, http://FUZZ, http://FUZZ/
    # But NOT template variables like https://{domain} which are meaningful
    if text == f'https://{placeholder}' or text == f'https://{placeholder}/' or \
       text == f'http://{placeholder}' or text == f'http://{placeholder}/':
        return True

    # Property paths (word.word.word without slashes)
    # BUT exclude legitimate filenames with valid extensions
    if re.match(r'^[a-z]+\.[a-z]+\.[a-z.]+$', text, re.IGNORECASE) and '/' not in text:
        # Check if it's a valid filename first
        if not is_filename_pattern(text):
            return True

    # W3C/XML namespaces
    if text.startswith('http://www.w3.org/'):
        return True

    # Generic single-parameter paths
    if re.match(r'^/\{[^}]+\}$', text):  # /{t}, /{a}, /{n.pathname}
        return True

    # Generic localhost/test URLs
    if text in ['http://localhost', 'http://a', 'http://test/path']:
        return True

    # Too generic paths
    if text in ['./', f'/{placeholder}', f'//{placeholder}']:
        return True

    # Paths that are only placeholders separated by slashes (no actual path info)
    # Examples: FUZZ/FUZZ, FUZZ/FUZZ/FUZZ/FUZZ/FUZZ
    if re.match(f'^{re.escape(placeholder)}(/{re.escape(placeholder)})+$', text):
        return True

    # Date/time format placeholders (no actual value)
    # Examples: /yyyy/mm/dd/, /YYYY/MM/DD/, /yyyy-mm-dd/, /dd/mm/yyyy/
    # Also catches template versions: /yyyy/{mm}/{dd}/, /{yyyy}/{mm}/{dd}/
    if re.match(r'^/+(yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})[/-](mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})/?$', text, re.IGNORECASE):
        return True
    if re.match(r'^/+(dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-](mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$', text, re.IGNORECASE):
        return True
    if re.match(r'^/+(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})[/-](dd|DD|d|D|\{dd\}|\{DD\}|\{d\}|\{D\})[/-](yyyy|YYYY|yy|YY|\{yyyy\}|\{YYYY\}|\{yy\}|\{YY\})/?$', text, re.IGNORECASE):
        return True
    # Time format placeholders: /hh:mm:ss/, /HH:MM/, /{hh}:{mm}/, etc.
    if re.match(r'^/+(hh|HH|h|H|\{hh\}|\{HH\}|\{h\}|\{H\}):(mm|MM|m|M|\{mm\}|\{MM\}|\{m\}|\{M\})(:(ss|SS|s|S|\{ss\}|\{SS\}|\{s\}|\{S\}))?/?$', text, re.IGNORECASE):
        return True

    # IANA timezone identifiers (Continent/City format)
    # Examples: Europe/Bucharest, America/New_York, Asia/Tokyo
    # These are not valid URLs and should be filtered
    if re.match(r'^(Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Z][a-zA-Z_-]+$', text):
        return True

    return False


def consolidate_adjacent_placeholders(text, placeholder='FUZZ'):
    """
    Consolidates adjacent placeholders into a single placeholder.

    Example: 'FUZZFUZZ' -> 'FUZZ', '/spaces/FUZZFUZZ' -> '/spaces/FUZZ'

    This handles cases where adjacent template expressions like {t}{i}
    get replaced to become FUZZFUZZ without separators.
    """
    if not text or placeholder not in text:
        return text

    # Replace 2+ consecutive placeholders with single placeholder
    pattern = f'({re.escape(placeholder)}){{2,}}'
    return re.sub(pattern, placeholder, text)


def add_alias(var_name, alias, confidence='medium'):
    """
    Associates a semantic alias with a variable name.

    Parameters:
    - var_name: The original variable name (e.g., 't', 'r', 'a')
    - alias: The meaningful name (e.g., 'contentId', 'orderBy')
    - confidence: How confident we are in this alias ('high', 'medium', 'low')
    """
    if var_name not in alias_table:
        alias_table[var_name] = []

    # Avoid duplicates
    for existing in alias_table[var_name]:
        if existing['alias'] == alias:
            # Update confidence if higher
            if confidence == 'high' and existing['confidence'] != 'high':
                existing['confidence'] = confidence
            return

    alias_table[var_name].append({
        'alias': alias,
        'confidence': confidence
    })


def get_best_alias(var_name):
    """
    Returns the most meaningful alias for a variable name.

    Heuristics:
    1. Prefer high-confidence aliases
    2. Avoid generic/temporary names (temp, tmp, val, etc.)
    3. Avoid very generic names (id, key, name, value) - prefer more specific ones
    4. Prefer names with meaningful suffixes (contentId over id, spaceKey over key)
    5. Fall back to original variable name if no good alias found
    """
    if var_name not in alias_table or not alias_table[var_name]:
        return var_name

    # Generic patterns to avoid (substrings and full names)
    generic_patterns = ['temp', 'tmp', 'val', 'test', 'dummy', 'placeholder']
    generic_single = {'x', 'y', 'z', 'i', 'j', 'k', 'n', 'a', 'b', 'c', 'd', 'e'}
    # Very generic but valid names - prefer more specific alternatives
    very_generic = {'id', 'key', 'name', 'title', 'value', 'data', 'item', 'type'}

    # Sort by confidence (high > medium > low)
    confidence_order = {'high': 3, 'medium': 2, 'low': 1}

    candidates = alias_table[var_name][:]

    # Separate candidates into categories
    specific_candidates = []      # Best: specific names like 'contentId', 'spaceKey'
    acceptable_candidates = []    # OK: not generic, not super specific
    very_generic_candidates = []  # Last resort: 'id', 'key', 'name'
    generic_candidates = []       # Avoid: 'temp', 'tmp', 'val'

    for candidate in candidates:
        alias = candidate['alias']
        alias_lower = alias.lower()

        # Check if it's a generic temporary name
        is_temp_generic = (
            alias_lower in generic_single or
            any(pattern in alias_lower for pattern in generic_patterns)
        )

        if is_temp_generic:
            generic_candidates.append(candidate)
            continue

        # Check if it's very generic but valid
        if alias_lower in very_generic:
            very_generic_candidates.append(candidate)
            continue

        # Check if it's a specific compound name (e.g., contentId, spaceKey)
        # These have a generic part but are more specific
        has_generic_part = any(gen in alias_lower for gen in very_generic)
        if has_generic_part and len(alias) > 4:  # Compound names are longer
            specific_candidates.append(candidate)
        else:
            acceptable_candidates.append(candidate)

    # Try each category in order of preference
    for category in [specific_candidates, acceptable_candidates, very_generic_candidates, generic_candidates]:
        if category:
            # Within category, sort by confidence then by length (shorter better for similar confidence)
            category.sort(
                key=lambda x: (confidence_order.get(x['confidence'], 0), -len(x['alias'])),
                reverse=True
            )
            return category[0]['alias']

    return var_name


def extract_local_aliases(node, variables_to_find):
    """
    Extracts aliases from the local context (current function scope or nearby nodes).
    This is called during pass 2 when we encounter template strings/concatenations.

    Parameters:
    - node: The current AST node (template_string, binary_expression, etc.)
    - variables_to_find: Set of variable names we want to find aliases for

    Returns:
    - Dictionary mapping variable names to their best local alias
    """
    # If semantic aliases are disabled, return empty dict (use raw variable names)
    global disable_semantic_aliases
    if disable_semantic_aliases:
        return {}

    # Collect ALL possible aliases for each variable first
    all_aliases = {}  # var_name -> list of aliases

    # Walk up the tree to find the enclosing function or block
    current = node.parent
    max_depth = 15  # Increased to allow scanning more context
    depth = 0

    while current and depth < max_depth:
        depth += 1

        # Look for function parameters with destructuring
        if current.type in ['arrow_function', 'function_declaration', 'function', 'method_definition']:
            # Check parameters for destructuring patterns
            if current.type == 'arrow_function':
                # Arrow functions can have parameters directly or in a formal_parameters node
                for child in current.named_children:
                    if child.type == 'formal_parameters':
                        for param in child.named_children:
                            if param.type == 'object_pattern':
                                _collect_aliases_from_pattern(param, variables_to_find, all_aliases)
                    elif child.type == 'object_pattern':
                        _collect_aliases_from_pattern(child, variables_to_find, all_aliases)
            else:
                # Regular function - look for formal_parameters
                params_node = current.child_by_field_name('parameters')
                if params_node:
                    for param in params_node.named_children:
                        if param.type == 'object_pattern':
                            _collect_aliases_from_pattern(param, variables_to_find, all_aliases)

        # Look for nearby patterns in the same block or program
        if current.type in ['statement_block', 'program']:
            for sibling in current.named_children:
                # Check variable declarations with object literals
                if sibling.type in ['lexical_declaration', 'variable_declaration']:
                    for declarator in sibling.named_children:
                        if declarator.type == 'variable_declarator':
                            value = declarator.child_by_field_name('value')
                            # Object literal: const obj = { id: x }
                            if value and value.type == 'object':
                                _collect_aliases_from_pattern(value, variables_to_find, all_aliases)
                            # Destructuring: const {id: x} = obj
                            elif value and value.type == 'object_pattern':
                                _collect_aliases_from_pattern(value, variables_to_find, all_aliases)
                            # Check if the name itself is a destructuring pattern
                            name = declarator.child_by_field_name('name')
                            if name and name.type == 'object_pattern':
                                _collect_aliases_from_pattern(name, variables_to_find, all_aliases)

                # Check for FormData.append() calls
                if sibling.type == 'expression_statement':
                    # expression_statement doesn't have 'expression' field, use first named child
                    named_children = sibling.named_children
                    if named_children:
                        expr = named_children[0]
                        if expr.type == 'call_expression':
                            # Check if it's formData.append('key', value)
                            func_node = expr.child_by_field_name('function')
                            if func_node and func_node.type == 'member_expression':
                                prop = func_node.child_by_field_name('property')
                                if prop and prop.text.decode('utf8') == 'append':
                                    # Get arguments
                                    args_node = expr.child_by_field_name('arguments')
                                    if args_node:
                                        args = [c for c in args_node.named_children]
                                        if len(args) >= 2:
                                            # First arg is the key (string)
                                            # Second arg is the value (could be variable)
                                            key_node = args[0]
                                            value_node = args[1]

                                            if key_node.type == 'string' and value_node.type == 'identifier':
                                                key = extract_string_value(key_node)
                                                var_name = value_node.text.decode('utf8')
                                                if var_name in variables_to_find:
                                                    if var_name not in all_aliases:
                                                        all_aliases[var_name] = []
                                                    all_aliases[var_name].append(key)

                # Check for URLSearchParams constructor: new URLSearchParams({key: value})
                if sibling.type in ['lexical_declaration', 'variable_declaration']:
                    for declarator in sibling.named_children:
                        if declarator.type == 'variable_declarator':
                            value = declarator.child_by_field_name('value')
                            if value and value.type == 'new_expression':
                                # Check if it's URLSearchParams
                                constructor = value.child_by_field_name('constructor')
                                if constructor and constructor.text.decode('utf8') == 'URLSearchParams':
                                    args_node = value.child_by_field_name('arguments')
                                    if args_node:
                                        args = [c for c in args_node.named_children]
                                        if args and args[0].type == 'object':
                                            _collect_aliases_from_pattern(args[0], variables_to_find, all_aliases)

        current = current.parent

    # Now choose the best alias for each variable from all collected aliases
    return _choose_best_aliases(all_aliases)


def _collect_aliases_from_pattern(pattern_node, variables_to_find, all_aliases_dict):
    """
    Helper to collect aliases from an object literal or destructuring pattern.
    Appends to the list of aliases for each variable.
    """
    if pattern_node.type not in ['object', 'object_pattern']:
        return

    for pair in pattern_node.named_children:
        if pair.type in ['pair', 'pair_pattern']:
            key_node = pair.child_by_field_name('key')
            value_node = pair.child_by_field_name('value')

            if not key_node or not value_node:
                continue

            # Get property name (the alias)
            prop_name = key_node.text.decode('utf8').strip('"\'')

            # Check if value is an identifier we care about
            if value_node.type == 'identifier':
                var_name = value_node.text.decode('utf8')
                if var_name in variables_to_find:
                    if var_name not in all_aliases_dict:
                        all_aliases_dict[var_name] = []
                    all_aliases_dict[var_name].append(prop_name)


def _choose_best_aliases(all_aliases):
    """
    Given a dict of variable_name -> [list of aliases], choose the best alias for each.
    Returns a dict of variable_name -> best_alias.
    """
    result = {}

    for var_name, alias_list in all_aliases.items():
        if not alias_list:
            continue

        # If only one alias, use it
        if len(alias_list) == 1:
            result[var_name] = alias_list[0]
            continue

        # Multiple aliases - pick the best one using heuristics
        generic_patterns = {'temp', 'value', 'data', 'var', 'val', 'item'}

        def score_alias(alias):
            """Lower score is better."""
            score = len(alias)  # Start with length

            # Check if it's generic
            lower_alias = alias.lower()
            if any(pattern in lower_alias for pattern in generic_patterns):
                score += 100  # Heavily penalize generic names

            # Reward common meaningful suffixes/prefixes
            if any(pattern in lower_alias for pattern in ['id', 'key', 'name', 'code', 'type', 'status']):
                score -= 5

            return score

        # Sort by score and pick the best (lowest score)
        best_alias = min(alias_list, key=score_alias)
        result[var_name] = best_alias

    return result


def _extract_aliases_from_pattern(pattern_node, variables_to_find, aliases_dict):
    """
    DEPRECATED: Use _collect_aliases_from_pattern() instead.
    This is kept for backward compatibility but should not be used.

    Helper to extract aliases from an object literal or destructuring pattern.
    Only extracts for variables in variables_to_find set.

    When multiple aliases are found for the same variable, we use heuristics to pick the best one:
    - Prefer shorter names (likely more meaningful)
    - Prefer names that don't look generic (temp, value, data, etc.)
    """
    if pattern_node.type not in ['object', 'object_pattern']:
        return

    # Collect all aliases for each variable
    temp_aliases = {}  # var_name -> list of aliases

    for pair in pattern_node.named_children:
        if pair.type in ['pair', 'pair_pattern']:
            key_node = pair.child_by_field_name('key')
            value_node = pair.child_by_field_name('value')

            if not key_node or not value_node:
                continue

            # Get property name (the alias)
            prop_name = key_node.text.decode('utf8').strip('"\'')

            # Check if value is an identifier we care about
            if value_node.type == 'identifier':
                var_name = value_node.text.decode('utf8')
                if var_name in variables_to_find:
                    if var_name not in temp_aliases:
                        temp_aliases[var_name] = []
                    temp_aliases[var_name].append(prop_name)

    # Now choose the best alias for each variable
    for var_name, alias_list in temp_aliases.items():
        if not alias_list:
            continue

        # If only one alias, use it
        if len(alias_list) == 1:
            aliases_dict[var_name] = alias_list[0]
            continue

        # Multiple aliases - pick the best one
        # Heuristics:
        # 1. Avoid generic names (temp, value, data, etc.)
        # 2. Prefer shorter names
        # 3. Prefer names with meaningful prefixes (id, key, name, etc.)

        generic_patterns = {'temp', 'value', 'data', 'var', 'val', 'item'}

        def score_alias(alias):
            """Lower score is better."""
            score = len(alias)  # Start with length

            # Check if it's generic
            lower_alias = alias.lower()
            if any(pattern in lower_alias for pattern in generic_patterns):
                score += 100  # Heavily penalize generic names

            # Reward common meaningful suffixes/prefixes
            if any(pattern in lower_alias for pattern in ['id', 'key', 'name', 'code', 'type', 'status']):
                score -= 5

            return score

        # Sort by score and pick the best (lowest score)
        best_alias = min(alias_list, key=score_alias)
        aliases_dict[var_name] = best_alias


def extract_aliases_from_object(obj_node, context_vars=None):
    """
    Scans an object literal or destructuring pattern for property-value pairs
    where values are identifiers.
    Associates property names (aliases) with the variable names (values).

    Example: { contentId: t, orderBy: r } → t gets alias 'contentId', r gets 'orderBy'
    Also works with destructuring: const {contentId: t} = obj → t gets alias 'contentId'

    Parameters:
    - obj_node: AST node of type 'object' or 'object_pattern'
    - context_vars: Optional set of variable names to look for (for scoping)
    """
    if obj_node.type not in ['object', 'object_pattern']:
        return

    for pair in obj_node.named_children:
        # Handle both regular pairs and destructuring pairs
        if pair.type in ['pair', 'pair_pattern']:
            key_node = pair.child_by_field_name('key')
            value_node = pair.child_by_field_name('value')

            if not key_node or not value_node:
                continue

            # Get property name (the alias)
            prop_name = key_node.text.decode('utf8').strip('"\'')

            # Check if value is an identifier (variable reference)
            if value_node.type == 'identifier':
                var_name = value_node.text.decode('utf8')

                # Only add if we care about this variable (if context_vars specified)
                if context_vars is None or var_name in context_vars:
                    add_alias(var_name, prop_name, confidence='high')

            # Handle shorthand property notation: { contentId } → { contentId: contentId }
            elif value_node.type in ['shorthand_property_identifier', 'shorthand_property_identifier_pattern']:
                var_name = value_node.text.decode('utf8')
                if context_vars is None or var_name in context_vars:
                    # In shorthand, the property name IS the variable name, so no alias needed
                    pass


def scan_for_urlsearchparams(node, context_vars=None):
    """
    Detects URLSearchParams or FormData patterns and extracts aliases.

    Examples:
    - new URLSearchParams({ key: t }) → t gets alias 'key'
    - params.append('key', t) → t gets alias 'key'
    - new FormData().append('userId', u) → u gets alias 'userId'
    """
    if node.type == 'new_expression':
        # new URLSearchParams({ ... }) or new FormData()
        constructor = node.child_by_field_name('constructor')
        if constructor:
            constructor_name = constructor.text.decode('utf8')
            if constructor_name in ['URLSearchParams', 'FormData']:
                args_node = node.child_by_field_name('arguments')
                if args_node and args_node.named_child_count > 0:
                    first_arg = args_node.named_child(0)
                    if first_arg.type == 'object':
                        extract_aliases_from_object(first_arg, context_vars)

    elif node.type == 'call_expression':
        # params.append('key', value) or params.set('key', value)
        func_node = node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop and prop.text.decode('utf8') in ['append', 'set']:
                args_node = node.child_by_field_name('arguments')
                if args_node and args_node.named_child_count >= 2:
                    key_arg = args_node.named_child(0)
                    value_arg = args_node.named_child(1)

                    # Extract key name from string literal
                    if key_arg.type == 'string':
                        key_name = extract_string_value(key_arg)
                        if key_name and value_arg.type == 'identifier':
                            var_name = value_arg.text.decode('utf8')
                            if context_vars is None or var_name in context_vars:
                                add_alias(var_name, key_name, confidence='high')


def scan_sibling_nodes_for_aliases(parent_node, var_name):
    """
    Scans sibling nodes in the same statement/declaration for alias hints.
    This catches patterns like:

    const t = '123';
    const params = { contentId: t };
    """
    if not parent_node:
        return

    # Look at siblings in variable declarations
    for sibling in parent_node.named_children:
        if sibling.type == 'variable_declarator':
            value_node = sibling.child_by_field_name('value')
            if value_node:
                # Check for object literals
                if value_node.type == 'object':
                    extract_aliases_from_object(value_node, {var_name})
                # Check for URLSearchParams/FormData
                elif value_node.type in ['new_expression', 'call_expression']:
                    scan_for_urlsearchparams(value_node, {var_name})


def extract_string_value(node):
    """
    Extracts clean string value from AST string node (removes quotes).
    """
    if node.type != 'string':
        return None

    text = node.text.decode('utf8')
    # Remove quotes
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def resolve_member_expression(node, placeholder='FUZZ'):
    """
    Resolves member expressions by navigating object_table hierarchy
    or using defaults for known properties.

    Returns list of values.
    """
    if node.type != 'member_expression':
        return [placeholder]

    # Build path: window.location.origin -> ['window', 'location', 'origin']
    path = []
    current = node

    while current and current.type == 'member_expression':
        # Get property name
        prop_node = current.child_by_field_name('property')
        if prop_node:
            path.insert(0, prop_node.text.decode('utf8'))

        # Move to object
        current = current.child_by_field_name('object')

    # Get base object name
    if current:
        path.insert(0, current.text.decode('utf8'))

    # Special handling for location properties
    if len(path) >= 2:
        # Check for window.location.* or location.*
        loc_idx = -1
        if path[0] == 'window' and len(path) >= 2 and path[1] == 'location':
            loc_idx = 1
        elif path[0] == 'location':
            loc_idx = 0

        if loc_idx >= 0:
            if len(path) > loc_idx + 1:
                prop = path[loc_idx + 1]
                if prop == 'protocol':
                    return ['https:']
                elif prop == 'hostname':
                    return [placeholder]
                elif prop == 'host':
                    return [placeholder]
                elif prop == 'origin':
                    return [f'https://{placeholder}']
                elif prop == 'pathname':
                    return [f'/{placeholder}']
                elif prop in ['port', 'search', 'hash']:
                    return ['']

    # Navigate object_table
    if not path:
        return [placeholder]

    obj_name = path[0]
    if obj_name not in object_table:
        return [placeholder]

    current_obj = object_table[obj_name]
    for prop in path[1:]:
        if not isinstance(current_obj, dict) or prop not in current_obj:
            return [placeholder]
        current_obj = current_obj[prop]

    # Should be a list of values
    if isinstance(current_obj, list):
        return current_obj

    return [placeholder]


def resolve_subscript_expression(node, placeholder='FUZZ'):
    """
    Resolves computed property access (bracket notation).

    Returns list of values.
    """
    if node.type != 'subscript_expression':
        return [placeholder]

    obj_node = node.child_by_field_name('object')
    index_node = node.child_by_field_name('index')

    if not obj_node or not index_node:
        return [placeholder]

    # Get object name
    obj_name = obj_node.text.decode('utf8')

    # Get property key(s)
    keys = []
    if index_node.type == 'string':
        key = extract_string_value(index_node)
        if key:
            keys = [key]
    elif index_node.type == 'identifier':
        var_name = index_node.text.decode('utf8')
        if var_name in symbol_table:
            keys = symbol_table[var_name]

    if not keys:
        return [placeholder]

    # Navigate object_table
    results = []
    for key in keys:
        if obj_name in object_table and key in object_table[obj_name]:
            results.extend(object_table[obj_name][key])

    return results if results else [placeholder]


def resolve_join_call(node, placeholder='FUZZ'):
    """
    Resolves .join() method calls on arrays.

    Returns list with single joined string.
    """
    if node.type != 'call_expression':
        return [placeholder]

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return [placeholder]

    # Get array name
    obj_node = func_node.child_by_field_name('object')
    if not obj_node:
        return [placeholder]

    array_name = obj_node.text.decode('utf8')

    # Get separator from arguments
    args_node = node.child_by_field_name('arguments')
    separator = ''
    if args_node and args_node.named_child_count > 0:
        arg = args_node.named_child(0)
        if arg.type == 'string':
            separator = extract_string_value(arg) or ''

    # Lookup array in array_table
    if array_name not in array_table:
        return [placeholder]

    elements = array_table[array_name]
    return [separator.join(elements)]


def resolve_replace_call(node, placeholder='FUZZ'):
    """
    Resolves .replace() method calls with simple string replacements.

    Returns list with single replaced string.
    """
    if node.type != 'call_expression':
        return [placeholder]

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return [placeholder]

    # Get base string
    obj_node = func_node.child_by_field_name('object')
    if not obj_node:
        return [placeholder]

    base_values = []
    if obj_node.type == 'string':
        val = extract_string_value(obj_node)
        if val:
            base_values = [val]
    elif obj_node.type == 'identifier':
        var_name = obj_node.text.decode('utf8')
        if var_name in symbol_table:
            base_values = symbol_table[var_name]

    if not base_values:
        return [placeholder]

    # Get search pattern and replacement
    args_node = node.child_by_field_name('arguments')
    if not args_node or args_node.named_child_count < 2:
        return [placeholder]

    search_node = args_node.named_child(0)
    replace_node = args_node.named_child(1)

    # Only support string literal search (not regex)
    if search_node.type != 'string':
        return [placeholder]

    search_str = extract_string_value(search_node)
    if not search_str:
        return [placeholder]

    # Get replacement value
    replace_values = []
    if replace_node.type == 'string':
        val = extract_string_value(replace_node)
        if val:
            replace_values = [val]
    elif replace_node.type == 'identifier':
        var_name = replace_node.text.decode('utf8')
        if var_name in symbol_table:
            replace_values = symbol_table[var_name]

    if not replace_values:
        replace_values = [placeholder]

    # Perform replacement for all combinations
    results = []
    for base in base_values:
        for replace_val in replace_values:
            results.append(base.replace(search_str, replace_val))

    return results


def resolve_binary_expression(node, placeholder='FUZZ'):
    """
    Resolves binary expressions:
    - + operator: string concatenation
    - || operator: logical OR (returns right side as fallback)
    - && operator: logical AND (returns right side as result)

    Returns list of possible values.
    """
    if node.type != 'binary_expression':
        return None

    op = node.child_by_field_name('operator')
    if not op:
        return None

    operator = op.text.decode('utf8')

    left_node = node.child_by_field_name('left')
    right_node = node.child_by_field_name('right')

    left_node = node.child_by_field_name('left')
    right_node = node.child_by_field_name('right')

    if not left_node or not right_node:
        return None

    # Handle logical OR (||) - return right side (fallback value)
    # e.g., window.GLOBAL_URI || "/default" -> ["/default"]
    if operator == '||':
        # For OR expressions, we return the right side (fallback)
        # since we can't evaluate the left side at static analysis time
        if right_node.type == 'string':
            val = extract_string_value(right_node)
            if val is not None:
                return [val]
        elif right_node.type == 'identifier':
            var_name = right_node.text.decode('utf8')
            if var_name in symbol_table:
                return symbol_table[var_name]
        elif right_node.type == 'member_expression':
            return resolve_member_expression(right_node, placeholder)
        # For any other type, return placeholder
        return [placeholder]

    # Handle logical AND (&&) - return right side (result value)
    # e.g., config && config.url -> [config.url value]
    if operator == '&&':
        # For AND expressions, we return the right side (result)
        # assuming the left side is truthy
        if right_node.type == 'string':
            val = extract_string_value(right_node)
            if val is not None:
                return [val]
        elif right_node.type == 'identifier':
            var_name = right_node.text.decode('utf8')
            if var_name in symbol_table:
                return symbol_table[var_name]
        elif right_node.type == 'member_expression':
            return resolve_member_expression(right_node, placeholder)
        # For any other type, return placeholder
        return [placeholder]

    # Handle concatenation (+) - only for this operator do we combine left and right
    if operator != '+':
        return None

    # Resolve left side
    left_values = []
    if left_node.type == 'string':
        val = extract_string_value(left_node)
        if val is not None:
            left_values = [val]
    elif left_node.type == 'identifier':
        var_name = left_node.text.decode('utf8')
        if var_name in symbol_table:
            left_values = symbol_table[var_name]
    elif left_node.type == 'member_expression':
        left_values = resolve_member_expression(left_node, placeholder)
    elif left_node.type == 'subscript_expression':
        left_values = resolve_subscript_expression(left_node, placeholder)
    elif left_node.type == 'binary_expression':
        left_values = resolve_binary_expression(left_node, placeholder)
    elif left_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = left_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    left_values = resolve_join_call(left_node, placeholder)
                elif method_name == 'replace':
                    left_values = resolve_replace_call(left_node, placeholder)

    if not left_values:
        left_values = [placeholder]

    # Resolve right side
    right_values = []
    if right_node.type == 'string':
        val = extract_string_value(right_node)
        if val is not None:
            right_values = [val]
    elif right_node.type == 'identifier':
        var_name = right_node.text.decode('utf8')
        if var_name in symbol_table:
            right_values = symbol_table[var_name]
    elif right_node.type == 'member_expression':
        right_values = resolve_member_expression(right_node, placeholder)
    elif right_node.type == 'subscript_expression':
        right_values = resolve_subscript_expression(right_node, placeholder)
    elif right_node.type == 'binary_expression':
        right_values = resolve_binary_expression(right_node, placeholder)
    elif right_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = right_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    right_values = resolve_join_call(right_node, placeholder)
                elif method_name == 'replace':
                    right_values = resolve_replace_call(right_node, placeholder)

    if not right_values:
        right_values = [placeholder]

    # Generate all combinations
    results = []
    for left in left_values:
        for right in right_values:
            results.append(str(left) + str(right))

    return results


def collect_array_elements(node, array_name, placeholder):
    """
    Processes array literals and populates array_table.
    """
    if node.type != 'array':
        return

    elements = []
    for child in node.named_children:
        if child.type == 'string':
            val = extract_string_value(child)
            if val:
                elements.append(val)
        elif child.type == 'identifier':
            var_name = child.text.decode('utf8')
            if var_name in symbol_table and symbol_table[var_name]:
                # Add all values
                elements.extend(symbol_table[var_name])
            else:
                elements.append(placeholder)
        elif child.type == 'binary_expression':
            resolved = resolve_binary_expression(child, placeholder)
            if resolved:
                elements.extend(resolved)
            else:
                elements.append(placeholder)
        elif child.type == 'member_expression':
            resolved = resolve_member_expression(child, placeholder)
            elements.extend(resolved)
        else:
            elements.append(placeholder)

    array_table[array_name] = elements


def collect_object_properties(node, obj_name, placeholder):
    """
    Recursively processes object literals and populates object_table.
    Also extracts semantic aliases from property-value pairs.
    """
    if node.type != 'object':
        return

    if obj_name not in object_table:
        object_table[obj_name] = {}

    # Extract aliases from this object literal
    extract_aliases_from_object(node)

    for child in node.named_children:
        if child.type == 'pair':
            # Get property name
            key_node = child.child_by_field_name('key')
            value_node = child.child_by_field_name('value')

            if not key_node or not value_node:
                continue

            prop_name = key_node.text.decode('utf8')
            # Remove quotes if property is a string
            if prop_name.startswith('"') or prop_name.startswith("'"):
                prop_name = prop_name[1:-1]

            # Extract value
            values = []
            if value_node.type == 'string':
                val = extract_string_value(value_node)
                if val:
                    values = [val]
            elif value_node.type == 'identifier':
                var_name = value_node.text.decode('utf8')
                if var_name in symbol_table:
                    values = symbol_table[var_name]
                else:
                    values = [placeholder]
            elif value_node.type == 'binary_expression':
                resolved = resolve_binary_expression(value_node, placeholder)
                if resolved:
                    values = resolved
            elif value_node.type == 'member_expression':
                values = resolve_member_expression(value_node, placeholder)
            elif value_node.type == 'object':
                # Nested object
                nested_obj_name = f"{obj_name}.{prop_name}"
                collect_object_properties(value_node, obj_name, placeholder)
                # Create nested structure
                if prop_name not in object_table[obj_name]:
                    object_table[obj_name][prop_name] = {}
                continue

            if values:
                object_table[obj_name][prop_name] = values


def collect_object_assignment(node, placeholder):
    """
    Processes assignment expressions where left side is a member expression.
    """
    if node.type != 'assignment_expression':
        return

    left_node = node.child_by_field_name('left')
    right_node = node.child_by_field_name('right')

    if not left_node or not right_node or left_node.type != 'member_expression':
        return

    # Extract member expression path
    path = []
    current = left_node

    while current and current.type == 'member_expression':
        prop_node = current.child_by_field_name('property')
        if prop_node:
            path.insert(0, prop_node.text.decode('utf8'))
        current = current.child_by_field_name('object')

    if current:
        path.insert(0, current.text.decode('utf8'))

    if len(path) < 2:
        return

    # Extract right side value
    values = []
    if right_node.type == 'string':
        val = extract_string_value(right_node)
        if val:
            values = [val]
    elif right_node.type == 'identifier':
        var_name = right_node.text.decode('utf8')
        if var_name in symbol_table:
            values = symbol_table[var_name]
        else:
            values = [placeholder]
    elif right_node.type == 'binary_expression':
        resolved = resolve_binary_expression(right_node, placeholder)
        if resolved:
            values = resolved
    elif right_node.type == 'member_expression':
        values = resolve_member_expression(right_node, placeholder)

    if not values:
        return

    # Navigate/create path in object_table
    obj_name = path[0]
    if obj_name not in object_table:
        object_table[obj_name] = {}

    current_obj = object_table[obj_name]
    for i, prop in enumerate(path[1:-1]):
        if prop not in current_obj:
            current_obj[prop] = {}
        elif not isinstance(current_obj[prop], dict):
            # Property was previously set as a value, convert to nested structure
            current_obj[prop] = {}
        current_obj = current_obj[prop]

    # Set final property
    final_prop = path[-1]

    # If final_prop exists and is a dict (from nested paths), skip appending
    if final_prop in current_obj and isinstance(current_obj[final_prop], dict):
        return

    if final_prop not in current_obj:
        current_obj[final_prop] = []

    # Append values (deduplicate)
    for val in values:
        if val not in current_obj[final_prop]:
            current_obj[final_prop].append(val)


def collect_variable_assignment(node, placeholder, context=None, context_policy='merge'):
    """
    Processes variable declarators and appends their values to symbol_table.
    Also scans for semantic aliases from nearby object literals.

    Parameters:
    - node: AST node to process
    - placeholder: Placeholder string for unknown values
    - context: Parsed context dictionary (external variable definitions)
    - context_policy: How to handle context/file collisions ('merge', 'override', 'only')
    """
    var_name = None
    value_node = None
    parent_node = None

    if node.type == 'variable_declarator':
        name_node = node.child_by_field_name('name')
        value_node = node.child_by_field_name('value')
        if name_node:
            var_name = name_node.text.decode('utf8')
        # Get parent to scan siblings
        parent_node = node.parent
    elif node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node and left_node.type == 'identifier':
            var_name = left_node.text.decode('utf8')
            value_node = node.child_by_field_name('right')

    if not var_name or not value_node:
        return

    # Check context policy - should we use this file value?
    if context is not None:
        if not should_use_file_value(var_name, context, context_policy):
            # Policy says to ignore file value for this variable
            return

    # Initialize list if first assignment
    if var_name not in symbol_table:
        symbol_table[var_name] = []

    # Extract value
    values = []
    if value_node.type == 'string':
        val = extract_string_value(value_node)
        if val:
            values = [val]
    elif value_node.type == 'identifier':
        ref_name = value_node.text.decode('utf8')
        if ref_name in symbol_table:
            values = symbol_table[ref_name]
    elif value_node.type == 'binary_expression':
        resolved = resolve_binary_expression(value_node, placeholder)
        if resolved:
            values = resolved
    elif value_node.type == 'member_expression':
        values = resolve_member_expression(value_node, placeholder)
    elif value_node.type == 'subscript_expression':
        values = resolve_subscript_expression(value_node, placeholder)
    elif value_node.type == 'array':
        collect_array_elements(value_node, var_name, placeholder)
        # Scan siblings for aliases
        if parent_node:
            scan_sibling_nodes_for_aliases(parent_node, var_name)
        return
    elif value_node.type == 'object':
        collect_object_properties(value_node, var_name, placeholder)
        # Scan siblings for aliases
        if parent_node:
            scan_sibling_nodes_for_aliases(parent_node, var_name)
        return
    elif value_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = value_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    values = resolve_join_call(value_node, placeholder)
                elif method_name == 'replace':
                    values = resolve_replace_call(value_node, placeholder)

    # Append values (deduplicate)
    for val in values:
        if val and val not in symbol_table[var_name]:
            symbol_table[var_name].append(val)

    # Scan sibling nodes for semantic aliases
    if parent_node:
        scan_sibling_nodes_for_aliases(parent_node, var_name)


def build_symbol_table(node, placeholder, context=None, context_policy='merge'):
    """
    First pass - recursively traverses AST to collect variable assignments
    and build object structures.

    Parameters:
    - node: AST node to traverse
    - placeholder: Placeholder string for unknown values
    - context: Parsed context dictionary (external variable definitions)
    - context_policy: How to handle context/file collisions ('merge', 'override', 'only')
    """
    global node_visit_count, max_nodes_limit
    node_visit_count += 1

    if node_visit_count > max_nodes_limit:
        sys.stderr.write(f'\nWarning: Stopped after visiting {max_nodes_limit:,} nodes. File may be too large or complex.\n')
        return

    if node.type == 'lexical_declaration' or node.type == 'variable_declaration':
        for child in node.named_children:
            if child.type == 'variable_declarator':
                collect_variable_assignment(child, placeholder, context=context, context_policy=context_policy)
    elif node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node:
            if left_node.type == 'identifier':
                collect_variable_assignment(node, placeholder, context=context, context_policy=context_policy)
            elif left_node.type == 'member_expression':
                collect_object_assignment(node, placeholder)

    # Recurse
    for child in node.named_children:
        build_symbol_table(child, placeholder, context=context, context_policy=context_policy)


def add_url_entry(entry, verbose):
    """
    Adds entry to results, handles deduplication and lists.
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
                # Note: We don't have placeholder here, so using default 'FUZZ'
                if not is_junk_url(url_to_print):
                    print(f"{url_to_print}")


def convert_route_params(text, placeholder='FUZZ'):
    """
    Converts route parameters to template syntax.
    Handles: :id -> {id}, [param] -> {param}
    Returns (original_text, converted_text, has_params).

    Examples:
        '/users/:id' -> ('/users/:id', '/users/{id}', True)
        'archives/vendor-list-v[VERSION].json' -> ('archives/vendor-list-v[VERSION].json', 'archives/vendor-list-v{VERSION}.json', True)
        '/blog/:slug/comments/:commentId' -> ('/blog/:slug/comments/:commentId', '/blog/{slug}/comments/{commentId}', True)
        '/static/path' -> ('/static/path', '/static/path', False)
    """
    has_params = False
    converted = text

    # Match route parameters like :id, :slug, :userId
    route_param_pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)'
    if re.search(route_param_pattern, converted):
        converted = re.sub(route_param_pattern, r'{\1}', converted)
        has_params = True

    # Match bracket parameters like [VERSION], [ID], [param]
    bracket_param_pattern = r'\[([a-zA-Z_][a-zA-Z0-9_]*)\]'
    if re.search(bracket_param_pattern, converted):
        converted = re.sub(bracket_param_pattern, r'{\1}', converted)
        has_params = True

    return (text, converted, has_params)


def process_string_literal(node, placeholder):
    """
    Extracts URLs from plain string literals.
    Also detects HTML content and extracts URLs from HTML attributes.
    """
    if node.type != 'string':
        return None

    text = extract_string_value(node)
    if not text:
        return None

    # Check if string contains HTML content
    html_results = process_html_content(text, placeholder)
    if html_results:
        return html_results if len(html_results) > 1 else html_results[0]

    # Check if entire string is a URL or path
    if is_url_pattern(text) or is_path_pattern(text):
        # Check for route parameters like :id, :slug
        original_text, converted_text, has_params = convert_route_params(text, placeholder)

        if has_params:
            # Has route parameters - treat as template
            # Replace {param} with FUZZ for placeholder version
            placeholder_text = re.sub(r'\{[^}]+\}', placeholder, converted_text)
            return {
                'original': converted_text,  # Use template syntax {id}
                'placeholder': placeholder_text,  # Use FUZZ
                'resolved': placeholder_text,
                'has_template': True
            }
        else:
            # No route parameters - static URL
            return {
                'original': text,
                'placeholder': text,
                'resolved': text,
                'has_template': False
            }

    # Extract embedded URLs using regex
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    matches = re.findall(url_pattern, text)

    if matches:
        results = []
        for match in matches:
            results.append({
                'original': match,
                'placeholder': match,
                'resolved': match,
                'has_template': False
            })
        return results if len(results) > 1 else results[0]

    return None


def process_template_string(node, placeholder):
    """
    Handles template literals with ${} substitutions.
    Generates all combinations when variables have multiple values.
    Uses local context to extract semantic aliases for better parameter names.
    """
    if node.type != 'template_string':
        return None

    # First, collect all variables used in this template
    variables_in_template = set()
    for child in node.named_children:
        if child.type == 'template_substitution':
            expr = child.named_child(0)
            if expr and expr.type == 'identifier':
                variables_in_template.add(expr.text.decode('utf8'))
            elif expr and expr.type == 'member_expression':
                # Get base variable from member expression
                base_var = None
                current = expr
                while current and current.type == 'member_expression':
                    obj_node = current.child_by_field_name('object')
                    if obj_node and obj_node.type == 'identifier':
                        base_var = obj_node.text.decode('utf8')
                        break
                    current = obj_node
                if base_var:
                    variables_in_template.add(base_var)

    # Extract local aliases for these variables
    local_aliases = extract_local_aliases(node, variables_in_template)

    # Store parts as lists of possible values for generating combinations
    original_parts = []
    resolved_parts_lists = []  # List of lists - each inner list is possible values for that position
    has_template = False

    for child in node.named_children:
        if child.type == 'string_fragment':
            text = child.text.decode('utf8')
            # Convert route parameters in literal fragments before adding to parts
            _, converted_text, _ = convert_route_params(text, placeholder)
            original_parts.append(converted_text)
            resolved_parts_lists.append([converted_text])  # Single value - the literal text
        elif child.type == 'template_substitution':
            has_template = True
            expr = child.named_child(0)
            if expr:
                expr_text = expr.text.decode('utf8')

                # Use local context alias if available
                display_name = expr_text
                if expr.type == 'identifier':
                    var_name = expr_text
                    # Use local alias if found, otherwise use variable name
                    display_name = local_aliases.get(var_name, var_name)
                elif expr.type == 'member_expression':
                    # For member expressions, try to use alias for base variable
                    base_var = None
                    current = expr
                    while current and current.type == 'member_expression':
                        obj_node = current.child_by_field_name('object')
                        if obj_node and obj_node.type == 'identifier':
                            base_var = obj_node.text.decode('utf8')
                            break
                        current = obj_node

                    if base_var:
                        # Try to use local alias for base variable
                        alias = local_aliases.get(base_var, base_var)
                        if alias != base_var:
                            # Replace base variable name with alias in member expression
                            display_name = expr_text.replace(base_var, alias, 1)

                # Normalize to {var} format (not ${var})
                original_parts.append(f'{{{display_name}}}')

                # Try to resolve - collect ALL possible values
                values = []
                if expr.type == 'identifier':
                    var_name = expr_text
                    if var_name in symbol_table and symbol_table[var_name]:
                        # Use ALL values to generate all combinations
                        values = symbol_table[var_name][:]
                    else:
                        values = [placeholder]
                elif expr.type == 'member_expression':
                    resolved = resolve_member_expression(expr, placeholder)
                    values = resolved if resolved else [placeholder]
                else:
                    values = [placeholder]

                resolved_parts_lists.append(values)

    # Generate original template string with {var} syntax
    original = ''.join(original_parts)

    # Generate all combinations of resolved values
    all_combinations = list(product(*resolved_parts_lists))

    # If no template substitutions, just return single result
    if not has_template:
        resolved = ''.join(all_combinations[0]) if all_combinations else original
        placeholder_str = resolved

        # Check for HTML content first
        html_results = process_html_content(resolved, placeholder)
        if html_results:
            return html_results if len(html_results) > 1 else html_results[0]

        if is_url_pattern(original) or is_path_pattern(original):
            return {
                'original': original,
                'placeholder': placeholder_str,
                'resolved': resolved,
                'has_template': False
            }
        return None

    # Generate results for all combinations
    results = []
    for combo in all_combinations:
        resolved = ''.join(combo)

        # Check if this combination is a URL/path pattern
        if (is_url_pattern(original) or is_path_pattern(original) or
            is_url_pattern(resolved) or is_path_pattern(resolved)):

            # Check for route parameters in the result and convert them
            _, converted_original, has_route_params = convert_route_params(original, placeholder)
            _, converted_resolved, _ = convert_route_params(resolved, placeholder)

            if has_route_params:
                # Route params make it a template
                final_original = converted_original
                # Replace {param} with FUZZ
                final_resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
                final_resolved = consolidate_adjacent_placeholders(final_resolved, placeholder)
            else:
                # Has template substitutions but no route params
                final_original = converted_original
                final_resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
                final_resolved = consolidate_adjacent_placeholders(final_resolved, placeholder)

            entry = {
                'original': final_original,
                'placeholder': final_resolved,
                'has_template': True
            }
            if final_resolved != final_original:
                entry['resolved'] = final_resolved
            results.append(entry)

    # Return all results or None
    return results if results else None


def process_binary_expression(node, placeholder):
    """
    Handles string concatenation with + operator, .join(), and .replace().
    """
    if node.type != 'binary_expression':
        return None

    def extract_concat_parts(n):
        """Recursively extracts parts from concatenation tree."""
        if n.type == 'binary_expression':
            op = n.child_by_field_name('operator')
            if op and op.text.decode('utf8') == '+':
                left = n.child_by_field_name('left')
                right = n.child_by_field_name('right')
                left_parts = extract_concat_parts(left) if left else []
                right_parts = extract_concat_parts(right) if right else []
                return left_parts + right_parts

        if n.type == 'string':
            val = extract_string_value(n)
            return [('literal', val)] if val else []
        elif n.type == 'identifier':
            return [('identifier', n.text.decode('utf8'))]
        elif n.type == 'member_expression':
            return [('member', n)]  # Pass the node itself, not just text
        elif n.type == 'template_string':
            # Handle template string in concatenation
            result = process_template_string(n, placeholder)
            if result:
                return [('template', result)]
            return []
        elif n.type == 'call_expression':
            # Check for .join() or .replace()
            func_node = n.child_by_field_name('function')
            if func_node and func_node.type == 'member_expression':
                prop = func_node.child_by_field_name('property')
                if prop:
                    method_name = prop.text.decode('utf8')
                    if method_name == 'join':
                        return [('join', n)]
                    elif method_name == 'replace':
                        return [('replace', n)]

        return [('unknown', n.text.decode('utf8'))]

    parts = extract_concat_parts(node)

    # Collect all variables used in the concatenation for alias extraction
    variables_in_concat = set()
    for part_type, part_value in parts:
        if part_type == 'identifier':
            variables_in_concat.add(part_value)
        elif part_type == 'member':
            # Extract base variable from member expression
            member_node = part_value
            current = member_node
            while current and current.type == 'member_expression':
                obj_node = current.child_by_field_name('object')
                if obj_node and obj_node.type == 'identifier':
                    variables_in_concat.add(obj_node.text.decode('utf8'))
                    break
                current = obj_node

    # Extract local aliases for variables used in this concatenation
    local_aliases = extract_local_aliases(node, variables_in_concat)

    original_parts = []
    placeholder_parts = []
    resolved_parts = []
    has_template = False

    for part_type, part_value in parts:
        if part_type == 'literal':
            original_parts.append(part_value)
            placeholder_parts.append(part_value)
            resolved_parts.append(part_value)
        elif part_type == 'identifier':
            has_template = True
            # Use local alias for better template names
            display_name = local_aliases.get(part_value, part_value)
            original_parts.append(f'{{{display_name}}}')
            if part_value in symbol_table and symbol_table[part_value]:
                resolved_val = symbol_table[part_value][0]
                placeholder_parts.append(resolved_val)
                resolved_parts.append(resolved_val)
            else:
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        elif part_type == 'member':
            has_template = True
            member_node = part_value  # part_value is now the node
            # Extract base variable and apply local alias
            base_var = None
            current = member_node
            while current and current.type == 'member_expression':
                obj_node = current.child_by_field_name('object')
                if obj_node and obj_node.type == 'identifier':
                    base_var = obj_node.text.decode('utf8')
                    break
                current = obj_node

            member_text = member_node.text.decode('utf8')
            if base_var:
                # Try to use local alias for base variable
                alias = local_aliases.get(base_var, base_var)
                if alias != base_var:
                    # Replace base variable name with alias in member expression
                    member_text = member_text.replace(base_var, alias, 1)

            original_parts.append(f'{{{member_text}}}')
            # Resolve member expression properly
            values = resolve_member_expression(member_node, placeholder)
            if values:
                placeholder_parts.append(values[0])
                resolved_parts.append(values[0])
            else:
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        elif part_type == 'template':
            has_template = True
            result = part_value
            original_parts.append(result.get('original', ''))
            placeholder_parts.append(result.get('placeholder', placeholder))
            resolved_parts.append(result.get('resolved', result.get('placeholder', placeholder)))
        elif part_type == 'join':
            has_template = True
            join_node = part_value
            values = resolve_join_call(join_node, placeholder)
            if values:
                original_parts.append(f'{{{join_node.text.decode("utf8")}}}')
                placeholder_parts.append(values[0])
                resolved_parts.append(values[0])
            else:
                original_parts.append(placeholder)
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        elif part_type == 'replace':
            has_template = True
            replace_node = part_value
            values = resolve_replace_call(replace_node, placeholder)
            if values:
                original_parts.append(f'{{{replace_node.text.decode("utf8")}}}')
                placeholder_parts.append(values[0])
                resolved_parts.append(values[0])
            else:
                original_parts.append(placeholder)
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        else:
            has_template = True
            original_parts.append(f'{{{part_value}}}')
            placeholder_parts.append(placeholder)
            resolved_parts.append(placeholder)

    original = ''.join(original_parts)
    placeholder_str = ''.join(placeholder_parts)
    resolved = ''.join(resolved_parts)

    # Consolidate repeated placeholders (including with slashes)
    placeholder_str = re.sub(f'{re.escape(placeholder)}+', placeholder, placeholder_str)
    placeholder_str = re.sub(f'{re.escape(placeholder)}/{re.escape(placeholder)}', placeholder, placeholder_str)
    placeholder_str = re.sub(f'{re.escape(placeholder)}{re.escape(placeholder)}', placeholder, placeholder_str)
    resolved = re.sub(f'{re.escape(placeholder)}+', placeholder, resolved)
    resolved = re.sub(f'{re.escape(placeholder)}/{re.escape(placeholder)}', placeholder, resolved)

    # Check if the result (placeholder or resolved) is a URL/path pattern
    if (is_url_pattern(original) or is_path_pattern(original) or
        is_url_pattern(placeholder_str) or is_path_pattern(placeholder_str) or
        is_url_pattern(resolved) or is_path_pattern(resolved)):

        # Check for route parameters and convert them
        _, converted_original, has_route_params = convert_route_params(original, placeholder)
        _, converted_placeholder, _ = convert_route_params(placeholder_str, placeholder)
        _, converted_resolved, _ = convert_route_params(resolved, placeholder)

        if has_route_params:
            has_template = True  # Route params make it a template
            original = converted_original
            # Replace {param} with FUZZ in placeholder/resolved
            placeholder_str = re.sub(r'\{[^}]+\}', placeholder, converted_placeholder)
            resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
            # Consolidate adjacent placeholders created by route param replacement (e.g., {t}{i} -> FUZZFUZZ -> FUZZ)
            placeholder_str = consolidate_adjacent_placeholders(placeholder_str, placeholder)
            resolved = consolidate_adjacent_placeholders(resolved, placeholder)
        elif has_template:
            # Has template substitutions but no route params
            # Still need to replace remaining {} patterns and consolidate
            original = converted_original
            placeholder_str = re.sub(r'\{[^}]+\}', placeholder, converted_placeholder)
            resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
            placeholder_str = consolidate_adjacent_placeholders(placeholder_str, placeholder)
            resolved = consolidate_adjacent_placeholders(resolved, placeholder)

        entry = {
            'original': original,
            'placeholder': placeholder_str,
            'has_template': has_template
        }
        if resolved and resolved != placeholder_str:
            entry['resolved'] = resolved
        return entry

    return None


def extract_chained_parts(node, placeholder):
    """
    Recursively extract parts from chained method calls (concat, replace, etc.).
    Returns a list of (type, value) tuples.
    """
    parts = []

    # Base case: not a call_expression
    if node.type != 'call_expression':
        if node.type == 'string':
            val = extract_string_value(node)
            if val:
                return [('literal', val)]
        elif node.type == 'identifier':
            return [('identifier', node.text.decode('utf8'))]
        elif node.type == 'member_expression':
            return [('member', node)]  # Pass node itself
        else:
            return [('unknown', node.text.decode('utf8'))]

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return [('unknown', node.text.decode('utf8'))]

    prop = func_node.child_by_field_name('property')
    if not prop:
        return [('unknown', node.text.decode('utf8'))]

    method_name = prop.text.decode('utf8')
    obj_node = func_node.child_by_field_name('object')

    # Recursively process the object (which might be another chained call)
    if obj_node:
        if obj_node.type == 'call_expression':
            # Chained call - recursively process
            parts.extend(extract_chained_parts(obj_node, placeholder))
        elif obj_node.type == 'string':
            val = extract_string_value(obj_node)
            if val:
                parts.append(('literal', val))
        elif obj_node.type == 'identifier':
            parts.append(('identifier', obj_node.text.decode('utf8')))
        elif obj_node.type == 'member_expression':
            parts.append(('member', obj_node))  # Pass node itself
        else:
            parts.append(('unknown', obj_node.text.decode('utf8')))

    # Process current method call arguments
    if method_name == 'concat':
        args_node = node.child_by_field_name('arguments')
        if args_node:
            for arg in args_node.named_children:
                if arg.type == 'string':
                    val = extract_string_value(arg)
                    if val:
                        parts.append(('literal', val))
                elif arg.type == 'identifier':
                    parts.append(('identifier', arg.text.decode('utf8')))
                elif arg.type == 'member_expression':
                    parts.append(('member', arg))  # Pass node itself
                else:
                    parts.append(('unknown', arg.text.decode('utf8')))

    elif method_name == 'replace':
        # Handle replace in chain - apply the replacement
        args_node = node.child_by_field_name('arguments')
        if args_node and args_node.named_child_count >= 2:
            search_node = args_node.named_child(0)
            replace_node = args_node.named_child(1)

            if search_node.type == 'string':
                search_str = extract_string_value(search_node)
                if search_str:
                    # Get replacement value
                    replace_val = placeholder
                    if replace_node.type == 'string':
                        replace_val = extract_string_value(replace_node) or placeholder
                    elif replace_node.type == 'identifier':
                        var_name = replace_node.text.decode('utf8')
                        if var_name in symbol_table and symbol_table[var_name]:
                            replace_val = symbol_table[var_name][0]

                    # Apply replacement to the last literal part if exists
                    if parts and parts[-1][0] == 'literal':
                        old_val = parts[-1][1]
                        new_val = old_val.replace(search_str, replace_val)
                        parts[-1] = ('literal', new_val)
                    else:
                        parts.append(('replace_marker', '{' + search_str + '->' + replace_val + '}'))

    return parts


def process_concat_call(node, placeholder):
    """
    Handles .concat() method calls, including chained calls.
    """
    if node.type != 'call_expression':
        return None

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return None

    prop = func_node.child_by_field_name('property')
    if not prop or prop.text.decode('utf8') != 'concat':
        return None

    # Use the new chained parts extractor
    parts = extract_chained_parts(node, placeholder)
    has_template = False

    # Build original, placeholder, and resolved strings from parts
    original_parts = []
    placeholder_parts = []
    resolved_parts = []

    for part_type, part_value in parts:
        if part_type == 'literal':
            original_parts.append(part_value)
            placeholder_parts.append(part_value)
            resolved_parts.append(part_value)
        elif part_type == 'identifier':
            has_template = True  # Mark as template when we have identifiers
            original_parts.append(f'{{{part_value}}}')
            if part_value in symbol_table and symbol_table[part_value]:
                val = symbol_table[part_value][0]
                placeholder_parts.append(val)
                resolved_parts.append(val)
            else:
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        elif part_type == 'member':
            has_template = True
            member_node = part_value  # part_value is now the node
            original_parts.append(f'{{{member_node.text.decode("utf8")}}}')
            # Resolve member expression properly
            values = resolve_member_expression(member_node, placeholder)
            if values:
                placeholder_parts.append(values[0])
                resolved_parts.append(values[0])
            else:
                placeholder_parts.append(placeholder)
                resolved_parts.append(placeholder)
        else:
            has_template = True  # Mark as template for unknown parts
            original_parts.append(f'{{{part_value}}}')
            placeholder_parts.append(placeholder)
            resolved_parts.append(placeholder)

    original = ''.join(original_parts)
    placeholder_str = ''.join(placeholder_parts)
    resolved = ''.join(resolved_parts)

    # Consolidate repeated placeholders in concat results too
    placeholder_str = re.sub(f'{re.escape(placeholder)}+', placeholder, placeholder_str)
    placeholder_str = re.sub(f'{re.escape(placeholder)}/{re.escape(placeholder)}', placeholder, placeholder_str)
    placeholder_str = re.sub(f'{re.escape(placeholder)}{re.escape(placeholder)}', placeholder, placeholder_str)
    resolved = re.sub(f'{re.escape(placeholder)}+', placeholder, resolved)
    resolved = re.sub(f'{re.escape(placeholder)}/{re.escape(placeholder)}', placeholder, resolved)

    # Check if the result (placeholder or resolved) is a URL/path pattern
    if (is_url_pattern(original) or is_path_pattern(original) or
        is_url_pattern(placeholder_str) or is_path_pattern(placeholder_str) or
        is_url_pattern(resolved) or is_path_pattern(resolved)):

        # Check for route parameters and convert them
        _, converted_original, has_route_params = convert_route_params(original, placeholder)
        _, converted_placeholder, _ = convert_route_params(placeholder_str, placeholder)
        _, converted_resolved, _ = convert_route_params(resolved, placeholder)

        if has_route_params:
            has_template = True  # Route params make it a template
            original = converted_original
            # Replace {param} with FUZZ in placeholder/resolved
            placeholder_str = re.sub(r'\{[^}]+\}', placeholder, converted_placeholder)
            resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
            # Consolidate adjacent placeholders created by route param replacement (e.g., {t}{i} -> FUZZFUZZ -> FUZZ)
            placeholder_str = consolidate_adjacent_placeholders(placeholder_str, placeholder)
            resolved = consolidate_adjacent_placeholders(resolved, placeholder)
        elif has_template:
            # Has template substitutions but no route params
            # Still need to replace remaining {} patterns and consolidate
            original = converted_original
            placeholder_str = re.sub(r'\{[^}]+\}', placeholder, converted_placeholder)
            resolved = re.sub(r'\{[^}]+\}', placeholder, converted_resolved)
            placeholder_str = consolidate_adjacent_placeholders(placeholder_str, placeholder)
            resolved = consolidate_adjacent_placeholders(resolved, placeholder)

        entry = {
            'original': original,
            'placeholder': placeholder_str,
            'has_template': has_template
        }
        if resolved and resolved != placeholder_str:
            entry['resolved'] = resolved
        return entry

    return None


def process_call_expression(node, placeholder):
    """
    Handles method call expressions for .join() and .replace().
    """
    if node.type != 'call_expression':
        return None

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return None

    prop = func_node.child_by_field_name('property')
    if not prop:
        return None

    method_name = prop.text.decode('utf8')

    if method_name == 'join':
        values = resolve_join_call(node, placeholder)
        if values:
            original = f'{{{node.text.decode("utf8")}}}'
            placeholder_str = values[0]

            if is_url_pattern(placeholder_str) or is_path_pattern(placeholder_str):
                return {
                    'original': original,
                    'placeholder': placeholder_str,
                    'resolved': placeholder_str,
                    'has_template': True
                }
    elif method_name == 'replace':
        values = resolve_replace_call(node, placeholder)
        if values:
            original = f'{{{node.text.decode("utf8")}}}'
            placeholder_str = values[0]

            if is_url_pattern(placeholder_str) or is_path_pattern(placeholder_str):
                return {
                    'original': original,
                    'placeholder': placeholder_str,
                    'resolved': placeholder_str,
                    'has_template': True
                }

    return None


def process_comments(node, placeholder, verbose):
    """
    Extracts and parses JavaScript code from within comments.
    """
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

    # Try to parse as JavaScript
    try:
        _, comment_root = parse_javascript(text)
        traverse_node(comment_root, placeholder, verbose)
    except:
        pass


def traverse_node(node, placeholder, verbose):
    """
    Second pass - recursively traverses AST to extract URLs.
    """
    global node_visit_count, max_nodes_limit
    node_visit_count += 1

    if node_visit_count > max_nodes_limit:
        return

    # Process current node
    result = None

    if node.type == 'string':
        result = process_string_literal(node, placeholder)
    elif node.type == 'template_string':
        result = process_template_string(node, placeholder)
    elif node.type == 'binary_expression':
        result = process_binary_expression(node, placeholder)
    elif node.type == 'call_expression':
        # Check for .concat(), .join(), or .replace()
        func_node = node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'concat':
                    result = process_concat_call(node, placeholder)
                elif method_name in ['join', 'replace']:
                    result = process_call_expression(node, placeholder)
    elif node.type in ['comment', 'hash_bang_line']:
        process_comments(node, placeholder, verbose)

    if result:
        add_url_entry(result, verbose)

    # Recurse to children
    for child in node.named_children:
        traverse_node(child, placeholder, verbose)


def format_output(include_templates, placeholder):
    """
    Formats final output based on template inclusion flag.
    """
    results = []

    for entry in url_entries:
        # Filter out useless entries (bare FUZZ with no resolved value)
        if entry.get('placeholder') == placeholder and not entry.get('resolved'):
            continue

        if include_templates:
            # Include ALL URLs: static URLs, original template syntax, AND placeholder versions
            original = clean_unbalanced_brackets(entry.get('original', ''))
            placeholder_val = clean_unbalanced_brackets(entry.get('placeholder', ''))

            if entry.get('has_template', False):
                # Has template - add BOTH original ({x} syntax) AND placeholder (FUZZ) version
                if original and not is_junk_url(original, placeholder) and original not in results:
                    results.append(original)
                if placeholder_val and not is_junk_url(placeholder_val, placeholder) and placeholder_val not in results and placeholder_val != original:
                    results.append(placeholder_val)
            else:
                # Static URL - just add it once
                if placeholder_val and not is_junk_url(placeholder_val, placeholder) and placeholder_val not in results:
                    results.append(placeholder_val)
        else:
            # Only include static URLs or resolved placeholder versions (no {x} syntax)
            if not entry.get('has_template', False):
                # Static URL - use as-is
                output = clean_unbalanced_brackets(entry.get('resolved', entry.get('original', '')))
                if output and not is_junk_url(output, placeholder) and output not in results:
                    results.append(output)
            else:
                # Has template - use placeholder version (with FUZZ), NOT original (with {})
                placeholder_val = clean_unbalanced_brackets(entry.get('placeholder', ''))

                # Only include if we successfully replaced template markers
                if placeholder_val and '{' not in placeholder_val and not is_junk_url(placeholder_val, placeholder) and placeholder_val not in results:
                    results.append(placeholder_val)

    return results


def get_urls(node, placeholder, include_templates, verbose, file_size=0, max_nodes=1000000,
             max_file_size_mb=1.0, html_parser='lxml', skip_symbols=False, skip_aliases=False,
             context=None, context_policy='merge'):
    """
    Main function - orchestrates the two-pass extraction.

    Parameters:
    - node: Root AST node from tree-sitter
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

    Note: Large files (>max_file_size_mb) automatically skip both symbols and aliases.
          Context forces symbol resolution even for large files.

    Returns:
    - List of URLs
    """
    # Reset global state
    global url_entries, symbol_table, object_table, array_table, seen_urls, node_visit_count, max_nodes_limit, mime_types, html_parser_backend, alias_table, disable_semantic_aliases
    url_entries = []
    symbol_table = {}
    object_table = {}
    array_table = {}
    alias_table = {}  # Track semantic aliases for variable names
    seen_urls = set()
    node_visit_count = 0
    max_nodes_limit = max_nodes
    mime_types = load_mime_types()
    html_parser_backend = html_parser

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
        build_symbol_table(node, placeholder, context=context, context_policy=context_policy)

    # Pass 2: Extract URLs
    traverse_node(node, placeholder, verbose)

    # Format and return
    return format_output(include_templates, placeholder)
