import os
import json
import re

"""
Context management for external variable definitions.

This module provides functionality for parsing and managing external context
(variable definitions) that can be injected into the URL extraction process.
Context can be provided via file paths, JSON strings, or KEY=VALUE pairs.
"""


class ContextPolicy:
    """Policy options for handling context/file variable collisions."""
    MERGE = "merge"       # Append both context and file values (default)
    OVERRIDE = "override"  # Context values take precedence, ignore file values
    ONLY = "only"         # Use only context, skip Pass 1 entirely


def parse_context_input(context_input):
    """
    Auto-detect and parse context from file, JSON string, or KEY=VALUE format.

    Detection order (no ambiguity):
    1. File path check: If input is a valid file path → read as JSON file
    2. JSON parse: Try parsing as JSON object → structured context
    3. KEY=VALUE: Parse as key-value pairs (comma or space-separated) → flat context

    Args:
        context_input: String containing file path, JSON, or KEY=VALUE pairs

    Returns:
        Dictionary of context variable definitions

    Raises:
        ValueError: If input cannot be parsed in any format

    Examples:
        >>> parse_context_input('context.json')  # File path
        {'BASE_URL': 'https://api.example.com'}

        >>> parse_context_input('{"BASE_URL":"https://api.example.com"}')  # JSON
        {'BASE_URL': 'https://api.example.com'}

        >>> parse_context_input('BASE_URL=https://api.example.com,CDN=https://cdn.com')
        {'BASE_URL': 'https://api.example.com', 'CDN': 'https://cdn.com'}
    """
    if not context_input or not context_input.strip():
        raise ValueError("Context input cannot be empty")

    # 1. Check if it's a file path
    if os.path.isfile(context_input):
        try:
            with open(context_input, 'r') as f:
                context = json.load(f)
                if not isinstance(context, dict):
                    raise ValueError(
                        f"Context file must contain a JSON object, got {type(context).__name__}"
                    )
                return context
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in context file '{context_input}': {e}")
        except Exception as e:
            raise ValueError(f"Error reading context file '{context_input}': {e}")

    # 2. Try parsing as JSON string
    try:
        context = json.loads(context_input)
        if not isinstance(context, dict):
            raise ValueError(
                f"Context JSON must be an object, got {type(context).__name__}"
            )
        return context
    except json.JSONDecodeError:
        pass  # Not JSON, try KEY=VALUE format

    # 3. Parse as KEY=VALUE format
    context = {}
    # Split by comma or whitespace, filter empty strings
    items = [item.strip() for item in re.split(r'[,\s]+', context_input) if item.strip()]

    if not items:
        raise ValueError("No context variables found in input")

    for item in items:
        if '=' not in item:
            raise ValueError(
                f"Invalid context format: '{item}'. Expected KEY=VALUE or JSON."
            )

        key, value = item.split('=', 1)
        key = key.strip()
        value = value.strip()

        if not key:
            raise ValueError(f"Empty key in context pair: '{item}'")

        context[key] = value

    if not context:
        raise ValueError("No context variables parsed from input")

    return context


def populate_symbol_tables(
    context_data,
    symbol_table,
    object_table,
    array_table
):
    """
    Populate symbol/object/array tables from parsed context.

    This function pre-populates the internal tables with context before Pass 1 runs.
    Values are categorized based on their type:
    - Scalars (str, int, bool, etc.) → symbol_table
    - Dictionaries → object_table
    - Lists → array_table

    Args:
        context_data: Parsed context dictionary
        symbol_table: Symbol table to populate (modified in-place)
        object_table: Object table to populate (modified in-place)
        array_table: Array table to populate (modified in-place)
    """
    for key, value in context_data.items():
        if isinstance(value, dict):
            # Nested object → object_table
            object_table[key] = _build_object_structure(value)
        elif isinstance(value, list):
            # Array → array_table
            array_table[key] = value
        else:
            # Scalar → symbol_table (as list for merging)
            # Convert to string for consistency
            symbol_table[key] = [str(value)]


def _build_object_structure(obj):
    """
    Recursively build object structure for object_table.

    Converts nested dictionaries into the format expected by the object table,
    maintaining the hierarchical structure for property path resolution.

    Args:
        obj: Dictionary to convert

    Returns:
        Object structure suitable for object_table
    """
    result = {}
    for key, value in obj.items():
        if isinstance(value, dict):
            result[key] = _build_object_structure(value)
        elif isinstance(value, list):
            result[key] = value
        else:
            result[key] = str(value)
    return result


def should_skip_pass1(policy):
    """
    Determine if Pass 1 should be skipped based on context policy.

    Args:
        policy: Context policy (merge, override, or only)

    Returns:
        True if Pass 1 should be skipped, False otherwise
    """
    return policy == ContextPolicy.ONLY


def should_use_file_value(
    variable_name,
    context_data,
    policy
):
    """
    Determine if a file-defined value should be used based on context policy.

    This is called during Pass 1 when a variable is encountered in the file.

    Args:
        variable_name: Name of the variable being processed
        context_data: Parsed context dictionary
        policy: Context policy (merge, override, or only)

    Returns:
        True if file value should be added to tables, False if it should be ignored
    """
    if policy == ContextPolicy.MERGE:
        # Always add file values (they append to context values)
        return True
    elif policy == ContextPolicy.OVERRIDE:
        # Only add file value if variable not in context
        return variable_name not in context_data
    elif policy == ContextPolicy.ONLY:
        # Never add file values (this shouldn't be called if Pass 1 is skipped)
        return False
    else:
        # Unknown policy, default to merge behavior
        return True


def validate_policy(policy):
    """
    Validate and normalize context policy value.

    Args:
        policy: Policy string to validate

    Returns:
        Normalized policy string

    Raises:
        ValueError: If policy is not valid
    """
    valid_policies = {ContextPolicy.MERGE, ContextPolicy.OVERRIDE, ContextPolicy.ONLY}

    if policy not in valid_policies:
        raise ValueError(
            f"Invalid context policy: '{policy}'. "
            f"Must be one of: {', '.join(sorted(valid_policies))}"
        )

    return policy
