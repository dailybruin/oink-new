"""Compatibility shim for older references to `oink_project.settings`.

This file intentionally imports all settings from the new `src.settings` module.
"""
from src.settings import *  # noqa: F401,F403
