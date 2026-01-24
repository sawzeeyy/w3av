# ṣàwárí
> ṣàwárí (ṣe àwárí) means 'to discover, explore, or search' in Yorùbá

Extract URLs, strings, and more from JavaScript code using tree-sitter.

## Features
- **URLs Mode** - Extract API endpoints, URLs, and paths with intelligent variable resolution
- **Strings Mode** - Extract all string literals and template strings
- **Tree Mode** - Visualize Abstract Syntax Tree structure
- **Inspect Mode** - Discover node types and code patterns
- **Query Mode** - Custom tree-sitter queries for pattern matching

## Installation
**ṣàwárí** requires at least Python 3.11

```bash
pip install sawari
```

## Usage
Read more in the [documentation](docs/)

### Extract URLs and API endpoints
```bash
sawari urls app.js --include-templates
sawari urls bundle.js --context '{"API_URL":"https://api.example.com"}'
```

### Find potential secrets
```bash
sawari strings app.js --min 20 | grep -i "key\|token\|secret"
```

### Visualize code structure
```bash
sawari tree app.js --only-named
```

### Custom pattern matching
```bash
sawari query app.js --query '(function_declaration name: (identifier) @name)'
```

## Related Tools
- [LinkFinder](https://github.com/GerbenJavado/LinkFinder)
- [jsluice](https://github.com/BishopFox/jsluice/tree/main/cmd/jsluice)

## License

[MIT](LICENSE.md)
