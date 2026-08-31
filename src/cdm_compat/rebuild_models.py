"""
CDM Model Schema Synchronization and Rebuilding (cdm_compat.rebuild_models).

Provides utilities to rebuild Pydantic v2 core schemas for standalone FINOS CDM models
not covered by finos._bundle's internal Phase 3 rebuild order (e.g. InterestRateIndex).
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Type

from pydantic import BaseModel
from rune.runtime.base_data_class import BaseDataClass

if TYPE_CHECKING:
    from .config import CdmCompatConfig

logger = logging.getLogger(__name__)

_MODELS_REBUILT = False

# Known standalone models outside finos._bundle that benefit from explicit rebuild
_STANDALONE_MODEL_MODULES = [
    ("finos.cdm.observable.asset.InterestRateIndex", "InterestRateIndex"),
]


def get_bundle_namespace() -> Dict[str, Any]:
    """Retrieves the full type dictionary of finos._bundle if available."""
    try:
        import finos._bundle

        return finos._bundle.__dict__
    except ImportError:
        return {}


def sync_parent_fields(cls: Type[BaseModel]) -> bool:
    """
    Legacy utility: Inspects all base classes in `cls.__mro__`. For any base class that is a BaseModel
    (excluding root BaseModel and BaseDataClass), restores any fields that degenerated
    into NoneType annotations in the subclass.

    Note: With rune-python-generator PR #265 (Phase 2), field annotations are properly
    updated in _bundle.py, making this utility obsolete in normal operation.

    Parameters:
        cls: The Pydantic model subclass to repair.

    Returns:
        bool: True if fields were synced or updated.
    """
    if not issubclass(cls, BaseModel) or cls in (BaseModel, BaseDataClass):
        return False

    updated = False
    for base in cls.__mro__[1:]:
        if issubclass(base, BaseModel) and base not in (BaseModel, BaseDataClass) and hasattr(base, "model_fields"):
            for field_name, field_info in base.model_fields.items():
                child_field = cls.model_fields.get(field_name)
                if child_field is None or child_field.annotation in (None, type(None)):
                    cls.model_fields[field_name] = field_info
                    updated = True
                    logger.debug(
                        "Synced field '%s' from parent '%s' to child '%s'",
                        field_name,
                        base.__name__,
                        cls.__name__,
                    )
    return updated


def rebuild_cdm_model(
    cls: Type[BaseModel],
    force: bool = True,
    types_namespace: Optional[Dict[str, Any]] = None,
    sync_parents: bool = True,
) -> None:
    """
    Repairs and rebuilds any FINOS CDM Pydantic model core schema.

    Parameters:
        cls: The model class to rebuild.
        force: Whether to force rebuilding core validator schemas.
        types_namespace: Optional dictionary of types. Defaults to finos._bundle.__dict__.
        sync_parents: Whether to run sync_parent_fields. Defaults to True.
    """
    if not issubclass(cls, BaseModel) or cls in (BaseModel, BaseDataClass):
        return

    if types_namespace is None:
        types_namespace = get_bundle_namespace()

    if sync_parents:
        sync_parent_fields(cls)

    try:
        cls.model_rebuild(force=force, _types_namespace=types_namespace)
        logger.debug("Successfully rebuilt model '%s'", cls.__name__)
    except Exception as exc:
        logger.warning("Could not rebuild model '%s': %s", cls.__name__, exc)


def rebuild_cdm_models(*classes: Type[BaseModel]) -> None:
    """
    Rebuilds multiple CDM models.

    Parameters:
        *classes: Variable list of BaseModel subclasses to rebuild.
    """
    for cls in classes:
        rebuild_cdm_model(cls)


def rebuild_standalone_models() -> int:
    """
    Rebuilds standalone CDM models outside finos._bundle (e.g. InterestRateIndex).

    Returns:
        int: Number of rebuilt standalone models.
    """
    rebuilt_count = 0
    ns = get_bundle_namespace()

    for mod_path, class_name in _STANDALONE_MODEL_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, class_name, None)
            if cls is not None and issubclass(cls, BaseModel):
                rebuild_cdm_model(cls, types_namespace=ns)
                rebuilt_count += 1
        except Exception as exc:
            logger.debug("Could not import/rebuild standalone model %s: %s", class_name, exc)

    return rebuilt_count


def rebuild_all_cdm_models(sync_parents: bool = False) -> int:
    """
    Legacy utility: Discovers and rebuilds all CDM model classes across the entire finos._bundle.
    Note: In modern rune-runtime (PR #265), finos._bundle automatically executes
    topological model_rebuild on import.

    Returns:
        int: Number of rebuilt CDM models.
    """
    try:
        import finos._bundle
    except ImportError:
        logger.warning("finos._bundle could not be imported; skipping bulk rebuild.")
        return 0

    rebuilt_count = 0
    ns = finos._bundle.__dict__
    for name in dir(finos._bundle):
        obj = getattr(finos._bundle, name)
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj not in (BaseModel, BaseDataClass):
            rebuild_cdm_model(obj, types_namespace=ns, sync_parents=sync_parents)
            rebuilt_count += 1

    logger.debug("Rebuilt %d CDM models across finos._bundle.", rebuilt_count)
    return rebuilt_count


def rebuild_standard_models(config: Optional[CdmCompatConfig] = None) -> bool:
    """
    Rebuilds required CDM models according to configuration.
    Safe and idempotent.

    Args:
        config: Optional configuration instance. Defaults to cdm_compat.get_config().

    Returns:
        bool: True if models were rebuilt.
    """
    global _MODELS_REBUILT
    if _MODELS_REBUILT:
        return False

    if config is None:
        from .config import get_config

        config = get_config()

    rebuilt = False

    # 1. Rebuild standalone models (InterestRateIndex, etc.)
    if config.rebuild_standalone_models:
        standalone_count = rebuild_standalone_models()
        rebuilt = rebuilt or (standalone_count > 0)

    # 2. Legacy: Rebuild all bundle models if explicitly enabled
    if config.rebuild_all_bundle_models:
        bundle_count = rebuild_all_cdm_models(sync_parents=config.sync_parent_fields)
        rebuilt = rebuilt or (bundle_count > 0)

    _MODELS_REBUILT = True
    return rebuilt
