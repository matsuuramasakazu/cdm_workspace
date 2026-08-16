"""
cdm_workspace package.

FINOS CDM Plain Vanilla IRS generation and CDM utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .create_irs_trade import create_plain_irs_trade, generate_and_save_irs_json

__all__ = [
    "create_plain_irs_trade",
    "generate_and_save_irs_json",
]


def __getattr__(name: str):
    if name in ("create_plain_irs_trade", "generate_and_save_irs_json"):
        from . import create_irs_trade
        return getattr(create_irs_trade, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
