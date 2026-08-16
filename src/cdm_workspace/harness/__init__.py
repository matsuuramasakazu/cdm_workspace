"""
Universal AI Agent Harness package.

Exports core diagnostics, verification pipelines, safe code runners,
and CDM inspection tools.
"""

from __future__ import annotations

from .core import HarnessContext, doctor, exec_code, get_context, verify
from .cdm_plugin import generate_irs_sample, inspect_model, list_business_events
from .cli import main

__all__ = [
    "HarnessContext",
    "doctor",
    "verify",
    "exec_code",
    "get_context",
    "inspect_model",
    "list_business_events",
    "generate_irs_sample",
    "main",
]
