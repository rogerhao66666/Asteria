"""Safe arithmetic expressions over gameplay subjects (an optional power-user path).

Project data can write a number as an expression instead of a list of terms, for rules that are
not linear: a damage formula that multiplies level, power and an attack over a defence ratio, a
chance that grows with a speed ratio. The text is parsed once with Python's ``ast`` and only a
small whitelist runs: numbers, strings, ``+ - * / // % **``, comparisons, ``and or not``,
``x if c else y``, names the caller supplies and calls of the functions below. Nothing else -
no attributes but a subject's, no imports, no indexing, no lambdas.

Subjects (``source``, ``target``, ``self`` - whatever the caller passes) answer:

* ``source.attack`` - a stat (0 when it has none); a resource's current value when there is no
  stat of that name;
* ``source.current("hp")``, ``source.maximum("hp")``, ``source.ratio("hp")`` - a resource;
* ``source.has("type.grass")`` - a tag it carries or a state it is in.

Functions: ``floor ceil round abs min max sqrt clamp(x, lo, hi)``, ``random()`` (0..1 from the
caller's dice), ``randint(a, b)``, ``stage(n, base)`` - the stage ratio
``max(base, base + n) / max(base, base - n)`` (``stage(1, 2)`` is 1.5, ``stage(-1, 2)`` 0.667)
and ``choose(c, a, b)``.

Where a formula can be written (``FORMULA_FIELDS``, D94): each record kind (its ``schema``) and
field, with the names its formula may use. A stat read from a subject (``source.dex``) is a
variable: a project that defines its stats (Game Systems ▸ Stats) may only read the stats it
defines, and a resource (``source.current("hp")``) only the resources it has -
``undeclared`` lists the others. A formula left empty uses the record's other fields.
"""

from __future__ import annotations

import ast
import math
import random as _random
from functools import lru_cache

_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b if b else 0.0,
    ast.FloorDiv: lambda a, b: a // b if b else 0.0,
    ast.Mod: lambda a, b: a % b if b else 0.0,
    ast.Pow: lambda a, b: _power(a, b),
}
_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}
SUBJECT_METHODS = ("current", "maximum", "ratio", "has")
RESOURCE_METHODS = ("current", "maximum", "ratio")
SUBJECTS = ("self", "source", "target", "opponent")  # names that stand for a fighter
# (record schema, field) -> the names its formula may use (D94)
FORMULA_FIELDS = {
    ("asteria.rpg.derived_stat", "expression"): ("self",),
    ("asteria.rpg.outcome_check", "chance_expression"): ("source", "target"),
    ("asteria.rpg.battle_escape_rule", "chance_expression"): ("source", "opponent", "attempts"),
    ("asteria.rpg.battle_session_rules", "initiative_expression"): ("self",),
    ("asteria.rpg.battle_session_rules", "final_damage_expression"): (
        "value",
        "source",
        "target",
    ),
    ("asteria.value_formula", "expression"): ("source", "target"),
}


def _power(a, b):
    if abs(b) > 64 or abs(a) > 1e12:
        raise ExpressionError("power too large")
    return a**b


def _stage(n, base=2):
    n, base = float(n), float(base)
    return max(base, base + n) / max(base, base - n)


FUNCTIONS = {
    "floor": lambda x: float(math.floor(x)),
    "ceil": lambda x: float(math.ceil(x)),
    "round": lambda x, digits=0: float(round(x, int(digits))),
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": lambda x: math.sqrt(max(0.0, x)),
    "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
    "stage": _stage,
    "choose": lambda c, a, b: a if c else b,
}


class ExpressionError(ValueError):
    pass


class SubjectView:
    """What an expression sees of a gameplay subject (stats, resources, tags, states)."""

    __slots__ = ("subject", "stats")

    def __init__(self, subject, stats=None):
        self.subject = subject
        self.stats = stats if stats is not None else getattr(subject, "stats", None)

    def value(self, name):
        stats = self.stats
        if stats is not None and stats.contains(name):
            return float(stats.get(name))
        resources = getattr(self.subject, "resources", None)
        if resources is not None and resources.contains(name):
            return float(resources.current(name))
        return 0.0

    def current(self, name):
        resources = getattr(self.subject, "resources", None)
        return float(resources.current(name)) if resources and resources.contains(name) else 0.0

    def maximum(self, name):
        resources = getattr(self.subject, "resources", None)
        return float(resources.maximum(name)) if resources and resources.contains(name) else 0.0

    def ratio(self, name):
        top = self.maximum(name)
        return self.current(name) / top if top else 0.0

    def has(self, name):
        name = str(name)
        tags = getattr(self.subject, "tags", None)
        if tags is not None and tags.contains(name):
            return True
        states = getattr(self.subject, "states", None)
        return states is not None and states.get(name) is not None


@lru_cache(maxsize=512)
def compile_expression(text):
    """The parsed, checked expression (cached by its text); raises ExpressionError."""
    try:
        tree = ast.parse(str(text).strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"bad expression: {text!r}") from exc
    for node in ast.walk(tree):
        allowed = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
            ast.Call, ast.Name, ast.Attribute, ast.Constant, ast.Load, ast.operator,
            ast.unaryop, ast.boolop, ast.cmpop,
        )  # fmt: skip
        if not isinstance(node, allowed):
            raise ExpressionError(f"{type(node).__name__} is not allowed in {text!r}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ExpressionError(f"{node.attr} is not allowed in {text!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, str)):
            raise ExpressionError(f"{node.value!r} is not allowed in {text!r}")
        if isinstance(node, ast.BinOp) and type(node.op) not in _BINARY:
            raise ExpressionError(f"{type(node.op).__name__} is not allowed in {text!r}")
    return tree.body


def check_expression(text, names=()):
    """Raise ExpressionError unless ``text`` parses and only uses ``names`` (plus the
    functions) as bare names."""
    body = compile_expression(text)
    known = {*names, *FUNCTIONS, "random", "randint"}
    for node in ast.walk(body):
        if isinstance(node, ast.Name) and node.id not in known:
            raise ExpressionError(f"unknown name {node.id!r} in {text!r}")


def variables(text):
    """What ``text`` reads: ``(stats, resources)``, each a sorted tuple of the names read from a
    subject (``source.dex`` reads the stat ``dex``; ``source.current("hp")`` the resource
    ``hp``). Raises ExpressionError when ``text`` does not parse."""
    body = compile_expression(text)
    stats, resources = set(), set()
    calls = set()
    for node in ast.walk(body):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(id(node.func))
            name = node.func.attr
            if name in RESOURCE_METHODS and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    resources.add(arg.value)
    for node in ast.walk(body):
        if (
            isinstance(node, ast.Attribute)
            and id(node) not in calls
            and isinstance(node.value, ast.Name)
            and node.value.id in SUBJECTS
        ):
            stats.add(node.attr)
    return tuple(sorted(stats)), tuple(sorted(resources))


def undeclared(text, stats, resources=()):
    """The names ``text`` reads that are not declared: a stat read from a subject that is
    neither in ``stats`` nor a resource in ``resources`` (``source.hp`` reads the resource's
    current value), and a resource of ``current / maximum / ratio`` not in ``resources``."""
    read_stats, read_resources = variables(text)
    stats, resources = set(stats), set(resources)
    missing = [n for n in read_stats if n not in stats and n not in resources]
    missing += [n for n in read_resources if n not in resources]
    return list(dict.fromkeys(missing))


def evaluate(text, names, rng=None):
    """The value of ``text`` with ``names`` (numbers or SubjectViews); ``rng`` rolls
    ``random()`` and ``randint``."""
    body = compile_expression(text)
    dice = rng if rng is not None else _random
    functions = dict(FUNCTIONS)
    functions["random"] = lambda: float(dice.random())
    functions["randint"] = lambda a, b: float(dice.randint(int(a), int(b)))
    value = _eval(body, names, functions)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if not isinstance(value, (int, float)):
        raise ExpressionError(f"{text!r} is not a number")
    value = float(value)
    if not math.isfinite(value):
        raise ExpressionError(f"{text!r} is not finite")
    return value


def _eval(node, names, functions):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        if node.id in ("True", "False"):
            return node.id == "True"
        raise ExpressionError(f"unknown name {node.id!r}")
    if isinstance(node, ast.Attribute):
        owner = _eval(node.value, names, functions)
        if not isinstance(owner, SubjectView):
            raise ExpressionError(f".{node.attr} needs a subject")
        if node.attr in SUBJECT_METHODS:
            return getattr(owner, node.attr)
        return owner.value(node.attr)
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](
            _eval(node.left, names, functions), _eval(node.right, names, functions)
        )
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, names, functions)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.Not):
            return not value
        raise ExpressionError("unsupported unary operator")
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, names, functions) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, names, functions)
        for op, right_node in zip(node.ops, node.comparators):
            right = _eval(right_node, names, functions)
            if type(op) not in _COMPARE or not _COMPARE[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        test = _eval(node.test, names, functions)
        return _eval(node.body if test else node.orelse, names, functions)
    if isinstance(node, ast.Call):
        if node.keywords:
            raise ExpressionError("keyword arguments are not allowed")
        args = [_eval(a, names, functions) for a in node.args]
        if isinstance(node.func, ast.Name) and node.func.id in functions:
            return functions[node.func.id](*args)
        if isinstance(node.func, ast.Attribute):
            method = _eval(node.func, names, functions)
            if callable(method):
                return method(*args)
        raise ExpressionError("only the listed functions may be called")
    raise ExpressionError(f"{type(node).__name__} is not allowed")


__all__ = [
    "ExpressionError",
    "FORMULA_FIELDS",
    "FUNCTIONS",
    "SUBJECTS",
    "SubjectView",
    "check_expression",
    "compile_expression",
    "evaluate",
    "undeclared",
    "variables",
]
