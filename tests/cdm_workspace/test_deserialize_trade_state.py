"""
Tests for CDM TradeState JSON Deserialization Sample
"""

import json
from pathlib import Path
from decimal import Decimal

import pytest

import cdm_compat
from finos.cdm.event.common.TradeState import TradeState
from finos.cdm.event.common.Trade import Trade
from finos.cdm.base.datetime.daycount.DayCountFractionEnum import DayCountFractionEnum
from cdm_workspace.deserialize_trade_state import (
    deserialize_trade_state_from_json,
    print_trade_summary,
)


@pytest.fixture
def sample_json_path() -> Path:
    """Returns the path to ird-ex01-vanilla-swap.json."""
    return Path("ird-ex01-vanilla-swap.json")


def test_deserialize_trade_state_from_file(sample_json_path: Path):
    """
    Verifies that ird-ex01-vanilla-swap.json can be loaded and deserialized
    into a strongly-typed TradeState object.
    """
    assert sample_json_path.exists(), f"Sample file not found: {sample_json_path}"

    trade_state = deserialize_trade_state_from_json(sample_json_path)

    assert isinstance(trade_state, TradeState)
    assert isinstance(trade_state.trade, Trade)

    trade = trade_state.trade

    # 1. Trade date
    assert str(trade.tradeDate) == "1994-12-12"

    # 2. Trade identifiers
    identifiers = [
        getattr(aid.identifier, "value", aid.identifier)
        for tid in trade.tradeIdentifier or []
        for aid in tid.assignedIdentifier or []
    ]
    assert "TW9235" in identifiers
    assert "SW2000" in identifiers

    # 3. Product taxonomy
    taxonomy = trade.product.taxonomy[0]
    assert getattr(taxonomy.source, "value", taxonomy.source) == "ISDA"
    assert getattr(taxonomy.productQualifier, "value", taxonomy.productQualifier) == "InterestRate_IRSwap_FixedFloat"

    # 4. Payout legs
    payouts = trade.product.economicTerms.payout
    assert len(payouts) == 2

    float_leg = payouts[0].InterestRatePayout
    assert float_leg is not None
    assert float_leg.rateSpecification.FloatingRateSpecification is not None
    assert getattr(float_leg.dayCountFraction, "value", float_leg.dayCountFraction) == "ACT/360"

    fixed_leg = payouts[1].InterestRatePayout
    assert fixed_leg is not None
    assert fixed_leg.rateSpecification.FixedRateSpecification is not None
    assert getattr(fixed_leg.dayCountFraction, "value", fixed_leg.dayCountFraction) == "30E/360"

    # 5. Notional and price
    price_quantities = trade.tradeLot[0].priceQuantity
    quantities = [
        q.value
        for pq in price_quantities
        for q in pq.quantity or []
    ]
    assert Decimal("50000000.0") in quantities


def test_deserialize_trade_state_from_string(sample_json_path: Path):
    """
    Verifies that TradeState can be deserialized directly from a raw JSON string.
    """
    json_str = sample_json_path.read_text(encoding="utf-8")
    trade_state = deserialize_trade_state_from_json(json_str)

    assert isinstance(trade_state, TradeState)
    assert trade_state.trade.tradeDate is not None


def test_print_trade_summary_execution(sample_json_path: Path, capsys):
    """
    Verifies that print_trade_summary executes without exceptions and outputs key information.
    """
    trade_state = deserialize_trade_state_from_json(sample_json_path)
    print_trade_summary(trade_state)

    captured = capsys.readouterr()
    assert "FINOS CDM TradeState Deserialization Summary" in captured.out
    assert "1994-12-12" in captured.out
    assert "TW9235" in captured.out
    assert "InterestRate_IRSwap_FixedFloat" in captured.out
    assert "ACT/360" in captured.out
