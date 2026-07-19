"""Foundation smoke tests for the arranger package."""

import particular


def test_package_exposes_version() -> None:
    """The installable engine package exposes its build version."""
    assert particular.__version__ == "0.0.0"
