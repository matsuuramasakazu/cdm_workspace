"""
FINOS CDM Plain Vanilla Interest Rate Swap (IRS) Generator

This script demonstrates how to construct a standard Plain Vanilla Interest Rate
Swap (JPY Fixed vs. TONA OIS) using FINOS CDM (Common Domain Model 6.22.0+) and
export it to a fully valid CDM JSON file.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

# --- Runtime Compatibility ---
# Importing cdm_compat automatically configures Rune/Pydantic v2 runtime compatibility
import cdm_compat

# --- FINOS CDM Imports ---
from finos.cdm.base.datetime.AdjustableDate import AdjustableDate
from finos.cdm.base.datetime.AdjustableOrRelativeDate import AdjustableOrRelativeDate
from finos.cdm.base.datetime.BusinessCenters import BusinessCenters
from finos.cdm.base.datetime.BusinessDayAdjustments import BusinessDayAdjustments
from finos.cdm.base.datetime.BusinessDayConventionEnum import BusinessDayConventionEnum
from finos.cdm.base.datetime.CalculationPeriodFrequency import CalculationPeriodFrequency
from finos.cdm.base.datetime.Frequency import Frequency
from finos.cdm.base.datetime.PeriodExtendedEnum import PeriodExtendedEnum
from finos.cdm.base.datetime.RollConventionEnum import RollConventionEnum
from finos.cdm.base.datetime.daycount.DayCountFractionEnum import DayCountFractionEnum
from finos.cdm.base.math.NonNegativeQuantitySchedule import NonNegativeQuantitySchedule
from finos.cdm.base.math.UnitType import UnitType
from finos.cdm.base.staticdata.asset.common.AssetIdTypeEnum import AssetIdTypeEnum
from finos.cdm.base.staticdata.asset.common.AssetIdentifier import AssetIdentifier
from finos.cdm.base.staticdata.asset.common.AssetTypeEnum import AssetTypeEnum
from finos.cdm.base.staticdata.asset.rates.FloatingRateIndexEnum import FloatingRateIndexEnum
from finos.cdm.base.staticdata.identifier.AssignedIdentifier import AssignedIdentifier
from finos.cdm.base.staticdata.identifier.TradeIdentifierTypeEnum import TradeIdentifierTypeEnum
from finos.cdm.base.staticdata.party.Counterparty import Counterparty
from finos.cdm.base.staticdata.party.CounterpartyRoleEnum import CounterpartyRoleEnum
from finos.cdm.base.staticdata.party.Party import Party
from finos.cdm.base.staticdata.party.PartyIdentifier import PartyIdentifier
from finos.cdm.base.staticdata.party.PartyRole import PartyRole
from finos.cdm.base.staticdata.party.PartyRoleEnum import PartyRoleEnum
from finos.cdm.base.staticdata.party.PayerReceiver import PayerReceiver
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
from finos.cdm.observable.asset.FloatingRateIndex import FloatingRateIndex
from finos.cdm.observable.asset.InterestRateIndex import InterestRateIndex
from finos.cdm.observable.asset.PriceExpressionEnum import PriceExpressionEnum
from finos.cdm.observable.asset.PriceQuantity import PriceQuantity
from finos.cdm.observable.asset.PriceSchedule import PriceSchedule
from finos.cdm.observable.asset.PriceTypeEnum import PriceTypeEnum
from finos.cdm.product.asset.FixedRateSpecification import FixedRateSpecification
from finos.cdm.product.asset.FloatingRateSpecification import FloatingRateSpecification
from finos.cdm.product.asset.InterestRatePayout import InterestRatePayout
from finos.cdm.product.asset.RateSpecification import RateSpecification
from finos.cdm.product.common.schedule.CalculationPeriodDates import CalculationPeriodDates
from finos.cdm.product.common.schedule.PayRelativeToEnum import PayRelativeToEnum
from finos.cdm.product.common.schedule.PaymentDates import PaymentDates
from finos.cdm.product.common.schedule.RateSchedule import RateSchedule
from finos.cdm.product.common.schedule.ResetDates import ResetDates
from finos.cdm.product.common.schedule.ResetFrequency import ResetFrequency
from finos.cdm.product.common.schedule.ResetRelativeToEnum import ResetRelativeToEnum
from finos.cdm.product.common.settlement.ResolvablePriceQuantity import ResolvablePriceQuantity
from finos.cdm.product.template.EconomicTerms import EconomicTerms
from finos.cdm.product.template.NonTransferableProduct import NonTransferableProduct
from finos.cdm.product.template.Payout import Payout
from finos.cdm.product.template.TradeLot import TradeLot


def create_plain_irs_trade(
    trade_id_str: str = "IRS-JPY-TONA-20260820-001",
    trade_date: datetime.date = datetime.date(2026, 8, 16),
    start_date: datetime.date = datetime.date(2026, 8, 20),
    end_date: datetime.date = datetime.date(2031, 8, 20),
    notional_amount: Decimal = Decimal("1000000000"),
    currency: str = "JPY",
    fixed_rate_val: Decimal = Decimal("0.0075"),
    party1_name: str = "Bank A Tokyo",
    party1_lei: str = "5493006MHB84DD0ZWV18",
    party2_name: str = "Bank B Tokyo",
    party2_lei: str = "485400F9AM14CT701959",
) -> Trade:
    """
    Constructs a Plain Vanilla Interest Rate Swap Trade object in FINOS CDM.

    Parameters:
        trade_id_str: Trade UTI string.
        trade_date: Trade execution date.
        start_date: Effective date of the swap.
        end_date: Termination (maturity) date of the swap.
        notional_amount: Notional principal amount.
        currency: Currency code (e.g. 'JPY').
        fixed_rate_val: Fixed rate value (e.g. 0.0075 for 0.75%).
        party1_name: Name of Party 1 (Fixed rate payer).
        party1_lei: LEI of Party 1.
        party2_name: Name of Party 2 (Floating rate payer).
        party2_lei: LEI of Party 2.

    Returns:
        A fully constructed finos.cdm.event.common.Trade instance.
    """
    # 1. Define Parties
    party1 = Party(
        partyId=[PartyIdentifier(identifier=party1_lei)],
        name=party1_name,
    )
    party2 = Party(
        partyId=[PartyIdentifier(identifier=party2_lei)],
        name=party2_name,
    )

    # 2. Counterparties
    counterparty1 = Counterparty(
        role=CounterpartyRoleEnum.PARTY_1,
        partyReference=party1,
    )
    counterparty2 = Counterparty(
        role=CounterpartyRoleEnum.PARTY_2,
        partyReference=party2,
    )

    # 3. Trade Identifier (UTI)
    trade_id = TradeIdentifier(
        assignedIdentifier=[
            AssignedIdentifier(identifier=trade_id_str, version=1)
        ],
        identifierType=TradeIdentifierTypeEnum.UNIQUE_TRANSACTION_IDENTIFIER,
    )

    # 4. Dates and Business Centers (Tokyo: JPTO, Modified Following)
    biz_centers = BusinessCenters(businessCenter=["JPTO"])
    biz_adjustments = BusinessDayAdjustments(
        businessDayConvention=BusinessDayConventionEnum.MODFOLLOWING,
        businessCenters=biz_centers,
    )

    effective_date = AdjustableOrRelativeDate(
        adjustableDate=AdjustableDate(
            unadjustedDate=start_date,
            dateAdjustments=biz_adjustments,
        )
    )
    termination_date = AdjustableOrRelativeDate(
        adjustableDate=AdjustableDate(
            unadjustedDate=end_date,
            dateAdjustments=biz_adjustments,
        )
    )

    # 5. Calculation Period Dates (Annual / 12M)
    calc_period_dates = CalculationPeriodDates(
        effectiveDate=effective_date,
        terminationDate=termination_date,
        calculationPeriodFrequency=CalculationPeriodFrequency(
            periodMultiplier=12,
            period=PeriodExtendedEnum.M,
            rollConvention=RollConventionEnum._20,
        ),
        calculationPeriodDatesAdjustments=biz_adjustments,
    )

    # 6. Notional Quantity
    notional_quantity = NonNegativeQuantitySchedule(
        value=notional_amount,
        unit=UnitType(currency=currency),
    )
    price_quantity = ResolvablePriceQuantity(
        quantitySchedule=notional_quantity
    )

    # 7. Fixed Leg Payout (Party 1 pays Fixed Rate)
    fixed_rate = PriceSchedule(
        value=fixed_rate_val,
        priceType=PriceTypeEnum.INTEREST_RATE,
        priceExpression=PriceExpressionEnum.PERCENTAGE_OF_NOTIONAL,
    )
    fixed_rate_spec = FixedRateSpecification(
        rateSchedule=RateSchedule(price=fixed_rate)
    )

    fixed_payout = InterestRatePayout(
        payerReceiver=PayerReceiver(
            payer=CounterpartyRoleEnum.PARTY_1,
            receiver=CounterpartyRoleEnum.PARTY_2,
        ),
        priceQuantity=price_quantity,
        rateSpecification=RateSpecification(FixedRateSpecification=fixed_rate_spec),
        dayCountFraction=DayCountFractionEnum.ACT_365_FIXED,
        calculationPeriodDates=calc_period_dates,
        paymentDates=PaymentDates(
            paymentFrequency=Frequency(
                periodMultiplier=12,
                period=PeriodExtendedEnum.M,
            ),
            payRelativeTo=PayRelativeToEnum.CALCULATION_PERIOD_END_DATE,
            paymentDatesAdjustments=biz_adjustments,
        ),
    )

    # 8. Floating Leg Payout (Party 2 pays JPY TONA OIS)
    floating_index = FloatingRateIndex(
        floatingRateIndex=FloatingRateIndexEnum.JPY_TONA_OIS_COMPOUND,
        assetType=AssetTypeEnum.OTHER,
        identifier=[
            AssetIdentifier(
                identifier="JPY-TONA-OIS-COMPOUND",
                identifierType=AssetIdTypeEnum.NAME,
            )
        ],
    )
    floating_rate_spec = FloatingRateSpecification(
        rateOption=InterestRateIndex(FloatingRateIndex=floating_index)
    )

    floating_payout = InterestRatePayout(
        payerReceiver=PayerReceiver(
            payer=CounterpartyRoleEnum.PARTY_2,
            receiver=CounterpartyRoleEnum.PARTY_1,
        ),
        priceQuantity=price_quantity,
        rateSpecification=RateSpecification(FloatingRateSpecification=floating_rate_spec),
        dayCountFraction=DayCountFractionEnum.ACT_365_FIXED,
        calculationPeriodDates=calc_period_dates,
        paymentDates=PaymentDates(
            paymentFrequency=Frequency(
                periodMultiplier=12,
                period=PeriodExtendedEnum.M,
            ),
            payRelativeTo=PayRelativeToEnum.CALCULATION_PERIOD_END_DATE,
            paymentDatesAdjustments=biz_adjustments,
        ),
        resetDates=ResetDates(
            resetRelativeTo=ResetRelativeToEnum.CALCULATION_PERIOD_END_DATE,
            resetFrequency=ResetFrequency(
                periodMultiplier=12,
                period=PeriodExtendedEnum.M,
            ),
            resetDatesAdjustments=biz_adjustments,
        ),
    )

    # 9. Product & Economic Terms
    economic_terms = EconomicTerms(
        effectiveDate=effective_date,
        terminationDate=termination_date,
        payout=[
            Payout(InterestRatePayout=fixed_payout),
            Payout(InterestRatePayout=floating_payout),
        ],
    )

    non_transferable_product = NonTransferableProduct(
        economicTerms=economic_terms
    )

    # 10. Complete Trade Object
    trade = Trade(
        tradeIdentifier=[trade_id],
        tradeDate=trade_date,
        party=[party1, party2],
        partyRole=[
            PartyRole(partyReference=party1, role=PartyRoleEnum.BUYER),
            PartyRole(partyReference=party2, role=PartyRoleEnum.SELLER),
        ],
        counterparty=[counterparty1, counterparty2],
        tradeLot=[TradeLot(priceQuantity=[PriceQuantity(quantity=[notional_quantity])])],
        product=non_transferable_product,
    )

    return trade


def generate_and_save_irs_json(output_path: str | Path = "irs_trade.json") -> Path:
    """
    Generates the IRS trade, dumps it as formatted CDM JSON, saves to file,
    and performs round-trip validation.
    """
    output_file = Path(output_path)
    print("=" * 60)
    print("Constructing FINOS CDM Plain Vanilla IRS Trade...")
    trade = create_plain_irs_trade()

    print("Serializing Trade model to JSON format...")
    json_data = trade.model_dump_json(indent=2, exclude_none=True)

    print(f"Saving JSON to: {output_file.resolve()}")
    output_file.write_text(json_data, encoding="utf-8")
    print(f"File saved successfully ({len(json_data):,} characters).")

    print("\n--- Validation Check ---")
    print("Reloading and parsing JSON using Trade.model_validate_json()...")
    reloaded_trade = Trade.model_validate_json(json_data)
    trade_id = reloaded_trade.tradeIdentifier[0].assignedIdentifier[0].identifier
    id_val = getattr(trade_id, "value", trade_id)
    print(f"Validation successful! Verified Trade ID: {id_val}")
    print(f"Trade Date: {reloaded_trade.tradeDate}")
    print("=" * 60)

    return output_file


if __name__ == "__main__":
    generate_and_save_irs_json("irs_trade.json")
