"""
FINOS CDM TradeState JSON Deserialization Sample

This script demonstrates how to deserialize a standard FINOS CDM (v6 / v7)
TradeState JSON file (such as `ird-ex01-vanilla-swap.json`) into strongly-typed
finos-cdm Pydantic data classes, inspect financial components, and navigate
the trade lifecycle hierarchy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

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
                print(f"Trade Identifier [{idx}] : {id_val}")

    # 2. Parties
    print("\n--- Parties ---")
    if trade.party:
        for idx, party in enumerate(trade.party, start=1):
            party_name = getattr(party.name, "value", party.name) if party.name else "(Unnamed)"
            lei = party.partyId[0].identifier if party.partyId else "N/A"
            lei_val = getattr(lei, "value", lei)
            print(f"Party [{idx}] : {party_name} (LEI/ID: {lei_val})")

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

            # Leg Type & Rate details
            leg_type = "Unknown"
            rate_info = ""
            if irs.rateSpecification:
                if irs.rateSpecification.FixedRateSpecification:
                    leg_type = "Fixed Rate Leg"
                    fixed_spec = irs.rateSpecification.FixedRateSpecification
                    if fixed_spec.rateSchedule and fixed_spec.rateSchedule.price:
                        rate_val = getattr(fixed_spec.rateSchedule.price, "value", None)
                        rate_info = f", Rate = {rate_val}"
                elif irs.rateSpecification.FloatingRateSpecification:
                    leg_type = "Floating Rate Leg"
                    float_spec = irs.rateSpecification.FloatingRateSpecification
                    rate_info = f", RateOption Address Ref"

            print(f"Leg [{leg_idx}] : {leg_type}")
            print(f"  Payer / Receiver : {payer} -> {receiver}")
            print(f"  Day Count Fraction: {dcf}")
            print(f"  Calculation Period: {eff_date} to {term_date}{rate_info}")

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
