"""
Runtime Metadata Patching for rune-runtime.

This module patches Rune 2.0.1+ metadata handling mixins to provide full
compatibility with both Rune JSON format (@data, @ref, @key) and official
Rosetta / FINOS CDM JSON schemas (value, globalKey, externalKey, references).
"""

from __future__ import annotations

from enum import Enum
from functools import partial
import logging
from typing import Any, Callable, Set

from pydantic.functional_serializers import PlainSerializer, WrapSerializer

logger = logging.getLogger(__name__)

_METADATA_PATCHED = False


def _normalize_rosetta_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Converts Rosetta CDM metadata dictionaries to Rune metadata slots."""
    normalized: dict[str, Any] = {}
    for k, v in meta.items():
        if k == "@data":
            continue
        elif k == "globalKey":
            normalized["@key"] = v
        elif k == "externalKey":
            normalized["@key:external"] = v
        elif k == "location":
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                loc_val = v[0].get("value")
                normalized["@key:scoped"] = loc_val
            elif isinstance(v, dict):
                normalized["@key:scoped"] = v.get("value")
            else:
                normalized["@key:scoped"] = v
        elif k == "scheme":
            normalized["@scheme"] = v
        elif k.startswith("@"):
            normalized[k] = v
        else:
            if k[0] != "@":
                normalized["@" + k.replace("_", ":")] = v
            else:
                normalized[k] = v
    return normalized


def _extract_rosetta_ref(data: dict[str, Any]) -> dict[str, Any] | None:
    """Extracts reference tags from either Rune or Rosetta reference dicts."""
    if not isinstance(data, dict):
        return None
    if "@ref" in data:
        return {"@ref": data["@ref"]}
    if "@ref:external" in data:
        return {"@ref:external": data["@ref:external"]}
    if "@ref:scoped" in data:
        return {"@ref:scoped": data["@ref:scoped"]}
    if "globalReference" in data:
        return {"@ref": data["globalReference"]}
    if "externalReference" in data:
        return {"@ref:external": data["externalReference"]}
    if "address" in data and isinstance(data["address"], dict):
        val = data["address"].get("value")
        return {"@ref:scoped": val}
    return None


def resolve_model_references(root_obj: Any) -> Any:
    """
    Recursively links parent pointers and resolves all UnresolvedReference instances
    within a Rune / FINOS CDM object tree to their actual target model objects.

    Args:
        root_obj: Root CDM model instance (e.g. TradeState, Trade, etc.)

    Returns:
        The root object with all references resolved and bound.
    """
    import rune.runtime.metadata as rmeta
    import rune.runtime.base_data_class as rbdc

    visited_parents: set[int] = set()

    def _setup_parents_recursive(obj: Any, parent: Any = None) -> None:
        if obj is None:
            return
        obj_id = id(obj)
        if obj_id in visited_parents:
            return
        visited_parents.add(obj_id)

        # Only BaseDataClass instances (complex models) need parent linking
        if isinstance(obj, rbdc.BaseDataClass) and parent is not None:
            obj._set_rune_parent(parent)

        if isinstance(obj, (list, tuple)):
            for item in obj:
                _setup_parents_recursive(item, parent)
        elif isinstance(obj, rbdc.BaseDataClass):
            for prop_nm, val in list(obj.__dict__.items()):
                if not prop_nm.startswith("_") and prop_nm != rmeta.PARENT_PROP:
                    _setup_parents_recursive(val, parent=obj)

    _setup_parents_recursive(root_obj)

    visited_resolve: set[int] = set()

    def _resolve_refs_recursive(obj: Any) -> None:
        if obj is None:
            return
        obj_id = id(obj)
        if obj_id in visited_resolve:
            return
        visited_resolve.add(obj_id)

        if isinstance(obj, (list, tuple)):
            for item in obj:
                _resolve_refs_recursive(item)
        elif hasattr(obj, "__dict__"):
            refs_to_bind = []
            for prop_nm, val in list(obj.__dict__.items()):
                if isinstance(val, (rmeta.UnresolvedReference, rmeta.Reference)):
                    try:
                        ref = val.get_reference(obj)
                        refs_to_bind.append((prop_nm, ref))
                    except Exception as exc:
                        logger.debug("Could not resolve reference for %s: %s", prop_nm, exc)

            for prop_nm, ref in refs_to_bind:
                try:
                    obj._bind_property_to(prop_nm, ref)
                except Exception:
                    # Fallback direct bind if property annotations differ
                    obj.__dict__[prop_nm] = ref.target
                    refs = obj.__dict__.setdefault(rmeta.REFS_CONTAINER, {})
                    refs[prop_nm] = (ref.target_key, ref.key_type)

            for prop_nm, val in list(obj.__dict__.items()):
                if not prop_nm.startswith("_") and prop_nm != rmeta.PARENT_PROP:
                    _resolve_refs_recursive(val)

    _resolve_refs_recursive(root_obj)
    return root_obj


def apply_metadata_patches() -> bool:
    """
    Applies patches to rune.runtime.metadata and base_data_class mixins.
    Safe to call multiple times (idempotent).

    Returns:
        bool: True if patches were applied, False if already applied.
    """
    global _METADATA_PATCHED
    if _METADATA_PATCHED:
        return False

    try:
        import rune.runtime.metadata as rmeta
        import rune.runtime.base_data_class as rbdc
    except ImportError:
        logger.warning("rune.runtime could not be imported; skipping metadata patches.")
        return False

    # 0. Patch BaseMetaDataMixin duplicate-safe object map updating
    def _safe_update_object_maps_fn(self: Any, new_maps: dict[Any, Any]) -> None:
        if parent := self.get_rune_parent():
            scoped, reduced_maps = self._extract_scoped_map(new_maps)
            parent._update_object_maps(reduced_maps)
            if not scoped:
                return
            new_maps = {rmeta.KeyType.SCOPED: scoped}

        obj_maps = self.__dict__.setdefault(rmeta.RUNE_OBJ_MAPS, {})
        for map_type, new_map in new_maps.items():
            local_map = obj_maps.setdefault(map_type, {})
            for k, v in new_map.items():
                if k not in local_map:
                    local_map[k] = v

    rmeta.BaseMetaDataMixin._update_object_maps = _safe_update_object_maps_fn

    # Patch BaseMetaDataMixin and reference creation
    def _create_unresolved_ref_fn(cls: Any, metadata: dict[str, Any]) -> Any:
        if not isinstance(metadata, dict):
            return None
        if ref_dict := _extract_rosetta_ref(metadata):
            return rmeta.UnresolvedReference(ref_dict)
        return None

    rmeta.BaseMetaDataMixin._create_unresolved_ref = classmethod(_create_unresolved_ref_fn)
    rmeta.ComplexTypeMetaDataMixin._create_unresolved_ref = classmethod(_create_unresolved_ref_fn)
    rmeta.BasicTypeMetaDataMixin._create_unresolved_ref = classmethod(_create_unresolved_ref_fn)
    rmeta.EnumWithMetaMixin._create_unresolved_ref = classmethod(_create_unresolved_ref_fn)

    # Patch BaseDataClass._deserialize_refs for Rosetta reference objects & FieldWithMeta envelopes
    def _deserialize_refs_fn(cls: Any, data: Any, handler: Any) -> Any:
        metadata: dict[str, Any] = {}
        if isinstance(data, dict):
            if aux := cls._create_unresolved_ref(data):
                return aux
            if "meta" in data and isinstance(data["meta"], dict):
                metadata.update(_normalize_rosetta_meta(data["meta"]))
                if aux := cls._create_unresolved_ref(metadata):
                    return aux
            for k, v in data.items():
                if k.startswith("@") and k != "@data":
                    metadata[k] = v

            # Check if wrapped in Rosetta FieldWithMeta envelope: {"value": {...}, "meta": {...}}
            if "value" in data and isinstance(data["value"], dict):
                val_dict = data["value"]
                meta_dict = data.get("meta", {})
                data = {**val_dict}
                if meta_dict:
                    data["meta"] = meta_dict

        obj = handler(data)
        if metadata and isinstance(obj, rmeta.BaseMetaDataMixin):
            obj.__dict__[rmeta.META_CONTAINER] = metadata
            obj._register_keys(metadata)
        if hasattr(obj, "_init_rune_parent"):
            obj._init_rune_parent()
            obj.resolve_references(ignore_dangling=True, recurse=False)
        return obj

    rbdc.BaseDataClass._deserialize_refs = classmethod(_deserialize_refs_fn)

    # Patch BaseDataClass._serialize_refs to safely serialize references, include metadata, and break recursion cycles
    def _safe_serialize_refs_fn(self: Any, serializer: Any, info: Any) -> Any:
        refs = self._get_rune_refs_container()
        meta = self.serialise_meta() if hasattr(self, "serialise_meta") else {}
        if not refs:
            res = serializer(self, info)
            return {**meta, **res}
        saved: dict[str, Any] = {}
        for prop_nm, (key, ref_type) in refs.items():
            if prop_nm in self.__dict__:
                saved[prop_nm] = self.__dict__[prop_nm]
                self.__dict__[prop_nm] = {ref_type.rune_ref_tag: key}
        try:
            res = serializer(self, info)
            for prop_nm, (key, ref_type) in refs.items():
                res[prop_nm] = {ref_type.rune_ref_tag: key}
            return {**meta, **res}
        finally:
            for prop_nm, orig_val in saved.items():
                self.__dict__[prop_nm] = orig_val

    rbdc.BaseDataClass._serialize_refs = _safe_serialize_refs_fn

    # 1. Patch ComplexTypeMetaDataMixin
    orig_complex_deserialize = rmeta.ComplexTypeMetaDataMixin.deserialize
    orig_complex_serialise = rmeta.ComplexTypeMetaDataMixin.serialise

    def _complex_deserialize_fn(cls: Any, obj: Any, allowed_meta: Set[str]) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_complex_deserialize_fn(cls, item, allowed_meta) for item in obj]
        if isinstance(obj, cls):
            if cls.meta_checks_enabled():
                obj._init_meta(allowed_meta)
            return obj
        if isinstance(obj, rmeta.BaseReference):
            return obj
        if isinstance(obj, dict):
            if ref := cls._create_unresolved_ref(obj):
                return ref

            # Check if wrapped in Rosetta FieldWithMeta envelope: {"value": {...}, "meta": {...}}
            if "value" in obj and isinstance(obj["value"], dict):
                val_dict = obj["value"]
                meta_dict = obj.get("meta", {})
                obj_to_use = {**val_dict}
                if meta_dict:
                    obj_to_use["meta"] = meta_dict
            else:
                obj_to_use = obj

            metadata: dict[str, Any] = {}
            for k, v in obj_to_use.items():
                if k.startswith("@") and k != "@data":
                    metadata[k] = v
            if "meta" in obj_to_use and isinstance(obj_to_use["meta"], dict):
                metadata.update(_normalize_rosetta_meta(obj_to_use["meta"]))

            obj_clean = {k: v for k, v in obj_to_use.items() if not k.startswith("@") and k != "meta"}

            rune_cls = cls._type_to_cls(metadata) if hasattr(cls, "_type_to_cls") else cls
            if rune_cls != cls and not issubclass(rune_cls, cls):
                raise ValueError(f"{rune_cls} has to be a child class of {cls}!")

            model = rune_cls.model_validate(obj_clean)
            model.__dict__[rmeta.META_CONTAINER] = metadata
            if cls.meta_checks_enabled():
                model._init_meta(allowed_meta)
            model._register_keys(metadata)
            return model
        return orig_complex_deserialize.__func__(cls, obj, allowed_meta)

    def _format_ref_dict(ref_obj: Any) -> dict[str, Any]:
        if isinstance(ref_obj, rmeta.UnresolvedReference):
            return {ref_obj.key_type.rune_ref_tag: ref_obj.key}
        if isinstance(ref_obj, rmeta.Reference):
            return {ref_obj.key_type.rune_ref_tag: ref_obj.target_key}
        return {}

    def _complex_serialise_fn(cls: Any, obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_complex_serialise_fn(cls, item) for item in obj]
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, (rmeta.UnresolvedReference, rmeta.Reference, rmeta.BaseReference)):
            return _format_ref_dict(obj)
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
                elif isinstance(item, dict):
                    if ref := cls._create_unresolved_ref(item):
                        item = ref
                    else:
                        meta_dict: dict[str, Any] = {}
                        if "meta" in item and isinstance(item["meta"], dict):
                            meta_dict.update(_normalize_rosetta_meta(item["meta"]))
                        for k, v in item.items():
                            if k.startswith("@") and k != "@data":
                                meta_dict[k] = v
                        d_val = item.get("@data") if "@data" in item else item.get("value")
                        item = cls(d_val)
                        item.__dict__[rmeta.META_CONTAINER] = meta_dict
                    if cls.meta_checks_enabled() and hasattr(item, "_init_meta"):
                        item._init_meta(allowed_meta)
                deserialized_list.append(item)
            return handler(deserialized_list)
        if isinstance(obj, base_types) and not isinstance(obj, cls):
            model = cls(obj)
        elif isinstance(obj, dict):
            if ref := cls._create_unresolved_ref(obj):
                return handler(ref)
            meta_dict = {}
            if "meta" in obj and isinstance(obj["meta"], dict):
                meta_dict.update(_normalize_rosetta_meta(obj["meta"]))
            for k, v in obj.items():
                if k.startswith("@") and k != "@data":
                    meta_dict[k] = v
            d_val = obj.get("@data") if "@data" in obj else obj.get("value")
            model = cls(d_val)
            model.__dict__[rmeta.META_CONTAINER] = meta_dict
            model._register_keys(meta_dict)
        else:
            model = obj
        if cls.meta_checks_enabled() and hasattr(model, "_init_meta"):
            model._init_meta(allowed_meta)
        return handler(model)

    def _basic_serialise_fn(cls: Any, obj: Any, base_type: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_basic_serialise_fn(cls, item, base_type) for item in obj]
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, (rmeta.UnresolvedReference, rmeta.Reference, rmeta.BaseReference)):
            return _format_ref_dict(obj)
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
        if isinstance(obj, str) and not isinstance(obj, rmeta._EnumWrapper):
            return rmeta._EnumWrapper(cls(obj))
        if isinstance(obj, rmeta.EnumWithMetaMixin) and not isinstance(obj, rmeta._EnumWrapper):
            return rmeta._EnumWrapper(obj)
        if isinstance(obj, dict):
            if ref := cls._create_unresolved_ref(obj):
                return ref
            meta_dict = {}
            if "meta" in obj and isinstance(obj["meta"], dict):
                meta_dict.update(_normalize_rosetta_meta(obj["meta"]))
            for k, v in obj.items():
                if k.startswith("@") and k != "@data":
                    meta_dict[k] = v
            d_val = obj.get("@data") if "@data" in obj else obj.get("value")
            model = rmeta._EnumWrapper(cls(d_val))
            model.__dict__[rmeta.META_CONTAINER] = meta_dict
            model._register_keys(meta_dict)
            if rmeta._EnumWrapper.meta_checks_enabled():
                model._init_meta(allowed_meta)
            return model
        return orig_enum_deserialize.__func__(cls, obj, allowed_meta)

    def _enum_serialise_fn(cls: Any, obj: Any, handler: Callable[[Any, Any], Any], info: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [_enum_serialise_fn(cls, item, handler, info) for item in obj]
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, (rmeta.UnresolvedReference, rmeta.Reference, rmeta.BaseReference)):
            return _format_ref_dict(obj)
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
