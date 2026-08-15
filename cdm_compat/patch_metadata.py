"""
Runtime Metadata Patching for rune-runtime.

This module patches Rune 2.0.1 metadata handling mixins:
- ComplexTypeMetaDataMixin: Adds None checks to prevent Input Validation Error on None fields.
- BasicTypeMetaDataMixin: Supports list/tuple elements for annotated basic types like StrWithMeta.
- EnumWithMetaMixin: Adds None checks to prevent calling _init_meta on NoneType.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Set

logger = logging.getLogger(__name__)

_METADATA_PATCHED = False


def apply_metadata_patches() -> bool:
    """
    Applies patches to rune.runtime.metadata mixins.
    Safe to call multiple times (idempotent).

    Returns:
        bool: True if patches were applied, False if already applied.
    """
    global _METADATA_PATCHED
    if _METADATA_PATCHED:
        return False

    try:
        import rune.runtime.metadata as rmeta
    except ImportError:
        logger.warning("rune.runtime.metadata could not be imported; skipping metadata patches.")
        return False

    # 1. Patch ComplexTypeMetaDataMixin.deserialize
    orig_complex_deserialize = rmeta.ComplexTypeMetaDataMixin.deserialize

    @classmethod
    def _patched_complex_deserialize(cls: Any, obj: Any, allowed_meta: Set[str]) -> Any:
        if obj is None:
            return None
        return orig_complex_deserialize.__func__(cls, obj, allowed_meta)

    rmeta.ComplexTypeMetaDataMixin.deserialize = _patched_complex_deserialize
    rmeta.ComplexTypeMetaDataMixin.validator.cache_clear()

    # 2. Patch BasicTypeMetaDataMixin.deserialize & serialise
    orig_basic_deserialize = rmeta.BasicTypeMetaDataMixin.deserialize
    orig_basic_serialise = rmeta.BasicTypeMetaDataMixin.serialise

    @classmethod
    def _patched_basic_deserialize(
        cls: Any, obj: Any, handler: Callable[[Any], Any], base_types: Any, allowed_meta: Set[str]
    ) -> Any:
        if obj is None:
            return handler(None)
        if isinstance(obj, (list, tuple)):
            deserialized_list = []
            for item in obj:
                if isinstance(item, base_types) and not isinstance(item, cls):
                    item = cls(item)
                elif isinstance(item, dict) and "@data" in item:
                    data = item.copy()
                    d_val = data.pop("@data")
                    item = cls(d_val, **data)
                if cls.meta_checks_enabled() and hasattr(item, "_init_meta"):
                    item._init_meta(allowed_meta)
                deserialized_list.append(item)
            return handler(deserialized_list)
        return orig_basic_deserialize.__func__(cls, obj, handler, base_types, allowed_meta)

    @classmethod
    def _patched_basic_serialise(cls: Any, obj: Any, base_type: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [cls.serialise(item, base_type) for item in obj]
        return orig_basic_serialise.__func__(cls, obj, base_type)

    rmeta.BasicTypeMetaDataMixin.deserialize = _patched_basic_deserialize
    rmeta.BasicTypeMetaDataMixin.serialise = _patched_basic_serialise
    rmeta.BasicTypeMetaDataMixin.validator.cache_clear()
    rmeta.BasicTypeMetaDataMixin.serializer.cache_clear()

    # 3. Patch EnumWithMetaMixin.deserialize
    orig_enum_deserialize = rmeta.EnumWithMetaMixin.deserialize

    @classmethod
    def _patched_enum_deserialize(cls: Any, obj: Any, allowed_meta: Set[str]) -> Any:
        if obj is None:
            return None
        return orig_enum_deserialize.__func__(cls, obj, allowed_meta)

    rmeta.EnumWithMetaMixin.deserialize = _patched_enum_deserialize
    rmeta.EnumWithMetaMixin.validator.cache_clear()

    _METADATA_PATCHED = True
    logger.debug("Rune runtime metadata patches applied successfully.")
    return True
