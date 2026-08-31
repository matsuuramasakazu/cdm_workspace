"""
Unit Tests for FINOS CDM Trade Product Qualification Service (qualify_trade.py)
"""

from __future__ import annotations

from pathlib import Path
import pytest

import cdm_compat
from finos.cdm.event.common.TradeState import TradeState
from finos.cdm.event.common.Trade import Trade
from cdm_workspace.deserialize_trade_state import (
    deserialize_trade_state_from_json,
    get_sample_irs_json_path,
)
from cdm_workspace.create_irs_trade import create_plain_irs_trade
from cdm_workspace.qualify_trade import (
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


@pytest.fixture
def sample_vanilla_json_path() -> Path:
    """Path to appropriate version-specific ird-ex01-vanilla-swap sample JSON."""
    return get_sample_irs_json_path()


def test_qualify_vanilla_swap_from_file(sample_vanilla_json_path: Path):
    """
    【テストケース: ird-ex01-vanilla-swap.json の商品判定】

    検証項目:
        1. ird-ex01-vanilla-swap.json をインプットとして判定を実行する。
        2. qualifier が "InterestRate_IRSwap_FixedFloat" であること。
        3. asset_class が AssetClass.INTEREST_RATE ("InterestRate") であること。
        4. base_product が BaseProduct.IR_SWAP ("IRSwap") であること。
        5. sub_product が SubProduct.FIXED_FLOAT ("FixedFloat") であること。
        6. is_vanilla_fixed_float が True であること。
        7. display_name_ja が "バニラ固定/変動金利スワップ" であること。
    """
    assert sample_vanilla_json_path.exists(), f"Sample file not found: {sample_vanilla_json_path}"

    result = qualify_from_json(sample_vanilla_json_path)

    assert isinstance(result, ProductQualificationResult)
    assert result.qualifier == ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FLOAT.value
    assert result.asset_class == AssetClass.INTEREST_RATE
    assert result.base_product == BaseProduct.IR_SWAP
    assert result.sub_product == SubProduct.FIXED_FLOAT
    assert result.is_vanilla_fixed_float is True
    assert "バニラ固定/変動金利スワップ" in result.display_name_ja
    assert "Vanilla Fixed/Float Interest Rate Swap" in result.display_name_en
    assert result.details.get("is_ois") is False


def test_qualify_trade_state_object(sample_vanilla_json_path: Path):
    """
    【テストケース: TradeState オブジェクト直接入力による判定】
    """
    trade_state = deserialize_trade_state_from_json(sample_vanilla_json_path)
    result = qualify_trade_state(trade_state)

    assert result.qualifier == "InterestRate_IRSwap_FixedFloat"
    assert result.is_vanilla_fixed_float is True


def test_qualify_created_irs_trade_ois():
    """
    【テストケース: create_plain_irs_trade (JPY TONA OIS) の判定】

    検証項目:
        1. create_plain_irs_trade() で生成された Trade オブジェクトを判定。
        2. asset_class が InterestRate, base_product が IRSwap, sub_product が FixedFloat であること。
        3. OIS インデックス (TONA) であるため、qualifier が InterestRate_IRSwap_FixedFloat_OIS と判定されること。
        4. details["is_ois"] が True であること。
    """
    trade = create_plain_irs_trade()
    result = qualify_trade(trade)

    assert isinstance(result, ProductQualificationResult)
    assert result.asset_class == AssetClass.INTEREST_RATE
    assert result.base_product == BaseProduct.IR_SWAP
    assert result.sub_product == SubProduct.FIXED_FLOAT
    assert result.qualifier == ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FLOAT_OIS.value
    assert result.details.get("is_ois") is True


def test_is_vanilla_fixed_float_swap_helper(sample_vanilla_json_path: Path):
    """
    【テストケース: is_vanilla_fixed_float_swap 簡易ヘルパー関数の検証】
    """
    # 1. Via file path
    assert is_vanilla_fixed_float_swap(sample_vanilla_json_path) is True

    # 2. Via JSON string
    raw_json = sample_vanilla_json_path.read_text(encoding="utf-8")
    assert is_vanilla_fixed_float_swap(raw_json) is True

    # 3. Via TradeState
    ts = deserialize_trade_state_from_json(sample_vanilla_json_path)
    assert is_vanilla_fixed_float_swap(ts) is True

    # 4. Via Trade
    assert is_vanilla_fixed_float_swap(ts.trade) is True


def test_print_qualification_summary(sample_vanilla_json_path: Path, capsys):
    """
    【テストケース: サマリー出力機能の検証】
    """
    result = qualify_from_json(sample_vanilla_json_path)
    print_qualification_summary(result)

    captured = capsys.readouterr()
    assert "FINOS CDM Product Qualification Summary" in captured.out
    assert "InterestRate_IRSwap_FixedFloat" in captured.out
    assert "バニラ固定/変動金利スワップ" in captured.out
