# Tree Mode

Display the Abstract Syntax Tree (AST) structure of JavaScript code.

| Option | Description | Default | Details |
|--------|-------------|---------|---------|
| `--input` | Specify input file (alternative to positional FILE) | `None` | [Details](#--input-file) |
| `--indent` | Set indentation level | `2` | [Details](#--indent-n) |
| `--only-named` | Show only named nodes (exclude punctuation and keywords) | `False` | [Details](#--only-named) |
| `--include-text` | Display the actual text content of each node | `False` | [Details](#--include-text) |
| `--parse-comments` | Include comment nodes in the tree | `False` | [Details](#--parse-comments) |
| `--output` | Write tree to a file | `stdout` | [Details](#--output-file) |

## Basic Usage

```bash
w3av tree script.js
w3av tree --input script.js
cat script.js | w3av tree
```

## Output

Generates a tree representation of the code's syntactic structure using tree-sitter.

**Example code:**
```javascript
const x = 5;
function greet(name) {
  return "Hello " + name;
}
```

**Example output:**
```
program
  lexical_declaration
    variable_declarator
      identifier: x
      number: 5
  function_declaration
    identifier: greet
    formal_parameters
      identifier: name
    statement_block
      return_statement
        binary_expression
          string: "Hello "
          identifier: name
```

## Options

### --input FILE
Specify the input JavaScript file. This is an alternative to providing the file as a positional argument. Supports pipeline input from stdin if not specified.

```bash
w3av tree --input script.js
```

### `--indent N`
Set indentation level (default: 2 spaces):

```bash
w3av tree script.js --indent 4
```

### `--only-named`
Show only named nodes (exclude punctuation and keywords):

```bash
w3av tree script.js --only-named
```

**Without `--only-named`:**
```
program
  lexical_declaration
    const
    variable_declarator
      identifier: x
      =
      number: 5
    ;
```

**With `--only-named`:**
```
program
  lexical_declaration
    variable_declarator
      identifier: x
      number: 5
```

### `--include-text`
Display the actual text content of each node:

```bash
w3av tree script.js --include-text
```

**Output:**
```
program
  lexical_declaration [const x = 5;]
    variable_declarator [x = 5]
      identifier: x [x]
      number: 5 [5]
```

### `--parse-comments`
Include comment nodes in the tree:

```bash
w3av tree script.js --parse-comments
```

By default, comments are ignored during parsing.

### `--output FILE`
Write tree to a file:

```bash
w3av tree script.js --output ast.txt
```

## Examples

### Basic tree structure
```bash
w3av tree app.js
```

### Clean tree without syntax noise
```bash
w3av tree app.js --only-named
```

### Tree with source text
```bash
w3av tree app.js --include-text
```

### Detailed tree with comments
```bash
w3av tree app.js --parse-comments --indent 4
```

### Save tree for analysis
```bash
w3av tree bundle.js --only-named --output bundle-ast.txt
```

## Use Cases

- **Code analysis**: Understand code structure
- **Parser development**: Study tree-sitter output
- **Debugging**: Investigate parsing issues
- **Education**: Learn about ASTs and syntax trees
- **Tool development**: Plan tree-sitter queries

## Node Types

Common node types you'll encounter:

**Declarations:**
- `program` - Root node
- `lexical_declaration` - const/let declarations
- `variable_declaration` - var declarations
- `function_declaration` - Function definitions
- `class_declaration` - Class definitions

**Expressions:**
- `binary_expression` - Operations like `+`, `-`, `&&`
- `call_expression` - Function calls
- `member_expression` - Property access (`obj.prop`)
- `template_string` - Template literals
- `arrow_function` - Arrow functions

**Statements:**
- `if_statement`
- `for_statement`
- `while_statement`
- `return_statement`
- `expression_statement`

**Literals:**
- `string` - String literals
- `number` - Numeric literals
- `identifier` - Variable/function names
- `true`, `false`, `null`

## Tree Structure

The tree is hierarchical:
- **Parent nodes** represent language constructs
- **Child nodes** represent components of those constructs
- **Leaf nodes** contain actual code tokens (identifiers, literals, operators)

## Performance

Tree mode is fast and can handle large files efficiently. The output size grows with code complexity rather than file size.

## Tips

1. Use `--only-named` for cleaner output when learning
2. Add `--include-text` to correlate tree structure with source
3. Pipe to `less` or `more` for large trees: `w3av tree bundle.js | less`
4. Use with grep to find specific node types: `w3av tree app.js | grep "function_declaration"`
