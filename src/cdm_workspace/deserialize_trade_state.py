"""
FINOS CDM TradeState JSON Deserialization Sample

This script demonstrates how to deserialize a standard FINOS CDM (v6 / v7)
TradeState JSON file (such as `ird-ex01-vanilla-swap.json`) into strongly-typed
finos-cdm Pydantic data classes, inspect financial components, and navigate
the trade lifecycle hierarchy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Union

# Add src/ to sys.path if running as a standalone script
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# --- Step 1: Initialize CDM Compatibility Layer ---
# Always import cdm_compat before any finos.cdm.* imports to ensure
# Rune runtime metadata patches and Pydantic v2 schemas are active.
import cdm_compat

# --- Step 2: Import FINOS CDM Data Classes ---
from finos.cdm.event.common.TradeState import TradeState
from finos.cdm.event.common.Trade import Trade
from finos.cdm.product.asset.InterestRatePayout import InterestRatePayout


def deserialize_trade_state_from_json(json_path_or_str: Union[str, Path]) -> TradeState:
    """
    Deserializes a FINOS CDM TradeState JSON file or JSON string into a TradeState object.

    Args:
        json_path_or_str: Path to the CDM JSON file or a raw JSON string.

    Returns:
        TradeState: Strongly-typed FINOS CDM TradeState model instance.
    """
    if isinstance(json_path_or_str, Path) or (
        isinstance(json_path_or_str, str) and Path(json_path_or_str).is_file()
    ):
        file_path = Path(json_path_or_str)
        raw_json_str = file_path.read_text(encoding="utf-8")
    else:
        raw_json_str = str(json_path_or_str)

    # Use Pydantic v2 model_validate_json for high-performance deserialization
    trade_state = TradeState.model_validate_json(raw_json_str)
    # Resolve all internal and scoped references to actual target model objects
    trade_state = cdm_compat.resolve_model_references(trade_state)
    return trade_state


def print_trade_summary(trade_state: TradeState) -> None:
    """
    Prints a formatted summary of financial attributes extracted from the TradeState.
    """
    trade: Trade = trade_state.trade

    print("=" * 70)
    print("FINOS CDM TradeState Deserialization Summary")
    print("=" * 70)

    # 1. Header & Identifiers
    trade_date = trade.tradeDate
    print(f"Trade Execution Date : {trade_date}")
    if trade.tradeIdentifier:
        for idx, tid in enumerate(trade.tradeIdentifier, start=1):
            for aid in tid.assignedIdentifier or []:
                id_val = getattr(aid.identifier, "value", aid.identifier)
                issuer_ref = getattr(tid.issuerReference, "name", getattr(tid.issuerReference, "partyId", None))
                issuer_str = f" (Issuer: {issuer_ref})" if issuer_ref else ""
                print(f"Trade Identifier [{idx}] : {id_val}{issuer_str}")

    # 2. Parties & Counterparties
    print("\n--- Parties & Counterparties ---")
    if trade.party:
        for idx, party in enumerate(trade.party, start=1):
            party_name = getattr(party.name, "value", party.name) if party.name else "(Unnamed)"
            lei = party.partyId[0].identifier if party.partyId else "N/A"
            lei_val = getattr(lei, "value", lei)
            print(f"Party [{idx}] : {party_name} (LEI/ID: {lei_val})")

    if trade.counterparty:
        for idx, cp in enumerate(trade.counterparty, start=1):
            role = getattr(cp.role, "value", cp.role)
            p_ref = cp.partyReference
            p_name = getattr(p_ref, "name", "N/A") if p_ref else "N/A"
            print(f"Counterparty [{idx}] : Role = {role} -> Party = {p_name}")

    # 3. Product & Taxonomy
    print("\n--- Product Classification ---")
    if trade.product and trade.product.taxonomy:
        for tax in trade.product.taxonomy:
            source = getattr(tax.source, "value", tax.source)
            qualifier = getattr(tax.productQualifier, "value", tax.productQualifier)
            print(f"Taxonomy : {source} -> {qualifier}")

    # 4. Interest Rate Payout Legs
    print("\n--- Economic Terms & Payout Legs ---")
    economic_terms = trade.product.economicTerms if trade.product else None
    if economic_terms and economic_terms.payout:
        for leg_idx, payout in enumerate(economic_terms.payout, start=1):
            irs: InterestRatePayout | None = payout.InterestRatePayout
            if irs is None:
                continue

            payer = getattr(irs.payerReceiver.payer, "value", irs.payerReceiver.payer) if irs.payerReceiver else "N/A"
            receiver = getattr(irs.payerReceiver.receiver, "value", irs.payerReceiver.receiver) if irs.payerReceiver else "N/A"
            dcf = getattr(irs.dayCountFraction, "value", irs.dayCountFraction) if irs.dayCountFraction else "N/A"

            # Dates
            eff_date = "N/A"
            term_date = "N/A"
            if irs.calculationPeriodDates:
                if irs.calculationPeriodDates.effectiveDate and irs.calculationPeriodDates.effectiveDate.adjustableDate:
                    eff_date = str(irs.calculationPeriodDates.effectiveDate.adjustableDate.unadjustedDate)
                if irs.calculationPeriodDates.terminationDate and irs.calculationPeriodDates.terminationDate.adjustableDate:
                    term_date = str(irs.calculationPeriodDates.terminationDate.adjustableDate.unadjustedDate)

            # Notional Quantity via resolved quantitySchedule
            notional_info = ""
            if irs.priceQuantity and irs.priceQuantity.quantitySchedule:
                sched = irs.priceQuantity.quantitySchedule
                q_val = getattr(sched, "value", None)
                q_unit = getattr(sched, "unit", None)
                q_curr = getattr(q_unit, "currency", "") if q_unit else ""
                q_curr_val = getattr(q_curr, "value", q_curr)
                if q_val is not None:
                    notional_info = f", Notional = {q_val:,.2f} {q_curr_val}"

            # Leg Type & Rate details
            leg_type = "Unknown"
            rate_info = ""
            if irs.rateSpecification:
                if irs.rateSpecification.FixedRateSpecification:
                    leg_type = "Fixed Rate Leg"
                    fixed_spec = irs.rateSpecification.FixedRateSpecification
                    if fixed_spec.rateSchedule and fixed_spec.rateSchedule.price:
                        price_sched = fixed_spec.rateSchedule.price
                        rate_val = getattr(price_sched, "value", None)
                        rate_info = f", Fixed Rate = {rate_val}"
                elif irs.rateSpecification.FloatingRateSpecification:
                    leg_type = "Floating Rate Leg"
                    float_spec = irs.rateSpecification.FloatingRateSpecification
                    rate_opt = float_spec.rateOption
                    rate_opt_type = getattr(rate_opt, "floatingRateIndex", getattr(rate_opt, "_FQRTN", "RateIndex"))
                    rate_info = f", Floating Index = {rate_opt_type}"

            print(f"Leg [{leg_idx}] : {leg_type}")
            print(f"  Payer / Receiver : {payer} -> {receiver}")
            print(f"  Day Count Fraction: {dcf}")
            print(f"  Calculation Period: {eff_date} to {term_date}{notional_info}{rate_info}")

    # 5. Notional & Pricing (TradeLot)
    print("\n--- Trade Lot & Notional Details ---")
    if trade.tradeLot:
        for lot_idx, lot in enumerate(trade.tradeLot, start=1):
            if not lot.priceQuantity:
                continue
            for pq_idx, pq in enumerate(lot.priceQuantity, start=1):
                if pq.quantity:
                    for q in pq.quantity:
                        q_val = getattr(q, "value", None)
                        curr = q.unit.currency if q.unit else ""
                        curr_val = getattr(curr, "value", curr)
                        print(f"Lot [{lot_idx}] Notional Quantity [{pq_idx}]: {q_val:,} {curr_val}")
                if pq.price:
                    for pr in pq.price:
                        p_val = getattr(pr, "value", None)
                        p_type = getattr(pr.priceType, "value", pr.priceType)
                        print(f"Lot [{lot_idx}] Price [{pq_idx}]: {p_val} (Type: {p_type})")

    print("=" * 70)


def main() -> None:
    """Main execution function loading ird-ex01-vanilla-swap.json."""
    default_json_path = Path("ird-ex01-vanilla-swap.json")
    if not default_json_path.exists():
        # Fallback if run from different working directory
        default_json_path = Path(__file__).parent.parent.parent / "ird-ex01-vanilla-swap.json"

    print(f"Loading and deserializing: {default_json_path.resolve()}")
    trade_state = deserialize_trade_state_from_json(default_json_path)
    print_trade_summary(trade_state)


if __name__ == "__main__":
    main()
