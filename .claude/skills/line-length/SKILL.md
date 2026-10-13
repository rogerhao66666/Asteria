---
name: line-length
description: Asteria lint rule — every line of Python in the project is shorter than 100 characters (ruff line-length 99). Use whenever writing or editing any .py file in this repository, and before committing.
---

# Line length: every line < 100 characters

**Rule (project-wide, set by the user on 2026-10-13):** every line of every Python file in this
repository is at most **99 characters** — `src/`, `tests/`, `scripts/`, `reference_projects/`,
`demos/`, everything except third-party code in `local_reference/` (git-ignored).

Enforced by ruff: `pyproject.toml` → `[tool.ruff] line-length=99`. `E501` is in the selected rules,
and `ruff format` wraps code to the same width.

## Check before every commit

```bash
.venv/bin/ruff format .
.venv/bin/ruff check --select E501 .
.venv/bin/ruff check src tests scripts
```

All three must report nothing to fix (`All checks passed!`).

## Writing code that fits

`ruff format` wraps code, but it does **not** shorten these — fix them by hand:

- **Comments**: wrap onto several `#` lines with the same indent; move a long trailing comment to its
  own line above the code. Divider comments (`# -- name ----`) end at column 99.
- **Docstrings**: wrap the text. A one-line docstring that is too long must split its *text* over two
  lines — moving only the closing `"""` is undone by the formatter.
- **String literals**: split into adjacent literals inside brackets (`("first part " "second part")`)
  — the value stays identical. In f-strings, split outside `{…}`; pull long expressions into a local
  variable first.
- **Strings that are code or data** (GLSL shaders, embedded Python, QSS, Markdown tables written to
  files): never break a line in the middle. In GLSL a split `//` comment turns its tail into code;
  put the comment on its own line instead. Re-run the tests that use the string.
- **Long names** (test functions, identifiers): shorten the name rather than break the line.

## Not covered

Markdown documents (`docs/`, READMEs) and JSON data are not linted by ruff; keep new Markdown prose
readable but this rule is about source code.
