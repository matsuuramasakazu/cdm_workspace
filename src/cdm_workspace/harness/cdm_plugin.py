"""
CDM Adapter & Domain Plugin for AI Agent Harness.

Provides model discovery, field inspection, business event listing,
and IRS trade generation utilities with safe CDM runtime compatibility.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


def _get_bundle_classes() -> Dict[str, Type[Any]]:
    """Retrieves all classes registered in finos._bundle after patch application."""
    import cdm_compat
    import finos._bundle as bundle
    classes: Dict[str, Type[Any]] = {}
    for attr_name, obj in bundle.__dict__.items():
        if isinstance(obj, type):
            classes[attr_name] = obj
            cls_name = getattr(obj, "__name__", None)
            if cls_name:
                classes[cls_name] = obj
                classes[cls_name.lower()] = obj
            classes[attr_name.lower()] = obj
            if "_" in attr_name:
                short_name = attr_name.split("_")[-1]
                classes[short_name] = obj
                classes[short_name.lower()] = obj
    return classes


def inspect_model(model_name: str) -> Dict[str, Any]:
    """
    Safely inspects a CDM model class's fields, types, and inheritance hierarchy.

    Parameters:
        model_name: Name of the class to inspect (e.g. 'Trade', 'InterestRatePayout', 'TradeState').

    Returns:
        A dictionary containing fields, types, base classes, docstring, and a formatted report.
    """
    import cdm_compat
    from pydantic import BaseModel

    bundle_classes = _get_bundle_classes()
    target_cls = bundle_classes.get(model_name)

    if target_cls is None:
        # Case-insensitive fallback
        matches = [k for k in bundle_classes if k.lower() == model_name.lower()]
        if matches:
            target_cls = bundle_classes[matches[0]]

    if target_cls is None:
        available_sample = sorted(list(bundle_classes.keys()))[:15]
        return {
            "found": False,
            "error": f"Model '{model_name}' not found in finos._bundle. Some available: {available_sample}...",
            "report": f"Error: Model '{model_name}' not found in CDM bundle.",
        }

    doc = inspect.getdoc(target_cls) or "(No docstring)"
    bases = [b.__name__ for b in target_cls.__bases__ if b is not object]

    field_info: List[Dict[str, Any]] = []
    if issubclass(target_cls, BaseModel) and hasattr(target_cls, "model_fields"):
        for fname, ffield in target_cls.model_fields.items():
            field_info.append({
                "name": fname,
                "type": str(ffield.annotation),
                "required": ffield.is_required(),
                "default": str(ffield.default) if ffield.default is not None else None,
            })

    short_name = target_cls.__name__.split("_")[-1] if "_" in target_cls.__name__ else target_cls.__name__

    lines = [
        "=" * 60,
        f" CDM MODEL INSPECTOR : {short_name} ({target_cls.__name__})",
        "=" * 60,
        f"Module : {target_cls.__module__}",
        f"Bases  : {', '.join(bases) if bases else 'BaseModel'}",
        "-" * 60,
        "Fields:",
    ]
    if field_info:
        for f in field_info:
            req_str = "Required" if f["required"] else "Optional"
            lines.append(f" - {f['name']:<25} : {f['type']} ({req_str})")
    else:
        lines.append(" (No pydantic fields found or enum class)")
    lines.append("-" * 60)
    lines.append(f"Docstring: {doc.splitlines()[0] if doc else ''}")
    lines.append("=" * 60)

    report_str = "\n".join(lines)

    return {
        "found": True,
        "class_name": short_name,
        "full_name": target_cls.__name__,
        "module": target_cls.__module__,
        "bases": bases,
        "fields": field_info,
        "docstring": doc,
        "report": report_str,
    }


def list_business_events() -> Dict[str, Any]:
    """
    Returns an overview of supported IRS business events and qualification status.
    """
    events = [
        {"name": "Execution", "phase": "Inception", "qualifier": "Qualify_Execution", "description": "Trade execution agreement"},
        {"name": "ContractFormation", "phase": "Inception", "qualifier": "Qualify_ContractFormation", "description": "Legally binding OTC contract formation"},
        {"name": "ClearedTrade", "phase": "Inception / Clearing", "qualifier": "Qualify_ClearedTrade", "description": "Clearing at CCP (Alpha -> Beta/Gamma)"},
        {"name": "Reset", "phase": "Periodic", "qualifier": "Qualify_Reset", "description": "Floating rate index fixing / observation"},
        {"name": "CashTransfer", "phase": "Periodic / Settlement", "qualifier": "Qualify_CashTransfer", "description": "Coupon payment & net cashflow settlement"},
        {"name": "Increase", "phase": "Amendment", "qualifier": "Qualify_Increase", "description": "Notional quantity increase"},
        {"name": "PartialTermination", "phase": "Amendment", "qualifier": "Qualify_PartialTermination", "description": "Partial unwind with unwind fee"},
        {"name": "Termination", "phase": "Unwind", "qualifier": "Qualify_Termination", "description": "Full contract early termination"},
        {"name": "Renegotiation", "phase": "Amendment", "qualifier": "Qualify_Renegotiation", "description": "Terms / rate amendment"},
        {"name": "IndexTransition", "phase": "Benchmark", "qualifier": "Qualify_IndexTransition", "description": "IBOR to RFR fallback & spread adjustment"},
        {"name": "Novation", "phase": "Portfolio", "qualifier": "Qualify_Novation", "description": "Counterparty replacement & transfer"},
        {"name": "Allocation", "phase": "Portfolio", "qualifier": "Qualify_Allocation", "description": "Block trade split across accounts"},
        {"name": "Compression", "phase": "Portfolio", "qualifier": "Qualify_Compression", "description": "Portfolio netting & position collapse"},
        {"name": "ValuationUpdate", "phase": "Valuation", "qualifier": "Qualify_ValuationUpdate", "description": "Mark-to-market MTM update"},
    ]

    lines = [
        "=" * 70,
        " FINOS CDM : INTEREST RATE SWAP (IRS) BUSINESS EVENTS",
        "=" * 70,
        f"{'Event Name':<20} {'Lifecycle Phase':<20} {'Qualifier Function'}",
        "-" * 70,
    ]
    for ev in events:
        lines.append(f"{ev['name']:<20} {ev['phase']:<20} {ev['qualifier']}")
    lines.append("=" * 70)

    report_str = "\n".join(lines)

    return {
        "events": events,
        "count": len(events),
        "report": report_str,
    }


def generate_irs_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Constructs a sample Plain Vanilla IRS trade and validates JSON round-trip.
    """
    import cdm_compat
    from cdm_workspace.create_irs_trade import create_plain_irs_trade, generate_and_save_irs_json

    out_file = output_path or "irs_trade.json"
    saved_path = generate_and_save_irs_json(out_file)

    return {
        "ok": True,
        "output_path": str(saved_path),
        "size_bytes": saved_path.stat().st_size,
    }
