"""
Unit Tests for cdm_workspace.create_irs_trade module.

Tests Plain Vanilla IRS trade generation, parameter customization,
payout/schedule structures, and JSON serialization using pytest.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

import cdm_compat
from finos.cdm.base.datetime.BusinessDayConventionEnum import BusinessDayConventionEnum
from finos.cdm.base.datetime.PeriodExtendedEnum import PeriodExtendedEnum
from finos.cdm.base.datetime.daycount.DayCountFractionEnum import DayCountFractionEnum
from finos.cdm.base.staticdata.asset.rates.FloatingRateIndexEnum import FloatingRateIndexEnum
from finos.cdm.base.staticdata.party.CounterpartyRoleEnum import CounterpartyRoleEnum
from finos.cdm.base.staticdata.party.PartyRoleEnum import PartyRoleEnum
from finos.cdm.event.common.Trade import Trade
from finos.cdm.observable.asset.PriceTypeEnum import PriceTypeEnum

from cdm_workspace.create_irs_trade import (
    create_plain_irs_trade,
    generate_and_save_irs_json,
)


def _get_str_val(field_val: object) -> str:
    """Helper to extract string value whether raw string or StrWithMeta."""
    if hasattr(field_val, "value"):
        return str(field_val.value)
    return str(field_val)


def _get_notional_schedule(trade: Trade) -> object:
    """Helper to extract Notional quantity schedule compatible with both CDM 6.x and 7.x."""
    pq = trade.tradeLot[0].priceQuantity[0]
    return pq.quantity[0] if isinstance(pq.quantity, list) else pq.quantity


def test_create_plain_irs_trade_defaults():
    """
    【テストケース: デフォルト引数を用いた標準 Plain Vanilla IRS 取引生成の検証】

    目的:
        引数を指定せずに create_plain_irs_trade() を実行した際、標準的な JPY 固定 vs TONA OIS
        プレーン・バニラ金利スワップ（IRS）取引オブジェクト（Trade）が FINOS CDM 規格に沿って
        正しく生成されることを検証します。

    検証項目:
        1. 生成されたオブジェクトが Trade のインスタンスであること。
        2. 取引日（tradeDate）が 2026-08-16 であること。
        3. UTI（Unique Transaction Identifier）が 'IRS-JPY-TONA-20260820-001' として設定されていること。
        4. 取引当事者（Party）が2社（Bank A Tokyo / Bank B Tokyo）とその LEI が設定されていること。
        5. 当事者ロール（Buyer / Seller）および取引相手ロール（Party 1 / Party 2）が正しく割り当てられていること。
        6. 名義元本（Notional）が 10億円（1,000,000,000）で通貨が 'JPY' であること。
    """
    trade = create_plain_irs_trade()

    assert isinstance(trade, Trade)
    assert trade.tradeDate == datetime.date(2026, 8, 16)

    # Trade Identifier
    assert len(trade.tradeIdentifier) == 1
    raw_id = trade.tradeIdentifier[0].assignedIdentifier[0].identifier
    assert _get_str_val(raw_id) == "IRS-JPY-TONA-20260820-001"

    # Parties
    assert len(trade.party) == 2
    party1 = trade.party[0]
    party2 = trade.party[1]
    assert _get_str_val(party1.name) == "Bank A Tokyo"
    assert _get_str_val(party1.partyId[0].identifier) == "5493006MHB84DD0ZWV18"
    assert _get_str_val(party2.name) == "Bank B Tokyo"
    assert _get_str_val(party2.partyId[0].identifier) == "485400F9AM14CT701959"

    # Party Roles & Counterparties
    assert len(trade.partyRole) == 2
    assert trade.partyRole[0].role == PartyRoleEnum.BUYER
    assert trade.partyRole[1].role == PartyRoleEnum.SELLER

    assert len(trade.counterparty) == 2
    assert trade.counterparty[0].role == CounterpartyRoleEnum.PARTY_1
    assert trade.counterparty[1].role == CounterpartyRoleEnum.PARTY_2

    # Notional quantity
    notional = _get_notional_schedule(trade)
    assert notional.value == Decimal("1000000000")
    assert _get_str_val(notional.unit.currency) == "JPY"


def test_create_plain_irs_trade_custom_parameters():
    """
    【テストケース: カスタム引数を指定した IRS 取引生成の検証】

    目的:
        取引ID、約定日、開始日、終了日、名義元本、通貨（例: USD）、固定金利（例: 3.85%）、
        当事者名・LEI などの任意のカスタム値を指定して create_plain_irs_trade() を実行した際、
        すべてのパラメータが生成された Trade オブジェクトに正しく反映されることを検証します。

    検証項目:
        1. カスタム取引ID（'CUSTOM-IRS-USD-SOFR-001'）および約定日が反映されていること。
        2. カスタム取引先名（Alpha Global Bank / Beta Investment Corp）および各 LEI が反映されていること。
        3. 指定した通貨（'USD'）および名義元本（50,000,000）が反映されていること。
        4. 固定レグの固定金利（0.0385）が正しく設定されていること。
    """
    custom_trade = create_plain_irs_trade(
        trade_id_str="CUSTOM-IRS-USD-SOFR-001",
        trade_date=datetime.date(2026, 9, 1),
        start_date=datetime.date(2026, 9, 5),
        end_date=datetime.date(2036, 9, 5),
        notional_amount=Decimal("50000000"),
        currency="USD",
        fixed_rate_val=Decimal("0.0385"),
        party1_name="Alpha Global Bank",
        party1_lei="1111006MHB84DD0ZWV11",
        party2_name="Beta Investment Corp",
        party2_lei="222200F9AM14CT701922",
    )

    assert custom_trade.tradeDate == datetime.date(2026, 9, 1)

    raw_id = custom_trade.tradeIdentifier[0].assignedIdentifier[0].identifier
    assert _get_str_val(raw_id) == "CUSTOM-IRS-USD-SOFR-001"

    # Custom party checks
    assert _get_str_val(custom_trade.party[0].name) == "Alpha Global Bank"
    assert _get_str_val(custom_trade.party[0].partyId[0].identifier) == "1111006MHB84DD0ZWV11"
    assert _get_str_val(custom_trade.party[1].name) == "Beta Investment Corp"
    assert _get_str_val(custom_trade.party[1].partyId[0].identifier) == "222200F9AM14CT701922"

    # Custom Notional and Currency
    notional = _get_notional_schedule(custom_trade)
    assert notional.value == Decimal("50000000")
    assert _get_str_val(notional.unit.currency) == "USD"

    # Custom Fixed Rate
    fixed_payout = custom_trade.product.economicTerms.payout[0].InterestRatePayout
    assert fixed_payout.rateSpecification.FixedRateSpecification.rateSchedule.price.value == Decimal("0.0385")


def test_irs_payout_and_schedule_structure():
    """
    【テストケース: 固定・変動レグの Payout およびスケジュール構造の検証】

    目的:
        生成された IRS 取引の経済条件（EconomicTerms）内部に、固定レグ（Fixed Leg）および
        変動レグ（Floating Leg: JPY TONA OIS）が FINOS CDM の標準構造に準拠して
        正しく定義されていることを詳細に検証します。

    検証項目:
        1. EconomicTerms 内に 2 つの Payout（固定レグと変動レグ）が存在すること。
        2. 固定レグ:
           - 支払元が Party 1、受取先が Party 2 であること。
           - DayCountFraction が ACT/365.FIXED であること。
           - 計算期間頻度が 12ヶ月（年1回）、ロールコンベンションおよび営業日補正（Modified Following）が設定されていること。
           - 固定金利（0.0075）が RateSchedule 内に定義されていること。
        3. 変動レグ:
           - 支払元が Party 2、受取先が Party 1 であること。
           - 参照インデックスが JPY_TONA_OIS_COMPOUND であること。
           - リセット頻度（Reset Frequency）が 12ヶ月（年1回）に設定されていること。
    """
    trade = create_plain_irs_trade()
    econ = trade.product.economicTerms

    assert len(econ.payout) == 2

    # --- Fixed Leg ---
    fixed_payout = econ.payout[0].InterestRatePayout
    assert fixed_payout.payerReceiver.payer == CounterpartyRoleEnum.PARTY_1
    assert fixed_payout.payerReceiver.receiver == CounterpartyRoleEnum.PARTY_2
    assert fixed_payout.dayCountFraction == DayCountFractionEnum.ACT_365_FIXED

    # Calculation Period Dates
    calc_dates = fixed_payout.calculationPeriodDates
    freq = calc_dates.calculationPeriodFrequency
    assert freq.periodMultiplier == 12
    assert freq.period == PeriodExtendedEnum.M
    assert calc_dates.calculationPeriodDatesAdjustments.businessDayConvention == BusinessDayConventionEnum.MODFOLLOWING

    # Fixed Rate Specification
    fixed_spec = fixed_payout.rateSpecification.FixedRateSpecification
    assert fixed_spec.rateSchedule.price.value == Decimal("0.0075")
    assert fixed_spec.rateSchedule.price.priceType == PriceTypeEnum.INTEREST_RATE

    # --- Floating Leg ---
    floating_payout = econ.payout[1].InterestRatePayout
    assert floating_payout.payerReceiver.payer == CounterpartyRoleEnum.PARTY_2
    assert floating_payout.payerReceiver.receiver == CounterpartyRoleEnum.PARTY_1
    assert floating_payout.dayCountFraction == DayCountFractionEnum.ACT_365_FIXED

    # Floating Rate Specification
    floating_spec = floating_payout.rateSpecification.FloatingRateSpecification
    assert floating_spec.rateOption.FloatingRateIndex.floatingRateIndex == FloatingRateIndexEnum.JPY_TONA_OIS_COMPOUND

    # Reset Dates
    assert floating_payout.resetDates.resetFrequency.periodMultiplier == 12
    assert floating_payout.resetDates.resetFrequency.period == PeriodExtendedEnum.M


def test_generate_and_save_irs_json(tmp_path: Path):
    """
    【テストケース: IRS 取引の JSON ファイル出力とバリデーション実行の検証】

    目的:
        generate_and_save_irs_json() を呼び出した際、指定したファイルパスに
        フォーマット済みの CDM JSON ファイルが書き出され、かつその JSON を再読み込みした
        検証（Round-trip validation）が成功することを確認します。

    検証項目:
        1. pytest の tmp_path フィクスチャを利用して一時ファイルに出力できること。
        2. 出力ファイルが実際に作成され、ファイルサイズが 0 より大きいこと。
        3. 保存された JSON を Trade.model_validate_json() で正常にデシリアライズできること。
        4. 復元された Trade インスタンスの取引IDおよび Payout 数が元の設定と一致すること。
    """
    output_file = tmp_path / "test_irs_trade.json"

    saved_path = generate_and_save_irs_json(output_path=output_file)

    assert saved_path.exists()
    assert saved_path.stat().st_size > 0

    # Validate file content is valid JSON matching CDM Trade schema
    json_content = saved_path.read_text(encoding="utf-8")
    reloaded_trade = Trade.model_validate_json(json_content)

    assert isinstance(reloaded_trade, Trade)
    assert reloaded_trade.tradeDate == datetime.date(2026, 8, 16)
    raw_id = reloaded_trade.tradeIdentifier[0].assignedIdentifier[0].identifier
    assert _get_str_val(raw_id) == "IRS-JPY-TONA-20260820-001"
    assert len(reloaded_trade.product.economicTerms.payout) == 2


def test_json_roundtrip_fidelity():
    """
    【テストケース: JSON シリアライズ / デシリアライズのデータ整合性検証】

    目的:
        Trade インスタンスを model_dump_json() でシリアライズし、直後に
        Trade.model_validate_json() で復元した際、取引日、当事者数、取引相手数、
        Payout 数などのコア属性が完全に損なわれずに維持されることを検証します。

    検証項目:
        1. 元の Trade と復元後の Trade で tradeDate が完全一致すること。
        2. party リストおよび counterparty リストの長さが一致すること。
        3. economicTerms.payout の要素数が一致すること。
    """
    original_trade = create_plain_irs_trade()
    json_str = original_trade.model_dump_json(exclude_none=True)

    reloaded_trade = Trade.model_validate_json(json_str)

    assert reloaded_trade.tradeDate == original_trade.tradeDate
    assert len(reloaded_trade.party) == len(original_trade.party)
    assert len(reloaded_trade.counterparty) == len(original_trade.counterparty)
    assert len(reloaded_trade.product.economicTerms.payout) == len(original_trade.product.economicTerms.payout)
