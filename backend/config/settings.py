"""
Configuration management for AutoAltText backend.

This module handles loading and merging configuration from:
- config.json (basic settings: LLM, logging, prompts, languages)
- config.advanced.json (advanced settings: folders, scraping, context extraction)
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Get the project root directory (parent of backend)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = Path(__file__).parent / "config.json"
CONFIG_ADVANCED_FILE = Path(__file__).parent / "config.advanced.json"

# Global configuration dictionary
_config: Dict[str, Any] = {}
_debug_mode: bool = True


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries. Override values take precedence.

    Args:
        base: Base dictionary
        override: Dictionary with values to override

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _deep_merge(result[key], value)
        else:
            # Override value
            result[key] = value

    return result


def load_config(config_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load and merge configuration from JSON files.

    Loads both config.json (basic) and config.advanced.json (advanced),
    then merges them with basic config taking precedence for overlapping keys.

    Args:
        config_file: Path to basic config file (defaults to backend/config/config.json)

    Returns:
        Dictionary containing merged configuration

    Raises:
        FileNotFoundError: If basic config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    global _config, _debug_mode

    if config_file is None:
        config_file = CONFIG_FILE

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    # Load basic configuration
    with open(config_file, 'r', encoding='utf-8') as f:
        basic_config = json.load(f)

    # Load advanced configuration (if exists)
    advanced_config = {}
    if CONFIG_ADVANCED_FILE.exists():
        try:
            with open(CONFIG_ADVANCED_FILE, 'r', encoding='utf-8') as f:
                advanced_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load advanced config: {e}")

    # Merge configurations: advanced first, then override with basic
    _config = _deep_merge(advanced_config, basic_config)

    _debug_mode = _config.get('debug_mode', True)

    return _config


def get_config() -> Dict[str, Any]:
    """
    Get the current configuration dictionary.

    Returns:
        Configuration dictionary
    """
    if not _config:
        load_config()
    return _config


def get(key: str, default: Any = None) -> Any:
    """
    Get a configuration value by key.

    Args:
        key: Configuration key
        default: Default value if key doesn't exist

    Returns:
        Configuration value or default
    """
    config = get_config()
    return config.get(key, default)


def get_nested(path: str, default: Any = None) -> Any:
    """
    Get a nested configuration value using dot notation.

    Args:
        path: Dot-separated path (e.g., 'folders.images')
        default: Default value if path doesn't exist

    Returns:
        Configuration value or default

    Example:
        >>> get_nested('folders.images')
        'input/images'
    """
    config = get_config()
    keys = path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default

        if value is None:
            return default

    return value


def get_folder_path(folder_name: str) -> Path:
    """
    Get absolute path for a configured folder.

    Args:
        folder_name: Name of the folder (e.g., 'images', 'alt_text', 'reports')

    Returns:
        Absolute path to the folder

    Example:
        >>> get_folder_path('images')
        Path('/home/developer/AutoAltText/input/images')
    """
    # First check main folders
    folder_config = get_nested('folders', {})
    relative_path = folder_config.get(folder_name)

    # If not found, check testing.folders
    if relative_path is None:
        test_folders = get_nested('testing.folders', {})
        relative_path = test_folders.get(folder_name, folder_name)

    return PROJECT_ROOT / relative_path


def is_debug_mode() -> bool:
    """
    Check if debug mode is enabled.

    Returns:
        True if debug mode is enabled
    """
    if not _config:
        load_config()
    return _debug_mode


# Configuration property getters for common settings

@property
def llm_provider() -> str:
    """Get the configured LLM provider (OpenAI or ECB-LLM)."""
    return get('llm_provider', 'OpenAI')


@property
def model() -> str:
    """Get the configured model name."""
    return get('model', 'gpt-4o')


@property
def folders() -> Dict[str, str]:
    """Get all configured folder paths."""
    return get('folders', {})


@property
def languages() -> Dict[str, Any]:
    """Get language configuration."""
    return get('languages', {})


# Initialize configuration on module import
try:
    load_config()
except Exception as e:
    print(f"Warning: Could not load configuration: {e}")
    print(f"Looking for config at: {CONFIG_FILE}")
