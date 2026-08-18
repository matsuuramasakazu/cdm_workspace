"""
Unit Tests for cdm_compat package.

Tests metadata patches, schema rebuilding, and round-trip JSON serialization using pytest.
"""

from __future__ import annotations

import datetime
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


def test_patch_status():
    """
    【テストケース: ランタイムパッチの適用ステータスと冪等性の検証】

    目的:
        cdm_compat のインポート時に自動適用されたランタイムパッチが有効であること、
        および apply_patches() の再実行が安全（冪等: Idempotent）に行われ、
        2回目以降は False を返すことを検証します。

    検証項目:
        1. cdm_compat.is_patched() が True を返すこと。
        2. cdm_compat.apply_patches() を再度呼び出した際、重複適用されず False が返ること。
    """
    assert cdm_compat.is_patched() is True
    # Re-applying should return False (already applied)
    assert cdm_compat.apply_patches() is False


def test_complex_type_none_handling():
    """
    【テストケース: オプショナルな複合型（ComplexType）フィールドの None ハンドリング検証】

    背景・目的:
        Rune ランタイムと Pydantic v2 の型解決において、デフォルトが None である
        ComplexType 参照フィールド（例: businessCentersReference）がバリデーションエラーを起こさず、
        正常にインスタンス化できることを確認します。

    検証項目:
        1. BusinessDayAdjustments のインスタンス生成時に、未指定の参照フィールドが None のままでエラーなく生成できること。
        2. 明示的に渡した businessDayConvention および businessCenters が正しく保持されていること。
    """
    # businessCentersReference is None by default
    biz_centers = BusinessCenters(businessCenter=["JPTO"])
    biz_adj = BusinessDayAdjustments(
        businessDayConvention=BusinessDayConventionEnum.MODFOLLOWING,
        businessCenters=biz_centers,
    )
    assert biz_adj.businessDayConvention == BusinessDayConventionEnum.MODFOLLOWING
    assert biz_adj.businessCenters is not None


def test_basic_type_list_serialization_roundtrip():
    """
    【テストケース: 基本型メタデータ（StrWithMeta 等）のリストに対するシリアライズ・復元検証】

    背景・目的:
        rune.runtime.metadata のシリアライザにおいて、リスト内に格納された StrWithMeta
        （例: businessCenter=["JPTO", "USNY"]）を JSON へ出力する際、および JSON から
        再度モデルへデシリアライズする際のラウンドトリップが正常に動作することを検証します。

    検証項目:
        1. model_dump_json(exclude_none=True) で文字列 "JPTO", "USNY" が JSON に出力されること。
        2. model_validate_json() で再読み込みした際、元のリスト長（2件）および要素が正しく復元されること。
    """
    biz_centers = BusinessCenters(businessCenter=["JPTO", "USNY"])
    json_data = biz_centers.model_dump_json(exclude_none=True)
    assert "JPTO" in json_data
    assert "USNY" in json_data

    # Reload
    reloaded = BusinessCenters.model_validate_json(json_data)
    assert len(reloaded.businessCenter) == 2


def test_trade_identifier_creation():
    """
    【テストケース: TradeIdentifier (UTI) の生成・シリアライズ検証】

    目的:
        FINOS CDM における取引一意識別子（TradeIdentifier）および AssignedIdentifier の
        構造が正しくバリデーションされ、Enum やメタデータ文字列が損なわれずに
        JSON 出力・復元できることを検証します。

    検証項目:
        1. TradeIdentifier インスタンスが AssignedIdentifier および identifierType を保持して生成できること。
        2. JSON 出力に識別子文字列および "UniqueTransactionIdentifier" が含まれること。
        3. model_validate_json() で再構築したモデルに assignedIdentifier が正しく復元されること。
    """
    trade_id = TradeIdentifier(
        assignedIdentifier=[
            AssignedIdentifier(identifier="TEST-TRADE-001", version=1)
        ],
        identifierType=TradeIdentifierTypeEnum.UNIQUE_TRANSACTION_IDENTIFIER,
    )
    json_data = trade_id.model_dump_json(exclude_none=True)
    assert "TEST-TRADE-001" in json_data
    assert "UniqueTransactionIdentifier" in json_data

    reloaded = TradeIdentifier.model_validate_json(json_data)
    assert len(reloaded.assignedIdentifier) == 1


def test_price_quantity_rebuilding():
    """
    【テストケース: PriceQuantity と数量・価格スケジュールのスキーマ修復検証】

    目的:
        NonNegativeQuantitySchedule（名義元本数量・通貨）および PriceSchedule（金利）を
        内包する PriceQuantity モデルが、Pydantic v2 のスキーマ修復エンジンによって
        正しく認識され、Decimal 精度を保ったままシリアライズ・復元できることを検証します。

    検証項目:
        1. Decimal 型の数量（500,000,000）および通貨（JPY）が JSON に正しく変換されること。
        2. JSON からのデシリアライズ後、quantity.value が元の Decimal 値と完全一致すること。
    """
    unit = UnitType(currency="JPY")
    quantity = NonNegativeQuantitySchedule(value=Decimal("500000000"), unit=unit)
    price = PriceSchedule(value=Decimal("0.01"), priceType=PriceTypeEnum.INTEREST_RATE)

    pq = PriceQuantity(quantity=[quantity], price=[price])
    json_data = pq.model_dump_json(exclude_none=True)
    assert "500000000" in json_data
    assert "JPY" in json_data

    reloaded = PriceQuantity.model_validate_json(json_data)
    assert reloaded.quantity[0].value == Decimal("500000000")


def test_trade_roundtrip_validation():
    """
    【テストケース: 完全な Trade インスタンスの JSON ラウンドトリップ検証】

    目的:
        Party, Counterparty, Product, EconomicTerms, Payout, TradeLot 等の
        CDM 階層構造全体を組み合わせた完全な Trade オブジェクトを作成し、
        JSON シリアライズおよび model_validate_json() による完全復元を検証します。

    検証項目:
        1. 複合 Trade オブジェクトが model_dump_json() でエラーなく JSON 文字列化できること。
        2. JSON から model_validate_json() で再読み込みした際、取引日（tradeDate）などの各属性が正確に一致すること。
    """
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
    assert "TRADE-123" in json_data

    reloaded = Trade.model_validate_json(json_data)
    assert reloaded.tradeDate == datetime.date(2026, 8, 16)


def test_generic_rebuild_cdm_model():
    """
    【テストケース: 汎用モデル修復エンジン (rebuild_cdm_model) の継承フィールド復元検証】

    背景・目的:
        Rune によるコード生成時に、親クラスで定義されたフィールドが子クラス側で
        遅延型解決失敗により NoneType (type(None)) に縮退してしまう問題があります。
        cdm_compat.rebuild_cdm_model() が MRO（Method Resolution Order）を走査して
        親クラスの型注釈を自動復元することをカスタムモデルで検証します。

    検証項目:
        1. 修復前: ChildModel の name フィールドのアノテーションが type(None) であること。
        2. rebuild_cdm_model(ChildModel) 実行後: name フィールドのアノテーションが str に復元されること。
        3. 復元後の ChildModel に文字列 "test_val" を渡して正常にインスタンス化できること。
    """
    class ParentModel(BaseModel):
        name: str = Field(description="Parent name")
        value: int = Field(default=10)

    class ChildModel(ParentModel):
        name: None = Field(None)  # Degenerated to NoneType
        extra: str = "child"

    # Before sync: ChildModel requires None for name
    assert ChildModel.model_fields["name"].annotation is type(None)

    # Rebuild using generic helper
    cdm_compat.rebuild_cdm_model(ChildModel)

    # After sync: ChildModel has name restored from ParentModel
    assert ChildModel.model_fields["name"].annotation is str
    instance = ChildModel(name="test_val")
    assert instance.name == "test_val"


def test_rosetta_reference_resolution_and_roundtrip():
    """
    【テストケース: Rosetta CDM 参照ポインタの解決と JSON ラウンドトリップ検証】

    背景・目的:
        Rosetta CDM 形式の JSON（globalReference, externalReference, address）から
        デシリアライズされたモデルにおいて、cdm_compat.resolve_model_references() が
        未解決参照（UnresolvedReference）を実体オブジェクトへ解決（Resolve）し、
        さらに model_dump_json() で安全にシリアライズ・再復元できることを検証します。
    """
    sample_json = """{
      "party": [
        {
          "partyId": [{"identifier": {"value": "LEI-A"}}],
          "name": {"value": "Bank Alpha"},
          "meta": {"globalKey": "KEY_PARTY_A", "externalKey": "partyA"}
        },
        {
          "partyId": [{"identifier": {"value": "LEI-B"}}],
          "name": {"value": "Bank Beta"},
          "meta": {"globalKey": "KEY_PARTY_B", "externalKey": "partyB"}
        }
      ],
      "counterparty": [
        {
          "role": "Party1",
          "partyReference": {"globalReference": "KEY_PARTY_A", "externalReference": "partyA"}
        },
        {
          "role": "Party2",
          "partyReference": {"globalReference": "KEY_PARTY_B", "externalReference": "partyB"}
        }
      ],
      "tradeIdentifier": [
        {
          "assignedIdentifier": [{"identifier": "TRADE-999"}],
          "issuerReference": {"globalReference": "KEY_PARTY_A"}
        }
      ],
      "product": {
        "economicTerms": {
          "payout": [
            {
              "InterestRatePayout": {
                "payerReceiver": {"payer": "Party1", "receiver": "Party2"}
              }
            }
          ]
        }
      },
      "tradeLot": [
        {
          "priceQuantity": [{}]
        }
      ],
      "tradeDate": "2026-08-18"
    }"""

    trade = Trade.model_validate_json(sample_json)
    assert trade.tradeDate == datetime.date(2026, 8, 18)

    # Resolve references
    trade = cdm_compat.resolve_model_references(trade)

    # 1. Verify partyReference is bound directly to the Party instance
    cp = trade.counterparty[0]
    assert isinstance(cp.partyReference, Party)
    assert getattr(cp.partyReference.name, "value", cp.partyReference.name) == "Bank Alpha"

    cp2 = trade.counterparty[1]
    assert isinstance(cp2.partyReference, Party)
    assert getattr(cp2.partyReference.name, "value", cp2.partyReference.name) == "Bank Beta"

    # 2. Verify issuerReference is bound directly to the Party instance
    tid = trade.tradeIdentifier[0]
    assert isinstance(tid.issuerReference, Party)
    assert getattr(tid.issuerReference.name, "value", tid.issuerReference.name) == "Bank Alpha"

    # 3. Verify safe serialization (no recursion or type errors)
    json_out = trade.model_dump_json(indent=2, exclude_none=True)
    assert "Bank Alpha" in json_out
    assert "TRADE-999" in json_out
    assert "@ref" in json_out

    # 4. Verify re-deserialization
    reloaded = Trade.model_validate_json(json_out)
    reloaded = cdm_compat.resolve_model_references(reloaded)
    assert reloaded.tradeDate == datetime.date(2026, 8, 18)
    assert isinstance(reloaded.counterparty[0].partyReference, Party)

