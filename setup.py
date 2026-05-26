"""Backwards-compatible setup shim.

All real configuration lives in pyproject.toml. This file exists so older
pip versions (<21.3, which lack PEP 660 support) can still install the
package in editable mode.
"""

from setuptools import setup

setup()
