"""Configuration module for AutoAltText backend."""

from .settings import (
    load_config,
    get_config,
    get,
    get_nested,
    get_folder_path,
    is_debug_mode,
    PROJECT_ROOT,
    CONFIG_FILE
)

__all__ = [
    'load_config',
    'get_config',
    'get',
    'get_nested',
    'get_folder_path',
    'is_debug_mode',
    'PROJECT_ROOT',
    'CONFIG_FILE'
]
