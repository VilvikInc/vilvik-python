import pytest
from types import SimpleNamespace

from vilvik.exceptions import CaptureError, VilvikError
from vilvik import _capture


def test_capture_error_is_vilvik_error():
    assert issubclass(CaptureError, VilvikError)
    e = CaptureError("nope")
    assert "nope" in str(e)


def module_level_fitness(ga_instance, solution, solution_idx):
    return 0.0


class _CallableObj:
    def __call__(self, ga_instance, solution, solution_idx):
        return 1.0


def test_capture_module_level_function():
    src, entry, reason = _capture.capture_callable_source(module_level_fitness)
    assert reason == ""
    assert entry == "module_level_fitness"
    assert "def module_level_fitness" in src


def test_capture_lambda_unresolved():
    src, entry, reason = _capture.capture_callable_source(lambda g, s, i: 0.0)
    assert src is None and entry is None
    assert "lambda" in reason.lower()


def test_capture_bound_method_unresolved():
    obj = _CallableObj()
    src, entry, reason = _capture.capture_callable_source(obj.__call__)
    assert src is None
    assert "method" in reason.lower()


def test_capture_callable_instance_unresolved():
    src, entry, reason = _capture.capture_callable_source(_CallableObj())
    assert src is None
    assert "callable object" in reason.lower() or "instance" in reason.lower()


def test_capture_builtin_unresolved():
    src, entry, reason = _capture.capture_callable_source(len)
    assert src is None
    assert reason


def on_generation_cb(ga_instance):
    return None


def test_capture_code_auto_fitness_and_callback():
    ga = SimpleNamespace(fitness_func=module_level_fitness, on_generation=on_generation_cb)
    report = _capture.capture_code(ga)
    assert report.ok()
    roles = {r.role: r for r in report.roles}
    assert roles["fitness_func"].provenance == "auto"
    assert roles["fitness_func"].entry == "module_level_fitness"
    assert roles["on_generation"].provenance == "auto"
    assert roles["on_stop"].provenance == "absent"


def test_override_source_string_wins():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    report = _capture.capture_code(
        ga, fitness_source="def f(ga_instance, solution, solution_idx):\n    return 1.0",
        fitness_entry="f")
    r = report.role("fitness_func")
    assert r.provenance == "override"
    assert r.entry == "f"
    assert "return 1.0" in r.source


def test_override_callable_reextracts():
    ga = SimpleNamespace(fitness_func=lambda g, s, i: 0.0)
    report = _capture.capture_code(ga, fitness_func=module_level_fitness)
    r = report.role("fitness_func")
    assert r.provenance == "override"
    assert r.entry == "module_level_fitness"


def test_unresolved_fitness_makes_report_not_ok():
    ga = SimpleNamespace(fitness_func=lambda g, s, i: 0.0)
    report = _capture.capture_code(ga)
    assert not report.ok()
    r = report.role("fitness_func")
    assert r.provenance == "unresolved"
    assert "lambda" in r.reason.lower()
    assert "fitness_source" in str(report) or "fitness_func=" in str(report)


def test_callback_override_via_callbacks_dict():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    report = _capture.capture_code(
        ga, callbacks={"on_stop": "def on_stop(ga_instance, last):\n    pass"})
    r = report.role("on_stop")
    assert r.provenance == "override"
    assert r.entry == "on_stop"


def test_both_fitness_forms_is_error():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    with pytest.raises(ValueError):
        _capture.capture_code(ga, fitness_func=module_level_fitness, fitness_source="def f(): pass")


def test_callbacks_cannot_contain_fitness_func():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    with pytest.raises(ValueError):
        _capture.capture_code(ga, callbacks={"fitness_func": "def f(): pass"})


def test_unknown_callback_role_rejected():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    with pytest.raises(ValueError):
        _capture.capture_code(ga, callbacks={"on_bogus": "def f(): pass"})


def test_lambda_callback_override_is_unresolved():
    ga = SimpleNamespace(fitness_func=module_level_fitness)
    report = _capture.capture_code(ga, callbacks={"on_generation": lambda g: None})
    r = report.role("on_generation")
    assert r.provenance == "unresolved"
    assert not report.ok()  # a present-but-unresolved role fails the report


import math as _math_alias  # module-level import the helper below references


def _helper_double(x):
    return x * 2.0


def fitness_using_helpers(ga_instance, solution, solution_idx):
    return _helper_double(_math_alias.fsum(solution))


def fitness_using_unknown_data(ga_instance, solution, solution_idx):
    return sum(s * w for s, w in zip(solution, SOME_WEIGHTS))  # noqa: F821


def test_auto_preamble_imports_and_helpers():
    ga = SimpleNamespace(fitness_func=fitness_using_helpers)
    report = _capture.capture_code(ga)
    assert report.ok()
    assert "import math as _math_alias" in report.preamble
    assert "def _helper_double" in report.preamble
    assert not report.referenced_unresolved


def test_unknown_global_reported():
    globals()["SOME_WEIGHTS"] = [1.0, 2.0, 3.0]
    ga = SimpleNamespace(fitness_func=fitness_using_unknown_data)
    report = _capture.capture_code(ga)
    assert "SOME_WEIGHTS" in report.referenced_unresolved


def test_explicit_preamble_skips_autoscan():
    ga = SimpleNamespace(fitness_func=fitness_using_helpers)
    report = _capture.capture_code(ga, preamble="import math as _math_alias")
    assert report.preamble == "import math as _math_alias"
    assert "def _helper_double" not in report.preamble
