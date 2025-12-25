# Strings Mode

Extract string literals and template strings from JavaScript code.

| Option | Description | Default | Details |
|--------|-------------|---------|---------|
| `--input` | Specify input file (alternative to positional FILE) | `None` | [Details](#--input-file) |
| `--min` | Set minimum string length | `None` | [Details](#--min-n) |
| `--max` | Set maximum string length | `None` | [Details](#--max-n) |
| `--include-error` | Include strings from syntax error nodes | `False` | [Details](#--include-error) |
| `--output` | Write results to a file | `stdout` | [Details](#--output-file) |

## Basic Usage

```bash
w3av strings script.js
w3av strings --input script.js
cat script.js | w3av strings
```

## Output

Extracts all string content from:
- Regular string literals (`"..."`, `'...'`)
- Template strings (`` `...` ``)
- Optionally, strings from error nodes

**Example:**
```javascript
const msg = "Hello World";
const path = '/api/users';
const template = `User: ${name}`;
```

**Output:**
```
Hello World
/api/users
User:
```

## Options

### --input FILE
Specify the input JavaScript file. This is an alternative to providing the file as a positional argument. Supports pipeline input from stdin if not specified.

```bash
w3av strings --input script.js
```

### `--min N`
Set minimum string length (default: 1):

```bash
w3av strings script.js --min 10
```

Only extracts strings with 10 or more characters.

### `--max N`
Set maximum string length (default: no limit):

```bash
w3av strings script.js --max 100
```

Only extracts strings up to 100 characters. Useful for filtering out large data blobs.

### `--include-error`
Include strings from syntax error nodes:

```bash
w3av strings broken.js --include-error
```

Useful when parsing partially valid or malformed JavaScript.

### `--output FILE`
Write results to a file:

```bash
w3av strings script.js --output strings.txt
```

## Examples

### Extract all strings
```bash
w3av strings app.js
```

### Extract strings between 5-50 characters
```bash
w3av strings app.js --min 5 --max 50
```

### Find potential secrets
```bash
w3av strings app.js --min 20 | grep -i "key\|token\|secret"
```

### Extract from broken code
```bash
w3av strings partial.js --include-error
```

## Use Cases

- **Secret detection**: Find hardcoded API keys, tokens, passwords
- **Content extraction**: Pull user-facing text for i18n
- **Configuration discovery**: Find configuration strings
- **Data analysis**: Analyze string patterns in codebases
- **Debugging**: Extract strings from minified or obfuscated code

## Output Format

Each line contains one extracted string value. Empty strings are included. Results are not deduplicated (same string appearing multiple times will appear multiple times in output).

## Performance

This mode is very fast as it only needs to traverse the AST once without any symbol resolution or complex analysis.
