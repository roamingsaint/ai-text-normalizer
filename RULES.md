# Rules

`rules.json` supports two kinds of replacements:

- `literal_replacements`
- `regex_replacements`

It also carries lightweight metadata:

- `rules_version`: version of the bundled default rules shipped in this release
- live user copies may also include `based_on_rules_version` and `base_rules_digest`

`rules.json` stays machine-readable JSON. Human guidance and examples live in `RULES.md`, and both files should be versioned together in the same repo tag/release.

Processing order is:

1. literal replacements
2. regex replacements

## When to use literal

Use a literal replacement when you want an exact character-for-character substitution.

Examples:

- curly quote to straight quote
- ellipsis to `...`
- non-breaking space to normal space

Example:

```json
{ "find": "\u2019", "replace": "'" }
```

## When to use regex

Use a regex replacement when spacing or surrounding context can vary.

Examples:

- en dash / em dash with optional surrounding whitespace
- collapsing inconsistent punctuation spacing
- pattern-based cleanup that is not an exact fixed string

Example:

```json
{ "pattern": "(?<=\\S)[\\u2013\\u2014](?=\\S)", "replace": " - " }
{ "pattern": "[ \\t]*[\\u2013\\u2014][ \\t]*", "replace": " - " }
```

Those rules mean:

- if an en dash or em dash appears directly between non-whitespace characters, replace it with ` - `
- otherwise, normalize any en dash or em dash plus surrounding spaces/tabs to ` - `

Examples:

- `role—owning` -> `role - owning`
- `role – owning` -> `role - owning`
- `hello—world` -> `hello - world`
- `hello — world` -> `hello - world`

The second rule means:

- match zero or more spaces or tabs
- then an en dash or em dash
- then zero or more spaces or tabs
- replace the whole match with ` - `

## Why regex is used for dashes

These two literal rules are weaker:

```json
{ "find": " — ", "replace": " - " }
{ "find": "—", "replace": " - " }
```

They only cover exact cases and can overlap in awkward ways.

The regex version is better because it handles all common spacing forms consistently.
