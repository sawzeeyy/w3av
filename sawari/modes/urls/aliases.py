"""
Semantic alias extraction and management.

Provides context-aware naming for template parameters by extracting
meaningful aliases from local context (destructuring, object literals,
URLSearchParams, FormData, etc.).
"""

from .resolvers import extract_string_value


def add_alias(var_name, alias, confidence='medium', alias_table=None):
    """
    Associates a semantic alias with a variable name.

    Parameters:
    - var_name: The original variable name (e.g., 't', 'r', 'a')
    - alias: The meaningful name (e.g., 'contentId', 'orderBy')
    - confidence: How confident we are in this alias ('high', 'medium', 'low')
    - alias_table: Dictionary to store aliases (mutated in place)
    """
    if alias_table is None:
        alias_table = {}

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


def get_best_alias(var_name, alias_table=None):
    """
    Returns the most meaningful alias for a variable name.

    Heuristics:
    1. Prefer high-confidence aliases
    2. Avoid generic/temporary names (temp, tmp, val, etc.)
    3. Avoid very generic names (id, key, name, value) - prefer more specific ones
    4. Prefer names with meaningful suffixes (contentId over id, spaceKey over key)
    5. Fall back to original variable name if no good alias found
    """
    if alias_table is None:
        alias_table = {}

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


def extract_local_aliases(node, variables_to_find, alias_table=None, disable_semantic_aliases=False):
    """
    Extracts aliases from the local context (current function scope or nearby nodes).
    This is called during pass 2 when we encounter template strings/concatenations.

    Parameters:
    - node: The current AST node (template_string, binary_expression, etc.)
    - variables_to_find: Set of variable names we want to find aliases for
    - alias_table: Optional alias table (not used directly, but for consistency)
    - disable_semantic_aliases: If True, return empty dict (use raw variable names)

    Returns:
    - Dictionary mapping variable names to their best local alias
    """
    # If semantic aliases are disabled, return empty dict (use raw variable names)
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


def extract_aliases_from_object(obj_node, context_vars=None, alias_table=None):
    """
    Scans an object literal or destructuring pattern for property-value pairs
    where values are identifiers.
    Associates property names (aliases) with the variable names (values).

    Example: { contentId: t, orderBy: r } → t gets alias 'contentId', r gets 'orderBy'
    Also works with destructuring: const {contentId: t} = obj → t gets alias 'contentId'

    Parameters:
    - obj_node: AST node of type 'object' or 'object_pattern'
    - context_vars: Optional set of variable names to look for (for scoping)
    - alias_table: Dictionary to store aliases (mutated in place)
    """
    if alias_table is None:
        alias_table = {}

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
                    add_alias(var_name, prop_name, confidence='high', alias_table=alias_table)

            # Handle shorthand property notation: { contentId } → { contentId: contentId }
            elif value_node.type in ['shorthand_property_identifier', 'shorthand_property_identifier_pattern']:
                var_name = value_node.text.decode('utf8')
                if context_vars is None or var_name in context_vars:
                    # In shorthand, the property name IS the variable name, so no alias needed
                    pass


def scan_for_urlsearchparams(node, context_vars=None, alias_table=None):
    """
    Detects URLSearchParams or FormData patterns and extracts aliases.

    Examples:
    - new URLSearchParams({ key: t }) → t gets alias 'key'
    - params.append('key', t) → t gets alias 'key'
    - new FormData().append('userId', u) → u gets alias 'userId'
    """
    if alias_table is None:
        alias_table = {}

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
                        extract_aliases_from_object(first_arg, context_vars, alias_table)

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
                                add_alias(var_name, key_name, confidence='high', alias_table=alias_table)


def scan_sibling_nodes_for_aliases(parent_node, var_name, alias_table=None):
    """
    Scans sibling nodes in the same statement/declaration for alias hints.
    This catches patterns like:

    const t = '123';
    const params = { contentId: t };
    """
    if alias_table is None:
        alias_table = {}

    if not parent_node:
        return

    # Look at siblings in variable declarations
    for sibling in parent_node.named_children:
        if sibling.type == 'variable_declarator':
            value_node = sibling.child_by_field_name('value')
            if value_node:
                # Check for object literals
                if value_node.type == 'object':
                    extract_aliases_from_object(value_node, {var_name}, alias_table)
                # Check for URLSearchParams/FormData
                elif value_node.type in ['new_expression', 'call_expression']:
                    scan_for_urlsearchparams(value_node, {var_name}, alias_table)
