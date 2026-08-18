"""
cdm_workspace package.

FINOS CDM Plain Vanilla IRS generation and CDM utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .create_irs_trade import create_plain_irs_trade, generate_and_save_irs_json
    from .deserialize_trade_state import deserialize_trade_state_from_json
    from .qualify_trade import (
        AssetClass,
        BaseProduct,
        SubProduct,
        ProductQualifierEnum,
        ProductQualificationResult,
        qualify_trade_state,
        qualify_trade,
        qualify_economic_terms,
        qualify_from_json,
        is_vanilla_fixed_float_swap,
        print_qualification_summary,
    )
    from .harness import doctor, verify, exec_code, inspect_model, list_business_events, generate_irs_sample

__all__ = [
    "create_plain_irs_trade",
    "generate_and_save_irs_json",
    "deserialize_trade_state_from_json",
    "AssetClass",
    "BaseProduct",
    "SubProduct",
    "ProductQualifierEnum",
    "ProductQualificationResult",
    "qualify_trade_state",
    "qualify_trade",
    "qualify_economic_terms",
    "qualify_from_json",
    "is_vanilla_fixed_float_swap",
    "print_qualification_summary",
    "doctor",
    "verify",
    "exec_code",
    "inspect_model",
    "list_business_events",
    "generate_irs_sample",
]


def __getattr__(name: str):
    if name in ("create_plain_irs_trade", "generate_and_save_irs_json"):
        from . import create_irs_trade
        return getattr(create_irs_trade, name)
    if name == "deserialize_trade_state_from_json":
        from . import deserialize_trade_state
        return getattr(deserialize_trade_state, name)
    if name in (
        "AssetClass",
        "BaseProduct",
        "SubProduct",
        "ProductQualifierEnum",
        "ProductQualificationResult",
        "qualify_trade_state",
        "qualify_trade",
        "qualify_economic_terms",
        "qualify_from_json",
        "is_vanilla_fixed_float_swap",
        "print_qualification_summary",
    ):
        from . import qualify_trade
        return getattr(qualify_trade, name)
    if name in ("doctor", "verify", "exec_code", "inspect_model", "list_business_events", "generate_irs_sample"):
        from . import harness
        return getattr(harness, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
