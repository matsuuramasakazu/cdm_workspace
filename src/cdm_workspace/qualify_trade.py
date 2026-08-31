"""
FINOS CDM Trade Product Qualification Service

This module provides financial product qualification and classification services
for FINOS CDM TradeState and Trade models, utilizing native FINOS CDM qualification
functions (`finos.cdm.product.qualification.functions.*`).

It inspects economic terms, payout legs, and rate specifications to classify trades
into standardized ISDA Taxonomy / CDM Product Qualifiers (e.g. Vanilla Fixed/Float IRS,
OIS Swap, Basis Swap, Cross-Currency Swap, FRA, Cap/Floor, Swaption).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Add src/ to sys.path if running as a standalone script
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# --- Step 1: Initialize CDM Compatibility Layer ---
# Mandatory import to apply Rune runtime patches and Pydantic v2 type fixes
import cdm_compat

# --- Step 2: Import FINOS CDM Data Classes ---
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeState import TradeState
from finos.cdm.product.asset.InterestRatePayout import InterestRatePayout
from finos.cdm.product.template.EconomicTerms import EconomicTerms
from finos.cdm.product.template.Payout import Payout

# --- Step 3: Import FINOS CDM Native Qualification Functions ---
from finos.cdm.product.qualification.functions.Qualify_AssetClass_InterestRate import (
    Qualify_AssetClass_InterestRate,
)
from finos.cdm.product.qualification.functions.Qualify_BaseProduct_CrossCurrency import (
    Qualify_BaseProduct_CrossCurrency,
)
from finos.cdm.product.qualification.functions.Qualify_BaseProduct_Fra import (
    Qualify_BaseProduct_Fra,
)
from finos.cdm.product.qualification.functions.Qualify_BaseProduct_IRSwap import (
    Qualify_BaseProduct_IRSwap,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_CapFloor import (
    Qualify_InterestRate_CapFloor,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_CrossCurrency_Basis import (
    Qualify_InterestRate_CrossCurrency_Basis,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_CrossCurrency_FixedFloat import (
    Qualify_InterestRate_CrossCurrency_FixedFloat,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_Fra import (
    Qualify_InterestRate_Fra,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_IRSwap_Basis import (
    Qualify_InterestRate_IRSwap_Basis,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_IRSwap_Basis_OIS import (
    Qualify_InterestRate_IRSwap_Basis_OIS,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_IRSwap_FixedFixed import (
    Qualify_InterestRate_IRSwap_FixedFixed,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_IRSwap_FixedFloat import (
    Qualify_InterestRate_IRSwap_FixedFloat,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_IRSwap_FixedFloat_OIS import (
    Qualify_InterestRate_IRSwap_FixedFloat_OIS,
)
from finos.cdm.product.qualification.functions.Qualify_InterestRate_Option_Swaption import (
    Qualify_InterestRate_Option_Swaption,
)
from finos.cdm.product.qualification.functions.Qualify_SubProduct_Basis import (
    Qualify_SubProduct_Basis,
)
from finos.cdm.product.qualification.functions.Qualify_SubProduct_FixedFixed import (
    Qualify_SubProduct_FixedFixed,
)
from finos.cdm.product.qualification.functions.Qualify_SubProduct_FixedFloat import (
    Qualify_SubProduct_FixedFloat,
)
from finos.cdm.product.qualification.functions.Qualify_Transaction_OIS import (
    Qualify_Transaction_OIS,
)
from finos.cdm.product.qualification.functions.Qualify_Transaction_ZeroCoupon import (
    Qualify_Transaction_ZeroCoupon,
)


class AssetClass(str, Enum):
    """CDM / ISDA Asset Class taxonomy."""

    INTEREST_RATE = "InterestRate"
    CREDIT = "Credit"
    EQUITY = "Equity"
    FOREIGN_EXCHANGE = "ForeignExchange"
    COMMODITY = "Commodity"
    UNKNOWN = "Unknown"


class BaseProduct(str, Enum):
    """CDM / ISDA Base Product taxonomy."""

    IR_SWAP = "IRSwap"
    FRA = "Fra"
    CAP_FLOOR = "CapFloor"
    CROSS_CURRENCY = "CrossCurrency"
    SWAPTION = "Swaption"
    SPOT_FORWARD = "Spot_Forward"
    FX_SWAP = "Swap"
    UNKNOWN = "Unknown"


class SubProduct(str, Enum):
    """CDM / ISDA Sub Product taxonomy."""

    FIXED_FLOAT = "FixedFloat"
    FIXED_FIXED = "FixedFixed"
    BASIS = "Basis"
    INFLATION = "Inflation"
    UNKNOWN = "Unknown"


class ProductQualifierEnum(str, Enum):
    """Standard FINOS CDM Product Qualifiers."""

    INTEREST_RATE_IR_SWAP_FIXED_FLOAT = "InterestRate_IRSwap_FixedFloat"
    INTEREST_RATE_IR_SWAP_FIXED_FLOAT_OIS = "InterestRate_IRSwap_FixedFloat_OIS"
    INTEREST_RATE_IR_SWAP_BASIS = "InterestRate_IRSwap_Basis"
    INTEREST_RATE_IR_SWAP_BASIS_OIS = "InterestRate_IRSwap_Basis_OIS"
    INTEREST_RATE_IR_SWAP_FIXED_FIXED = "InterestRate_IRSwap_FixedFixed"
    INTEREST_RATE_CROSS_CURRENCY_FIXED_FLOAT = "InterestRate_CrossCurrency_FixedFloat"
    INTEREST_RATE_CROSS_CURRENCY_BASIS = "InterestRate_CrossCurrency_Basis"
    INTEREST_RATE_FRA = "InterestRate_Fra"
    INTEREST_RATE_CAP_FLOOR = "InterestRate_CapFloor"
    INTEREST_RATE_OPTION_SWAPTION = "InterestRate_Option_Swaption"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class ProductQualificationResult:
    """
    Strongly-typed qualification and classification result.
    """

    qualifier: str
    asset_class: AssetClass
    base_product: BaseProduct
    sub_product: SubProduct
    display_name_ja: str
    display_name_en: str
    is_vanilla_fixed_float: bool
    details: Dict[str, Any] = field(default_factory=dict)


def _extract_economic_terms(target: Any) -> EconomicTerms:
    """Extracts the EconomicTerms instance from various supported input objects."""
    if isinstance(target, EconomicTerms):
        return target
    if isinstance(target, TradeState):
        if target.trade and target.trade.product and target.trade.product.economicTerms:
            return target.trade.product.economicTerms
    if isinstance(target, Trade):
        if target.product and target.product.economicTerms:
            return target.product.economicTerms
    if hasattr(target, "economicTerms") and isinstance(target.economicTerms, EconomicTerms):
        return target.economicTerms
    raise ValueError(f"Unable to extract EconomicTerms from object of type: {type(target)}")


def _extract_leg_details(economic_terms: EconomicTerms) -> Dict[str, Any]:
    """Extracts detailed financial metadata from economic terms for diagnostic inspection."""
    details: Dict[str, Any] = {
        "payout_count": len(economic_terms.payout or []),
        "currencies": [],
        "leg_types": [],
        "floating_indices": [],
        "is_ois": False,
        "is_zero_coupon": False,
    }

    try:
        details["is_ois"] = bool(Qualify_Transaction_OIS(economic_terms))
    except Exception:
        pass

    try:
        details["is_zero_coupon"] = bool(Qualify_Transaction_ZeroCoupon(economic_terms))
    except Exception:
        pass

    if economic_terms.payout:
        for idx, p in enumerate(economic_terms.payout, start=1):
            irs = p.InterestRatePayout
            if irs is None:
                continue

            # Check leg rate specification
            leg_type = "Unknown"
            if irs.rateSpecification:
                if irs.rateSpecification.FixedRateSpecification is not None:
                    leg_type = "Fixed"
                elif irs.rateSpecification.FloatingRateSpecification is not None:
                    leg_type = "Floating"
                    float_spec = irs.rateSpecification.FloatingRateSpecification
                    rate_opt = float_spec.rateOption
                    rate_idx = getattr(
                        rate_opt,
                        "floatingRateIndex",
                        getattr(rate_opt, "_FQRTN", "RateIndex"),
                    )
                    details["floating_indices"].append(str(rate_idx))
                elif irs.rateSpecification.InflationRateSpecification is not None:
                    leg_type = "Inflation"
            details["leg_types"].append(leg_type)

            # Currency
            curr = None
            if irs.priceQuantity and hasattr(irs.priceQuantity, "quantitySchedule"):
                qs = irs.priceQuantity.quantitySchedule
                unit = getattr(qs, "unit", None)
                if unit and hasattr(unit, "currency"):
                    curr = getattr(unit.currency, "value", unit.currency)
            if curr:
                details["currencies"].append(str(curr))

    return details


def qualify_economic_terms(economic_terms: EconomicTerms) -> ProductQualificationResult:
    """
    Qualifies an EconomicTerms instance using FINOS CDM native qualification functions.

    Args:
        economic_terms: The EconomicTerms model containing payouts and schedule.

    Returns:
        ProductQualificationResult: Complete classification and taxonomy result.
    """
    details = _extract_leg_details(economic_terms)

    # 1. Evaluate Asset Class
    is_ir = Qualify_AssetClass_InterestRate(economic_terms)
    asset_class = AssetClass.INTEREST_RATE if is_ir else AssetClass.UNKNOWN

    # 2. Evaluate Base Products
    is_ir_swap = Qualify_BaseProduct_IRSwap(economic_terms) if is_ir else False
    is_fra = Qualify_BaseProduct_Fra(economic_terms) if is_ir else False
    is_xccy = Qualify_BaseProduct_CrossCurrency(economic_terms) if is_ir else False

    base_product = BaseProduct.UNKNOWN
    if is_ir_swap:
        base_product = BaseProduct.IR_SWAP
    elif is_fra:
        base_product = BaseProduct.FRA
    elif is_xccy:
        base_product = BaseProduct.CROSS_CURRENCY

    # 3. Evaluate Sub Products
    is_fixed_float = Qualify_SubProduct_FixedFloat(economic_terms) if is_ir else False
    is_basis = Qualify_SubProduct_Basis(economic_terms) if is_ir else False
    is_fixed_fixed = Qualify_SubProduct_FixedFixed(economic_terms) if is_ir else False

    sub_product = SubProduct.UNKNOWN
    if is_fixed_float:
        sub_product = SubProduct.FIXED_FLOAT
    elif is_basis:
        sub_product = SubProduct.BASIS
    elif is_fixed_fixed:
        sub_product = SubProduct.FIXED_FIXED

    # 4. Specific Product Qualifiers
    qualifier = ProductQualifierEnum.UNKNOWN.value
    display_ja = "不明な商品"
    display_en = "Unknown Product"
    is_vanilla_ff = False

    # Check Vanilla Fixed/Float Swap
    if Qualify_InterestRate_IRSwap_FixedFloat(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FLOAT.value
        display_ja = "バニラ固定/変動金利スワップ"
        display_en = "Vanilla Fixed/Float Interest Rate Swap"
        is_vanilla_ff = True
    elif Qualify_InterestRate_IRSwap_FixedFloat_OIS(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FLOAT_OIS.value
        display_ja = "OIS 固定/変動金利スワップ"
        display_en = "OIS Fixed/Float Interest Rate Swap"
    elif Qualify_InterestRate_IRSwap_Basis(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_BASIS.value
        display_ja = "変動/変動金利スワップ（ベーシススワップ）"
        display_en = "Float/Float Basis Swap"
    elif Qualify_InterestRate_IRSwap_Basis_OIS(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_BASIS_OIS.value
        display_ja = "OIS 変動/変動金利スワップ"
        display_en = "OIS Float/Float Basis Swap"
    elif Qualify_InterestRate_IRSwap_FixedFixed(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FIXED.value
        display_ja = "固定/固定金利スワップ"
        display_en = "Fixed/Fixed Interest Rate Swap"
    elif Qualify_InterestRate_CrossCurrency_FixedFloat(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_CROSS_CURRENCY_FIXED_FLOAT.value
        display_ja = "通貨スワップ（固定/変動）"
        display_en = "Cross-Currency Fixed/Float Swap"
    elif Qualify_InterestRate_CrossCurrency_Basis(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_CROSS_CURRENCY_BASIS.value
        display_ja = "通貨スワップ（変動/変動）"
        display_en = "Cross-Currency Basis Swap"
    elif Qualify_InterestRate_Fra(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_FRA.value
        display_ja = "金利先渡取引 (FRA)"
        display_en = "Forward Rate Agreement (FRA)"
    elif Qualify_InterestRate_CapFloor(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_CAP_FLOOR.value
        display_ja = "金利キャップ / フロア"
        display_en = "Interest Rate Cap / Floor"
    elif Qualify_InterestRate_Option_Swaption(economic_terms):
        qualifier = ProductQualifierEnum.INTEREST_RATE_OPTION_SWAPTION.value
        display_ja = "スワップション（金利スワップオプション）"
        display_en = "Interest Rate Swaption"
    elif is_ir_swap and is_fixed_float:
        # Fallback if specific qualifier rule had edge case
        qualifier = ProductQualifierEnum.INTEREST_RATE_IR_SWAP_FIXED_FLOAT.value
        display_ja = "バニラ固定/変動金利スワップ"
        display_en = "Vanilla Fixed/Float Interest Rate Swap"
        is_vanilla_ff = True

    return ProductQualificationResult(
        qualifier=qualifier,
        asset_class=asset_class,
        base_product=base_product,
        sub_product=sub_product,
        display_name_ja=display_ja,
        display_name_en=display_en,
        is_vanilla_fixed_float=is_vanilla_ff,
        details=details,
    )


def qualify_trade_state(trade_state: TradeState) -> ProductQualificationResult:
    """
    Qualifies a FINOS CDM TradeState instance.

    Args:
        trade_state: Strongly-typed TradeState object.

    Returns:
        ProductQualificationResult: Complete qualification and taxonomy result.
    """
    econ = _extract_economic_terms(trade_state)
    return qualify_economic_terms(econ)


def qualify_trade(trade: Trade) -> ProductQualificationResult:
    """
    Qualifies a FINOS CDM Trade instance.

    Args:
        trade: Strongly-typed Trade object.

    Returns:
        ProductQualificationResult: Complete qualification and taxonomy result.
    """
    econ = _extract_economic_terms(trade)
    return qualify_economic_terms(econ)


def qualify_from_json(json_path_or_str: Union[str, Path]) -> ProductQualificationResult:
    """
    Convenience function to load and qualify a trade directly from a JSON file or string.

    Args:
        json_path_or_str: Path to the JSON file or a raw JSON string.

    Returns:
        ProductQualificationResult: Complete qualification and taxonomy result.
    """
    if isinstance(json_path_or_str, Path) or (
        isinstance(json_path_or_str, str) and Path(json_path_or_str).is_file()
    ):
        file_path = Path(json_path_or_str)
        raw_json = file_path.read_text(encoding="utf-8")
    else:
        raw_json = str(json_path_or_str)

    # Attempt to deserialize as TradeState first, then Trade
    try:
        trade_state = TradeState.model_validate_json(raw_json)
        return qualify_trade_state(trade_state)
    except Exception as e_ts:
        try:
            trade = Trade.model_validate_json(raw_json)
            return qualify_trade(trade)
        except Exception as e_t:
            raise ValueError(
                f"Failed to deserialize JSON as either TradeState or Trade: {e_ts} | {e_t}"
            )


def is_vanilla_fixed_float_swap(target: Union[TradeState, Trade, EconomicTerms, str, Path]) -> bool:
    """
    Convenience boolean helper returning True if the target product is a
    Plain Vanilla Fixed/Float Interest Rate Swap.

    Args:
        target: TradeState, Trade, EconomicTerms, file path, or raw JSON string.

    Returns:
        bool: True if qualified as Plain Vanilla Fixed/Float IRS.
    """
    if isinstance(target, (str, Path)):
        res = qualify_from_json(target)
    elif isinstance(target, TradeState):
        res = qualify_trade_state(target)
    elif isinstance(target, Trade):
        res = qualify_trade(target)
    elif isinstance(target, EconomicTerms):
        res = qualify_economic_terms(target)
    else:
        raise TypeError(f"Unsupported target type for qualification: {type(target)}")
    return res.is_vanilla_fixed_float


def print_qualification_summary(result: ProductQualificationResult) -> None:
    """
    Prints a formatted summary of the product qualification result.
    """
    print("=" * 70)
    print("FINOS CDM Product Qualification Summary")
    print("=" * 70)
    print(f"Product Qualifier : {result.qualifier}")
    print(f"Asset Class       : {result.asset_class.value}")
    print(f"Base Product      : {result.base_product.value}")
    print(f"Sub Product       : {result.sub_product.value}")
    print(f"Display Name (JA) : {result.display_name_ja}")
    print(f"Display Name (EN) : {result.display_name_en}")
    print(f"Is Vanilla IRS?   : {'YES' if result.is_vanilla_fixed_float else 'NO'}")

    if result.details:
        print("\n--- Economic Details ---")
        for k, v in result.details.items():
            print(f"  {k:20}: {v}")
    print("=" * 70)


def main() -> None:
    """Main CLI entry point for standalone qualification execution."""
    from cdm_workspace.deserialize_trade_state import get_sample_irs_json_path

    if len(sys.argv) > 1:
        target_file = Path(sys.argv[1])
    else:
        target_file = get_sample_irs_json_path()

    if not target_file.exists():
        print(f"Error: Target file not found: {target_file}")
        sys.exit(1)

    print(f"Qualifying FINOS CDM Product in: {target_file.resolve()}")
    result = qualify_from_json(target_file)
    print_qualification_summary(result)


if __name__ == "__main__":
    main()
