import re
import sys
import importlib.resources

from weav.core.jsparser import parse_javascript
from weav.core.url_utils import is_url_pattern, is_path_pattern


# Load MIME types from config file
def load_mime_types():
    with importlib.resources.files('weav.config').joinpath('mimetypes.txt')\
            .open('r') as file:
        return set(line.strip() for line in file if line.strip())


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

    # Property paths (word.word.word without slashes)
    if re.match(r'^[a-z]+\.[a-z]+\.[a-z.]+$', text, re.IGNORECASE) and '/' not in text:
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
    import re
    pattern = f'({re.escape(placeholder)}){{2,}}'
    return re.sub(pattern, placeholder, text)


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
    """
    if node.type != 'object':
        return

    if obj_name not in object_table:
        object_table[obj_name] = {}

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


def collect_variable_assignment(node, placeholder):
    """
    Processes variable declarators and appends their values to symbol_table.
    """
    var_name = None
    value_node = None

    if node.type == 'variable_declarator':
        name_node = node.child_by_field_name('name')
        value_node = node.child_by_field_name('value')
        if name_node:
            var_name = name_node.text.decode('utf8')
    elif node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node and left_node.type == 'identifier':
            var_name = left_node.text.decode('utf8')
            value_node = node.child_by_field_name('right')

    if not var_name or not value_node:
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
        return
    elif value_node.type == 'object':
        collect_object_properties(value_node, var_name, placeholder)
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


def build_symbol_table(node, placeholder):
    """
    First pass - recursively traverses AST to collect variable assignments
    and build object structures.
    """
    global node_visit_count, max_nodes_limit
    node_visit_count += 1

    if node_visit_count > max_nodes_limit:
        sys.stderr.write(f'\nWarning: Stopped after visiting {max_nodes_limit:,} nodes. File may be too large or complex.\n')
        return

    if node.type == 'lexical_declaration' or node.type == 'variable_declaration':
        for child in node.named_children:
            if child.type == 'variable_declarator':
                collect_variable_assignment(child, placeholder)
    elif node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node:
            if left_node.type == 'identifier':
                collect_variable_assignment(node, placeholder)
            elif left_node.type == 'member_expression':
                collect_object_assignment(node, placeholder)

    # Recurse
    for child in node.named_children:
        build_symbol_table(child, placeholder)


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
    """
    if node.type != 'string':
        return None

    text = extract_string_value(node)
    if not text:
        return None

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
    """
    if node.type != 'template_string':
        return None

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
                # Normalize to {var} format (not ${var})
                original_parts.append(f'{{{expr_text}}}')

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
    from itertools import product

    all_combinations = list(product(*resolved_parts_lists))

    # If no template substitutions, just return single result
    if not has_template:
        resolved = ''.join(all_combinations[0]) if all_combinations else original
        placeholder_str = resolved

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
            original_parts.append(f'{{{part_value}}}')
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
            original_parts.append(f'{{{member_node.text.decode("utf8")}}}')
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


def get_urls(node, placeholder, include_templates, verbose, file_size=0, max_nodes=1000000, max_file_size_mb=1.0):
    """
    Main function - orchestrates the two-pass extraction.

    Parameters:
    - node: Root AST node from tree-sitter
    - placeholder: String for unknown values (default: "FUZZ")
    - include_templates: Whether to include templated URLs
    - verbose: Print URLs as discovered
    - file_size: Size of input file in bytes (for optimization)
    - max_nodes: Maximum number of AST nodes to visit (default: 1,000,000)
    - max_file_size_mb: Max file size in MB for symbol resolution (default: 1.0)

    Returns:
    - List of URLs
    """
    # Reset global state
    global url_entries, symbol_table, object_table, array_table, seen_urls, node_visit_count, max_nodes_limit, mime_types
    url_entries = []
    symbol_table = {}
    object_table = {}
    array_table = {}
    seen_urls = set()
    node_visit_count = 0
    max_nodes_limit = max_nodes
    mime_types = load_mime_types()

    # For large files (>max_file_size_mb), skip symbol table building to avoid hanging
    file_size_mb = file_size / (1024 * 1024)
    skip_symbols = file_size_mb > max_file_size_mb

    if skip_symbols and verbose:
        sys.stderr.write(f'Large file ({file_size_mb:.1f}MB): Skipping symbol resolution for faster processing.\n')

    # Pass 1: Build symbol table (skip for large files)
    if not skip_symbols:
        build_symbol_table(node, placeholder)

    # Pass 2: Extract URLs
    traverse_node(node, placeholder, verbose)

    # Format and return
    return format_output(include_templates, placeholder)
