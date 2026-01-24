# Query Mode

Execute tree-sitter queries to extract specific code patterns from JavaScript.

| Option | Description | Default | Details |
|--------|-------------|---------|---------|
| `--input` | Specify input file (alternative to positional FILE) | `None` | [Details](#--input-file) |
| `--query` | The tree-sitter query pattern to match (required) | `None` | [Details](#--query-query-required) |
| `--unique` | Output only unique results (deduplicate) | `False` | [Details](#--unique) |
| `--trim` | Remove leading/trailing whitespace from results | `False` | [Details](#--trim) |
| `--output` | Write results to a file | `stdout` | [Details](#--output-file) |

## Basic Usage

```bash
sawari query script.js --query '(string) @str'
sawari query --input script.js --query '(function_declaration) @func'
cat script.js | sawari query --query '(identifier) @id'
```

## Query Syntax

Uses tree-sitter's S-expression query language. Queries consist of patterns that match AST nodes.

### Basic Pattern

```
(node_type) @capture_name
```

**Example:**
```bash
sawari query app.js --query '(string) @s'
```

Matches all string nodes and captures them with the name `s`.

### Predicates

Add conditions to patterns:

```
(node_type (#predicate-name args))
```

### Field Access

Match nodes with specific fields:

```
(function_declaration name: (identifier) @func_name)
```

## Options

### --input FILE
Specify the input JavaScript file. This is an alternative to providing the file as a positional argument. Supports pipeline input from stdin if not specified.

```bash
sawari query --input script.js --query '(string) @str'
```

### `--query QUERY` (required)
The tree-sitter query pattern to match:

```bash
sawari query app.js --query '(call_expression) @call'
```

### `--unique`
Output only unique results (deduplicate):

```bash
sawari query app.js --query '(identifier) @id' --unique
```

Without this flag, the same identifier appearing multiple times will be output multiple times.

### `--trim`
Remove leading/trailing whitespace from results:

```bash
sawari query app.js --query '(function_declaration) @func' --trim
```

Useful for cleaner output when matching multi-line constructs.

### `--output FILE`
Write results to a file:

```bash
sawari query app.js --query '(string) @str' --output strings.txt
```

## Query Examples

### Extract all function names
```bash
sawari query app.js --query '(function_declaration name: (identifier) @name)'
```

### Find all string literals
```bash
sawari query app.js --query '(string) @str'
```

### Extract variable names
```bash
sawari query app.js --query '(variable_declarator name: (identifier) @var)'
```

### Find arrow functions
```bash
sawari query app.js --query '(arrow_function) @arrow'
```

### Extract call expression functions
```bash
sawari query app.js --query '(call_expression function: (identifier) @func)'
```

### Find member expressions
```bash
sawari query app.js --query '(member_expression) @member'
```

### Extract property names
```bash
sawari query app.js --query '(member_expression property: (property_identifier) @prop)'
```

### Find class names
```bash
sawari query app.js --query '(class_declaration name: (identifier) @class)'
```

### Extract import sources
```bash
sawari query app.js --query '(import_statement source: (string) @import)'
```

### Find async functions
```bash
sawari query app.js --query '(async_function_declaration) @async'
```

## Advanced Queries

### Nested Patterns

Match nested structures:

```bash
sawari query app.js --query '
  (call_expression
    function: (member_expression
      property: (property_identifier) @method))
'
```

Finds method calls like `obj.method()`.

### Multiple Captures

Capture different parts:

```bash
sawari query app.js --query '
  (function_declaration
    name: (identifier) @name
    parameters: (formal_parameters) @params)
'
```

### Alternative Patterns

Use brackets for OR logic:

```bash
sawari query app.js --query '
  [
    (function_declaration)
    (arrow_function)
  ] @func
'
```

Matches both regular and arrow functions.

### Wildcards

Use `_` to match any node:

```bash
sawari query app.js --query '(call_expression arguments: (_) @arg)'
```

## Common Patterns

### Security Analysis

**Find eval calls:**
```bash
sawari query app.js --query '(call_expression function: (identifier) @func (#eq? @func "eval"))'
```

**Find innerHTML usage:**
```bash
sawari query app.js --query '(member_expression property: (property_identifier) @prop (#eq? @prop "innerHTML"))'
```

### Code Quality

**Find console.log:**
```bash
sawari query app.js --query '
  (call_expression
    function: (member_expression
      object: (identifier) @obj (#eq? @obj "console")
      property: (property_identifier) @method (#eq? @method "log")))
'
```

**Find TODO comments:**
First enable comment parsing in the tree, then query.

### Refactoring

**Find all function names for renaming:**
```bash
sawari query app.js --query '(function_declaration name: (identifier) @name)' --unique
```

**Find all uses of a variable:**
```bash
sawari query app.js --query '(identifier) @id' | grep "specificVar"
```

## Output Format

Each match is output on a separate line, showing the matched code text.

**Example output for string query:**
```
"Hello World"
'api/users'
`User: ${name}`
```

## Discovering Query Patterns

Use `inspect` mode to find available node types:

```bash
# Step 1: See what node types exist
sawari inspect app.js

# Step 2: Check the full list
sawari inspect --get-types | grep "function"

# Step 3: Query for those types
sawari query app.js --query '(function_declaration) @func'
```

## Learning Resources

Tree-sitter query syntax:
- [Tree-sitter Query Documentation](https://tree-sitter.github.io/tree-sitter/using-parsers#pattern-matching-with-queries)
- [JavaScript Grammar](https://github.com/tree-sitter/tree-sitter-javascript)

Use `sawari tree` to visualize the AST structure:
```bash
sawari tree app.js --only-named
```

Then write queries based on the structure you see.

## Performance

Query mode performance depends on query complexity. Simple patterns are very fast. Complex nested patterns with multiple predicates may be slower on large files.

## Tips

1. Start with simple queries and add complexity gradually
2. Use `--unique` to reduce output volume
3. Combine with shell tools: `sawari query app.js --query '...' | sort | uniq -c`
4. Test queries on small files first
5. Use `inspect` mode to discover available node types before querying
