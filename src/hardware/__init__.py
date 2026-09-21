"""
OpenJ5 Hardware package (HAL ports + concrete drivers).
"""
from . import hal  # noqa: F401
from . import drivers  # noqa: F401

__all__ = ["hal", "drivers"]