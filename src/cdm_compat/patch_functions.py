"""
Rune & Rosetta Function Compatibility Patches (cdm_compat.patch_functions)

Fixes three critical issues in finos-cdm and rune-runtime function execution:
1. Missing model type names in global scope during Pydantic @validate_call type hint evaluation
   (e.g., finos_cdm_product_template_EconomicTerms not imported in generated qualification functions).
2. rune.runtime.utils.rune_all_elements failing on scalar RHS comparisons
   (e.g., rune_all_elements([True, True], "=", True)).
3. FuncProxy.__call__ bypassing pydantic @validate_call validation overhead and metadata slot errors
   on resolved models (using raw_function when available, matching rune_call_unchecked semantics).
"""

from __future__ import annotations

import builtins
import sys
from typing import Any

_FUNCTIONS_PATCHED = False


def patch_rosetta_function_types() -> bool:
    """
    Injects all CDM model classes from finos._bundle into builtins so that
    Pydantic's @validate_call decorator can evaluate forward type references in
    Rosetta-generated functions (e.g. finos_cdm_product_template_EconomicTerms)
    without NameError.
    """
    try:
        import finos._bundle as bundle

        for name in dir(bundle):
            if not name.startswith("__"):
                setattr(builtins, name, getattr(bundle, name))
        return True
    except Exception:
        return False


def patch_rune_all_elements() -> bool:
    """
    Patches rune.runtime.utils.rune_all_elements to properly handle scalar RHS values.

    In rune-runtime, rune_all_elements(lhs, op, rhs) is implemented as:
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

        # Also patch in rune.runtime.conditions if it exists there
        try:
            import rune.runtime.conditions as rrc

            if hasattr(rrc, "rune_all_elements"):
                rrc.rune_all_elements = patched_rune_all_elements
        except ImportError:
            pass

        return True
    except Exception:
        return False


def patch_func_proxy_call() -> bool:
    """
    Patches rune.runtime.func_proxy.FuncProxy.__call__ to invoke raw_function directly
    when available, bypassing pydantic @validate_call parameter re-validation errors
    on resolved reference models.
    """
    try:
        from rune.runtime.func_proxy import FuncProxy, rune_finalize_return

        def patched_func_proxy_call(self, *args, **kwargs):
            target = getattr(self._func, "raw_function", self._func)
            return rune_finalize_return(target(*args, **kwargs))

        FuncProxy.__call__ = patched_func_proxy_call
        return True
    except Exception:
        return False


def apply_function_patches() -> bool:
    """
    Applies all function-level compatibility patches.
    Idempotent: safe to call multiple times.

    Returns:
        bool: True if patches were freshly applied, False if already applied.
    """
    global _FUNCTIONS_PATCHED
    if _FUNCTIONS_PATCHED:
        return False

    t_ok = patch_rosetta_function_types()
    a_ok = patch_rune_all_elements()
    f_ok = patch_func_proxy_call()

    _FUNCTIONS_PATCHED = True
    return t_ok or a_ok or f_ok
