"""Pytest configuration.

Enables the Home Assistant custom-component test harness when it is installed.
The pure-protocol tests in ``tests/test_protocol.py`` do not need it and run
with a plain ``python3 tests/test_protocol.py``.
"""

import os
import sys

# Ensure the repo root is importable so ``custom_components.pacekeeper`` resolves.
sys.path.insert(0, os.path.dirname(__file__))

try:
    import pytest_homeassistant_custom_component  # noqa: F401

    pytest_plugins = ("pytest_homeassistant_custom_component",)
except ImportError:  # pragma: no cover - harness not installed
    pass
