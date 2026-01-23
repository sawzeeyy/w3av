"""
Node processing functions for URL extraction (Pass 2).

Handles processing of different AST node types to extract URLs:
- String literals
- Template strings
- Binary expressions (concatenation)
- Call expressions (.concat(), .join(), .replace())
"""
import re
from itertools import product

from w3av.core.url_utils import is_url_pattern, is_path_pattern
from w3av.core.html import extract_urls_from_html, extract_inline_scripts_from_html

from .resolvers import (
    decode_js_string,
    extract_string_value,
    resolve_member_expression,
    resolve_join_call,
    resolve_replace_call,
)
from .aliases import extract_local_aliases
from .output import convert_route_params
from .filters import consolidate_adjacent_placeholders


def extract_urls_from_prose(text, placeholder='FUZZ'):
    """
    Detects if text is prose/error message and extracts embedded URLs.

    Returns:
        - List of extracted URL dicts if prose with embedded URLs
        - None if not prose (let normal processing continue)
        - Empty list if prose with no embedded URLs (discard entirely)
    """
    # Skip HTML content - let the HTML parser handle it
    if '<' in text and '>' in text:
        return None

    # Prose indicators - common phrases in error/warning messages
    prose_indicators = [
        'has been deprecated',
        'must be one of',
        'called on incompatible',
        'please change',
        'this means',
        'will never render',
        'in favor of',
        'for the full message',
        'minified',
        'invariant',
        'warning:',
        'error:',
    ]

    text_lower = text.lower()
    is_prose = any(indicator in text_lower for indicator in prose_indicators)

    # Also detect by space count (prose has many spaces)
    if not is_prose and text.count(' ') >= 4:
        # But only if it doesn't start with URL indicators
        if not text.startswith(('http://', 'https://', '/', './', '../')):
            is_prose = True

    # React/JSX warning patterns (but not actual JSX/HTML content)
    if 'useRoutes()' in text:
        is_prose = True

    if not is_prose:
        return None  # Not prose, let normal processing continue

    # Extract embedded full URLs (http/https) from the prose
    # Note: We intentionally do NOT extract paths from prose, as they are usually:
    # - Fragments of URLs we already extracted (e.g., /warnings/zone/ from http://example.com/#/warnings/zone/)
    # - False positives like /ISO from "RFC2822/ISO"
    results = []

    url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\])]+'
    for match in re.findall(url_pattern, text):
        # Clean trailing punctuation
        match = match.rstrip('.,;:')
        if len(match) > 10:  # Skip very short URLs
            results.append({
                'original': match,
                'placeholder': match,
                'resolved': match,
                'has_template': placeholder in match
            })

    return results  # Empty list means prose with no URLs (discard)


def process_html_content(text, placeholder, html_parser_backend='lxml', traverse_func=None):
    """
    Helper function to extract URLs from HTML content and inline scripts.
    Returns list of URL entries or None if no URLs found.

    Parameters:
    - text: HTML content string
    - placeholder: Placeholder for unknown values
    - html_parser_backend: HTML parser to use ('lxml', 'html.parser', etc.)
    - traverse_func: Optional function to traverse inline script ASTs
    """
    from w3av.core.jsparser import parse_javascript

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
            if script_root_node and traverse_func:
                # Traverse the inline script's AST directly
                # URLs will be added via the traverse function
                # Note: traverse_func signature is (node, placeholder, verbose) - all positional
                traverse_func(script_root_node, placeholder, False)
        except Exception:
            # If parsing fails, skip this inline script
            pass

    return results if results else None


def process_string_literal(node, placeholder, symbol_table=None, object_table=None, array_table=None,
                           html_parser_backend='lxml', traverse_func=None):
    """
    Extracts URLs from plain string literals.
    Also detects HTML content and extracts URLs from HTML attributes.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}

    if node.type != 'string':
        return None

    text = extract_string_value(node)
    if not text:
        return None

    # Check for prose/error messages first - extract embedded URLs if any
    prose_urls = extract_urls_from_prose(text, placeholder)
    if prose_urls is not None:
        # It's prose - return extracted URLs (or None if empty)
        return prose_urls if prose_urls else None

    # Check if string contains HTML content
    html_results = process_html_content(text, placeholder, html_parser_backend, traverse_func)
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


def process_template_string(node, placeholder, symbol_table=None, object_table=None, array_table=None,
                            alias_table=None, disable_semantic_aliases=False,
                            html_parser_backend='lxml', traverse_func=None):
    """
    Handles template literals with ${} substitutions.
    Generates all combinations when variables have multiple values.
    Uses local context to extract semantic aliases for better parameter names.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}
    if alias_table is None:
        alias_table = {}

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
    local_aliases = extract_local_aliases(node, variables_in_template, alias_table, disable_semantic_aliases)

    # Store parts as lists of possible values for generating combinations
    original_parts = []
    resolved_parts_lists = []  # List of lists - each inner list is possible values for that position
    has_template = False

    for child in node.named_children:
        if child.type == 'string_fragment':
            text = child.text.decode('utf8')
            # Decode escape sequences in template string fragments
            text = decode_js_string(text)
            # Convert route parameters in literal fragments before adding to parts
            _, converted_text, _ = convert_route_params(text, placeholder)
            original_parts.append(converted_text)
            resolved_parts_lists.append([converted_text])  # Single value - the literal text
        elif child.type == 'escape_sequence':
            # Handle escape sequences in template strings (e.g., \x3d, \u003d)
            text = child.text.decode('utf8')
            decoded = decode_js_string(text)
            original_parts.append(decoded)
            resolved_parts_lists.append([decoded])
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
                    resolved = resolve_member_expression(expr, placeholder, symbol_table, object_table)
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
        html_results = process_html_content(resolved, placeholder, html_parser_backend, traverse_func)
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

        # Check for prose/error messages first - extract embedded URLs if any
        prose_urls = extract_urls_from_prose(resolved, placeholder)
        if prose_urls is not None:
            # It's prose - add extracted URLs (if any)
            results.extend(prose_urls)
            continue

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


def process_binary_expression(node, placeholder, symbol_table=None, object_table=None, array_table=None,
                              alias_table=None, disable_semantic_aliases=False):
    """
    Handles string concatenation with + operator, .join(), and .replace().
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}
    if alias_table is None:
        alias_table = {}

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
            result = process_template_string(n, placeholder, symbol_table, object_table, array_table,
                                            alias_table, disable_semantic_aliases)
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
    local_aliases = extract_local_aliases(node, variables_in_concat, alias_table, disable_semantic_aliases)

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
            values = resolve_member_expression(member_node, placeholder, symbol_table, object_table)
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
            values = resolve_join_call(join_node, placeholder, symbol_table, array_table)
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
            values = resolve_replace_call(replace_node, placeholder, symbol_table)
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


def extract_chained_parts(node, placeholder, symbol_table=None, object_table=None, array_table=None):
    """
    Recursively extract parts from chained method calls (concat, replace, etc.).
    Returns a list of (type, value) tuples.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}

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
            parts.extend(extract_chained_parts(obj_node, placeholder, symbol_table, object_table, array_table))
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


def process_concat_call(node, placeholder, symbol_table=None, object_table=None, array_table=None,
                        alias_table=None, disable_semantic_aliases=False):
    """
    Handles .concat() method calls, including chained calls.
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}
    if alias_table is None:
        alias_table = {}

    if node.type != 'call_expression':
        return None

    func_node = node.child_by_field_name('function')
    if not func_node or func_node.type != 'member_expression':
        return None

    prop = func_node.child_by_field_name('property')
    if not prop or prop.text.decode('utf8') != 'concat':
        return None

    # Use the chained parts extractor
    parts = extract_chained_parts(node, placeholder, symbol_table, object_table, array_table)
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
            values = resolve_member_expression(member_node, placeholder, symbol_table, object_table)
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


def process_call_expression(node, placeholder, symbol_table=None, object_table=None, array_table=None):
    """
    Handles method call expressions for .join() and .replace().
    """
    if symbol_table is None:
        symbol_table = {}
    if object_table is None:
        object_table = {}
    if array_table is None:
        array_table = {}

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
        values = resolve_join_call(node, placeholder, symbol_table, array_table)
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
        values = resolve_replace_call(node, placeholder, symbol_table)
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
