"""
Unit Tests for cdm_compat package.

Tests metadata patches, schema rebuilding, and round-trip JSON serialization.
"""

from __future__ import annotations

import datetime
import unittest
from decimal import Decimal

import cdm_compat
from pydantic import BaseModel, Field

# CDM imports
from finos.cdm.base.datetime.BusinessCenters import BusinessCenters
from finos.cdm.base.datetime.BusinessDayAdjustments import BusinessDayAdjustments
from finos.cdm.base.datetime.BusinessDayConventionEnum import BusinessDayConventionEnum
from finos.cdm.base.math.NonNegativeQuantitySchedule import NonNegativeQuantitySchedule
from finos.cdm.base.math.UnitType import UnitType
from finos.cdm.base.staticdata.identifier.AssignedIdentifier import AssignedIdentifier
from finos.cdm.base.staticdata.identifier.TradeIdentifierTypeEnum import TradeIdentifierTypeEnum
from finos.cdm.base.staticdata.party.Counterparty import Counterparty
from finos.cdm.base.staticdata.party.CounterpartyRoleEnum import CounterpartyRoleEnum
from finos.cdm.base.staticdata.party.Party import Party
from finos.cdm.base.staticdata.party.PartyIdentifier import PartyIdentifier
from finos.cdm.base.staticdata.party.PayerReceiver import PayerReceiver
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
from finos.cdm.observable.asset.PriceQuantity import PriceQuantity
from finos.cdm.observable.asset.PriceSchedule import PriceSchedule
from finos.cdm.observable.asset.PriceTypeEnum import PriceTypeEnum
from finos.cdm.product.asset.InterestRatePayout import InterestRatePayout
from finos.cdm.product.template.EconomicTerms import EconomicTerms
from finos.cdm.product.template.NonTransferableProduct import NonTransferableProduct
from finos.cdm.product.template.Payout import Payout
from finos.cdm.product.template.TradeLot import TradeLot


class TestCdmCompat(unittest.TestCase):
    def test_patch_status(self):
        """Test that patches are active and idempotent."""
        self.assertTrue(cdm_compat.is_patched())
        # Re-applying should return False (already applied)
        self.assertFalse(cdm_compat.apply_patches())

    def test_complex_type_none_handling(self):
        """Test that ComplexType fields handle None values without validation error."""
        # businessCentersReference is None by default
        biz_centers = BusinessCenters(businessCenter=["JPTO"])
        biz_adj = BusinessDayAdjustments(
            businessDayConvention=BusinessDayConventionEnum.MODFOLLOWING,
            businessCenters=biz_centers,
        )
        self.assertEqual(biz_adj.businessDayConvention, BusinessDayConventionEnum.MODFOLLOWING)
        self.assertIsNotNone(biz_adj.businessCenters)

    def test_basic_type_list_serialization_roundtrip(self):
        """Test that list of StrWithMeta (e.g. businessCenter) serializes and deserializes properly."""
        biz_centers = BusinessCenters(businessCenter=["JPTO", "USNY"])
        json_data = biz_centers.model_dump_json(exclude_none=True)
        self.assertIn("JPTO", json_data)
        self.assertIn("USNY", json_data)

        # Reload
        reloaded = BusinessCenters.model_validate_json(json_data)
        self.assertEqual(len(reloaded.businessCenter), 2)

    def test_trade_identifier_creation(self):
        """Test that TradeIdentifier properly validates assignedIdentifier and identifierType."""
        trade_id = TradeIdentifier(
            assignedIdentifier=[
                AssignedIdentifier(identifier="TEST-TRADE-001", version=1)
            ],
            identifierType=TradeIdentifierTypeEnum.UNIQUE_TRANSACTION_IDENTIFIER,
        )
        json_data = trade_id.model_dump_json(exclude_none=True)
        self.assertIn("TEST-TRADE-001", json_data)
        self.assertIn("UniqueTransactionIdentifier", json_data)

        reloaded = TradeIdentifier.model_validate_json(json_data)
        self.assertEqual(len(reloaded.assignedIdentifier), 1)

    def test_price_quantity_rebuilding(self):
        """Test that PriceQuantity handles quantity and price schedules."""
        unit = UnitType(currency="JPY")
        quantity = NonNegativeQuantitySchedule(value=Decimal("500000000"), unit=unit)
        price = PriceSchedule(value=Decimal("0.01"), priceType=PriceTypeEnum.INTEREST_RATE)

        pq = PriceQuantity(quantity=quantity, price=[price])
        json_data = pq.model_dump_json(exclude_none=True)
        self.assertIn("500000000", json_data)
        self.assertIn("JPY", json_data)

        reloaded = PriceQuantity.model_validate_json(json_data)
        self.assertEqual(reloaded.quantity.value, Decimal("500000000"))

    def test_trade_roundtrip_validation(self):
        """Test that a complete Trade instance serializes and parses without schema errors."""
        party1 = Party(partyId=[PartyIdentifier(identifier="PARTY_A")])
        party2 = Party(partyId=[PartyIdentifier(identifier="PARTY_B")])

        trade_id = TradeIdentifier(
            assignedIdentifier=[AssignedIdentifier(identifier="TRADE-123", version=1)],
            identifierType=TradeIdentifierTypeEnum.UNIQUE_TRANSACTION_IDENTIFIER,
        )

        payout = Payout(
            InterestRatePayout=InterestRatePayout(
                payerReceiver=PayerReceiver(
                    payer=CounterpartyRoleEnum.PARTY_1,
                    receiver=CounterpartyRoleEnum.PARTY_2,
                )
            )
        )
        econ = EconomicTerms(payout=[payout])
        product = NonTransferableProduct(economicTerms=econ)
        trade_lot = TradeLot(priceQuantity=[PriceQuantity()])

        trade = Trade(
            tradeIdentifier=[trade_id],
            tradeDate=datetime.date(2026, 8, 16),
            party=[party1, party2],
            counterparty=[
                Counterparty(role=CounterpartyRoleEnum.PARTY_1, partyReference=party1),
                Counterparty(role=CounterpartyRoleEnum.PARTY_2, partyReference=party2),
            ],
            tradeLot=[trade_lot],
            product=product,
        )

        json_data = trade.model_dump_json(indent=2, exclude_none=True)
        self.assertIn("TRADE-123", json_data)

        reloaded = Trade.model_validate_json(json_data)
        self.assertEqual(reloaded.tradeDate, datetime.date(2026, 8, 16))

    def test_generic_rebuild_cdm_model(self):
        """Test the generic rebuild_cdm_model function on a custom subclass."""
        class ParentModel(BaseModel):
            name: str = Field(description="Parent name")
            value: int = Field(default=10)

        class ChildModel(ParentModel):
            name: None = Field(None)  # Degenerated to NoneType
            extra: str = "child"

        # Before sync: ChildModel requires None for name
        self.assertIs(ChildModel.model_fields["name"].annotation, type(None))

        # Rebuild using generic helper
        cdm_compat.rebuild_cdm_model(ChildModel)

        # After sync: ChildModel has name restored from ParentModel
        self.assertIs(ChildModel.model_fields["name"].annotation, str)
        instance = ChildModel(name="test_val")
        self.assertEqual(instance.name, "test_val")


if __name__ == "__main__":
    unittest.main()
