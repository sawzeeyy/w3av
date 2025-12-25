# Inspect Mode

Discover available node types in JavaScript code or get statistics about node type usage.

| Option | Description | Default | Details |
|--------|-------------|---------|---------|
| `--input` | Specify input file (alternative to positional FILE) | `None` | [Details](#--input-file) |
| `--get-types` | Display all possible node types supported by tree-sitter-javascript | `False` | [Details](#--get-types) |
| `--types` | Filter output to show only specific node types | `None` | [Details](#--types-type-type-) |
| `--output` | Write results to a file | `stdout` | [Details](#--output-file) |

## Basic Usage

```bash
w3av inspect script.js
w3av inspect --input script.js
cat script.js | w3av inspect
```

## Output

Lists all unique AST node types found in the code.

**Example:**
```
program
lexical_declaration
variable_declarator
identifier
number
function_declaration
formal_parameters
statement_block
return_statement
binary_expression
string
```

## Options

### --input FILE
Specify the input JavaScript file. This is an alternative to providing the file as a positional argument. Supports pipeline input from stdin if not specified.

```bash
w3av inspect --input script.js
```

### `--get-types`
Display all possible node types supported by tree-sitter-javascript:

```bash
w3av inspect --get-types
```

**Note:** This option doesn't require input JavaScript. It shows the complete list of node types that the parser can recognize.

**Output snippet:**
```
abstract_class_declaration
accessibility_modifier
ambiguous_export_specifier
arguments
array
array_pattern
arrow_function
as_expression
...
```

### `--types TYPE [TYPE ...]`
Filter output to show only specific node types:

```bash
w3av inspect script.js --types string number identifier
```

**Output:**
```
string
number
identifier
```

Only lists the specified types if they exist in the code.

### `--output FILE`
Write results to a file:

```bash
w3av inspect script.js --output node-types.txt
```

## Examples

### List all node types in a file
```bash
w3av inspect app.js
```

### Get complete node type reference
```bash
w3av inspect --get-types
```

### Check if file contains specific constructs
```bash
w3av inspect app.js --types class_declaration arrow_function
```

### Find all available types matching a pattern
```bash
w3av inspect --get-types | grep "declaration"
```

### Save node type inventory
```bash
w3av inspect bundle.js --output node-inventory.txt
```

## Use Cases

- **Code analysis**: Understand what constructs are used
- **Query planning**: Discover node types before writing queries
- **Code archaeology**: Identify patterns in unfamiliar code
- **Refactoring**: Find all files using specific constructs
- **Education**: Learn tree-sitter node type names

## Combining with Query Mode

Use inspect to discover node types, then query to extract them:

```bash
# Step 1: Find what's in the file
w3av inspect app.js
# Output shows: arrow_function, class_declaration

# Step 2: Query for those types
w3av query app.js --query '(arrow_function) @arrow'
w3av query app.js --query '(class_declaration) @class'
```

## Node Type Categories

**Declarations:**
- `function_declaration`
- `class_declaration`
- `lexical_declaration` (const/let)
- `variable_declaration` (var)

**Expressions:**
- `call_expression`
- `arrow_function`
- `binary_expression`
- `member_expression`
- `template_string`

**Statements:**
- `if_statement`
- `for_statement`
- `return_statement`
- `expression_statement`

**Literals:**
- `string`
- `number`
- `identifier`
- `true`, `false`, `null`

**Modern JavaScript:**
- `async_function_declaration`
- `async_arrow_function`
- `await_expression`
- `spread_element`
- `rest_parameter`

## Output Format

One node type per line, sorted alphabetically. Node types appear only once even if they occur multiple times in the code.

## Performance

Inspect mode is very fast as it only traverses the AST once to collect unique node types. No complex analysis is performed.
