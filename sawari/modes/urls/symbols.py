"""
Symbol table building for URL extraction (Pass 1).

Collects variable assignments, object properties, and array elements
during the first AST traversal pass.
"""
import sys

from .resolvers import (
    extract_string_value,
    resolve_member_expression,
    resolve_subscript_expression,
    resolve_binary_expression,
    resolve_join_call,
    resolve_replace_call,
)
from .aliases import (
    extract_aliases_from_object,
    scan_sibling_nodes_for_aliases,
)
from sawari.core.context import should_use_file_value


def collect_array_elements(node, array_name, placeholder, symbol_table, object_table, array_table):
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
            resolved = resolve_binary_expression(child, placeholder, symbol_table, object_table, array_table)
            if resolved:
                elements.extend(resolved)
            else:
                elements.append(placeholder)
        elif child.type == 'member_expression':
            resolved = resolve_member_expression(child, placeholder, symbol_table, object_table)
            elements.extend(resolved)
        else:
            elements.append(placeholder)

    array_table[array_name] = elements


def collect_object_properties(node, obj_name, placeholder, symbol_table, object_table, array_table, alias_table=None):
    """
    Recursively processes object literals and populates object_table.
    Also extracts semantic aliases from property-value pairs.
    """
    if alias_table is None:
        alias_table = {}

    if node.type != 'object':
        return

    if obj_name not in object_table:
        object_table[obj_name] = {}

    # Extract aliases from this object literal
    extract_aliases_from_object(node, alias_table=alias_table)

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
                resolved = resolve_binary_expression(value_node, placeholder, symbol_table, object_table, array_table)
                if resolved:
                    values = resolved
            elif value_node.type == 'member_expression':
                values = resolve_member_expression(value_node, placeholder, symbol_table, object_table)
            elif value_node.type == 'object':
                # Nested object
                nested_obj_name = f"{obj_name}.{prop_name}"
                collect_object_properties(value_node, obj_name, placeholder, symbol_table, object_table, array_table, alias_table)
                # Create nested structure
                if prop_name not in object_table[obj_name]:
                    object_table[obj_name][prop_name] = {}
                continue

            if values:
                object_table[obj_name][prop_name] = values


def collect_object_assignment(node, placeholder, symbol_table, object_table, array_table):
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
        resolved = resolve_binary_expression(right_node, placeholder, symbol_table, object_table, array_table)
        if resolved:
            values = resolved
    elif right_node.type == 'member_expression':
        values = resolve_member_expression(right_node, placeholder, symbol_table, object_table)

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


def collect_variable_assignment(node, placeholder, symbol_table, object_table, array_table,
                                alias_table=None, context=None, context_policy='merge'):
    """
    Processes variable declarators and appends their values to symbol_table.
    Also scans for semantic aliases from nearby object literals.

    Parameters:
    - node: AST node to process
    - placeholder: Placeholder string for unknown values
    - symbol_table: Dictionary mapping variable names to value lists
    - object_table: Dictionary mapping object names to property structures
    - array_table: Dictionary mapping array names to element lists
    - alias_table: Dictionary for semantic aliases
    - context: Parsed context dictionary (external variable definitions)
    - context_policy: How to handle context/file collisions ('merge', 'override', 'only')
    """
    if alias_table is None:
        alias_table = {}

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
        resolved = resolve_binary_expression(value_node, placeholder, symbol_table, object_table, array_table)
        if resolved:
            values = resolved
    elif value_node.type == 'member_expression':
        values = resolve_member_expression(value_node, placeholder, symbol_table, object_table)
    elif value_node.type == 'subscript_expression':
        values = resolve_subscript_expression(value_node, placeholder, symbol_table, object_table)
    elif value_node.type == 'array':
        collect_array_elements(value_node, var_name, placeholder, symbol_table, object_table, array_table)
        # Scan siblings for aliases
        if parent_node:
            scan_sibling_nodes_for_aliases(parent_node, var_name, alias_table)
        return
    elif value_node.type == 'object':
        collect_object_properties(value_node, var_name, placeholder, symbol_table, object_table, array_table, alias_table)
        # Scan siblings for aliases
        if parent_node:
            scan_sibling_nodes_for_aliases(parent_node, var_name, alias_table)
        return
    elif value_node.type == 'call_expression':
        # Check for .join() or .replace()
        func_node = value_node.child_by_field_name('function')
        if func_node and func_node.type == 'member_expression':
            prop = func_node.child_by_field_name('property')
            if prop:
                method_name = prop.text.decode('utf8')
                if method_name == 'join':
                    values = resolve_join_call(value_node, placeholder, symbol_table, array_table)
                elif method_name == 'replace':
                    values = resolve_replace_call(value_node, placeholder, symbol_table)

    # Append values (deduplicate)
    for val in values:
        if val and val not in symbol_table[var_name]:
            symbol_table[var_name].append(val)

    # Scan sibling nodes for semantic aliases
    if parent_node:
        scan_sibling_nodes_for_aliases(parent_node, var_name, alias_table)


def build_symbol_table(node, placeholder, symbol_table, object_table, array_table,
                       alias_table=None, context=None, context_policy='merge',
                       node_visit_count=None, max_nodes_limit=1000000):
    """
    First pass - recursively traverses AST to collect variable assignments
    and build object structures.

    Parameters:
    - node: AST node to traverse
    - placeholder: Placeholder string for unknown values
    - symbol_table: Dictionary mapping variable names to value lists
    - object_table: Dictionary mapping object names to property structures
    - array_table: Dictionary mapping array names to element lists
    - alias_table: Dictionary for semantic aliases
    - context: Parsed context dictionary (external variable definitions)
    - context_policy: How to handle context/file collisions ('merge', 'override', 'only')
    - node_visit_count: Mutable list [count] for tracking visits
    - max_nodes_limit: Maximum number of nodes to visit

    Returns:
    - Updated node_visit_count[0]
    """
    if alias_table is None:
        alias_table = {}
    if node_visit_count is None:
        node_visit_count = [0]

    node_visit_count[0] += 1

    if node_visit_count[0] > max_nodes_limit:
        sys.stderr.write(f'\nWarning: Stopped after visiting {max_nodes_limit:,} nodes. File may be too large or complex.\n')
        return node_visit_count[0]

    if node.type == 'lexical_declaration' or node.type == 'variable_declaration':
        for child in node.named_children:
            if child.type == 'variable_declarator':
                collect_variable_assignment(
                    child, placeholder, symbol_table, object_table, array_table,
                    alias_table, context, context_policy
                )
    elif node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node:
            if left_node.type == 'identifier':
                collect_variable_assignment(
                    node, placeholder, symbol_table, object_table, array_table,
                    alias_table, context, context_policy
                )
            elif left_node.type == 'member_expression':
                collect_object_assignment(node, placeholder, symbol_table, object_table, array_table)

    # Recurse
    for child in node.named_children:
        build_symbol_table(
            child, placeholder, symbol_table, object_table, array_table,
            alias_table, context, context_policy, node_visit_count, max_nodes_limit
        )

    return node_visit_count[0]
