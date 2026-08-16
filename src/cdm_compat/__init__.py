"""
CDM Compatibility Package (cdm_compat)

Provides runtime compatibility patches and model rebuilding utilities for FINOS CDM
(v6.22.0+ / v7.x) running on Rune 2.0.1+ and Pydantic v2.

Usage:
    # Simply importing cdm_compat automatically applies all required patches and rebuilds all models:
    import cdm_compat
    from finos.cdm.event.common.Trade import Trade
"""

from __future__ import annotations

from .patch_metadata import apply_metadata_patches
from .rebuild_models import (
    rebuild_all_cdm_models,
    rebuild_cdm_model,
    rebuild_cdm_models,
    rebuild_standard_models,
    sync_parent_fields,
)

__all__ = [
    "apply_patches",
    "apply_metadata_patches",
    "rebuild_all_cdm_models",
    "rebuild_standard_models",
    "rebuild_cdm_model",
    "rebuild_cdm_models",
    "sync_parent_fields",
    "is_patched",
]

_PATCHES_APPLIED = False


def is_patched() -> bool:
    """Returns True if the runtime compatibility patches have been applied."""
    return _PATCHES_APPLIED


def apply_patches() -> bool:
    """
    Applies all metadata patches and rebuilds all CDM models.
    Idempotent: safe to call multiple times.

    Returns:
        bool: True if patches were freshly applied, False if already applied.
    """
    global _PATCHES_APPLIED
    if _PATCHES_APPLIED:
        return False

    meta_ok = apply_metadata_patches()
    models_ok = rebuild_standard_models()

    _PATCHES_APPLIED = True
    return meta_ok or models_ok


# Automatically apply patches upon importing cdm_compat
apply_patches()
