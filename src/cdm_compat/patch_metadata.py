"""
Runtime Metadata Patching for rune-runtime.

This module patches Rune 2.0.1+ metadata handling mixins:
- ComplexTypeMetaDataMixin: Adds None and list checks on deserialize & serialise.
- BasicTypeMetaDataMixin: Supports list/tuple elements and None checks for annotated basic types like StrWithMeta.
- EnumWithMetaMixin: Supports list/tuple elements, _EnumWrapper, raw Enum, and None checks on deserialize & serialise.
"""

from __future__ import annotations

from enum import Enum
from functools import partial
import logging
from typing import Any, Callable, Set

from pydantic.functional_serializers import PlainSerializer, WrapSerializer

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

    # 1. Patch ComplexTypeMetaDataMixin
    orig_complex_deserialize = rmeta.ComplexTypeMetaDataMixin.deserialize
    orig_complex_serialise = rmeta.ComplexTypeMetaDataMixin.serialise

    def _complex_deserialize_fn(cls: Any, obj: Any, allowed_meta: Set[str]) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_complex_deserialize_fn(cls, item, allowed_meta) for item in obj]
        return orig_complex_deserialize.__func__(cls, obj, allowed_meta)

    def _complex_serialise_fn(cls: Any, obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_complex_serialise_fn(cls, item) for item in obj]
        return orig_complex_serialise.__func__(cls, obj)

    rmeta.ComplexTypeMetaDataMixin.deserialize = classmethod(_complex_deserialize_fn)
    rmeta.ComplexTypeMetaDataMixin.serialise = classmethod(_complex_serialise_fn)
    rmeta.ComplexTypeMetaDataMixin.serializer = classmethod(
        lambda cls: PlainSerializer(cls.serialise, return_type=Any)
    )
    rmeta.ComplexTypeMetaDataMixin.validator.cache_clear()

    # 2. Patch BasicTypeMetaDataMixin.deserialize & serialise
    orig_basic_deserialize = rmeta.BasicTypeMetaDataMixin.deserialize
    orig_basic_serialise = rmeta.BasicTypeMetaDataMixin.serialise

    def _basic_deserialize_fn(
        cls: Any, obj: Any, handler: Callable[[Any], Any], base_types: Any, allowed_meta: Set[str]
    ) -> Any:
        if obj is None:
            return handler(None)
        if isinstance(obj, (list, tuple)):
            deserialized_list = []
            for item in obj:
                if item is None:
                    deserialized_list.append(None)
                    continue
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

    def _basic_serialise_fn(cls: Any, obj: Any, base_type: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_basic_serialise_fn(cls, item, base_type) for item in obj]
        return orig_basic_serialise.__func__(cls, obj, base_type)

    rmeta.BasicTypeMetaDataMixin.deserialize = classmethod(_basic_deserialize_fn)
    rmeta.BasicTypeMetaDataMixin.serialise = classmethod(_basic_serialise_fn)
    rmeta.BasicTypeMetaDataMixin.serializer = classmethod(
        lambda cls: PlainSerializer(partial(cls.serialise, base_type=cls._OUTPUT_TYPE), return_type=Any)
    )
    rmeta.BasicTypeMetaDataMixin.validator.cache_clear()

    # 3. Patch EnumWithMetaMixin.deserialize & serialise
    orig_enum_deserialize = rmeta.EnumWithMetaMixin.deserialize
    orig_enum_serialise = rmeta.EnumWithMetaMixin.serialise

    def _enum_deserialize_fn(cls: Any, obj: Any, allowed_meta: Set[str]) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_enum_deserialize_fn(cls, item, allowed_meta) for item in obj]
        return orig_enum_deserialize.__func__(cls, obj, allowed_meta)

    def _enum_serialise_fn(cls: Any, obj: Any, handler: Callable[[Any, Any], Any], info: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_enum_serialise_fn(cls, item, handler, info) for item in obj]
        if isinstance(obj, rmeta._EnumWrapper):
            res = obj.serialise_meta()
            res["@data"] = handler(obj.enum_instance, info)
            return res
        if isinstance(obj, Enum):
            return handler(obj, info)
        return orig_enum_serialise.__func__(cls, obj, handler, info)

    rmeta.EnumWithMetaMixin.deserialize = classmethod(_enum_deserialize_fn)
    rmeta.EnumWithMetaMixin.serialise = classmethod(_enum_serialise_fn)
    rmeta.EnumWithMetaMixin.serializer = classmethod(
        lambda cls: WrapSerializer(cls.serialise, return_type=Any)
    )
    rmeta.EnumWithMetaMixin.validator.cache_clear()

    _METADATA_PATCHED = True
    logger.debug("Rune runtime metadata patches applied successfully.")
    return True
