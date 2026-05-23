"""Capture fitness/callback source from a local pygad.GA for import.

Pure stdlib (inspect/ast/textwrap). Operates on plain callables and a
duck-typed ``ga`` object; never imports pygad.
"""
from __future__ import annotations

import ast
import builtins as _builtins
import inspect
import textwrap
import types
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def capture_callable_source(obj) -> Tuple[Optional[str], Optional[str], str]:
    """Return (source, entry_name, reason).

    On success: (dedented source text, the def's name, "").
    On failure: (None, None, human reason) for lambdas, bound methods,
    callable instances, builtins, or when source is unavailable.
    """
    if isinstance(obj, types.LambdaType) and getattr(obj, "__name__", "") == "<lambda>":
        return None, None, "it is a lambda (lambdas have no named, standalone source)"
    if inspect.ismethod(obj):
        return None, None, "it is a bound method (methods cannot run standalone on Vilvik)"
    if inspect.isbuiltin(obj) or (inspect.isroutine(obj) and not inspect.isfunction(obj)):
        return None, None, "it is a built-in or C function (no Python source)"
    if not inspect.isfunction(obj):
        if callable(obj):
            return None, None, "it is a callable object/instance (pass its source explicitly)"
        return None, None, "it is not a callable"
    try:
        raw = inspect.getsource(obj)
    except (OSError, TypeError):
        return None, None, "its source is unavailable (defined in a REPL/notebook or dynamically)"
    return textwrap.dedent(raw), obj.__name__, ""


CODE_ROLES = (
    "fitness_func", "on_start", "on_fitness", "on_parents",
    "on_crossover", "on_mutation", "on_generation", "on_stop",
)


@dataclass
class RoleCapture:
    role: str
    source: Optional[str] = None
    entry: Optional[str] = None
    provenance: str = "absent"  # "override" | "auto" | "absent" | "unresolved"
    reason: str = ""


@dataclass
class CaptureReport:
    roles: List[RoleCapture] = field(default_factory=list)
    preamble: str = ""
    referenced_unresolved: List[str] = field(default_factory=list)

    def role(self, name: str) -> Optional[RoleCapture]:
        for r in self.roles:
            if r.role == name:
                return r
        return None

    def ok(self) -> bool:
        f = self.role("fitness_func")
        if f is None or f.provenance not in ("auto", "override"):
            return False
        return not any(r.provenance == "unresolved" for r in self.roles)

    def __str__(self) -> str:
        lines = ["Vilvik import capture report:"]
        for r in self.roles:
            if r.provenance == "absent":
                continue
            mark = {"auto": "auto-extracted", "override": "your override",
                    "unresolved": "NEEDS MANUAL"}.get(r.provenance, r.provenance)
            line = f"  - {r.role}: {mark}"
            if r.provenance == "unresolved":
                line += f" ({r.reason}). Pass it explicitly, e.g. "
                if r.role == "fitness_func":
                    line += "vilvik.push(ga, fitness_func=my_fn) or fitness_source='...'."
                else:
                    line += f"vilvik.push(ga, callbacks={{'{r.role}': my_fn_or_source}})."
            lines.append(line)
        if self.referenced_unresolved:
            lines.append(
                "  - referenced names not auto-included (add via preamble=...): "
                + ", ".join(sorted(self.referenced_unresolved)))
        return "\n".join(lines)


def _detect_entry_from_source(source: str) -> Optional[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    name = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
    return name


def _resolve_one(role: str, ga: Any, override: Any, override_entry: Optional[str] = None) -> RoleCapture:
    if override is not None:
        if isinstance(override, str):
            entry = override_entry or _detect_entry_from_source(override) or role
            return RoleCapture(role, override, entry, "override")
        src, entry, reason = capture_callable_source(override)
        if src is None:
            return RoleCapture(role, None, None, "unresolved", reason)
        return RoleCapture(role, src, override_entry or entry, "override")
    obj = getattr(ga, role, None)
    if obj is None:
        return RoleCapture(role, None, None, "absent")
    src, entry, reason = capture_callable_source(obj)
    if src is None:
        return RoleCapture(role, None, None, "unresolved", reason)
    return RoleCapture(role, src, entry, "auto")


def _referenced_globals(func) -> List[str]:
    """Names the function references that resolve in its module globals.

    Uses co_names intersected with __globals__, minus builtins. Best-effort;
    the safe fallback is the user passing an explicit preamble.
    """
    g = getattr(func, "__globals__", {}) or {}
    names: List[str] = []
    for n in getattr(getattr(func, "__code__", None), "co_names", ()) or ():
        if n in g and not hasattr(_builtins, n) and n not in names:
            names.append(n)
    return names


def _auto_preamble(func):
    """Return (preamble_str, unresolved_names) for a captured fitness function."""
    g = getattr(func, "__globals__", {}) or {}
    own_module = getattr(func, "__module__", None)
    import_lines: List[str] = []
    helper_sources: List[str] = []
    unresolved: List[str] = []
    for name in _referenced_globals(func):
        val = g.get(name)
        if inspect.ismodule(val):
            mod = val.__name__
            import_lines.append(f"import {mod}" if mod == name else f"import {mod} as {name}")
        elif inspect.isfunction(val) and getattr(val, "__module__", None) == own_module:
            src, _entry, reason = capture_callable_source(val)
            if src is not None:
                helper_sources.append(src)
            else:
                unresolved.append(name)
        elif inspect.isfunction(val) or inspect.isclass(val):
            mod = getattr(val, "__module__", None)
            if mod and mod != own_module:
                import_lines.append(f"from {mod} import {name}")
            else:
                unresolved.append(name)
        else:
            unresolved.append(name)
    return ("\n\n".join(import_lines + helper_sources), unresolved)


def capture_code(
    ga: Any,
    *,
    fitness_func: Any = None,
    fitness_source: Optional[str] = None,
    fitness_entry: Optional[str] = None,
    callbacks: Optional[Dict[str, Any]] = None,
    preamble: Optional[str] = None,
) -> CaptureReport:
    """Resolve fitness + callback code for an import, honoring per-role overrides."""
    if fitness_func is not None and fitness_source is not None:
        raise ValueError("Pass only one of fitness_func or fitness_source.")
    callbacks = callbacks or {}
    _callback_roles = set(CODE_ROLES) - {"fitness_func"}
    bad = set(callbacks) - _callback_roles
    if bad:
        raise ValueError(
            f"Unknown callback role(s) {sorted(bad)}; allowed callbacks are "
            f"{sorted(_callback_roles)}. Use fitness_func= / fitness_source= for the fitness function."
        )
    overrides: Dict[str, Any] = {}
    if fitness_func is not None:
        overrides["fitness_func"] = fitness_func
    if fitness_source is not None:
        overrides["fitness_func"] = fitness_source
    overrides.update(callbacks)

    report = CaptureReport()
    for role in CODE_ROLES:
        ov = overrides.get(role)
        ov_entry = fitness_entry if role == "fitness_func" else None
        report.roles.append(_resolve_one(role, ga, ov, ov_entry))
    if preamble:
        report.preamble = preamble
    else:
        f = report.role("fitness_func")
        ga_fitness = getattr(ga, "fitness_func", None)
        if f and f.provenance == "auto" and inspect.isfunction(ga_fitness):
            report.preamble, report.referenced_unresolved = _auto_preamble(ga_fitness)
        else:
            report.preamble = ""
    return report
