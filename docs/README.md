# w3av Documentation

Comprehensive documentation for **w3av** - extract URLs, strings, and more from JavaScript code.

| Mode | Purpose | Common Options |
|------|---------|---------------|
| `urls` | Extract URLs and endpoints | `--include-templates`, `--context` |
| `strings` | Extract string literals | `--min`, `--max` |
| `tree` | Show AST structure | `--only-named`, `--include-text` |
| `inspect` | List node types | `--get-types`, `--types` |
| `query` | Pattern matching | `--query`, `--unique` |

## Modes

w3av provides five modes for different JavaScript analysis tasks:

### [URLs Mode](urls.md)
Extract URLs, API endpoints, and paths from JavaScript with intelligent variable resolution.

**Use cases:**
- Security testing and reconnaissance
- API discovery
- Finding hardcoded endpoints
- Route extraction

**Quick start:**
```bash
w3av urls app.js --include-templates
w3av urls bundle.js --context '{"API_URL":"https://api.example.com"}'
```

[Read full documentation →](urls.md)

---

### [Strings Mode](strings.md)
Extract all string literals and template strings from JavaScript code.

**Use cases:**
- Secret detection
- Content extraction for i18n
- Configuration discovery
- Finding hardcoded credentials

**Quick start:**
```bash
w3av strings app.js --min 10
w3av strings app.js | grep -i "key\|token\|secret"
```

[Read full documentation →](strings.md)

---

### [Tree Mode](tree.md)
Display the Abstract Syntax Tree (AST) structure of JavaScript code.

**Use cases:**
- Understanding code structure
- Learning about ASTs
- Debugging parser issues
- Planning tree-sitter queries

**Quick start:**
```bash
w3av tree app.js --only-named
w3av tree app.js --include-text
```

[Read full documentation →](tree.md)

---

### [Inspect Mode](inspect.md)
Discover available node types or get statistics about AST node usage.

**Use cases:**
- Discovering node type names
- Code analysis
- Planning queries
- Understanding code patterns

**Quick start:**
```bash
w3av inspect app.js
w3av inspect --get-types
```

[Read full documentation →](inspect.md)

---

### [Query Mode](query.md)
Execute tree-sitter queries to extract specific code patterns.

**Use cases:**
- Custom code extraction
- Pattern matching
- Security analysis
- Refactoring assistance

**Quick start:**
```bash
w3av query app.js --query '(string) @str'
w3av query app.js --query '(function_declaration name: (identifier) @name)'
```

[Read full documentation →](query.md)

---

## Installation

```bash
pip install w3av
```

**Requirements:**
- Python 3.11 or higher
- tree-sitter
- tree-sitter-javascript
- beautifulsoup4 (for HTML parsing)

## Common Workflows

### Security Testing
```bash
# Find all URLs and endpoints
w3av urls app.js --include-templates > urls.txt

# Find potential secrets
w3av strings app.js --min 20 | grep -i "key\|token\|password"

# Find dangerous functions
w3av query app.js --query '(call_expression function: (identifier) @func)' | grep -E "eval|exec"
```

### API Discovery
```bash
# Extract all URLs with context
w3av urls app.js --context config.json --include-templates

# Find all HTTP methods
w3av query app.js --query '(member_expression property: (property_identifier) @method)' | grep -E "get|post|put|delete"
```

### Code Analysis
```bash
# Visualize structure
w3av tree app.js --only-named > structure.txt

# Find all function names
w3av query app.js --query '(function_declaration name: (identifier) @name)' --unique

# List all constructs
w3av inspect app.js
```

### Debugging
```bash
# See full AST with text
w3av tree broken.js --include-text --parse-comments

# Extract strings even from broken code
w3av strings broken.js --include-error

# Check what node types exist
w3av inspect broken.js
```

## Tips & Best Practices

### Performance
- Use `--skip-symbols` for quick URL scans
- Increase `--max-file-size` for large bundles
- Use `--max-nodes` to prevent hanging on massive files

### Accuracy
- Provide `--context` for better URL resolution
- Use `--include-templates` to see parameterized URLs
- Combine modes: inspect → query → extract

### Output Management
- Use `--output` to save results
- Pipe to shell tools: `sort`, `uniq`, `grep`, `awk`
- Use `--unique` in query mode to deduplicate

### Learning
- Start with `inspect --get-types` to see what's available
- Use `tree --only-named` to understand structure
- Test queries on small files first

## See Also

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [JavaScript Grammar](https://github.com/tree-sitter/tree-sitter-javascript)
- [Tree-sitter Query Syntax](https://tree-sitter.github.io/tree-sitter/using-parsers#pattern-matching-with-queries)
