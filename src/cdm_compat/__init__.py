"""
CDM Compatibility Package (cdm_compat)

Provides runtime compatibility patches, configuration management, and model rebuilding
utilities for FINOS CDM (v6.22.0+ / v6.99.99+ / v7.x) running on Rune 2.0.1+ and Pydantic v2.

Usage:
    # Simply importing cdm_compat automatically applies all required patches from cdm_compat.json / defaults:
    import cdm_compat
    from finos.cdm.event.common.Trade import Trade

    # Or configure patches explicitly:
    import cdm_compat
    cdm_compat.configure(patch_rune_all_elements=True, patch_metadata_mixins=True)
"""

from __future__ import annotations

from typing import Optional

from .config import CdmCompatConfig, get_config, load_config, set_config
from .patch_functions import apply_function_patches, patch_func_proxy_call, patch_rosetta_function_types, patch_rune_all_elements
from .patch_metadata import apply_metadata_patches, resolve_model_references
from .rebuild_models import (
    rebuild_all_cdm_models,
    rebuild_cdm_model,
    rebuild_cdm_models,
    rebuild_standalone_models,
    rebuild_standard_models,
    sync_parent_fields,
)

__all__ = [
    # Patching
    "apply_patches",
    "apply_metadata_patches",
    "apply_function_patches",
    "resolve_model_references",
    "patch_rune_all_elements",
    "patch_rosetta_function_types",
    "patch_func_proxy_call",
    # Model rebuilding
    "rebuild_all_cdm_models",
    "rebuild_standard_models",
    "rebuild_standalone_models",
    "rebuild_cdm_model",
    "rebuild_cdm_models",
    "sync_parent_fields",
    # Configuration
    "CdmCompatConfig",
    "get_config",
    "set_config",
    "load_config",
    "configure",
    "is_patched",
    "reset_patches",
]

_PATCHES_APPLIED = False


def is_patched() -> bool:
    """Returns True if the runtime compatibility patches have been applied."""
    return _PATCHES_APPLIED


def reset_patches() -> None:
    """Resets patch tracking state (primarily for testing purposes)."""
    global _PATCHES_APPLIED
    _PATCHES_APPLIED = False
    import cdm_compat.patch_functions as pf
    import cdm_compat.patch_metadata as pm
    import cdm_compat.rebuild_models as rm

    pf._FUNCTIONS_PATCHED = False
    pm._METADATA_PATCHED = False
    rm._MODELS_REBUILT = False


def apply_patches(config: Optional[CdmCompatConfig] = None) -> bool:
    """
    Applies configured metadata patches, function patches, and model rebuilds.
    Idempotent: safe to call multiple times.

    Args:
        config: Optional configuration instance. Defaults to cdm_compat.get_config().

    Returns:
        bool: True if patches were freshly applied, False if already applied.
    """
    global _PATCHES_APPLIED
    if _PATCHES_APPLIED:
        return False

    if config is None:
        config = get_config()
    else:
        set_config(config)

    meta_ok = apply_metadata_patches(config)
    func_ok = apply_function_patches(config)
    models_ok = rebuild_standard_models(config)

    _PATCHES_APPLIED = True
    return meta_ok or func_ok or models_ok


def configure(config_path: Optional[str] = None, **kwargs: bool) -> CdmCompatConfig:
    """
    Configures and reapplies cdm_compat patches with specified flags.

    Args:
        config_path: Optional path to a JSON configuration file.
        **kwargs: Configuration flags (e.g. patch_rune_all_elements=True, etc.).

    Returns:
        CdmCompatConfig: The active configuration.
    """
    if config_path is not None:
        cfg = load_config(config_path)
    else:
        cfg = get_config()

    if kwargs:
        current_dict = cfg.to_dict()
        current_dict.update(kwargs)
        cfg = CdmCompatConfig.from_dict(current_dict)

    set_config(cfg)
    reset_patches()
    apply_patches(cfg)
    return cfg


# Automatically apply patches upon importing cdm_compat using active configuration
apply_patches()
