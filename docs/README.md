# ṣàwárí Documentation

Comprehensive documentation for **ṣàwárí** - extract URLs, strings, and more from JavaScript code.

| Mode | Purpose | Common Options |
|------|---------|---------------|
| `urls` | Extract URLs and endpoints | `--include-templates`, `--context` |
| `strings` | Extract string literals | `--min`, `--max` |
| `tree` | Show AST structure | `--only-named`, `--include-text` |
| `inspect` | List node types | `--get-types`, `--types` |
| `query` | Pattern matching | `--query`, `--unique` |

## Modes

ṣàwárí provides five modes for different JavaScript analysis tasks:

### [URLs Mode](urls.md)
Extract URLs, API endpoints, and paths from JavaScript with intelligent variable resolution.

**Use cases:**
- Security testing and reconnaissance
- API discovery
- Finding hardcoded endpoints
- Route extraction

**Quick start:**
```bash
sawari urls app.js --include-templates
sawari urls bundle.js --context '{"API_URL":"https://api.example.com"}'
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
sawari strings app.js --min 10
sawari strings app.js | grep -i "key\|token\|secret"
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
sawari tree app.js --only-named
sawari tree app.js --include-text
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
sawari inspect app.js
sawari inspect --get-types
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
sawari query app.js --query '(string) @str'
sawari query app.js --query '(function_declaration name: (identifier) @name)'
```

[Read full documentation →](query.md)

---

## Installation

```bash
pip install sawari
```

**Requirements:**
- Python 3.11 or higher
- tree-sitter
- tree-sitter-javascript
- beautifulsoup4 (for HTML parsing)

## Shell Completion

sawari supports tab autocompletion for Bash, Zsh, and Fish shells.

### Bash
```bash
eval "$(register-python-argcomplete sawari)"
```
Add the above line to your `~/.bashrc` to enable permanently.

### Zsh
```bash
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete sawari)"
```
Add the above lines to your `~/.zshrc` to enable permanently.

### Fish
```bash
register-python-argcomplete --shell fish sawari | source
```
To enable permanently, run:
```bash
register-python-argcomplete --shell fish sawari > ~/.config/fish/completions/sawari.fish
```

## Common Workflows

### Security Testing
```bash
# Find all URLs and endpoints
sawari urls app.js --include-templates > urls.txt

# Find potential secrets
sawari strings app.js --min 20 | grep -i "key\|token\|password"

# Find dangerous functions
sawari query app.js --query '(call_expression function: (identifier) @func)' | grep -E "eval|exec"
```

### API Discovery
```bash
# Extract all URLs with context
sawari urls app.js --context config.json --include-templates

# Find all HTTP methods
sawari query app.js --query '(member_expression property: (property_identifier) @method)' | grep -E "get|post|put|delete"
```

### Code Analysis
```bash
# Visualize structure
sawari tree app.js --only-named > structure.txt

# Find all function names
sawari query app.js --query '(function_declaration name: (identifier) @name)' --unique

# List all constructs
sawari inspect app.js
```

### Debugging
```bash
# See full AST with text
sawari tree broken.js --include-text --parse-comments

# Extract strings even from broken code
sawari strings broken.js --include-error

# Check what node types exist
sawari inspect broken.js
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
