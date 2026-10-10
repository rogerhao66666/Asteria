"""Script editor support (EDT-09): Python highlighting and Authoring-API-aware completion.

``complete(source, position, namespace)`` is Qt-free. It finds the dotted
name before the cursor (``project.scene``, ``entity.trans``...) and resolves
it against the live Authoring API objects in ``namespace`` by attribute
lookup only — it never calls or executes anything — so suggestions are the
real public members of the objects the script will receive.
"""

from __future__ import annotations

import builtins
import keyword
import re

SCRIPT_GLOBALS = ("project", "selected", "scene", "entity")


_CHAIN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\([^()]*\))?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\([^()]*\))?)*)\.([A-Za-z_][A-Za-z0-9_]*)?$"
)
_SEGMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(\([^()]*\))?")


class _Type:
    """A statically known class (from a return annotation) — members only, never instantiated."""

    def __init__(self, cls):
        self.cls = cls


def _annotation_type(callable_obj):
    """Class named by a callable's return annotation (string annotations resolved in its module)."""
    import sys
    import typing

    func = getattr(callable_obj, "__func__", callable_obj)
    if isinstance(func, property):
        func = func.fget
    annotation = getattr(func, "__annotations__", {}).get("return")
    if annotation is None:
        return None
    if isinstance(annotation, str):
        module = sys.modules.get(getattr(func, "__module__", ""), None)
        annotation = getattr(module, annotation.strip("'\""), None)
    return annotation if isinstance(annotation, type) and annotation is not typing.Any else None


def _attribute(target, name):
    """Look up ``name`` on a live object or a statically known type; no calls are made."""
    if isinstance(target, _Type):
        member = getattr(target.cls, name, None)
        if isinstance(member, property):
            known = _annotation_type(member)
            return _Type(known) if known else None
        return member
    return getattr(target, name)


def _resolve(expression, namespace, assignments, depth=0):
    if depth > 8:
        return None
    segments = _SEGMENT.findall(expression)
    if not segments:
        return None
    first, call = segments[0]
    if first in namespace and namespace[first] is not None:
        target = namespace[first]
    elif first in assignments:
        target = _resolve(assignments[first], namespace, assignments, depth + 1)
    else:
        return None
    if call:
        known = _annotation_type(target)
        target = _Type(known) if known else None
    for name, call in segments[1:]:
        if target is None:
            return None
        try:
            target = _attribute(target, name)
        except Exception:  # noqa: BLE001 - completion must never raise
            return None
        if call:
            known = _annotation_type(target)
            target = _Type(known) if known else None
    return target


def _assignments(text):
    """Latest ``name = <expression>`` per name in the script text before the cursor."""
    found = {}
    for match in re.finditer(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*([^\n#]+)", text, re.MULTILINE):
        found[match.group(1)] = match.group(2).strip()
    return found


def complete(source, position, namespace):
    """Return ``(prefix, [candidates])`` for the identifier being typed at ``position``.

    Members come from the live namespace objects, from names the script
    assigned earlier, and from Authoring API return annotations for calls
    (``project.scene_named("Town").``). Nothing is called or executed.
    """
    text = source[: int(position)]
    line = text.rsplit("\n", 1)[-1]
    chain = _CHAIN.search(line)
    if chain:
        prefix = chain.group(2) or ""
        target = _resolve(chain.group(1), namespace, _assignments(text))
        if target is None:
            return prefix, []
        candidates = [n for n in dir(target.cls if isinstance(target, _Type) else target) if not n.startswith("_")]
    else:
        match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", line)
        if not match:
            return "", []
        prefix = match.group(1)
        candidates = (
            list(namespace)
            + list(_assignments(text))
            + keyword.kwlist
            + [n for n in dir(builtins) if not n.startswith("_")]
        )
    names = sorted(
        {n for n in candidates if n.startswith(prefix) and n != prefix and not n.startswith("__")},
        key=lambda n: (n.lower(), n),
    )
    return prefix, names


def script_frames(traceback_text, filename):
    """``[(line, function, source)]`` for frames of ``filename`` in a formatted traceback."""
    frames = []
    pattern = re.compile(r'File "(?P<file>.+?)", line (?P<line>\d+), in (?P<func>\S+)')
    lines = traceback_text.splitlines()
    for index, text in enumerate(lines):
        found = pattern.search(text)
        if found and found.group("file") == filename:
            code = (
                lines[index + 1].strip()
                if index + 1 < len(lines) and not lines[index + 1].lstrip().startswith("File ")
                else ""
            )
            frames.append((int(found.group("line")), found.group("func"), code))
    return frames


try:
    from PySide6.QtCore import QRegularExpression
    from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

    def _format(color, *, bold=False, italic=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    class PythonHighlighter(QSyntaxHighlighter):
        """Keywords, builtins, Asteria script globals, numbers, decorators, strings and comments."""

        def __init__(self, document):
            super().__init__(document)
            words = r"\b(" + "|".join(keyword.kwlist) + r")\b"
            builtin_names = (
                r"\b(" + "|".join(n for n in dir(builtins) if not n.startswith("_") and n.isidentifier()) + r")\b"
            )
            self.rules = [
                (QRegularExpression(builtin_names), _format("#7fc8d8")),
                (QRegularExpression(words), _format("#c792ea", bold=True)),
                (QRegularExpression(r"\b(" + "|".join(SCRIPT_GLOBALS) + r")\b"), _format("#f0c674", bold=True)),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), _format("#f78c6c")),
                (QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_.]*"), _format("#82aaff")),
                (QRegularExpression(r"\"[^\"\\n]*\"|'[^'\\n]*'"), _format("#c3e88d")),
                (QRegularExpression(r"#[^\n]*"), _format("#6c7a89", italic=True)),
            ]

        def highlightBlock(self, text):  # noqa: N802 - Qt API
            for expression, fmt in self.rules:
                iterator = expression.globalMatch(text)
                while iterator.hasNext():
                    match = iterator.next()
                    self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        def format_at(self, block_text, column):
            """Format name applied at ``column`` (for tests)."""
            names = ("builtin", "keyword", "global", "number", "decorator", "string", "comment")
            found = None
            for (expression, _), name in zip(self.rules, names):
                iterator = expression.globalMatch(block_text)
                while iterator.hasNext():
                    match = iterator.next()
                    if match.capturedStart() <= column < match.capturedStart() + match.capturedLength():
                        found = name
            return found

except ImportError:  # pragma: no cover - Qt-free environments
    PythonHighlighter = None
