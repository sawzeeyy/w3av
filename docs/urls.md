# URLs Mode

Extract URLs, API endpoints, and paths from JavaScript code with intelligent resolution of variables, templates, and concatenation.

| Option | Description | Default | Details |
|--------|-------------|---------|---------|
| `--input` | Specify input file (alternative to positional FILE) | `None` | [Details](#--input-file) |
| `--placeholder` | Customize the placeholder for unknown values | `FUZZ` | [Details](#--placeholder-str) |
| `--include-templates` | Include URLs containing templates or variables | `False` | [Details](#--include-templates) |
| `--verbose` | Print URLs as they are discovered in real-time | `False` | [Details](#--verbose) |
| `--output` | Write results to a file instead of stdout | `stdout` | [Details](#--output-file) |
| `--max-nodes` | Limit AST traversal to prevent hanging on extremely large files | `1,000,000` | [Details](#--max-nodes-n) |
| `--max-file-size` | Skip symbol resolution for files larger than specified size | `1.0 MB` | [Details](#--max-file-size-mb) |
| `--html-parser` | Choose HTML parser backend for extracting URLs from HTML strings | `lxml` | [Details](#--html-parser-parser) |
| `--skip-symbols` | Disable symbol resolution for faster processing | `False` | [Details](#--skip-symbols) |
| `--skip-aliases` | Use raw variable names instead of semantic aliases | `False` | [Details](#--skip-aliases) |
| `--extensions` | Specify additional file extensions to include in URL extraction (comma-separated) | `None` | [Details](#--extensions-extensions) |
| `--context` | Define known variables using JSON, KEY=VALUE pairs, or a JSON file | `None` | [Details](#--context-strfile) |
| `--context-policy` | Control how context values interact with file-defined variables | `merge` | [Details](#--context-policy-policy) |

## Basic Usage

```bash
sawari urls script.js
sawari urls --input script.js
cat script.js | sawari urls
```

## Features

### String Literals
Extracts complete URLs and paths from simple strings:

```javascript
const api = "https://api.example.com/users";
const path = "/api/v1/data";
```

### Template Strings
Resolves template literals with variable substitution:

```javascript
const userId = "123";
const url = `https://api.example.com/users/${userId}`;
// Extracts: https://api.example.com/users/123
```

### Binary Expressions
Handles string concatenation with the `+` operator:

```javascript
const base = "https://api.example.com";
const endpoint = "/users";
const url = base + endpoint;
// Extracts: https://api.example.com/users
```

### Route Parameters
Converts route parameter syntax to template format:

```javascript
const route = "/users/:id/posts/:postId";
// Extracts: /users/{id}/posts/{postId}
```

Supports both `:param` and `[PARAM]` styles.

### Method Calls
Resolves common string manipulation methods:

**Array.join()**
```javascript
const parts = ["https://api.example.com", "v1", "users"];
const url = parts.join("/");
// Extracts: https://api.example.com/v1/users
```

**String.concat()**
```javascript
const url = "https://api.example.com".concat("/users").concat("/123");
// Extracts: https://api.example.com/users/123
```

**String.replace()**
```javascript
const template = "/api/{env}/users";
const url = template.replace("{env}", "prod");
// Extracts: /api/prod/users
```

### Member Expressions
Tracks object properties and nested structures:

```javascript
const config = {
  api: {
    base: "https://api.example.com",
    version: "v1"
  }
};
const url = config.api.base + "/" + config.api.version + "/users";
// Extracts: https://api.example.com/v1/users
```

### Window.location Properties
Provides defaults for browser location properties:

```javascript
const url = window.location.origin + "/api/users";
// Extracts: https://FUZZ/api/users

const path = location.pathname + "/data";
// Extracts: /FUZZ/data
```

## Options

### --input FILE
Specify the input JavaScript file. This is an alternative to providing the file as a positional argument. Supports pipeline input from stdin if not specified.

```bash
sawari urls --input script.js
```

### `--placeholder STR`
Customize the placeholder for unknown values (default: `FUZZ`):

```bash
sawari urls script.js --placeholder UNKNOWN
```

### `--include-templates`
Include URLs containing templates or variables:

```bash
sawari urls script.js --include-templates
```

Without this flag, only fully resolved URLs are output.

**Example:**
```javascript
const url = `/users/${userId}`;
```

- Without `--include-templates`: Outputs only literal parts like `/users/`
- With `--include-templates`: Outputs `/users/{userId}` and `/users/FUZZ`

### `--verbose`
Print URLs as they are discovered in real-time:

```bash
sawari urls script.js --verbose
```

Useful for debugging or monitoring progress on large files.

### `--output FILE`
Write results to a file instead of stdout:

```bash
sawari urls script.js --output results.txt
```

### `--max-nodes N`
Limit AST traversal to prevent hanging on extremely large files (default: 1,000,000):

```bash
sawari urls large-bundle.js --max-nodes 5000000
```

### `--max-file-size MB`
Skip symbol resolution for files larger than specified size (default: 1.0 MB):

```bash
sawari urls bundle.js --max-file-size 2.0
```

Large files automatically skip symbol table building for faster processing.

### `--html-parser PARSER`
Choose HTML parser backend for extracting URLs from HTML strings (default: `lxml`):

```bash
sawari urls script.js --html-parser html5lib
```

**Available parsers:**
- `lxml` (fastest, default)
- `html.parser` (built-in, no dependencies)
- `html5lib` (most lenient)
- `html5-parser` (fast HTML5)

### `--skip-symbols`
Disable symbol resolution for faster processing:

```bash
sawari urls script.js --skip-symbols
```

Skips variable tracking and only extracts literal URLs. Useful for quick scans or very large files.

### `--skip-aliases`
Use raw variable names instead of semantic aliases:

```bash
sawari urls script.js --skip-aliases
```

**Example:**
```javascript
const t = "123";
const params = { contentId: t };
const url = `/api/content/${t}`;
```

- Without `--skip-aliases`: `/api/content/{contentId}`
- With `--skip-aliases`: `/api/content/{t}`

### `--extensions EXTENSIONS`

Specify additional file extensions to include in URL extraction (comma-separated):

```bash
sawari urls script.js --extensions proto,protobuf
```

This supplements the default extensions and allows extraction from custom file types without updating the tool. Extensions should be provided without the leading dot.

## Context Injection

Provide external variable definitions to improve URL extraction accuracy.

### `--context STR|FILE`
Define known variables using JSON, KEY=VALUE pairs, or a JSON file:

**JSON string:**
```bash
sawari urls script.js --context '{"API_BASE":"https://api.example.com"}'
```

**KEY=VALUE pairs:**
```bash
sawari urls script.js --context 'API_BASE=https://api.example.com,CDN=https://cdn.com'
```

**JSON file:**
```bash
echo '{"API_BASE":"https://api.example.com"}' > context.json
sawari urls script.js --context context.json
```

**Example usage:**
```javascript
const url = API_BASE + "/users";
// Without context: FUZZ/users
// With context: https://api.example.com/users
```

### `--context-policy POLICY`
Control how context values interact with file-defined variables (default: `merge`):

**merge** (default) - Append both context and file values:
```bash
sawari urls script.js --context 't=/api' --context-policy merge
```

```javascript
const t = "/v2";
const url = `${t}/users`;
// Outputs: /api/users, /v2/users
```

**override** - Context takes precedence, ignore file values:
```bash
sawari urls script.js --context 't=/api' --context-policy override
```

```javascript
const t = "/v2";
const url = `${t}/users`;
// Outputs: /api/users (only context value)
```

**only** - Use only context, skip file symbol resolution:
```bash
sawari urls script.js --context 't=/api' --context-policy only
```

Fastest option when you have complete context definitions.

## Examples

### Basic extraction
```bash
sawari urls app.js
```

### Extract with templates
```bash
sawari urls app.js --include-templates
```

### Provide API configuration
```bash
sawari urls app.js --context '{"BASE_URL":"https://api.example.com"}' --include-templates
```

### Override window.location.host
```bash
sawari urls app.js --context 'window.location.host=example.com'
```

### Process large bundle efficiently
```bash
sawari urls bundle.js --max-file-size 5.0 --skip-aliases
```

### Debug variable resolution
```bash
sawari urls app.js --include-templates --verbose
```

### Extract to file
```bash
sawari urls app.js --include-templates --output urls.txt
```

## Output Format

Each line contains a unique URL, path, or endpoint discovered in the code. Results are automatically deduplicated.

**Example output:**
```
https://api.example.com/users
https://api.example.com/posts
/api/v1/data
/users/{id}
/posts/{postId}/comments/{commentId}
```

## Filtering

The tool automatically filters out:
- MIME types (e.g., `application/json`)
- Incomplete protocols (e.g., `https://`, `//`)
- Property access patterns (e.g., `user.profile.name`)
- W3C/XML namespaces (e.g., `http://www.w3.org/2000/svg`)
- Generic test URLs (e.g., `http://localhost`, `http://a`)
- Pure placeholder paths (e.g., `FUZZ/FUZZ/FUZZ`)
- Date/time format placeholders (e.g., `/yyyy/mm/dd/`)
- IANA timezone identifiers (e.g., `America/New_York`)

## Performance Tips

1. **Large files**: Use `--skip-symbols` or increase `--max-file-size`
2. **Minified code**: Combine `--skip-aliases` with `--max-nodes`
3. **Accurate extraction**: Provide context with `--context`
4. **Quick scan**: Use `--skip-symbols --skip-aliases`

## Common Patterns

### Extracting from webpack bundles
```bash
sawari urls bundle.js --max-nodes 10000000 --skip-aliases
```

### Finding API endpoints in React apps
```bash
sawari urls app.js --context '{"API_URL":"https://api.example.com"}' --include-templates
```

### Security testing
```bash
sawari urls app.js --include-templates | grep -E "https?://"
```
