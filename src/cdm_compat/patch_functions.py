"""
Rune & Rosetta Function and Symbol Compatibility Patches (cdm_compat.patch_functions)

Fixes issues in finos-cdm and rune-runtime function execution:
1. Scalar RHS comparisons in rune.runtime.utils.rune_all_elements.
2. Cross-module Rosetta DSL symbols (functions, enums, models) resolution in builtins via lazy loader.
3. Cross-enum instantiation (e.g. PeriodEnum(PeriodExtendedEnum.M)) in Rosetta generated code.
4. Built-in implementations for Rosetta native datetime / math functions.
5. FuncProxy.__call__ bypassing Pydantic @validate_call validation overhead.
"""

from __future__ import annotations

import builtins
import datetime
from decimal import Decimal
from enum import Enum
import importlib
import logging
import pkgutil
import sys
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .config import CdmCompatConfig

logger = logging.getLogger(__name__)

_FUNCTIONS_PATCHED = False
_ROSETTA_SYMBOLS_REGISTERED = False


class _LazyRosettaSymbol:
    """
    Lazy proxy for any Rosetta / FINOS CDM class, enum, or function.
    Defers importing the underlying module until the symbol is first accessed or called.
    """

    __slots__ = ("_module_path", "_symbol_name", "_resolved")

    def __init__(self, module_path: str, symbol_name: str) -> None:
        self._module_path = module_path
        self._symbol_name = symbol_name
        self._resolved = None

    def _resolve(self) -> Any:
        if self._resolved is None:
            try:
                mod = importlib.import_module(self._module_path)
                self._resolved = getattr(mod, self._symbol_name)
            except Exception as exc:
                raise ImportError(
                    f"Failed to load Rosetta symbol '{self._symbol_name}' from '{self._module_path}': {exc}"
                ) from exc
        return self._resolved

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target = self._resolve()
        # If target is an Enum and first argument is provided
        if isinstance(target, type) and issubclass(target, Enum) and len(args) == 1 and not kwargs:
            arg0 = args[0]
            if arg0 is None:
                return None
            if isinstance(arg0, Enum):
                return target(arg0.value)
        return target(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._resolve(), item)

    def __repr__(self) -> str:
        if self._resolved is not None:
            return repr(self._resolved)
        return f"<LazyRosettaSymbol {self._symbol_name} from {self._module_path}>"


def _register_builtin_native_functions() -> None:
    """Registers standard native datetime and math functions into Rune native registry."""
    try:
        from rune.runtime.native_registry import rune_register_native

        def _native_add_days(inputDate: Any, numDays: Any) -> Any:
            if inputDate is None or numDays is None:
                return inputDate
            if isinstance(inputDate, datetime.datetime):
                return (inputDate + datetime.timedelta(days=int(numDays))).date()
            if isinstance(inputDate, datetime.date):
                return inputDate + datetime.timedelta(days=int(numDays))
            return inputDate

        def _native_date_difference(firstDate: Any, secondDate: Any) -> int:
            if firstDate is None or secondDate is None:
                return 0
            d1 = firstDate.date() if isinstance(firstDate, datetime.datetime) else firstDate
            d2 = secondDate.date() if isinstance(secondDate, datetime.datetime) else secondDate
            return (d1 - d2).days

        def _native_leap_year_date_difference(firstDate: Any, secondDate: Any) -> int:
            if not firstDate or not secondDate:
                return 0
            d1 = firstDate.date() if isinstance(firstDate, datetime.datetime) else firstDate
            d2 = secondDate.date() if isinstance(secondDate, datetime.datetime) else secondDate
            start, end = min(d1, d2), max(d1, d2)
            count = 0
            for y in range(start.year, end.year + 1):
                if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
                    leap_day = datetime.date(y, 2, 29)
                    if start <= leap_day <= end:
                        count += 1
            return count if d1 <= d2 else -count

        def _native_round_to_precision(value: Any, precision: Any, roundingDirection: Any = None, forceRoundUp: bool = False) -> Any:
            if value is None:
                return None
            dec_val = Decimal(str(value))
            prec = int(precision) if precision is not None else 0
            return round(dec_val, prec)

        rune_register_native("cdm.base.datetime.functions.AddDays", _native_add_days)
        rune_register_native("cdm.base.datetime.functions.DateDifference", _native_date_difference)
        rune_register_native("cdm.base.datetime.functions.LeapYearDateDifference", _native_leap_year_date_difference)
        rune_register_native("cdm.base.math.functions.RoundToPrecision", _native_round_to_precision)
        rune_register_native("cdm.base.datetime.functions.Today", lambda: datetime.date.today())
        rune_register_native("cdm.base.datetime.functions.Now", lambda: datetime.datetime.now().time())
    except Exception as exc:
        logger.debug("Could not register native functions: %s", exc)


def _patch_enum_cross_instantiation() -> None:
    """
    Allows all Enum subclasses in rune / finos to accept instances of other Enum types
    with matching string values (e.g. PeriodEnum(PeriodExtendedEnum.M)).
    """
    try:
        import rune.runtime.metadata as rmeta

        orig_missing = getattr(rmeta.EnumWithMetaMixin, "_orig_missing", None)
        if orig_missing is None:
            rmeta.EnumWithMetaMixin._orig_missing = rmeta.EnumWithMetaMixin._missing_

            @classmethod
            def _flexible_enum_missing(cls: Any, value: Any) -> Any:
                if isinstance(value, Enum):
                    return cls(value.value)
                return None

            rmeta.EnumWithMetaMixin._missing_ = _flexible_enum_missing
    except Exception as exc:
        logger.debug("Could not patch EnumWithMetaMixin._missing_: %s", exc)


def patch_rosetta_function_types() -> bool:
    """
    Injects CDM model classes from finos._bundle and lazy symbol loaders for all
    Rosetta DSL functions, enums, and models into builtins so that Pydantic's @validate_call
    decorator and generated qualification functions can execute without NameError.
    """
    global _ROSETTA_SYMBOLS_REGISTERED
    try:
        import finos._bundle as bundle

        for name in dir(bundle):
            if not name.startswith("__"):
                obj = getattr(bundle, name)
                if isinstance(obj, type) and issubclass(obj, Enum):
                    obj._missing_ = classmethod(lambda cls, val: cls(val.value) if isinstance(val, Enum) else None)
                setattr(builtins, name, obj)

        if not _ROSETTA_SYMBOLS_REGISTERED:
            import finos.cdm

            for info in pkgutil.walk_packages(finos.cdm.__path__, "finos.cdm."):
                sym_name = info.name.split(".")[-1]
                if not hasattr(builtins, sym_name):
                    setattr(builtins, sym_name, _LazyRosettaSymbol(info.name, sym_name))
            _ROSETTA_SYMBOLS_REGISTERED = True

        _patch_enum_cross_instantiation()
        _register_builtin_native_functions()
        return True
    except Exception as e:
        logger.warning("Failed to patch Rosetta function types: %s", e)
        return False


def patch_rune_all_elements() -> bool:
    """
    Patches rune.runtime.utils.rune_all_elements to properly handle scalar RHS values.

    In rune-runtime 2.0 - 2.2+, rune_all_elements(lhs, op, rhs) is implemented as:
        all(cmp(el1, el2) for el1, el2 in zip(op1, op2)) if len(op1) == len(op2) else False
    When rhs is a scalar (e.g. True or False), op2 becomes [rhs] (len=1).
    If len(op1) > 1 (e.g. [True, True] for a 2-leg swap), it returns False incorrectly.

    This patch ensures that when rhs is not a sequence, each element of lhs is compared against rhs.
    """
    try:
        import rune.runtime.utils as rru

        orig_rune_all_elements = getattr(rru, "_orig_rune_all_elements", rru.rune_all_elements)

        def patched_rune_all_elements(lhs: Any, op: str, rhs: Any) -> bool:
            cmp_fn = rru._cmp[op]
            op1 = rru._to_list(lhs)

            # If rhs is a list/tuple/sequence (and not a string/dict/bytes), perform zip comparison
            if isinstance(rhs, (list, tuple)):
                op2 = rru._to_list(rhs)
                if len(op1) != len(op2):
                    return False
                return all(cmp_fn(el1, el2) for el1, el2 in zip(op1, op2))
            else:
                # Scalar broadcast comparison: all elements in lhs must satisfy cmp_fn(el, rhs)
                if len(op1) == 0:
                    return False
                return all(cmp_fn(el, rhs) for el in op1)

        rru._orig_rune_all_elements = orig_rune_all_elements
        rru.rune_all_elements = patched_rune_all_elements

        # Also patch in rune.runtime.conditions if present
        try:
            import rune.runtime.conditions as rrc

            if hasattr(rrc, "rune_all_elements"):
                rrc.rune_all_elements = patched_rune_all_elements
        except ImportError:
            pass

        return True
    except Exception as e:
        logger.warning("Failed to patch rune_all_elements: %s", e)
        return False


def patch_func_proxy_call() -> bool:
    """
    Patches rune.runtime.func_proxy.FuncProxy.__call__ to invoke raw_function directly
    when available, bypassing pydantic @validate_call parameter re-validation overhead
    on resolved reference models.
    """
    try:
        from rune.runtime.func_proxy import FuncProxy, rune_finalize_return

        def patched_func_proxy_call(self: Any, *args: Any, **kwargs: Any) -> Any:
            target = getattr(self._func, "raw_function", self._func)
            return rune_finalize_return(target(*args, **kwargs))

        FuncProxy.__call__ = patched_func_proxy_call
        return True
    except Exception as e:
        logger.warning("Failed to patch FuncProxy.__call__: %s", e)
        return False


def apply_function_patches(config: Optional[CdmCompatConfig] = None) -> bool:
    """
    Applies function-level compatibility patches based on configuration flags.

    Args:
        config: Optional configuration instance. Defaults to cdm_compat.get_config().

    Returns:
        bool: True if at least one patch was applied.
    """
    global _FUNCTIONS_PATCHED
    if config is None:
        from .config import get_config

        config = get_config()

    applied_any = False

    if config.patch_rosetta_function_types:
        applied_any = patch_rosetta_function_types() or applied_any

    if config.patch_rune_all_elements:
        applied_any = patch_rune_all_elements() or applied_any

    if config.patch_func_proxy_call:
        applied_any = patch_func_proxy_call() or applied_any

    _FUNCTIONS_PATCHED = True
    return applied_any
