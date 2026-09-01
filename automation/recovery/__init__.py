"""Safe incident recovery orchestration with lazy public imports."""

from importlib import import_module
from typing import Any


_PUBLIC_FUNCTIONS = {
    "run_escalation": (".escalation_engine", "run_escalation"),
    "run_recovery": (".recovery_runner", "run_recovery"),
    "run_standard_build": (".standard_build_runner", "run_standard_build"),
    "run_workflow": (".workflow_runner", "run_workflow"),
}
__all__ = list(_PUBLIC_FUNCTIONS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _PUBLIC_FUNCTIONS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value
