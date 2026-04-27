"""YAML config loader with environment variable override support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(
    config_path: str | Path | None = None,
    defaults_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load config with layered override precedence.

    Precedence (highest last):
        1. defaults from configs/default.yaml
        2. exchange-specific config
        3. environment variables (ACTOSHA_* prefix)
        4. runtime kwargs
    """
    config: dict[str, Any] = {}

    # 1. Defaults
    if defaults_path is None:
        defaults_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    if Path(defaults_path).exists():
        with open(defaults_path) as f:
            config = yaml.safe_load(f) or {}

    # 2. User config override
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            user = yaml.safe_load(f) or {}
            _deep_merge(config, user)

    # 3. Environment variable overrides (ACTOSHA_*)
    config = _apply_env_overrides(config)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, overriding existing keys."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Override config values with ACTOSHA_* environment variables."""
    prefix = "ACTOSHA_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        # Convert ACTOSHA_DATA_CACHE_DIR → data.cache_dir
        subkeys = key[len(prefix) :].lower().split("_")
        _set_nested(config, subkeys, value)
    return config


def _set_nested(d: dict, keys: list[str], value: Any) -> None:
    """Set a nested dict key, creating intermediate dicts as needed."""
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


__all__ = ["load_config"]