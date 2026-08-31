"""
Configuration management for cdm_compat.

Allows granular control over which monkey patches, metadata converters,
and model rebuilding utilities are activated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CdmCompatConfig:
    """
    Configuration flags for cdm_compat runtime patches.

    Attributes:
        patch_rune_all_elements: Fix scalar RHS comparisons in rune.runtime.utils.rune_all_elements.
        patch_metadata_mixins: Support Rosetta JSON metadata formats (@key, globalKey, FieldWithMeta).
        patch_rosetta_function_types: Resolve cross-module Rosetta DSL function calls in builtins/globals.
        patch_func_proxy_call: Bypass Pydantic @validate_call revalidation overhead in FuncProxy.
        rebuild_standalone_models: Automatically rebuild standalone CDM models (e.g. InterestRateIndex).
        sync_parent_fields: Legacy flag - synchronize parent fields in MRO (obsoleted by PR #265).
        rebuild_all_bundle_models: Legacy flag - rebuild all 300+ classes in finos._bundle (obsoleted by PR #265).
    """

    patch_rune_all_elements: bool = True
    patch_metadata_mixins: bool = True
    patch_rosetta_function_types: bool = True
    patch_func_proxy_call: bool = True
    rebuild_standalone_models: bool = True
    sync_parent_fields: bool = False
    rebuild_all_bundle_models: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CdmCompatConfig:
        """Create configuration instance from dictionary, ignoring unknown keys."""
        valid_keys = {
            "patch_rune_all_elements",
            "patch_metadata_mixins",
            "patch_rosetta_function_types",
            "patch_func_proxy_call",
            "rebuild_standalone_models",
            "sync_parent_fields",
            "rebuild_all_bundle_models",
        }
        filtered = {k: bool(v) for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


_CURRENT_CONFIG: Optional[CdmCompatConfig] = None


def find_default_config_file() -> Optional[Path]:
    """Searches for cdm_compat.json in standard workspace locations."""
    # 1. Environment variable
    env_path = os.environ.get("CDM_COMPAT_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # 2. Current working directory
    cwd_path = Path.cwd() / "cdm_compat.json"
    if cwd_path.is_file():
        return cwd_path

    # 3. Project root (parent of src)
    module_dir = Path(__file__).resolve().parent
    for parent in [module_dir.parent.parent, module_dir.parent]:
        candidate = parent / "cdm_compat.json"
        if candidate.is_file():
            return candidate

    return None


def _apply_env_overrides(config: CdmCompatConfig) -> CdmCompatConfig:
    """Applies environment variable overrides of the form CDM_COMPAT_<PATCH_NAME>."""
    cfg_dict = config.to_dict()
    for key in list(cfg_dict.keys()):
        env_var = f"CDM_COMPAT_{key.upper()}"
        if env_var in os.environ:
            raw_val = os.environ[env_var].strip().lower()
            cfg_dict[key] = raw_val in ("1", "true", "yes", "on")
    return CdmCompatConfig.from_dict(cfg_dict)


def load_config(config_path: Optional[Path | str] = None) -> CdmCompatConfig:
    """
    Loads configuration from file, environment variables, or defaults.

    Priority:
        1. Explicitly passed config_path
        2. File pointed to by CDM_COMPAT_CONFIG environment variable
        3. cdm_compat.json in current working directory or workspace root
        4. Environment variable overrides (CDM_COMPAT_<NAME>)
        5. Built-in defaults
    """
    file_to_read: Optional[Path] = None

    if config_path is not None:
        file_to_read = Path(config_path)
    else:
        file_to_read = find_default_config_file()

    config_data: dict[str, Any] = {}
    if file_to_read and file_to_read.is_file():
        try:
            with open(file_to_read, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            logger.debug("Loaded cdm_compat configuration from %s", file_to_read)
        except Exception as exc:
            logger.warning("Failed to parse config file %s: %s", file_to_read, exc)

    base_config = CdmCompatConfig.from_dict(config_data)
    final_config = _apply_env_overrides(base_config)
    return final_config


def get_config() -> CdmCompatConfig:
    """Gets the currently active configuration, loading defaults if not set."""
    global _CURRENT_CONFIG
    if _CURRENT_CONFIG is None:
        _CURRENT_CONFIG = load_config()
    return _CURRENT_CONFIG


def set_config(config: CdmCompatConfig) -> None:
    """Sets the active configuration."""
    global _CURRENT_CONFIG
    _CURRENT_CONFIG = config
