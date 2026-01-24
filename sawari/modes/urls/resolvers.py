"""
Expression resolution functions for URL extraction.

Handles resolving JavaScript expressions to their values:
- String literals and escape sequences
- Member expressions (object property access)
- Subscript expressions (bracket notation)
- Binary expressions (concatenation)
- Method calls (.join(), .replace())
"""


def decode_js_string(text):
    """
    Decode JavaScript string escape sequences to their actual characters.
    Handles: \\xHH, \\uHHHH, \\u{HHHHHH}, \\OOO (octal), \\n, \\t, \\r, etc.
    """
    if not text:
        return text

    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]

            # Hex escape: \xHH
            if next_char == 'x' and i + 3 < len(text):
                try:
                    hex_code = text[i+2:i+4]
                    result.append(chr(int(hex_code, 16)))
                    i += 4
                    continue
                except (ValueError, OverflowError):
                    pass

            # Unicode escape: \uHHHH
            elif next_char == 'u':
                # Unicode code point: \u{HHHHHH}
                if i + 2 < len(text) and text[i+2] == '{':
                    end = text.find('}', i+3)
                    if end != -1:
                        try:
                            code_point = text[i+3:end]
                            result.append(chr(int(code_point, 16)))
                            i = end + 1
                            continue
                        except (ValueError, OverflowError):
                            pass
                # Standard unicode: \uHHHH
                elif i + 5 < len(text):
                    try:
                        unicode_code = text[i+2:i+6]
                        result.append(chr(int(unicode_code, 16)))
                        i += 6
                        continue
                    except (ValueError, OverflowError):
                        pass

            # Octal escape: \OOO (up to 3 digits)
            elif next_char.isdigit():
                octal_str = ''
                j = i + 1
                while j < len(text) and j < i + 4 and text[j].isdigit():
                    octal_str += text[j]
                    j += 1
                try:
                    result.append(chr(int(octal_str, 8)))
                    i = j
                    continue
                except (ValueError, OverflowError):
                    pass

            # Standard escapes
            escape_map = {
                'n': '\n', 't': '\t', 'r': '\r',
                'b': '\b', 'f': '\f', 'v': '\v',
                '\\': '\\', "'": "'", '"': '"', '0': '\0'
            }
            if next_char in escape_map:
                result.append(escape_map[next_char])
                i += 2
                continue

            # Unknown escape, keep as-is
            result.append(text[i])
            i += 1
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


def extract_string_value(node):
    """
    Extracts clean string value from AST string node (removes quotes and decodes escapes).
    """
    if node.type != 'string':
        return None

    text = node.text.decode('utf8')
    # Remove quotes
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]

    # Decode JavaScript escape sequences
    return decode_js_string(text)


def resolve_member_expression(node, placeholder='FUZZ', symbol_table=None, object_table=None):
    """
    Resolves member expressions by navigating object_table hierarchy
    or using defaults for known properties.

    Returns list of values.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}

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

    # Check if full path exists in symbol_table (from context)
    # This allows context to override defaults like window.location.host
    full_path = '.'.join(path)
    if full_path in symbol_table:
        return symbol_table[full_path]

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


def resolve_subscript_expression(node, placeholder='FUZZ', symbol_table=None, object_table=None):
    """
    Resolves computed property access (bracket notation).

    Returns list of values.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}

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


def resolve_join_call(node, placeholder='FUZZ', symbol_table=None, array_table=None):
    """
    Resolves .join() method calls on arrays.

    Returns list with single joined string.
    """
    if symbol_table is None:
        symbol_table = {}
    if array_table is None:
        array_table = {}

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


def resolve_replace_call(node, placeholder='FUZZ', symbol_table=None):
    """
    Resolves .replace() method calls with simple string replacements.

    Returns list with single replaced string.
    """
    if symbol_table is None:
        symbol_table = {}

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


def resolve_binary_expression(node, placeholder='FUZZ', symbol_table=None, object_table=None, array_table=None):
    """
    Resolves binary expressions:
    - + operator: string concatenation
    - || operator: logical OR (returns right side as fallback)
    - && operator: logical AND (returns right side as result)

    Returns list of possible values.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}

    if node.type != 'binary_expression':
        return None

    op = node.child_by_field_name('operator')
    if not op:
        return None

    operator = op.text.decode('utf8')

    left_node = node.child_by_field_name('left')
    right_node = node.child_by_field_name('right')

    if not left_node or not right_node:
        return None

    # Handle logical OR (||) - return right side (fallback)
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
            return resolve_member_expression(right_node, placeholder, symbol_table, object_table)
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
            return resolve_member_expression(right_node, placeholder, symbol_table, object_table)
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
        left_values = resolve_member_expression(left_node, placeholder, symbol_table, object_table)
    elif left_node.type == 'subscript_expression':
        left_values = resolve_subscript_expression(left_node, placeholder, symbol_table, object_table)
    elif left_node.type == 'binary_expression':
        left_values = resolve_binary_expression(left_node, placeholder, symbol_table, object_table, array_table)
    elif left_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = left_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    left_values = resolve_join_call(left_node, placeholder, symbol_table, array_table)
                elif method_name == 'replace':
                    left_values = resolve_replace_call(left_node, placeholder, symbol_table)

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
        right_values = resolve_member_expression(right_node, placeholder, symbol_table, object_table)
    elif right_node.type == 'subscript_expression':
        right_values = resolve_subscript_expression(right_node, placeholder, symbol_table, object_table)
    elif right_node.type == 'binary_expression':
        right_values = resolve_binary_expression(right_node, placeholder, symbol_table, object_table, array_table)
    elif right_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = right_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    right_values = resolve_join_call(right_node, placeholder, symbol_table, array_table)
                elif method_name == 'replace':
                    right_values = resolve_replace_call(right_node, placeholder, symbol_table)

    if not right_values:
        right_values = [placeholder]

    # Generate all combinations
    results = []
    for left in left_values:
        for right in right_values:
            results.append(str(left) + str(right))

    return results
