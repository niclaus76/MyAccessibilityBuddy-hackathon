import requests
import os
import sys
import argparse
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import base64
from mimetypes import guess_type
from openai import OpenAI

# Store startup messages to log after logging system is initialized
STARTUP_MESSAGES = []

# Import ECB-LLM client if available
try:
    from ecb_llm_client import CredentialManager, ECBAzureOpenAI
    cm = CredentialManager()
    cm.set_credentials()
    ECB_LLM_AVAILABLE = True
except ImportError:
    ECB_LLM_AVAILABLE = False
    # Note: Warning message will be conditionally added based on config.ecb_llm.enabled setting

# Import SVG conversion library if available
try:
    import cairosvg
    import io
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
    STARTUP_MESSAGES.append(("WARNING", "cairosvg not installed. SVG files will not be supported."))
    STARTUP_MESSAGES.append(("INFO", "To enable SVG support, install with: pip install cairosvg"))

# Import Ollama client if available
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    # Note: Warning message will be conditionally added based on config.ollama.enabled setting

# Import Google GenAI (Gemini) client if available (prefer new google.genai, fallback to deprecated google.generativeai)
genai = None
try:
    import importlib
    import warnings

    try:
        genai = importlib.import_module("google.genai")
    except ImportError:
        genai = importlib.import_module("google.generativeai")
        # Silence deprecation warning when falling back
        warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    # Note: Warning message will be conditionally added based on config if enabled

# Helper to configure Gemini client across library versions
def configure_gemini(api_key):
    """
    Configure the Gemini client, supporting both google.genai and google.generativeai.

    Some environments have a legacy module without `configure`; this helper falls back
    to google.generativeai when needed.
    """
    global genai, GEMINI_AVAILABLE
    if not GEMINI_AVAILABLE:
        debug_log("Google Gemini client not installed. Install google-genai or google-generativeai.", "ERROR")
        return False

    try:
        if hasattr(genai, "configure"):
            genai.configure(api_key=api_key)
            return True

        # Fallback: try legacy google.generativeai
        import importlib
        legacy_genai = importlib.import_module("google.generativeai")
        legacy_genai.configure(api_key=api_key)
        genai = legacy_genai
        return True
    except Exception as e:
        debug_log(f"Failed to configure Gemini client: {e}", "ERROR")
        return False

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    STARTUP_MESSAGES.append(("INFO", "Loaded environment variables from .env file"))
except ImportError:
    STARTUP_MESSAGES.append(("WARNING", "python-dotenv not installed. Using system environment variables only."))
    STARTUP_MESSAGES.append(("INFO", "To use .env files, install with: pip install python-dotenv"))

# Import configuration management
from config import settings as config_settings

# Global configuration (for backward compatibility)
CONFIG = {}
DEBUG_MODE = True
CURRENT_LOG_FILE = None  # Track current log file for this session
LOG_START_TIME = None  # Track when the log session started
CURRENT_SESSION_LOGS = None  # Track session-specific logs folder when available

def get_cet_time():
    """Get current time in CET (Central European Time) timezone."""
    return datetime.now(ZoneInfo("Europe/Paris"))

def load_config(config_file=None):
    """Load configuration from JSON file with error handling."""
    global CONFIG, DEBUG_MODE, STARTUP_MESSAGES
    try:
        # Use new config module
        if config_file is None:
            CONFIG = config_settings.get_config()
        else:
            # Support legacy config file path
            from pathlib import Path
            CONFIG = config_settings.load_config(Path(config_file))

        DEBUG_MODE = CONFIG.get('debug_mode', True)
        debug_log(f"Configuration loaded from {config_settings.CONFIG_FILE}")

        # Add provider warnings if enabled but not available
        ecb_llm_enabled = CONFIG.get('ecb_llm', {}).get('enabled', True)  # Default True for backward compatibility
        if ecb_llm_enabled and not ECB_LLM_AVAILABLE:
            STARTUP_MESSAGES.append(("WARNING", "ecb_llm_client not installed. ECB-LLM provider will not be available."))
            STARTUP_MESSAGES.append(("INFORMATION", "To use ECB-LLM, install with: pip install ecb_llm_client"))

        ollama_enabled = CONFIG.get('ollama', {}).get('enabled', True)  # Default True for backward compatibility
        if ollama_enabled and not OLLAMA_AVAILABLE:
            STARTUP_MESSAGES.append(("WARNING", "ollama not installed. Ollama provider will not be available."))
            STARTUP_MESSAGES.append(("INFORMATION", "To use Ollama, install with: pip install ollama"))

        gemini_enabled = CONFIG.get('gemini', {}).get('enabled', True)  # Default True
        if gemini_enabled and not GEMINI_AVAILABLE:
            STARTUP_MESSAGES.append(("WARNING", "google-generativeai not installed. Gemini provider will not be available."))
            STARTUP_MESSAGES.append(("INFORMATION", "To use Gemini, install with: pip install google-generativeai"))

        # Output deferred startup messages now that logging is initialized
        for level, message in STARTUP_MESSAGES:
            log_message(message, level)
        STARTUP_MESSAGES = []  # Clear after logging

    except Exception as e:
        CONFIG = {}
        DEBUG_MODE = True
        debug_log(f"Error loading configuration: {str(e)}, using defaults")

def get_max_chars(use_geo_boost: bool = False) -> int:
    """
    Calculate max character limit for alt-text based on GEO boost setting.

    Args:
        use_geo_boost: Whether GEO boost is enabled

    Returns:
        int: Maximum character limit (base limit or boosted limit)
    """
    base_limit = CONFIG.get('alt_text_max_chars', 125)
    if use_geo_boost:
        increase_percent = CONFIG.get('geo_boost_increase_percent', 20)
        return int(base_limit * (1 + increase_percent / 100))
    return base_limit

def initialize_log_file(url=None):
    """
    Initialize a log file for the current session.

    Args:
        url: Optional URL to include in the log filename

    Returns:
        Path to the created log file or None if logging is disabled
    """
    global CURRENT_LOG_FILE, LOG_START_TIME

    if not DEBUG_MODE:
        return None

    try:
        # Get logs folder path (prefer session-specific if set)
        logs_folder = CURRENT_SESSION_LOGS if CURRENT_SESSION_LOGS else get_absolute_folder_path('logs')

        # Create logs directory if it doesn't exist
        os.makedirs(logs_folder, exist_ok=True)

        # Store start time in CET
        LOG_START_TIME = get_cet_time()
        timestamp = LOG_START_TIME.strftime("%Y%m%d_%H%M%S")

        if url:
            # Sanitize URL for filename (remove protocol, special chars)
            parsed = urlparse(url)
            sanitized_url = parsed.netloc or parsed.path
            # Replace non-alphanumeric chars with underscore
            sanitized_url = re.sub(r'[^\w\-_.]', '_', sanitized_url)
            # Limit length to avoid filesystem issues
            sanitized_url = sanitized_url[:50]
            filename = f"{timestamp}_{sanitized_url}.log"
        else:
            filename = f"{timestamp}_session.log"

        log_path = os.path.join(logs_folder, filename)
        CURRENT_LOG_FILE = log_path

        # Create log file with header
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"=== MyAccessibilityBuddy Log ===\n")
            f.write(f"Start Time: {LOG_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if url:
                f.write(f"URL: {url}\n")
                # Add page name (sanitized URL from filename)
                f.write(f"Page: {sanitized_url}\n")
            f.write(f"{'='*50}\n\n")

        return log_path
    except Exception as e:
        print(f"Warning: Could not initialize log file: {e}")
        CURRENT_LOG_FILE = None
        LOG_START_TIME = None
        return None

def log_message(message, level="INFORMATION"):
    """
    Universal logging function that always prints with timestamp and category.

    Args:
        message: The message to log
        level: Log level - must be one of: DEBUG, INFORMATION, WARNING, ERROR
               Legacy levels (INFO, PROGRESS, SUCCESS) are automatically mapped to INFORMATION
               - DEBUG, INFORMATION: Controlled by show_information
               - WARNING: Controlled by show_warnings
               - ERROR: Controlled by show_errors
    """
    # Normalize legacy level names to the 4 standard categories
    level_mapping = {
        "INFO": "INFORMATION",
        "PROGRESS": "INFORMATION",
        "SUCCESS": "INFORMATION"
    }
    level = level_mapping.get(level, level)

    timestamp = get_cet_time().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {level}: {message}"

    # Determine if message should be printed to console based on config
    should_print = True  # Default to showing

    if level in ["DEBUG", "INFORMATION"]:
        should_print = CONFIG.get('logging', {}).get('show_information', False)
    elif level == "WARNING":
        should_print = CONFIG.get('logging', {}).get('show_warnings', True)
    elif level == "ERROR":
        should_print = CONFIG.get('logging', {}).get('show_errors', True)

    if should_print:
        print(log_line)

    # Write to log file if debug mode is enabled and file is initialized
    if DEBUG_MODE and CURRENT_LOG_FILE:
        try:
            with open(CURRENT_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except Exception as e:
            print(f"[{timestamp}] WARNING: Could not write to log file: {e}")

def debug_log(message, level="DEBUG"):
    """
    Debug logging function - wrapper around log_message for backward compatibility.
    Only logs when DEBUG_MODE is enabled.
    """
    if DEBUG_MODE:
        log_message(message, level)


# Global variable to store progress file path (set from CLI args)
PROGRESS_FILE_PATH = None


def write_progress(percent, message, phase=None, current_image=None, total_images=None):
    """
    Write progress update to a JSON file for async API polling.

    Args:
        percent (int): Progress percentage (0-100)
        message (str): Human-readable status message
        phase (str): Current phase (e.g., 'downloading', 'processing', 'generating')
        current_image (int): Current image number being processed
        total_images (int): Total number of images to process
    """
    global PROGRESS_FILE_PATH

    if not PROGRESS_FILE_PATH:
        return  # No progress file configured, skip

    try:
        import json
        progress_data = {
            "percent": percent,
            "message": message,
            "timestamp": get_cet_time().isoformat()
        }

        if phase:
            progress_data["phase"] = phase
        if current_image is not None:
            progress_data["current_image"] = current_image
        if total_images is not None:
            progress_data["total_images"] = total_images

        # Write atomically by writing to temp file first
        temp_file = PROGRESS_FILE_PATH + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)

        # Rename to final file (atomic on most systems)
        import shutil
        shutil.move(temp_file, PROGRESS_FILE_PATH)

    except Exception as e:
        # Don't let progress reporting errors break the main process
        debug_log(f"Failed to write progress: {e}", "WARNING")


def close_log_file():
    """Close the current log file and add footer with duration."""
    global CURRENT_LOG_FILE, LOG_START_TIME

    if CURRENT_LOG_FILE and os.path.exists(CURRENT_LOG_FILE):
        try:
            end_time = get_cet_time()

            # Calculate duration
            duration = None
            duration_str = "Unknown"
            if LOG_START_TIME:
                duration = end_time - LOG_START_TIME
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                if hours > 0:
                    duration_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_str = f"{minutes}m {seconds}s"
                else:
                    duration_str = f"{seconds}s"

            with open(CURRENT_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Duration: {duration_str}\n")
                f.write(f"=== End of Log ===\n")
        except Exception as e:
            log_message(f"Could not close log file: {e}", "WARNING")

    CURRENT_LOG_FILE = None
    LOG_START_TIME = None

def handle_exception(func_name, exception, context=""):
    """Centralized exception handling with debug logging."""
    error_msg = f"Error in {func_name}: {str(exception)}"
    if context:
        error_msg += f" (Context: {context})"
    
    debug_log(error_msg, "ERROR")
    
    # Log common exceptions with specific messages
    if isinstance(exception, requests.exceptions.RequestException):
        debug_log(f"Network error: Check internet connection and URL validity", "ERROR")
    elif isinstance(exception, FileNotFoundError):
        debug_log(f"File not found: {context}", "ERROR")
    elif isinstance(exception, PermissionError):
        debug_log(f"Permission denied: Check file/folder permissions for {context}", "ERROR")
    elif isinstance(exception, json.JSONDecodeError):
        debug_log(f"Invalid JSON format in file: {context}", "ERROR")
    
    return error_msg

def get_step_config(step_name):
    """
    Get provider and model configuration for a specific step (vision, processing, or translation).

    Args:
        step_name (str): Step name ('vision', 'processing', or 'translation')

    Returns:
        tuple: (provider, model, credentials_dict)
    """
    func_name = "get_step_config"

    # Get step configuration
    steps_config = CONFIG.get('steps', {})
    step_config = steps_config.get(step_name, {})
    provider = step_config.get('provider', 'OpenAI')
    model = step_config.get('model', 'gpt-4o')

    debug_log(f"Step '{step_name}' configured: provider={provider}, model={model}")

    # Get credentials for the provider
    credentials = {}

    if provider == 'OpenAI':
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            debug_log("OPENAI_API_KEY not found in environment variables", "ERROR")
            return None, None, None
        credentials = {'api_key': api_key}

    elif provider == 'Claude':
        api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('CLAUDE_API_KEY')
        if not api_key:
            debug_log("ANTHROPIC_API_KEY or CLAUDE_API_KEY not found in environment variables", "ERROR")
            return None, None, None
        credentials = {'api_key': api_key}

    elif provider == 'ECB-LLM':
        if not ECB_LLM_AVAILABLE:
            debug_log("ECB-LLM client not installed. Install with: pip install ecb_llm_client", "ERROR")
            return None, None, None

        client_id = os.environ.get('CLIENT_ID_U2A')
        client_secret = os.environ.get('CLIENT_SECRET_U2A')

        if not client_id or not client_secret:
            debug_log("CLIENT_ID_U2A or CLIENT_SECRET_U2A not found in environment variables", "ERROR")
            return None, None, None
        credentials = {'auth_mode': 'U2A'}

    elif provider == 'Ollama':
        if not OLLAMA_AVAILABLE:
            debug_log("Ollama client not installed. Install with: pip install ollama", "ERROR")
            return None, None, None

        ollama_config = CONFIG.get('ollama', {})
        base_url = ollama_config.get('base_url', 'http://localhost:11434')
        credentials = {'base_url': base_url}

    elif provider == 'Gemini':
        if not GEMINI_AVAILABLE:
            debug_log("Google Generative AI not installed. Install with: pip install google-generativeai", "ERROR")
            return None, None, None

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            debug_log("GEMINI_API_KEY not found in environment variables", "ERROR")
            return None, None, None
        # Defer configuration to helper for compatibility
        credentials = {'api_key': api_key}

    else:
        debug_log(f"Unknown provider: {provider}", "ERROR")
        return None, None, None

    return provider, model, credentials

def get_llm_credentials():
    """
    Retrieve LLM credentials based on the configured provider.
    DEPRECATED: Use get_step_config() for per-step provider selection.
    This function is maintained for backward compatibility.

    Returns:
        tuple: (provider, credentials_dict) where credentials_dict contains the necessary auth info
    """
    func_name = "get_llm_credentials"

    # For backward compatibility, use vision step config as default
    vision_provider, vision_model, credentials = get_step_config('vision')
    if not vision_provider:
        return None, None

    # Add model information to credentials
    processing_provider, processing_model, _ = get_step_config('processing')
    translation_provider, translation_model, _ = get_step_config('translation')

    credentials['vision_model'] = vision_model
    credentials['processing_model'] = processing_model if processing_model else vision_model
    credentials['translation_model'] = translation_model if translation_model else processing_model

    debug_log(f"LLM credentials (backward compat): provider={vision_provider}, vision={vision_model}, processing={processing_model}, translation={translation_model}")

    return vision_provider, credentials

def get_absolute_folder_path(folder_name):
    """
    Get absolute path for a configured folder.
    Converts relative paths from config.json to absolute paths based on project root.

    Args:
        folder_name (str): Name of the folder key in config (e.g., 'images', 'prompt')

    Returns:
        str: Absolute path to the folder
    """
    # Get folder path from config
    folders_config = CONFIG.get('folders', {})
    relative_path = folders_config.get(folder_name, folder_name)

    # If already absolute, return as-is
    if os.path.isabs(relative_path):
        return relative_path

    # Determine project root
    project_root_config = CONFIG.get('project_root', 'auto')

    if project_root_config == 'auto' or not project_root_config:
        # Auto-detect: project root is parent of backend directory
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(backend_dir)
    else:
        # Use custom project root from config
        project_root = project_root_config

    absolute_path = os.path.join(project_root, relative_path)

    debug_log(f"Resolved folder '{folder_name}': {relative_path} -> {absolute_path} (project_root: {project_root})")
    return absolute_path

# ============================================================================
# CLI Session Management Functions
# ============================================================================

def get_cli_session_folders(session_id=None, shared=False, legacy=False, required_keys=None):
    """
    Get CLI session-specific folder paths with backward compatibility.

    Args:
        session_id: Explicit session ID (cli-xxx format) or None for auto-detect
        shared: Use shared folder (input/images/shared, output/alt-text/shared)
        legacy: Use legacy flat structure (input/images, output/alt-text)
        required_keys: Optional list of folder keys to create (e.g., ['images']); defaults to all

    Returns:
        dict: Folder paths with keys 'images', 'context', 'alt_text', 'reports', 'session_id', 'mode'
    """
    import uuid

    # Determine mode
    if legacy:
        # Legacy mode: use base folders directly
        return {
            'images': get_absolute_folder_path('images'),
            'context': get_absolute_folder_path('context'),
            'alt_text': get_absolute_folder_path('alt_text'),
            'reports': get_absolute_folder_path('reports'),
            'logs': get_absolute_folder_path('logs'),
            'session_id': None,
            'mode': 'legacy'
        }

    if shared:
        # Shared mode: use shared subfolder
        base_images = get_absolute_folder_path('images')
        base_context = get_absolute_folder_path('context')
        base_alt_text = get_absolute_folder_path('alt_text')
        base_reports = get_absolute_folder_path('reports')

        folders = {
            'images': os.path.join(base_images, 'shared'),
            'context': os.path.join(base_context, 'shared'),
            'alt_text': os.path.join(base_alt_text, 'shared'),
            'reports': os.path.join(base_reports, 'shared'),
            'logs': os.path.join(get_absolute_folder_path('logs'), 'shared'),
            'session_id': 'shared',
            'mode': 'shared'
        }

        # Create folders
        for folder in folders.values():
            if isinstance(folder, str):
                os.makedirs(folder, exist_ok=True)

        return folders

    # Session mode: use session-specific folders
    root_folder = get_absolute_folder_path('root')
    os.makedirs(root_folder, exist_ok=True)

    if session_id is None:
        # Auto-detect or create new session
        session_file = os.path.join(root_folder, '.cli_session')
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                session_id = f.read().strip()
        else:
            # Create new session with datetime prefix
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            session_id = f"{timestamp}-{uuid.uuid4()}"
            with open(session_file, 'w') as f:
                f.write(session_id)

    # Get base folders
    base_images = get_absolute_folder_path('images')
    base_context = get_absolute_folder_path('context')
    base_alt_text = get_absolute_folder_path('alt_text')
    base_reports = get_absolute_folder_path('reports')

    # Create session-specific paths
    folders = {
        'images': os.path.join(base_images, session_id),
        'context': os.path.join(base_context, session_id),
        'alt_text': os.path.join(base_alt_text, session_id),
        'reports': os.path.join(base_reports, session_id),
        'logs': os.path.join(get_absolute_folder_path('logs'), session_id),
        'session_id': session_id,
        'mode': 'session'
    }

    # Create folders
    # Determine which folder keys to create on disk
    keys_to_create = [k for k in folders.keys() if k not in ['session_id', 'mode']]
    if required_keys:
        keys_to_create = [k for k in keys_to_create if k in required_keys]

    # Create folders
    for key in keys_to_create:
        folder = folders[key]
        os.makedirs(folder, exist_ok=True)

    # Save current session
    session_file = os.path.join(root_folder, '.cli_session')
    with open(session_file, 'w') as f:
        f.write(session_id)

    return folders

def list_cli_sessions():
    """
    List all sessions (CLI and Web).

    Returns:
        list: List of session info dicts
    """
    import glob
    from datetime import datetime

    sessions = []
    base_images = get_absolute_folder_path('images')

    # Find all cli- folders
    pattern = os.path.join(base_images, 'cli-*')
    for folder in glob.glob(pattern):
        session_id = os.path.basename(folder)

        # Get folder stats
        stat_info = os.stat(folder)
        created = datetime.fromtimestamp(stat_info.st_ctime)
        modified = datetime.fromtimestamp(stat_info.st_mtime)

        # Count files
        image_count = len([f for f in os.listdir(folder)
                          if os.path.isfile(os.path.join(folder, f))])

        sessions.append({
            'session_id': session_id,
            'created': created.isoformat(),
            'modified': modified.isoformat(),
            'image_count': image_count,
            'path': folder,
            'type': 'cli'
        })

    # Find all web- folders
    pattern = os.path.join(base_images, 'web-*')
    for folder in glob.glob(pattern):
        session_id = os.path.basename(folder)

        # Get folder stats
        stat_info = os.stat(folder)
        created = datetime.fromtimestamp(stat_info.st_ctime)
        modified = datetime.fromtimestamp(stat_info.st_mtime)

        # Count files
        image_count = len([f for f in os.listdir(folder)
                          if os.path.isfile(os.path.join(folder, f))])

        sessions.append({
            'session_id': session_id,
            'created': created.isoformat(),
            'modified': modified.isoformat(),
            'image_count': image_count,
            'path': folder,
            'type': 'web'
        })

    # Add shared if it exists
    shared_path = os.path.join(base_images, 'shared')
    if os.path.exists(shared_path):
        stat_info = os.stat(shared_path)
        image_count = len([f for f in os.listdir(shared_path)
                          if os.path.isfile(os.path.join(shared_path, f))])
        sessions.append({
            'session_id': 'shared',
            'created': datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            'image_count': image_count,
            'path': shared_path,
            'type': 'shared'
        })

    sorted_sessions = sorted(sessions, key=lambda x: x['modified'], reverse=True)

    # Print sessions
    if not sorted_sessions:
        print("No sessions found.")
    else:
        print(f"\n{'Session ID':<40} {'Type':<8} {'Created':<20} {'Modified':<20} {'Images':>8}")
        print("-" * 103)
        for session in sorted_sessions:
            session_type = session.get('type', 'unknown')
            print(f"{session['session_id']:<40} {session_type:<8} {session['created'][:19]:<20} {session['modified'][:19]:<20} {session['image_count']:>8}")
        print(f"\nTotal sessions: {len(sorted_sessions)}")

    return sorted_sessions

def clear_cli_session(session_id, force=False):
    """
    Clear data for a specific CLI session.

    Args:
        session_id: Session ID to clear
        force: Skip confirmation prompt

    Returns:
        dict: Summary of deleted items
    """
    import shutil
    import sys

    # Validate session exists
    base_images = get_absolute_folder_path('images')
    base_alt_text = get_absolute_folder_path('alt_text')
    base_reports = get_absolute_folder_path('reports')
    base_logs = get_absolute_folder_path('logs')
    # Legacy layout (output/<session>/...) for backward compatibility
    base_output = get_absolute_folder_path('output')

    session_images = os.path.join(base_images, session_id)
    session_alt_text = os.path.join(base_alt_text, session_id)
    session_reports = os.path.join(base_reports, session_id)
    session_logs = os.path.join(base_logs, session_id)
    legacy_output = os.path.join(base_output, session_id)

    if not os.path.exists(session_images) and not os.path.exists(session_alt_text) and not os.path.exists(legacy_output):
        raise ValueError(f"Session not found: {session_id}")

    # Confirmation prompt
    if not force:
        if not sys.stdout.isatty():
            print(f"Running in a non-interactive environment. Use --force to clear session '{session_id}' without confirmation.")
            return {'cancelled': True}
        confirm = input(f"Delete all data for session '{session_id}'? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled")
            return {'cancelled': True}

    # Delete session folders
    deleted = {'images': 0, 'outputs': 0, 'folders': 0}

    if os.path.exists(session_images):
        try:
            deleted['images'] = len([f for f in os.listdir(session_images)
                                    if os.path.isfile(os.path.join(session_images, f))])
            shutil.rmtree(session_images)
            deleted['folders'] += 1
        except Exception as e:
            print(f"Error deleting images folder: {e}")

    # Delete current layout outputs
    for path in [session_alt_text, session_reports, session_logs]:
        if os.path.exists(path):
            try:
                for root, dirs, files in os.walk(path):
                    deleted['outputs'] += len(files)
                shutil.rmtree(path)
                deleted['folders'] += 1
            except Exception as e:
                print(f"Error deleting output folder: {e}")

    # Delete legacy layout outputs (output/<session>/...)
    if os.path.exists(legacy_output):
        try:
            for root, dirs, files in os.walk(legacy_output):
                deleted['outputs'] += len(files)
            shutil.rmtree(legacy_output)
            deleted['folders'] += 1
        except Exception as e:
            print(f"Error deleting legacy output folder: {e}")

    # Clear session file if this was the current session
    session_file = os.path.join(get_absolute_folder_path('root'), '.cli_session')
    if os.path.exists(session_file):
        with open(session_file, 'r') as f:
            current_session = f.read().strip()
        if current_session == session_id:
            os.remove(session_file)

    return deleted

def clear_all_cli_sessions(force=False):
    """
    Clear all CLI sessions.

    Args:
        force: Skip confirmation prompt

    Returns:
        dict: Summary of deleted items
    """
    import shutil
    import sys

    # Get all sessions
    sessions = list_cli_sessions()

    if not sessions:
        print("No sessions to clear")
        return {'sessions_deleted': 0}

    # Confirmation prompt
    if not force:
        if not sys.stdout.isatty():
            print("Running in a non-interactive environment. Use --force to clear all sessions without confirmation.")
            return {'cancelled': True}
        print(f"Found {len(sessions)} session(s):")
        for session in sessions:
            print(f"  - {session['session_id']}: {session['image_count']} images")
        print()
        confirm = input("Are you sure you want to delete all images and data for all sessions? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled")
            return {'cancelled': True}

    # Delete all sessions
    total_deleted = {'sessions': 0, 'images': 0, 'outputs': 0}

    for session in sessions:
        result = clear_cli_session(session['session_id'], force=True)
        if not result.get('cancelled'):
            total_deleted['sessions'] += 1
            total_deleted['images'] += result.get('images', 0)
            total_deleted['outputs'] += result.get('outputs', 0)

    return total_deleted

def get_enabled_image_tags():
    """
    Get list of enabled HTML tags for image extraction from config.

    Returns:
        list: List of enabled tag names (e.g., ['img', 'picture'])
    """
    tags_config = CONFIG.get('image_extraction', {}).get('tags', {})
    enabled_tags = [tag for tag, enabled in tags_config.items() if enabled]

    # Default to img and picture if no config
    if not enabled_tags:
        enabled_tags = ['img', 'picture']

    return enabled_tags

def get_enabled_image_attributes():
    """
    Get list of enabled image attributes for extraction from config.

    Returns:
        list: List of enabled attribute names (e.g., ['src', 'data-src', 'data-image'])
    """
    attrs_config = CONFIG.get('image_extraction', {}).get('attributes', {})
    enabled_attrs = [attr for attr, enabled in attrs_config.items() if enabled]

    # Default attributes if no config
    if not enabled_attrs:
        enabled_attrs = ['src', 'data-src', 'data-image', 'data-image-webp', 'srcset', 'data-srcset']

    return enabled_attrs

def get_image_url_from_element(element, attributes):
    """
    Extract image URL from an element using the specified attributes.

    Args:
        element: BeautifulSoup element
        attributes (list): List of attribute names to check

    Returns:
        str: Image URL or None if not found
    """
    for attr in attributes:
        value = element.get(attr)
        if value:
            return value
    return None

def get_image_url_and_attribute(element, attributes):
    """
    Extract image URL and the attribute used from an element.

    Args:
        element: BeautifulSoup element
        attributes (list): List of attribute names to check

    Returns:
        tuple: (url, attribute_name) or (None, None) if not found
    """
    for attr in attributes:
        value = element.get(attr)
        if value:
            return (value, attr)
    return (None, None)

def generate_html_report(alt_text_folder=None, images_folder=None, output_filename="alt-text-report.html", page_title=None):
    """
    Generate an accessible HTML report summarizing all alt-text JSON files.

    Args:
        alt_text_folder (str): Folder containing JSON files (uses config default if None)
        images_folder (str): Folder containing image files (uses config default if None)
        output_filename (str): Name of the output HTML file
        page_title (str): The title of the source webpage (optional, for HTML title tag)

    Returns:
        str: Path to generated HTML file, or None if failed
    """
    func_name = "generate_html_report"
    debug_log(f"Starting {func_name}")

    try:
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')

        # Read all JSON files from alt-text folder
        json_files = [f for f in os.listdir(alt_text_folder) if f.endswith('.json')]

        if not json_files:
            debug_log("No JSON files found in alt-text folder", "WARNING")
            return None

        debug_log(f"Found {len(json_files)} JSON files to include in report")

        # Load all JSON data
        image_data = []
        source_url = ""
        report_page_title = ""
        ai_provider = ""
        vision_provider = ""
        ai_vision_model = ""
        processing_provider = ""
        ai_processing_model = ""
        translation_provider = ""
        ai_translation_model = ""
        translation_method = ""
        total_processing_time = 0.0
        for json_file in sorted(json_files):
            json_path = os.path.join(alt_text_folder, json_file)
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    image_data.append(data)
                    # Extract web_site_url from first item (should be same for all)
                    # Check both new field name (web_site_url) and legacy field name (source_url) for backward compatibility
                    if not source_url:
                        source_url = data.get('web_site_url') or data.get('source_url', '')
                    # Extract page_title from first item
                    if not report_page_title:
                        report_page_title = data.get('page_title', '')
                    # Extract AI model info from first item (should be same for all)
                    if not ai_provider:
                        ai_info = data.get('ai_model', {})
                        # Get per-step provider and model information
                        vision_provider = ai_info.get('vision_provider', 'Unknown')
                        ai_vision_model = ai_info.get('vision_model', 'Unknown')
                        processing_provider = ai_info.get('processing_provider', 'Unknown')
                        ai_processing_model = ai_info.get('processing_model', 'Unknown')
                        translation_provider = ai_info.get('translation_provider', 'Unknown')
                        ai_translation_model = ai_info.get('translation_model', 'Unknown')

                        # For backward compatibility, try old structure if new fields are missing
                        if vision_provider == 'Unknown' and 'provider' in ai_info:
                            vision_provider = ai_info.get('provider', 'Unknown')
                            processing_provider = vision_provider
                            translation_provider = vision_provider

                        # Store provider info as comma-separated list of unique providers
                        providers = set([vision_provider, processing_provider])
                        if translation_provider and translation_provider != 'Unknown':
                            providers.add(translation_provider)
                        ai_provider = ', '.join(sorted(providers))
                    # Extract translation mode from first item (should be same for all)
                    if not translation_method:
                        translation_method = data.get('translation_mode', data.get('translation_method', 'none'))
                    # Sum up processing times
                    total_processing_time += data.get('processing_time_seconds', 0.0)
            except Exception as e:
                debug_log(f"Error reading {json_file}: {str(e)}", "WARNING")
                continue

        # Calculate statistics for image types and tags/attributes
        type_stats = {}
        tag_stats = {}
        attr_stats = {}
        for data in image_data:
            # Count image types
            img_type = data.get('image_type', 'unknown').lower()
            type_stats[img_type] = type_stats.get(img_type, 0) + 1

            # Count tags and attributes
            tag_attr = data.get('image_tag_attribute', {})
            if isinstance(tag_attr, dict):
                tag = tag_attr.get('tag', 'unknown')
                attr = tag_attr.get('attribute', 'unknown')
                tag_stats[tag] = tag_stats.get(tag, 0) + 1
                attr_stats[attr] = attr_stats.get(attr, 0) + 1

        # Generate HTML report
        # Load and encode logo
        logo_base64 = ""
        try:
            logo_path = config_settings.PROJECT_ROOT / "frontend" / "assets" / "MyAccessibilityBuddy-logo.png"
            if logo_path.exists():
                import base64
                with open(logo_path, 'rb') as logo_file:
                    logo_base64 = base64.b64encode(logo_file.read()).decode('utf-8')
        except Exception as e:
            debug_log(f"Could not load logo: {str(e)}", "WARNING")

        # Determine report output folder
        base_reports_folder = get_absolute_folder_path('reports')
        reports_folder = base_reports_folder
        # If alt_text_folder is a session folder (e.g., .../alt-text/cli-123),
        # place the report in the matching reports/cli-123 folder
        try:
            alt_text_parts = Path(alt_text_folder).parts
            if 'alt-text' in alt_text_parts:
                alt_text_index = alt_text_parts.index('alt-text')
                # Session folder is the element after 'alt-text' (if present)
                if alt_text_index + 1 < len(alt_text_parts):
                    session_id = alt_text_parts[alt_text_index + 1]
                    reports_folder = os.path.join(reports_folder, session_id)
        except Exception:
            # Fallback to base reports folder
            pass

        # Ensure reports folder exists
        os.makedirs(reports_folder, exist_ok=True)

        # Load HTML template from base reports folder
        template_path = os.path.join(base_reports_folder, 'report_template.html')

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                html_template = f.read()
        except FileNotFoundError:
            debug_log(f"Template file not found at {template_path}", "ERROR")
            return None

        # Prepare template variables
        logo_html = f"<img src='data:image/png;base64,{logo_base64}' alt='My Accessibility Buddy logo.' class='logo'>" if logo_base64 else ""
        page_title_html = f"<p><strong>Page Title:</strong> {report_page_title}</p>" if report_page_title else ""
        source_url_html = f"<p><strong>Source URL:</strong> <a href='{source_url}' target='blank' rel='noopener'>{source_url}</a></p>" if source_url else ""

        # Translation method text
        if translation_method == "fast":
            translation_method_text = "Fast (generated once, then translated by AI)"
        elif translation_method == "accurate":
            translation_method_text = "Accurate (generated for every language)"
        else:
            translation_method_text = "None (single language)"

        geo_boost_values = [
            item.get('geo_boost_status')
            for item in image_data
            if isinstance(item, dict) and 'geo_boost_status' in item
        ]
        if any(val is True for val in geo_boost_values):
            geo_boost_status_text = "Enabled"
        elif geo_boost_values and all(val is False for val in geo_boost_values):
            geo_boost_status_text = "Disabled"
        else:
            geo_boost_status_text = "Unknown"

        # Get display settings from config.advanced.json
        display_settings = CONFIG.get('html_report_display', {})
        display_geo_boost = display_settings.get('display_geo_boost', True)

        # Generate GEO Boost HTML line conditionally based on display_geo_boost setting
        if display_geo_boost:
            geo_boost_html = f'<p><strong>GEO Boost:</strong> {geo_boost_status_text}</p>'
        else:
            geo_boost_html = ""

        prompt_details_html = ""
        prompt_display_settings = CONFIG.get('html_report_display', {})
        show_vision_prompt = prompt_display_settings.get('display_vision_prompt', False)
        show_processing_prompt = prompt_display_settings.get('display_processing_prompt', False)
        show_translation_prompt = prompt_display_settings.get('display_translation_prompt', False)
        if show_vision_prompt or show_processing_prompt or show_translation_prompt:
            import html as html_lib
            prompt_blocks = []
            prompt_source = None
            for item in image_data:
                if isinstance(item, dict) and isinstance(item.get('prompts_used'), dict):
                    prompt_source = item.get('prompts_used')
                    break

            def build_prompt_block(title, prompt_text, subtitle=None):
                safe_text = html_lib.escape(prompt_text) if prompt_text else "(prompt unavailable)"
                subtitle_text = f" {subtitle}" if subtitle else ""
                return f"""
        <div class="field prompt-block">
            <p><strong>{html_lib.escape(title)}{html_lib.escape(subtitle_text)}</strong></p>
            <pre class="prompt-text">{safe_text}</pre>
        </div>
"""

            def format_processing_prompts(prompts):
                if not prompts:
                    return ""
                if isinstance(prompts, list):
                    blocks = []
                    for entry in prompts:
                        if isinstance(entry, dict):
                            lang = entry.get("language", "").strip()
                            prompt_text = entry.get("prompt", "")
                            label = f"[{lang}]" if lang else "[LANG]"
                            blocks.append(f"{label}\n{prompt_text}")
                        else:
                            blocks.append(str(entry))
                    return "\n\n".join(blocks)
                return str(prompts)

            def format_translation_prompts(prompts):
                if not prompts:
                    return ""
                if isinstance(prompts, list):
                    blocks = []
                    for entry in prompts:
                        if isinstance(entry, dict):
                            lang = entry.get("language", "").strip()
                            system_prompt = entry.get("system", "")
                            user_prompt = entry.get("user", "")
                            label = f"[{lang}]" if lang else "[LANG]"
                            blocks.append(f"{label}\nSYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}")
                        else:
                            blocks.append(str(entry))
                    return "\n\n".join(blocks)
                if isinstance(prompts, dict):
                    system_prompt = prompts.get("system", "")
                    user_prompt = prompts.get("user", "")
                    return f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"
                return str(prompts)

            if show_vision_prompt:
                vision_prompt_text = ""
                if prompt_source:
                    vision_prompt_text = prompt_source.get("vision", "")
                prompt_blocks.append(build_prompt_block("Vision Prompt", vision_prompt_text))

            if show_processing_prompt:
                processing_prompt_text = format_processing_prompts(prompt_source.get("processing", []) if prompt_source else [])
                prompt_blocks.append(build_prompt_block("Processing Prompt", processing_prompt_text))

            if show_translation_prompt:
                translation_prompt_text = format_translation_prompts(prompt_source.get("translation", []) if prompt_source else [])
                prompt_blocks.append(build_prompt_block("Translation Prompt", translation_prompt_text))

            if prompt_blocks:
                prompt_details_html = """
        <div class="stats-section">
            <h3>Prompts</h3>
""" + "".join(prompt_blocks) + """
        </div>
"""

        # Get global display settings from config.json
        global_display_settings = CONFIG.get('html_report_display', {
            'display_image_type_distribution': True,
            'display_html_tags_used': True,
            'display_html_attributes_used': True,
            'display_image_analysis_overview': True
        })

        # Generate stats HTML conditionally based on display settings
        if global_display_settings.get('display_image_type_distribution', True):
            type_stats_html = """
        <div class="stats-section">
            <h3>Image Type Distribution</h3>
            <div class="stats-grid">
                """ + "".join([f'<div class="stat-item"><span class="stat-label">{img_type.capitalize()}</span><span class="stat-value">{count}</span></div>' for img_type, count in sorted(type_stats.items())]) + """
            </div>
        </div>
"""
        else:
            type_stats_html = ""

        if global_display_settings.get('display_html_tags_used', True):
            tag_stats_html = """
        <div class="stats-section">
            <h3>HTML Tags Used</h3>
            <div class="stats-grid">
                """ + "".join([f'<div class="stat-item"><span class="stat-label">&lt;{tag}&gt;</span><span class="stat-value">{count}</span></div>' for tag, count in sorted(tag_stats.items())]) + """
            </div>
        </div>
"""
        else:
            tag_stats_html = ""

        if global_display_settings.get('display_html_attributes_used', True):
            attr_stats_html = """
        <div class="stats-section">
            <h3>HTML Attributes Used</h3>
            <div class="stats-grid">
                """ + "".join([f'<div class="stat-item"><span class="stat-label">{attr}</span><span class="stat-value">{count}</span></div>' for attr, count in sorted(attr_stats.items())]) + """
            </div>
        </div>
"""
        else:
            attr_stats_html = ""

        # Build Image Analysis Overview section with heading and statistics
        # If display_image_analysis_overview is false, hide the entire section
        if global_display_settings.get('display_image_analysis_overview', True):
            image_analysis_overview_html = """        <h3>Image Analysis Overview</h3>
""" + type_stats_html + tag_stats_html + attr_stats_html
        else:
            image_analysis_overview_html = ""

        # Build Image Analysis Overview section with heading and statistics
        # If display_image_analysis_overview is false, hide the entire section
        if global_display_settings.get('display_image_analysis_overview', True):
            image_analysis_overview_html = """        <h3>Image Analysis Overview</h3>
""" + type_stats_html + tag_stats_html + attr_stats_html
        else:
            image_analysis_overview_html = ""

        # Build image cards HTML
        image_cards_html = ""

        # Get images folder (use parameter if provided, otherwise use config default)
        if images_folder is None:
            images_folder = get_absolute_folder_path('images')

        for idx, data in enumerate(image_data, 1):
            image_id = data.get('image_id', 'Unknown')
            image_type = data.get('image_type', 'unknown')
            image_url = data.get('image_URL', '')
            image_context = data.get('image_context', '')
            current_alt_text = data.get('current_alt_text', '')
            # Use human-reviewed alt text if present (even if empty), otherwise fall back to proposed alt text
            human_reviewed_alt_text = data.get('human_reviewed_alt_text')
            has_human_reviewed = 'human_reviewed_alt_text' in data and not (
                isinstance(human_reviewed_alt_text, list) and len(human_reviewed_alt_text) == 0
            )
            proposed_alt_text_raw = human_reviewed_alt_text if has_human_reviewed else data.get('proposed_alt_text', '')
            reasoning = data.get('reasoning', '')

            # Get display settings from config.json
            display_settings = CONFIG.get('html_report_display', {
                'display_proposed_alt_text': True,
                'display_image_type': True,
                'display_current_alt_text': True,
                'display_image_tag_attribute': True,
                'display_reasoning': True,
                'display_context': True,
                'display_image_preview': True,
                'display_html_attributes_used': True,
                'display_html_tags_used': True,
                'display_image_type_distribution': True,
                'display_image_analysis_overview': True
            })

            # Normalize alt-text entries to a list of (lang, text) tuples
            def normalize_alt_items(raw, default_lang):
                items = []
                if isinstance(raw, list):
                    for entry in raw:
                        lang_code = None
                        text_val = None
                        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                            lang_code, text_val = entry[0], entry[1]
                        elif isinstance(entry, dict):
                            lang_code = entry.get('language') or entry.get('lang') or entry.get('code')
                            text_val = entry.get('text') or entry.get('value')
                        elif isinstance(entry, str):
                            parts = entry.split(':', 1)
                            if len(parts) == 2 and len(parts[0].strip()) <= 5:
                                lang_code, text_val = parts[0], parts[1]
                        if lang_code is None:
                            lang_code = default_lang
                        if text_val is None:
                            text_val = ""
                        items.append((str(lang_code).upper(), str(text_val)))
                else:
                    items.append((str(default_lang).upper(), str(raw)))
                return items

            lang_field = data.get('language', 'en')
            if isinstance(lang_field, list):
                default_lang = lang_field[0] if lang_field else 'en'
                is_multilingual = True
            else:
                default_lang = lang_field
                is_multilingual = isinstance(proposed_alt_text_raw, list)

            proposed_alt_text_items = normalize_alt_items(proposed_alt_text_raw, default_lang or 'EN')
            tag_attr_raw = data.get('image_tag_attribute', {})
            
            # Defensive check: ensure tag_attr is a dictionary
            if isinstance(tag_attr_raw, dict):
                tag_attr = tag_attr_raw
            else:
                tag_attr = {} # Default to an empty dict if it's not a dictionary

            # Format image type with appropriate CSS class
            type_class = f"type-{image_type.replace(' ', '_')}"

            # Generate alt text for image - use first language from multilingual or the single language alt text
            if is_multilingual and proposed_alt_text_items:
                # Use first language's alt text
                first_lang_code, first_alt_text = proposed_alt_text_items[0]
                image_alt_text = first_alt_text if first_alt_text else f"Preview of {image_id}"
            else:
                # Use single language alt text
                if proposed_alt_text_items:
                    _, single_alt_text = proposed_alt_text_items[0]
                    image_alt_text = single_alt_text if single_alt_text else f"Preview of {image_id}"
                else:
                    image_alt_text = f"Preview of {image_id}"

            # Generate embedded image data URI
            image_preview_html = ""
            image_path = os.path.join(images_folder, image_id)
            try:
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as img_file:
                        image_binary = img_file.read()
                        base64_data = base64.b64encode(image_binary).decode('utf-8')
                        mime_type, _ = guess_type(image_id)
                        if mime_type:
                            data_uri = f"data:{mime_type};base64,{base64_data}"
                            image_preview_html = f'<img src="{data_uri}" alt="{image_alt_text}" class="image-preview">'
                        else:
                            image_preview_html = f'<p class="error">Unable to determine image type for {image_id}</p>'
                else:
                    image_preview_html = f'<p class="error">Image file not found: {image_id}</p>'
            except Exception as e:
                image_preview_html = f'<p class="error">Error loading image: {str(e)}</p>'

            image_cards_html += f"""
    <article class="image-card" role="article" aria-labelledby="image-{idx}-title">
        <h3 id="image-{idx}-title">{idx}. {image_id}</h3>
"""

            # Conditionally add Image Preview field
            if display_settings.get('display_image_preview', True):
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">Image Preview:</span>
            {image_preview_html}
        </div>
"""

            # Conditionally add Image Type field
            if display_settings.get('display_image_type', True):
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">Image Type:</span>
            <div class="field-value">
                <span class="image-type {type_class}">{image_type}</span>
            </div>
        </div>
"""

            # Conditionally add Current Alt Text field (BEFORE Proposed Alt Text)
            if display_settings.get('display_current_alt_text', True):
                current_alt = data.get('current_alt_text', '')
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">Current Alt Text:</span>
            <div class="field-value">{current_alt if current_alt else '(none)'}</div>
        </div>
"""

            # Conditionally add Proposed Alt Text field
            if display_settings.get('display_proposed_alt_text', True):
                # Use different label if showing human-reviewed text
                alt_text_label = "Reviewed Alt Text:" if has_human_reviewed else "Proposed Alt Text:"
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">{alt_text_label}</span>
            <div class="field-value alt-text">"""

                # Generate HTML for proposed alt text (single or multilingual)
                if is_multilingual:
                    # Display multiple languages
                    image_cards_html += "<dl style='margin: 0;'>"
                    for lang_code, alt_text in proposed_alt_text_items:
                        image_cards_html += f"<dt style='font-weight: bold; margin-top: 0.5em;'>{lang_code}:</dt>"
                        image_cards_html += f"<dd style='margin-left: 1.5em;'>{alt_text if alt_text else '(empty)'}</dd>"
                    image_cards_html += "</dl>"
                else:
                    # Display single language
                    lang_code, alt_text = proposed_alt_text_items[0]
                    image_cards_html += f"{alt_text if alt_text else '(empty - decorative image)'}"

                image_cards_html += """</div>
        </div>
"""

            # Conditionally add Image HTML Tag or Attribute field
            if display_settings.get('display_image_tag_attribute', True):
                tag = tag_attr.get('tag', 'unknown')
                attribute = tag_attr.get('attribute', 'unknown')
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">Image HTML Tag or Attribute:</span>
            <div class="field-value">Tag: &lt;{tag}&gt;, Attribute: {attribute}</div>
        </div>
"""

            # Conditionally add Vision Model Output field
            vision_output = data.get('vision_model_output', '') or data.get('extended_description', '')
            if vision_output and vision_output != 'LLM analysis failed - LLM not available or credentials invalid':
                image_cards_html += """
        <div class="field">
            <span class="field-label">Vision Model Output (Step 1 - Image Analysis):</span>
            <div class="field-value">""" + vision_output + """</div>
        </div>
"""

            # Conditionally add Reasoning field
            if display_settings.get('display_reasoning', True):
                image_cards_html += """
        <div class="field">
            <span class="field-label">Reasoning:</span>
            <div class="field-value">"""

                # Add reasoning (handle both multilingual and single language)
                reasoning = data.get('reasoning', '')
                if isinstance(reasoning, list) and reasoning:
                    # Multilingual reasoning
                    image_cards_html += "<dl style='margin: 0;'>"
                    for lang_code, reason_text in reasoning:
                        image_cards_html += f"<dt style='font-weight: bold; margin-top: 0.5em;'>{lang_code}:</dt>"
                        image_cards_html += f"<dd style='margin-left: 1.5em;'>{reason_text if reason_text else '(none)'}</dd>"
                    image_cards_html += "</dl>"
                else:
                    # Single language reasoning
                    image_cards_html += f"{reasoning if reasoning else '(none)'}"

                image_cards_html += """</div>
        </div>
"""

            # Conditionally add Context field
            if display_settings.get('display_context', True):
                context = data.get('image_context', '')
                # Truncate context if too long for display
                max_context_length = 500
                if context and len(context) > max_context_length:
                    context = context[:max_context_length] + "..."
                image_cards_html += f"""
        <div class="field">
            <span class="field-label">Context:</span>
            <div class="field-value context-text">{context if context else '(none)'}</div>
        </div>
"""

            image_cards_html += """    </article>
"""

        # Replace placeholders in template
        html_content = html_template.replace('{LOGO_HTML}', logo_html)
        html_content = html_content.replace('{PAGE_TITLE_HTML}', page_title_html)
        html_content = html_content.replace('{SOURCE_URL_HTML}', source_url_html)
        html_content = html_content.replace('{AI_PROVIDER}', ai_provider)
        html_content = html_content.replace('{VISION_PROVIDER}', vision_provider)
        html_content = html_content.replace('{AI_VISION_MODEL}', ai_vision_model)
        html_content = html_content.replace('{PROCESSING_PROVIDER}', processing_provider)
        html_content = html_content.replace('{AI_PROCESSING_MODEL}', ai_processing_model)
        html_content = html_content.replace('{TRANSLATION_PROVIDER}', translation_provider)
        html_content = html_content.replace('{AI_TRANSLATION_MODEL}', ai_translation_model)
        html_content = html_content.replace('{TRANSLATION_METHOD_TEXT}', translation_method_text)
        html_content = html_content.replace('{GEO_BOOST_HTML}', geo_boost_html)
        html_content = html_content.replace('{TOTAL_IMAGES}', str(len(image_data)))
        html_content = html_content.replace('{TOTAL_PROCESSING_TIME}', f"{total_processing_time:.2f}")
        html_content = html_content.replace('{GENERATION_TIMESTAMP}', get_cet_time().strftime('%Y-%m-%d %H:%M:%S CET'))
        html_content = html_content.replace('{IMAGE_ANALYSIS_OVERVIEW_HTML}', image_analysis_overview_html)
        html_content = html_content.replace('{IMAGE_CARDS_HTML}', image_cards_html)
        html_content = html_content.replace('{PROMPT_DETAILS_HTML}', prompt_details_html)

        # Generate filename based on source URL and date
        # Format: <date>-analysis-report-<url>.html
        from datetime import datetime

        # Get current date/time in YYYY-MM-DDTHH-MM-SS format (safe for filenames)
        date_str = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')

        # Check if user provided custom filename (not the default)
        is_default_filename = output_filename in ["alt-text-report.html", "MyAccessibilityBuddy-AltTextReport.html"]

        if source_url and is_default_filename:
            # Extract domain/path from URL for filename
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(source_url)
                # Use domain + path, clean for filename
                url_part = parsed_url.netloc + parsed_url.path
                # Remove invalid filename characters
                clean_url = "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in url_part)
                # Remove leading/trailing underscores and limit length
                clean_url = clean_url.strip('_')[:80]
                final_filename = f"{date_str}-analysis-report-{clean_url}.html"
            except Exception:
                # Fallback if URL parsing fails
                final_filename = f"{date_str}-analysis-report.html"
        elif not is_default_filename:
            # User provided custom filename, use it
            final_filename = output_filename
        else:
            # No source URL available, use date only
            final_filename = f"{date_str}-analysis-report.html"

        # Write HTML file to reports folder (already resolved/created above)
        output_path = os.path.join(reports_folder, final_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        debug_log(f"HTML report generated: {output_path}")
        return output_path

    except Exception as e:
        handle_exception(func_name, e, "generating HTML report")
        return None


def get_allowed_languages():
    """
    Get list of allowed language codes from configuration.

    Returns:
        list: List of allowed language codes (e.g., ['en', 'es', 'fr', ...])
    """
    languages_config = CONFIG.get('languages', {}).get('allowed', [])
    if languages_config:
        return [lang['code'] for lang in languages_config]

    # Default fallback to common EU languages
    return ['bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr',
            'ga', 'hr', 'hu', 'it', 'lt', 'lv', 'mt', 'nl', 'pl', 'pt',
            'ro', 'sk', 'sl', 'sv']

def get_language_name(language_code):
    """
    Get the display name for a language code.

    Args:
        language_code (str): ISO language code (e.g., 'en', 'es')

    Returns:
        str: Language name (e.g., 'English', 'Español') or the code if not found
    """
    languages_config = CONFIG.get('languages', {}).get('allowed', [])
    for lang in languages_config:
        if lang['code'] == language_code:
            return lang['name']
    return language_code

def validate_language(language_code):
    """
    Validate that a language code is in the allowed list.

    Args:
        language_code (str): ISO language code to validate

    Returns:
        tuple: (is_valid: bool, message: str)
    """
    if not language_code:
        default_lang = CONFIG.get('languages', {}).get('default', 'en')
        return True, f"Using default language: {default_lang}"

    allowed_languages = get_allowed_languages()

    if language_code.lower() in allowed_languages:
        lang_name = get_language_name(language_code.lower())
        return True, f"Language '{language_code}' ({lang_name}) is supported"
    else:
        allowed_list = ', '.join(allowed_languages)
        return False, f"Language '{language_code}' not supported. Allowed languages: {allowed_list}"

def local_image_to_data_url(image_path):
    """
    Convert a local image file to a data URL with proper MIME type detection.
    SVG files are automatically converted to PNG for vision model compatibility.

    Args:
        image_path (str): Path to the local image file

    Returns:
        str: Data URL string in format "data:{mime_type};base64,{encoded_data}"
    """
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    # Check if this is an SVG file
    if mime_type == "image/svg+xml":
        if not SVG_SUPPORT:
            debug_log("SVG file detected but cairosvg not installed. Cannot convert to PNG.", "ERROR")
            raise ValueError("SVG conversion not supported. Install cairosvg: pip install cairosvg")

        # Convert SVG to PNG
        debug_log(f"SVG file detected: {image_path}. Converting to PNG for vision model compatibility...")
        try:
            with open(image_path, "rb") as svg_file:
                svg_data = svg_file.read()

            # Convert SVG to PNG using cairosvg
            png_data = cairosvg.svg2png(bytestring=svg_data)

            # Use PNG MIME type
            mime_type = "image/png"
            base64_encoded_data = base64.b64encode(png_data).decode("utf-8")

            debug_log(f"Successfully converted SVG to PNG (size: {len(png_data)} bytes)")
        except Exception as e:
            debug_log(f"Failed to convert SVG to PNG: {str(e)}", "ERROR")
            raise
    else:
        # Regular image file - read and encode
        with open(image_path, "rb") as image_file:
            base64_encoded_data = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:{mime_type};base64,{base64_encoded_data}"

def load_and_merge_prompts(prompt_folder):
    """
    Load and merge multiple processing prompt files based on configuration.
    These prompts are used for generating WCAG-compliant alt-text.

    Args:
        prompt_folder (str): Path to the processing folder containing prompt files

    Returns:
        tuple: (merged_prompt_text, list_of_loaded_files)
    """
    func_name = "load_and_merge_prompts"
    debug_log(f"Loading processing prompts from folder: {prompt_folder}")

    # Get prompt configuration
    prompt_config = CONFIG.get('prompt', {})
    prompt_files = prompt_config.get('processing_files', prompt_config.get('files', ['processing_prompt_v0.txt']))
    merge_separator = prompt_config.get('merge_separator', '\n\n---\n\n')
    default_prompt = prompt_config.get('default_processing_prompt', prompt_config.get('default_prompt', 'processing_prompt_v0.txt'))

    merged_prompt = ""
    loaded_files = []

    # Try to load each configured prompt file
    for prompt_file in prompt_files:
        prompt_path = os.path.join(prompt_folder, prompt_file)
        debug_log(f"Looking for prompt file: {prompt_path}")

        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_content = f.read().strip()
                    if prompt_content:
                        if merged_prompt:
                            merged_prompt += merge_separator
                        merged_prompt += prompt_content
                        loaded_files.append(prompt_file)
                        debug_log(f"Loaded prompt file: {prompt_file}")
            except Exception as e:
                handle_exception(func_name, e, f"reading prompt file {prompt_path}")
                continue
        else:
            debug_log(f"Prompt file not found: {prompt_file}", "WARNING")

    # If no files were loaded, try the default prompt
    if not merged_prompt and default_prompt not in prompt_files:
        default_path = os.path.join(prompt_folder, default_prompt)
        if os.path.exists(default_path):
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    merged_prompt = f.read().strip()
                    loaded_files.append(default_prompt)
                    debug_log(f"Loaded default prompt file: {default_prompt}")
            except Exception as e:
                handle_exception(func_name, e, f"reading default prompt file {default_path}")

    if loaded_files:
        debug_log(f"Successfully loaded and merged {len(loaded_files)} prompt file(s): {', '.join(loaded_files)}")
        log_message(f"Loaded prompt file(s): {', '.join(loaded_files)}", "INFORMATION")
    else:
        debug_log("No prompt files could be loaded", "WARNING")

    return merged_prompt, loaded_files

def load_vision_prompt(vision_prompt_folder):
    """
    Load vision prompt for Ollama's first-step image description.

    Args:
        vision_prompt_folder (str): Path to the folder containing vision prompt files

    Returns:
        str: The vision prompt text
    """
    func_name = "load_vision_prompt"
    debug_log(f"Loading vision prompt from folder: {vision_prompt_folder}")

    # Get prompt configuration
    prompt_config = CONFIG.get('prompt', {})
    vision_files = prompt_config.get('vision_files', ['vision_prompt_v0.txt'])
    default_vision_prompt = prompt_config.get('default_vision_prompt', 'vision_prompt_v0.txt')

    # Try to load the first configured vision prompt file
    for vision_file in vision_files:
        vision_path = os.path.join(vision_prompt_folder, vision_file)
        debug_log(f"Looking for vision prompt file: {vision_path}")

        if os.path.exists(vision_path):
            try:
                with open(vision_path, 'r', encoding='utf-8') as f:
                    vision_prompt = f.read().strip()
                    if vision_prompt:
                        debug_log(f"Loaded vision prompt file: {vision_file}")
                        return vision_prompt
            except Exception as e:
                handle_exception(func_name, e, f"reading vision prompt file {vision_path}")
                continue

    # If no files were loaded, try the default
    default_path = os.path.join(vision_prompt_folder, default_vision_prompt)
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                vision_prompt = f.read().strip()
                debug_log(f"Loaded default vision prompt file: {default_vision_prompt}")
                return vision_prompt
        except Exception as e:
            handle_exception(func_name, e, f"reading default vision prompt file {default_path}")

    # Fallback to hardcoded prompt
    debug_log("No vision prompt files found, using hardcoded fallback", "WARNING")
    return "Describe this image in detail."

def load_translation_prompt(translation_prompt_folder):
    """
    Load translation prompt for alt-text translation.

    Args:
        translation_prompt_folder (str): Path to the folder containing translation prompt files

    Returns:
        str: The translation prompt text
    """
    func_name = "load_translation_prompt"
    debug_log(f"Loading translation prompt from folder: {translation_prompt_folder}")

    # Get prompt configuration
    prompt_config = CONFIG.get('prompt', {})
    translation_files = prompt_config.get('translation_files', ['translation_prompt_v0.txt'])
    default_translation_prompt = prompt_config.get('default_translation_prompt', 'translation_prompt_v0.txt')

    # Try to load the first configured translation prompt file
    for translation_file in translation_files:
        translation_path = os.path.join(translation_prompt_folder, translation_file)
        debug_log(f"Looking for translation prompt file: {translation_path}")

        if os.path.exists(translation_path):
            try:
                with open(translation_path, 'r', encoding='utf-8') as f:
                    translation_prompt = f.read().strip()
                    if translation_prompt:
                        debug_log(f"Loaded translation prompt file: {translation_file}")
                        return translation_prompt
            except Exception as e:
                handle_exception(func_name, e, f"reading translation prompt file {translation_path}")
                continue

    # If no files were loaded, try the default
    default_path = os.path.join(translation_prompt_folder, default_translation_prompt)
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                translation_prompt = f.read().strip()
                debug_log(f"Loaded default translation prompt file: {default_translation_prompt}")
                return translation_prompt
        except Exception as e:
            handle_exception(func_name, e, f"reading default translation prompt file {default_path}")

    # Fallback to hardcoded prompt
    debug_log("No translation prompt files found, using hardcoded fallback", "WARNING")
    max_chars = CONFIG.get('alt_text_max_chars', 125)
    return f"""Translate the following alternative text from {{SOURCE_LANGUAGE}} to {{TARGET_LANGUAGE}}.

CRITICAL REQUIREMENTS:
1. The translation MUST be {max_chars} characters or less (including spaces and punctuation)
2. Maintain the meaning and accessibility compliance
3. End with a period
4. Be concise and natural in the target language
5. If the direct translation exceeds {max_chars} characters, use a shorter equivalent that preserves the core meaning

Source text ({{SOURCE_LANGUAGE}}): "{{ALT_TEXT}}"

Provide ONLY the translated text in {{TARGET_LANGUAGE}}, nothing else. Do not include explanations or metadata."""

def load_translation_system_prompt(translation_prompt_folder):
    """
    Load translation system prompt for alt-text translation.

    Args:
        translation_prompt_folder (str): Path to the folder containing translation system prompt files

    Returns:
        str: The translation system prompt text
    """
    func_name = "load_translation_system_prompt"
    debug_log(f"Loading translation system prompt from folder: {translation_prompt_folder}")

    # Get prompt configuration
    prompt_config = CONFIG.get('prompt', {})
    translation_system_files = prompt_config.get('translation_system_files', ['translation_system_prompt_v0.txt'])
    default_translation_system_prompt = prompt_config.get('default_translation_system_prompt', 'translation_system_prompt_v0.txt')

    # Try to load the first configured translation system prompt file
    for translation_system_file in translation_system_files:
        translation_system_path = os.path.join(translation_prompt_folder, translation_system_file)
        debug_log(f"Looking for translation system prompt file: {translation_system_path}")

        if os.path.exists(translation_system_path):
            try:
                with open(translation_system_path, 'r', encoding='utf-8') as f:
                    translation_system_prompt = f.read().strip()
                    if translation_system_prompt:
                        debug_log(f"Loaded translation system prompt file: {translation_system_file}")
                        return translation_system_prompt
            except Exception as e:
                handle_exception(func_name, e, f"reading translation system prompt file {translation_system_path}")
                continue

    # If no files were loaded, try the default
    default_path = os.path.join(translation_prompt_folder, default_translation_system_prompt)
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                translation_system_prompt = f.read().strip()
                debug_log(f"Loaded default translation system prompt file: {default_translation_system_prompt}")
                return translation_system_prompt
        except Exception as e:
            handle_exception(func_name, e, f"reading default translation system prompt file {default_path}")

    # Fallback to hardcoded prompt
    debug_log("No translation system prompt files found, using hardcoded fallback", "WARNING")
    max_chars = CONFIG.get('alt_text_max_chars', 125)
    return f"You are a professional translator specializing in WCAG-compliant alternative text. Translate to {{TARGET_LANGUAGE}} while ensuring the output is exactly {max_chars} characters or less."

def translate_alt_text(alt_text, source_language, target_language, return_prompt: bool = False):
    """
    Translate alt-text from source language to target language while maintaining configured character limit.

    Args:
        alt_text (str): The alt-text to translate
        source_language (str): ISO language code of source text (e.g., 'en')
        target_language (str): ISO language code for translation (e.g., 'it', 'es')

    Returns:
        str: Translated alt-text (max config.alt_text_max_chars) or None if failed
    """
    func_name = "translate_alt_text"
    debug_log(f"Translating alt-text from {source_language} to {target_language}")

    try:
        # Get credentials based on configured LLM provider
        provider, credentials = get_llm_credentials()
        if not provider or credentials is None:
            debug_log("Failed to retrieve LLM credentials", "ERROR")
            return None

        # Initialize client based on provider
        if provider == 'OpenAI':
            client = OpenAI(api_key=credentials['api_key'])
        elif provider == 'Claude':
            from anthropic import Anthropic
            client = Anthropic(api_key=credentials['api_key'])
        elif provider == 'ECB-LLM':
            client = ECBAzureOpenAI()
        elif provider == 'Ollama':
            import ollama
            base_url = credentials.get('base_url', 'http://localhost:11434')
            client = ollama.Client(host=base_url)
        elif provider == 'Gemini':
            if not configure_gemini(credentials['api_key']):
                return None
            # Get model from config
            gemini_config = CONFIG.get('gemini', {})
            model_name = gemini_config.get('translation_model', gemini_config.get('model', 'gemini-2.0-flash-exp'))
            client = genai.GenerativeModel(model_name)
        else:
            debug_log(f"Unsupported provider: {provider}", "ERROR")
            return None

        # Language name mapping
        language_map = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
            'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish', 'bg': 'Bulgarian', 'cs': 'Czech',
            'da': 'Danish', 'el': 'Greek', 'et': 'Estonian', 'fi': 'Finnish', 'ga': 'Irish',
            'hr': 'Croatian', 'hu': 'Hungarian', 'lt': 'Lithuanian', 'lv': 'Latvian',
            'mt': 'Maltese', 'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sv': 'Swedish'
        }
        source_lang_name = language_map.get(source_language.lower(), source_language)
        target_lang_name = language_map.get(target_language.lower(), target_language)

        # Load translation prompts from files
        translation_prompt_folder = get_absolute_folder_path('prompt_translation')
        translation_prompt_template = load_translation_prompt(translation_prompt_folder)
        translation_system_prompt_template = load_translation_system_prompt(translation_prompt_folder)

        # Replace placeholders in translation prompt
        translation_prompt = translation_prompt_template.replace('{SOURCE_LANGUAGE}', source_lang_name)
        translation_prompt = translation_prompt.replace('{TARGET_LANGUAGE}', target_lang_name)
        translation_prompt = translation_prompt.replace('{ALT_TEXT}', alt_text)

        # Replace placeholders in system prompt
        translation_system_prompt = translation_system_prompt_template.replace('{TARGET_LANGUAGE}', target_lang_name)

        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": translation_system_prompt
            },
            {
                "role": "user",
                "content": translation_prompt
            }
        ]

        # Get translation model from provider-specific config
        provider_config = CONFIG.get(provider.lower().replace('-', '_'), {})
        model = provider_config.get('translation_model', provider_config.get('processing_model', 'gpt-4o'))
        debug_log(f"Using translation model: {model}")

        # Prepare API request parameters
        api_params = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": 200
        }

        # Make API request based on provider
        if provider == 'Claude':
            # Claude uses a different API structure
            response = client.messages.create(
                model=model,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": translation_prompt
                    }
                ],
                system=translation_system_prompt,  # Claude uses system parameter separately
                temperature=0.3
            )
            translated_text = response.content[0].text
        elif provider == 'Ollama':
            # Ollama uses a simpler API structure
            response = client.chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": translation_system_prompt
                    },
                    {
                        "role": "user",
                        "content": translation_prompt
                    }
                ]
            )
            translated_text = response['message']['content']
        elif provider == 'Gemini':
            # Gemini API structure
            combined_prompt = f"{translation_system_prompt}\n\n{translation_prompt}"
            response = client.generate_content(combined_prompt)
            translated_text = response.text
        else:
            # OpenAI and ECB-LLM use the standard OpenAI API
            # Only add temperature for models that support it (gpt-5.1 doesn't support custom temperature)
            if not model.startswith('gpt-5'):
                api_params["temperature"] = 0.3  # Lower temperature for more consistent translations

            response = client.chat.completions.create(**api_params)
            translated_text = response.choices[0].message.content

        # Check if response is None or empty
        if translated_text is None:
            debug_log(f"Translation API returned None response for {target_language}", "ERROR")
            debug_log(f"Full API response: {response}", "ERROR")
            return None

        translated_text = translated_text.strip()

        if not translated_text or len(translated_text) == 0:
            debug_log(f"Translation API returned empty response for {target_language}", "ERROR")
            debug_log(f"Response object: {response}", "ERROR")
            return None

        # Remove quotes if present
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]
        if translated_text.startswith("'") and translated_text.endswith("'"):
            translated_text = translated_text[1:-1]

        # Ensure compliance with configured max character limit
        max_chars = CONFIG.get('alt_text_max_chars', 125)
        if len(translated_text) > max_chars:
            debug_log(f"Translation exceeds {max_chars} chars ({len(translated_text)}), truncating", "WARNING")
            translated_text = translated_text[:max_chars - 3] + "..."

        if translated_text and not translated_text.endswith('.'):
            translated_text += "."

        debug_log(f"Translation successful: {translated_text} ({len(translated_text)} chars)")
        if return_prompt:
            return translated_text, {
                "system": translation_system_prompt,
                "user": translation_prompt
            }
        return translated_text

    except Exception as e:
        handle_exception(func_name, e, f"translating alt-text to {target_language}")
        if return_prompt:
            return None, None
        return None


def translate_text(text, source_language, target_language, text_type="reasoning"):
    """
    Translate any text from source language to target language.

    Args:
        text (str): The text to translate
        source_language (str): ISO language code of source text (e.g., 'en')
        target_language (str): ISO language code for translation (e.g., 'it', 'es')
        text_type (str): Type of text being translated (for context in prompt)

    Returns:
        str: Translated text or None if failed
    """
    func_name = "translate_text"
    debug_log(f"Translating {text_type} from {source_language} to {target_language}")

    try:
        # Get credentials based on configured LLM provider
        provider, credentials = get_llm_credentials()
        if not provider or credentials is None:
            debug_log("Failed to retrieve LLM credentials", "ERROR")
            return None

        # Initialize client based on provider
        if provider == 'OpenAI':
            client = OpenAI(api_key=credentials['api_key'])
        elif provider == 'Claude':
            from anthropic import Anthropic
            client = Anthropic(api_key=credentials['api_key'])
        elif provider == 'ECB-LLM':
            client = ECBAzureOpenAI()
        elif provider == 'Ollama':
            import ollama
            base_url = credentials.get('base_url', 'http://localhost:11434')
            client = ollama.Client(host=base_url)
        elif provider == 'Gemini':
            if not GEMINI_AVAILABLE or genai is None:
                debug_log("Google GenAI client not installed. Install google-genai (or google-generativeai for fallback).", "ERROR")
                return None
            genai.configure(api_key=credentials['api_key'])
            # Get model from config
            gemini_config = CONFIG.get('gemini', {})
            model_name = gemini_config.get('translation_model', gemini_config.get('model', 'gemini-2.0-flash-exp'))
            client = genai.GenerativeModel(model_name)
        else:
            debug_log(f"Unsupported provider: {provider}", "ERROR")
            return None

        # Language name mapping
        language_map = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian',
            'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish', 'bg': 'Bulgarian', 'cs': 'Czech',
            'da': 'Danish', 'el': 'Greek', 'et': 'Estonian', 'fi': 'Finnish', 'ga': 'Irish',
            'hr': 'Croatian', 'hu': 'Hungarian', 'lt': 'Lithuanian', 'lv': 'Latvian',
            'mt': 'Maltese', 'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sv': 'Swedish'
        }
        source_lang_name = language_map.get(source_language.lower(), source_language)
        target_lang_name = language_map.get(target_language.lower(), target_language)

        # Create translation prompt
        translation_prompt = f"""Translate the following {text_type} text from {source_lang_name} to {target_lang_name}.

REQUIREMENTS:
1. Maintain the meaning and technical accuracy
2. Be natural in the target language
3. Preserve any technical terminology appropriately

Source text ({source_lang_name}): "{text}"

Provide ONLY the translated text in {target_lang_name}, nothing else. Do not include explanations or metadata."""

        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": f"You are a professional translator. Translate to {target_lang_name} while maintaining accuracy and naturalness."
            },
            {
                "role": "user",
                "content": translation_prompt
            }
        ]

        # Get translation model from credentials
        model = credentials.get('translation_model', 'gpt-4o')
        debug_log(f"Using translation model: {model}")

        # Make API request based on provider
        if provider == 'Claude':
            # Claude uses a different API structure
            response = client.messages.create(
                model=model,
                max_tokens=500,
                messages=[{"role": "user", "content": translation_prompt}]
            )
            translated_text = response.content[0].text.strip()
        elif provider == 'Ollama':
            # Ollama uses a different API structure
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": translation_prompt}]
            )
            translated_text = response['message']['content'].strip()
        elif provider == 'Gemini':
            # Gemini API structure
            response = client.generate_content(translation_prompt)
            translated_text = response.text.strip()
        else:
            # OpenAI and ECB-LLM use OpenAI-compatible API
            api_params = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": 500
            }

            # Only add temperature for models that support it
            if not model.startswith('gpt-5'):
                api_params["temperature"] = 0.3

            response = client.chat.completions.create(**api_params)
            translated_text = response.choices[0].message.content.strip()

        # Remove quotes if present
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]
        if translated_text.startswith("'") and translated_text.endswith("'"):
            translated_text = translated_text[1:-1]

        debug_log(f"Translation successful: {translated_text[:100]}...")
        return translated_text

    except Exception as e:
        handle_exception(func_name, e, f"translating {text_type} to {target_language}")
        return None


def analyze_image_with_ai(image_path, combined_prompt, credentials, language=None, vision_prompt=None):
    """
    Analyze an image using two-step processing with support for all AI providers.

    This is the main image analysis function that supports:
    - OpenAI (GPT-4o, GPT-5.x)
    - Claude (Sonnet, Opus, Haiku)
    - ECB-LLM (internal ECB service)
    - Ollama (local models)

    Supports mixed providers (e.g., Claude for vision, OpenAI for processing).

    Args:
        image_path (str): Path to the image file
        combined_prompt (str): The combined prompt with context for analysis
        credentials (dict): DEPRECATED - kept for backward compatibility
        language (str): ISO language code for alt-text generation
        vision_prompt (str): Optional vision prompt for step 1. If None, loads from vision folder.

    Returns:
        dict: Parsed response with image_type, image_description, reasoning, and alt_text
    """
    func_name = "analyze_image_with_ai"

    debug_log(f"Starting two-step analysis for: {image_path} with multi-provider support")

    try:
        # Get provider and model configuration for each step
        vision_provider, vision_model, vision_creds = get_step_config('vision')
        processing_provider, processing_model, processing_creds = get_step_config('processing')
        translation_provider, translation_model, _ = get_step_config('translation')

        if not vision_provider or not processing_provider:
            debug_log("Failed to retrieve step configurations", "ERROR")
            return None

        debug_log(f"Vision step: {vision_provider} / {vision_model}")
        debug_log(f"Processing step: {processing_provider} / {processing_model}")
        debug_log(f"Translation step: {translation_provider} / {translation_model}")

        # Load vision prompt if not provided
        if vision_prompt is None:
            vision_prompt_folder = get_absolute_folder_path('prompt_vision')
            vision_prompt = load_vision_prompt(vision_prompt_folder)

        debug_log(f"Using vision prompt: {vision_prompt[:100]}...")

        # STEP 1: Vision model generates image description
        debug_log(f"Step 1: Generating image description with {vision_provider} / {vision_model}")

        if vision_provider == 'Ollama':
            # Ollama-specific initialization
            base_url = vision_creds.get('base_url', 'http://localhost:11434')
            vision_client = ollama.Client(host=base_url)
            debug_log(f"Ollama client initialized with host: {base_url}")

            # Ollama expects base64-encoded image data, not file paths
            # Handle SVG conversion to PNG for vision model compatibility
            import base64
            from mimetypes import guess_type

            mime_type, _ = guess_type(image_path)
            if mime_type == "image/svg+xml":
                if not SVG_SUPPORT:
                    debug_log("SVG file detected but cairosvg not installed. Cannot convert to PNG.", "ERROR")
                    raise ValueError("SVG conversion not supported. Install cairosvg: pip install cairosvg")

                debug_log(f"SVG file detected: {image_path}. Converting to PNG for Ollama vision model...")
                try:
                    with open(image_path, "rb") as svg_file:
                        svg_data = svg_file.read()
                    # Convert SVG to PNG
                    png_data = cairosvg.svg2png(bytestring=svg_data)
                    image_data = base64.b64encode(png_data).decode('utf-8')
                    debug_log(f"Successfully converted SVG to PNG (size: {len(png_data)} bytes)")
                except Exception as e:
                    debug_log(f"Failed to convert SVG to PNG: {str(e)}", "ERROR")
                    raise
            else:
                # Regular image file
                with open(image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')

            vision_response = vision_client.chat(
                model=vision_model,
                messages=[{
                    'role': 'user',
                    'content': vision_prompt,
                    'images': [image_data]
                }]
            )
            image_description = vision_response['message']['content']

        elif vision_provider == 'Claude':
            # Claude (Anthropic) initialization
            from anthropic import Anthropic
            import base64
            from mimetypes import guess_type

            vision_client = Anthropic(api_key=vision_creds['api_key'])
            debug_log("Claude client initialized")

            # Read and encode image to base64
            mime_type, _ = guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/png'  # Default fallback

            # Handle SVG conversion if needed
            if mime_type == "image/svg+xml":
                if not SVG_SUPPORT:
                    debug_log("SVG file detected but cairosvg not installed. Cannot convert to PNG.", "ERROR")
                    raise ValueError("SVG conversion not supported. Install cairosvg: pip install cairosvg")

                debug_log(f"SVG file detected: {image_path}. Converting to PNG for Claude vision...")
                with open(image_path, "rb") as svg_file:
                    svg_data = svg_file.read()
                png_data = cairosvg.svg2png(bytestring=svg_data)
                image_data = base64.standard_b64encode(png_data).decode('utf-8')
                media_type = "image/png"
            else:
                with open(image_path, 'rb') as img_file:
                    image_data = base64.standard_b64encode(img_file.read()).decode('utf-8')
                # Map MIME types to Claude's expected format
                media_type = mime_type if mime_type in ['image/jpeg', 'image/png', 'image/gif', 'image/webp'] else 'image/png'

            try:
                vision_response = vision_client.messages.create(
                    model=vision_model,
                    max_tokens=1024,
                    messages=[{
                        'role': 'user',
                        'content': [
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': media_type,
                                    'data': image_data
                                }
                            },
                            {
                                'type': 'text',
                                'text': vision_prompt
                            }
                        ]
                    }]
                )
                image_description = vision_response.content[0].text
            except Exception as claude_error:
                debug_log(f"Claude API error: {str(claude_error)}", "ERROR")
                # Check for common errors
                error_msg = str(claude_error).lower()
                if 'api_key' in error_msg or 'authentication' in error_msg:
                    raise ValueError("Claude API authentication failed. Check ANTHROPIC_API_KEY environment variable.")
                elif 'model' in error_msg:
                    raise ValueError(f"Claude model '{vision_model}' not found or not accessible.")
                elif 'rate_limit' in error_msg:
                    raise ValueError("Claude API rate limit exceeded. Please try again later.")
                else:
                    raise ValueError(f"Claude API error: {str(claude_error)}")

        elif vision_provider in ['OpenAI', 'ECB-LLM']:
            # OpenAI/ECB-LLM initialization
            if vision_provider == 'OpenAI':
                from openai import OpenAI
                vision_client = OpenAI(api_key=vision_creds['api_key'])
            else:  # ECB-LLM
                vision_client = ECBAzureOpenAI()

            # Convert image to data URL
            image_data_url = local_image_to_data_url(image_path)

            vision_response = vision_client.chat.completions.create(
                model=vision_model,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': vision_prompt},
                        {'type': 'image_url', 'image_url': {'url': image_data_url}}
                    ]
                }],
                max_completion_tokens=1000
            )
            image_description = vision_response.choices[0].message.content

        elif vision_provider == 'Gemini':
            # Gemini initialization
            if not configure_gemini(vision_creds['api_key']):
                return None
            vision_client = genai.GenerativeModel(vision_model)
            debug_log("Gemini client initialized")

            # Read image file
            import PIL.Image
            try:
                image = PIL.Image.open(image_path)

                # Generate description using Gemini's vision capabilities
                response = vision_client.generate_content([vision_prompt, image])
                image_description = response.text
                debug_log(f"Gemini vision analysis complete")
            except Exception as gemini_error:
                debug_log(f"Gemini API error: {str(gemini_error)}", "ERROR")
                error_msg = str(gemini_error).lower()
                if 'api_key' in error_msg or 'authentication' in error_msg or 'invalid' in error_msg:
                    raise ValueError("Gemini API authentication failed. Check GEMINI_API_KEY environment variable.")
                elif 'quota' in error_msg or 'resource_exhausted' in error_msg:
                    raise ValueError("Gemini API quota exceeded. Please check your billing and usage limits.")
                elif 'rate_limit' in error_msg or 'too many requests' in error_msg:
                    raise ValueError("Gemini API rate limit exceeded. Please try again later.")
                else:
                    raise ValueError(f"Gemini API error: {str(gemini_error)}")

        else:
            debug_log(f"Unsupported provider for vision step: {vision_provider}", "ERROR")
            return None

        debug_log(f"Image description generated: {image_description[:200]}...")

        # STEP 2: Processing model generates structured JSON with WCAG alt-text
        debug_log(f"Step 2: Processing with {processing_provider} / {processing_model} to generate alt-text")

        processing_prompt = f"""{combined_prompt}

Based on this image description, generate the required JSON output:
{image_description}"""

        # Initialize client for processing step (may be different provider than vision)
        if processing_provider == 'Ollama':
            base_url = processing_creds.get('base_url', 'http://localhost:11434')
            processing_client = ollama.Client(host=base_url)
            processing_response = processing_client.chat(
                model=processing_model,
                messages=[{
                    'role': 'user',
                    'content': processing_prompt
                }]
            )
            response_text = processing_response['message']['content']

        elif processing_provider == 'Claude':
            from anthropic import Anthropic
            processing_client = Anthropic(api_key=processing_creds['api_key'])
            processing_response = processing_client.messages.create(
                model=processing_model,
                max_tokens=1024,
                messages=[{
                    'role': 'user',
                    'content': processing_prompt
                }]
            )
            response_text = processing_response.content[0].text

        elif processing_provider in ['OpenAI', 'ECB-LLM']:
            if processing_provider == 'OpenAI':
                from openai import OpenAI
                processing_client = OpenAI(api_key=processing_creds['api_key'])
            else:  # ECB-LLM
                processing_client = ECBAzureOpenAI()

            processing_response = processing_client.chat.completions.create(
                model=processing_model,
                messages=[{
                    'role': 'user',
                    'content': processing_prompt
                }],
                max_completion_tokens=1000
            )
            response_text = processing_response.choices[0].message.content

        elif processing_provider == 'Gemini':
            if not configure_gemini(processing_creds['api_key']):
                return None
            processing_client = genai.GenerativeModel(processing_model)
            processing_response = processing_client.generate_content(processing_prompt)
            response_text = processing_response.text

        else:
            debug_log(f"Unsupported provider for processing step: {processing_provider}", "ERROR")
            return None

        debug_log(f"Processing response (first 500 chars): {response_text[:500]}...")

        # Parse JSON from response
        result = None
        try:
            # Try to parse entire response as JSON
            parsed_response = json.loads(response_text)
            if isinstance(parsed_response, dict):
                debug_log("Successfully parsed response as JSON", "INFORMATION")
                result = parsed_response
        except json.JSONDecodeError:
            debug_log("Response contains additional text, extracting JSON block", "INFORMATION")

        # Extract JSON from text if not yet parsed
        if result is None:
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')

            if first_brace != -1 and last_brace != -1:
                json_str = response_text[first_brace:last_brace + 1]
                try:
                    parsed_response = json.loads(json_str)
                    debug_log("Successfully extracted JSON from response", "INFORMATION")
                    result = parsed_response
                except json.JSONDecodeError:
                    debug_log("Could not parse JSON from response", "WARNING")

        # Fallback: create basic response structure
        if result is None:
            debug_log("Creating fallback response structure", "WARNING")
            max_chars = CONFIG.get('alt_text_max_chars', 125)
            result = {
                "image_type": "informative",
                "image_description": image_description,
                "reasoning": f"Generated via {processing_provider} two-step processing",
                "alt_text": image_description[:max_chars]  # Truncate to configured limit
            }

        # Add vision model output to the result (Step 1 output)
        result['vision_model_output'] = image_description

        # Add model information to the result (including provider info for mixed-provider support)
        result['_models_used'] = {
            'vision_provider': vision_provider,
            'vision_model': vision_model,
            'processing_provider': processing_provider,
            'processing_model': processing_model,
            'translation_provider': translation_provider,
            'translation_model': translation_model
        }

        return result

    except Exception as e:
        handle_exception(func_name, e, f"analyzing image with mixed providers (vision={vision_provider}, processing={processing_provider})")
        return None


def analyze_image_with_openai(image_path, combined_prompt, language=None):
    """
    DEPRECATED: This function is deprecated and will be removed in a future version.
    Use analyze_image_with_ai() instead, which supports all AI providers.

    This function now acts as a simple wrapper that routes all calls to analyze_image_with_ai().

    Args:
        image_path (str): Path to the image file
        combined_prompt (str): The combined prompt with context for analysis
        language (str): ISO language code for alt-text generation

    Returns:
        dict: Parsed response with image_type, image_description, reasoning, and alt_text
    """
    import warnings
    warnings.warn(
        "analyze_image_with_openai() is deprecated. Use analyze_image_with_ai() instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Get credentials for backward compatibility
    provider, credentials = get_llm_credentials()
    if not provider or credentials is None:
        debug_log("Failed to retrieve LLM credentials", "ERROR")
        return None

    # Route to the new multi-provider function
    return analyze_image_with_ai(image_path, combined_prompt, credentials, language)


# Backward compatibility alias for Ollama function (old name)
def analyze_image_with_ollama(image_path, combined_prompt, credentials, language=None, vision_prompt=None):
    """
    DEPRECATED: This function has been renamed to analyze_image_with_ai().
    This is a backward compatibility alias that will be removed in a future version.

    Args:
        image_path (str): Path to the image file
        combined_prompt (str): The combined prompt with context for analysis
        credentials (dict): DEPRECATED - kept for backward compatibility
        language (str): ISO language code for alt-text generation
        vision_prompt (str): Optional vision prompt for step 1

    Returns:
        dict: Parsed response with image_type, image_description, reasoning, and alt_text
    """
    import warnings
    warnings.warn(
        "analyze_image_with_ollama() has been renamed to analyze_image_with_ai(). Please update your code.",
        DeprecationWarning,
        stacklevel=2
    )
    return analyze_image_with_ai(image_path, combined_prompt, credentials, language, vision_prompt)


def _analyze_image_with_openai_legacy(image_path, combined_prompt, language=None):
    """
    LEGACY IMPLEMENTATION - KEPT FOR REFERENCE ONLY
    This is the old single-step processing implementation.
    It has been replaced by analyze_image_with_ai() which supports all providers
    and both single-step and two-step processing modes.

    This function is not called anywhere and exists only for historical reference.
    It will be removed in a future version.

    DO NOT USE THIS FUNCTION - Use analyze_image_with_ai() instead.
    """
    func_name = "_analyze_image_with_openai_legacy"
    debug_log(f"WARNING: Using deprecated legacy function - this should not be called", "ERROR")
    raise DeprecationWarning("This legacy function should not be called. Use analyze_image_with_ai() instead.")


def download_images_from_url(url, images_folder=None, max_images=None):
    """
    Downloads images from a given URL to the specified folder.

    Args:
        url (str): The URL to scrape images from
        images_folder (str): Folder to save images (uses config default if None)
        max_images (int): Maximum number of images to download (None for all)

    Returns:
        tuple: (list of filenames, dict of {filename: {tag, attribute, url}}, page_title)
    """
    func_name = "download_images_from_url"
    debug_log(f"Starting {func_name} for URL: {url}")

    try:
        # Use config values
        if images_folder is None:
            images_folder = get_absolute_folder_path('images')

        timeout = CONFIG.get('download', {}).get('timeout', 30)
        delay = CONFIG.get('download', {}).get('delay_between_requests', 0.5)
        user_agent = CONFIG.get('download', {}).get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        debug_log(f"Using images folder: {images_folder}")
        debug_log(f"Request timeout: {timeout}s, delay: {delay}s")
        if max_images:
            debug_log(f"Maximum images to download: {max_images}")

        # Create folder if it doesn't exist
        if not os.path.exists(images_folder):
            os.makedirs(images_folder)
            debug_log(f"Created directory: {images_folder}")

        downloaded_images = []
        image_metadata = {}  # Store {filename: {tag, attribute, url}}

        headers = {'User-Agent': user_agent}
        debug_log(f"Making request to: {url}")

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        debug_log(f"Successfully retrieved page content ({len(response.content)} bytes)")

        # Check if URL points directly to an image file
        content_type = response.headers.get('content-type', '').lower()
        debug_log(f"Content-Type: {content_type}")

        # If Content-Type indicates this is an image, download it directly
        if content_type.startswith('image/'):
            debug_log("URL points directly to an image file, downloading directly")

            # Determine filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)

            if not filename or '.' not in filename:
                # Generate filename based on content type
                ext_map = {
                    'image/jpeg': '.jpg',
                    'image/jpg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/svg+xml': '.svg',
                    'image/webp': '.webp',
                    'image/bmp': '.bmp',
                    'image/tiff': '.tiff'
                }
                ext = ext_map.get(content_type, '.jpg')
                filename = f"image_1{ext}"
                debug_log(f"Generated filename from content-type: {filename}")

            # Handle filename conflicts
            filepath = os.path.join(images_folder, filename)
            counter = 1
            base_name, ext = os.path.splitext(filename)
            original_filename = filename

            while os.path.exists(filepath):
                filename = f"{base_name}_{counter}{ext}"
                filepath = os.path.join(images_folder, filename)
                counter += 1

            if filename != original_filename:
                debug_log(f"Filename conflict resolved: {original_filename} -> {filename}")

            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            downloaded_images.append(filename)

            # Store metadata - mark as direct download
            image_metadata[filename] = {
                'tag': 'direct',
                'attribute': 'url',
                'url': url
            }

            debug_log(f"Successfully saved direct image: {filepath}")
            if CONFIG.get('logging', {}).get('show_information', True):
                log_message(f"Downloaded direct image: {filename}", "INFORMATION")

            # Return early - no HTML parsing needed
            return (downloaded_images, image_metadata, "")

        # Otherwise, parse as HTML page
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract page title
        page_title = ""
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text().strip()
            debug_log(f"Page title: {page_title}")

        # Get configuration for which tags and attributes to use
        enabled_tags = get_enabled_image_tags()
        enabled_attrs = get_enabled_image_attributes()

        debug_log(f"Using configured tags: {', '.join(enabled_tags)}")
        debug_log(f"Using configured attributes: {', '.join(enabled_attrs)}")

        # Collect all image sources from various tags and attributes
        # Store as list of dicts: [{url, tag, attribute}, ...]
        image_sources = []

        # Get images from img tags (if enabled)
        if 'img' in enabled_tags:
            img_tags = soup.find_all('img')
            for img in img_tags:
                img_url, attr_used = get_image_url_and_attribute(img, enabled_attrs)
                if img_url:
                    image_sources.append({'url': img_url, 'tag': 'img', 'attribute': attr_used})

        # Get images from picture elements (if enabled)
        if 'picture' in enabled_tags:
            picture_tags = soup.find_all('picture')
            for picture in picture_tags:
                # Check source elements within picture
                sources = picture.find_all('source')
                for source in sources:
                    src, attr_used = get_image_url_and_attribute(source, enabled_attrs)
                    if src:
                        # srcset can have multiple URLs, use the first one
                        src_url = src.split(',')[0].split()[0]
                        if not any(img['url'] == src_url for img in image_sources):
                            image_sources.append({'url': src_url, 'tag': 'picture>source', 'attribute': attr_used})

                # Also check img inside picture
                img_in_picture = picture.find('img')
                if img_in_picture:
                    img_url, attr_used = get_image_url_and_attribute(img_in_picture, enabled_attrs)
                    if img_url and not any(img['url'] == img_url for img in image_sources):
                        image_sources.append({'url': img_url, 'tag': 'picture>img', 'attribute': attr_used})

        # Get images from div elements with data-image attributes (if enabled)
        if 'div' in enabled_tags:
            div_tags = soup.find_all('div')
            for div in div_tags:
                div_url, attr_used = get_image_url_and_attribute(div, enabled_attrs)
                if div_url and not any(img['url'] == div_url for img in image_sources):
                    image_sources.append({'url': div_url, 'tag': 'div', 'attribute': attr_used})

        # Get images from link elements (favicons, touch icons) (if enabled)
        if 'link' in enabled_tags:
            link_tags = soup.find_all('link')
            for link in link_tags:
                # Check if this is an icon-related link
                rel = link.get('rel', [])
                if isinstance(rel, list):
                    rel_str = ' '.join(rel)
                else:
                    rel_str = rel

                # Look for icon-related rel attributes
                if any(icon_type in rel_str.lower() for icon_type in ['icon', 'apple-touch-icon', 'shortcut']):
                    link_url, attr_used = get_image_url_and_attribute(link, enabled_attrs)
                    if link_url and not any(img['url'] == link_url for img in image_sources):
                        image_sources.append({'url': link_url, 'tag': 'link', 'attribute': attr_used})
                        debug_log(f"Found favicon/icon from link tag: {link_url}")

        # Get images from meta tags (Open Graph, Twitter Cards) (if enabled)
        if 'meta' in enabled_tags:
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                # Check for Open Graph images (og:image)
                property_attr = meta.get('property', '')
                name_attr = meta.get('name', '')

                # Look for image-related meta tags (but exclude width/height properties)
                if (any(img_type in property_attr.lower() for img_type in ['og:image', 'twitter:image']) or \
                    any(img_type in name_attr.lower() for img_type in ['og:image', 'twitter:image'])) and \
                   not any(exclude in property_attr.lower() for exclude in ['width', 'height', 'alt']):
                    meta_url, attr_used = get_image_url_and_attribute(meta, enabled_attrs)
                    # Validate that the URL looks like an image URL (contains image extension or http)
                    if meta_url and not any(img['url'] == meta_url for img in image_sources):
                        # Skip if it looks like a dimension value (pure number)
                        if not meta_url.isdigit():
                            image_sources.append({'url': meta_url, 'tag': 'meta', 'attribute': attr_used})
                            debug_log(f"Found Open Graph/Twitter image from meta tag: {meta_url}")

        debug_log(f"Found {len(image_sources)} total image sources on the page")

        if CONFIG.get('logging', {}).get('show_information', True):
            if max_images:
                log_message(f"Found {len(image_sources)} image sources on the page (will download max {max_images})")
            else:
                log_message(f"Found {len(image_sources)} image sources on the page")

        # Calculate total images for progress
        total_to_download = min(len(image_sources), max_images) if max_images else len(image_sources)

        for i, img_data in enumerate(image_sources):
            # Check if we've reached the maximum number of images to download
            if max_images and len(downloaded_images) >= max_images:
                debug_log(f"Reached maximum number of images ({max_images}), stopping download")
                if CONFIG.get('logging', {}).get('show_information', True):
                    log_message(f"Reached maximum number of images ({max_images}), stopping download")
                break

            debug_log(f"Processing image {i+1}/{len(image_sources)}")

            # Report download progress (10-30% range for downloading phase)
            download_percent = 10 + int((i / total_to_download) * 20)
            write_progress(
                download_percent,
                f"Downloading image {i+1} of {total_to_download}...",
                phase="downloading",
                current_image=i+1,
                total_images=total_to_download
            )

            try:
                img_url = img_data['url']
                img_tag = img_data['tag']
                img_attr = img_data['attribute']

                if not img_url:
                    debug_log(f"Image {i+1} has no URL, skipping")
                    continue

                # Convert relative URLs to absolute
                img_url_absolute = urljoin(url, img_url)
                debug_log(f"Image URL: {img_url_absolute}")
                
                img_response = requests.get(img_url_absolute, headers=headers, timeout=timeout)
                img_response.raise_for_status()
                debug_log(f"Downloaded image content ({len(img_response.content)} bytes)")

                # Determine filename
                parsed_url = urlparse(img_url_absolute)
                filename = os.path.basename(parsed_url.path)
                
                if not filename or '.' not in filename:
                    content_type = img_response.headers.get('content-type', '')
                    debug_log(f"No filename in URL, using content-type: {content_type}")
                    
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        filename = f"image_{i+1}.jpg"
                    elif 'png' in content_type:
                        filename = f"image_{i+1}.png"
                    elif 'gif' in content_type:
                        filename = f"image_{i+1}.gif"
                    elif 'webp' in content_type:
                        filename = f"image_{i+1}.webp"
                    else:
                        filename = f"image_{i+1}.jpg"
                
                # Handle filename conflicts
                filepath = os.path.join(images_folder, filename)
                counter = 1
                base_name, ext = os.path.splitext(filename)
                original_filename = filename
                
                while os.path.exists(filepath):
                    filename = f"{base_name}_{counter}{ext}"
                    filepath = os.path.join(images_folder, filename)
                    counter += 1
                
                if filename != original_filename:
                    debug_log(f"Filename conflict resolved: {original_filename} -> {filename}")
                
                # Save file
                with open(filepath, 'wb') as f:
                    f.write(img_response.content)

                downloaded_images.append(filename)

                # Store metadata for this image
                image_metadata[filename] = {
                    'tag': img_tag,
                    'attribute': img_attr,
                    'url': img_url_absolute
                }

                debug_log(f"Successfully saved: {filepath}")
                
                if CONFIG.get('logging', {}).get('show_information', True):
                    log_message(f"Downloaded: {filename}", "INFORMATION")
                
                if delay > 0:
                    time.sleep(delay)
                
            except requests.exceptions.RequestException as e:
                handle_exception(func_name, e, f"downloading image {i+1}: {img_url_absolute}")
                continue
            except IOError as e:
                handle_exception(func_name, e, f"saving image {i+1} to {filepath}")
                continue
            except Exception as e:
                handle_exception(func_name, e, f"processing image {i+1}")
                continue

    except requests.exceptions.RequestException as e:
        handle_exception(func_name, e, f"accessing URL: {url}")
        return ([], {}, "")
    except Exception as e:
        handle_exception(func_name, e, f"general error")
        return ([], {}, "")

    debug_log(f"Download complete: {len(downloaded_images)} images successfully downloaded")
    if CONFIG.get('logging', {}).get('show_information', True):
        log_message(f"Successfully downloaded {len(downloaded_images)} images", "INFORMATION")

    return (downloaded_images, image_metadata, page_title)


def grab_context(image_filename, url, context_folder=None):
    """
    Crawls the URL to find a specific image and extracts surrounding text context.

    Args:
        image_filename (str): Name of the image file to search for
        url (str): The URL to crawl for the image
        context_folder (str): Folder to save context files (uses config default if None)

    Returns:
        tuple: (context_file_path, image_url, current_alt_text) or (None, None, None) if image not found
    """
    func_name = "grab_context"
    debug_log(f"Starting {func_name} for image: {image_filename}")
    debug_log(f"Target URL: {url}")
    
    try:
        # Use config values
        if context_folder is None:
            context_folder = get_absolute_folder_path('context')
        
        timeout = CONFIG.get('download', {}).get('timeout', 30)
        user_agent = CONFIG.get('download', {}).get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        max_text_length = CONFIG.get('context', {}).get('max_text_length', 1000)
        min_text_length = CONFIG.get('context', {}).get('min_text_length', 20)
        max_sibling_text_length = CONFIG.get('context', {}).get('max_sibling_text_length', 500)

        # Get context detail level and apply settings
        detail_level = CONFIG.get('context', {}).get('detail_level', 'medium').lower()
        if detail_level == 'low':
            max_parent_levels = 1
            max_headings = 1
        elif detail_level == 'high':
            max_parent_levels = CONFIG.get('context', {}).get('max_parent_levels', 5)
            max_headings = 999  # No limit on headings
        else:  # medium (default)
            max_parent_levels = 3
            max_headings = CONFIG.get('context', {}).get('max_headings', 3)

        debug_log(f"Using context folder: {context_folder}")
        debug_log(f"Context detail level: {detail_level} (max_parent_levels={max_parent_levels}, max_headings={max_headings})")
        
        # Create folder if it doesn't exist
        if not os.path.exists(context_folder):
            os.makedirs(context_folder)
            debug_log(f"Created directory: {context_folder}")
        
        headers = {'User-Agent': user_agent}
        debug_log(f"Making request to: {url}")
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        debug_log(f"Successfully retrieved page content ({len(response.content)} bytes)")
        
        soup = BeautifulSoup(response.content, 'html.parser')

        # Get configuration for which tags and attributes to use
        enabled_tags = get_enabled_image_tags()
        enabled_attrs = get_enabled_image_attributes()

        debug_log(f"Using configured tags: {', '.join(enabled_tags)}")
        debug_log(f"Using configured attributes: {', '.join(enabled_attrs)}")

        # Remove the extension from image_filename for comparison
        image_name_base = os.path.splitext(image_filename)[0]
        debug_log(f"Searching for image with base name: {image_name_base}")

        target_img = None
        found_image_url = None

        # Search through img tags (if enabled)
        if 'img' in enabled_tags:
            img_tags = soup.find_all('img')
            debug_log(f"Found {len(img_tags)} img tags on page")

            for i, img in enumerate(img_tags):
                # Check configured attributes
                img_src = get_image_url_from_element(img, enabled_attrs)

                if not img_src:
                    debug_log(f"Image {i+1} has no configured attributes, skipping")
                    continue

                # Check if the image filename matches
                img_path = urlparse(img_src).path
                img_basename = os.path.basename(img_path)
                img_name_no_ext = os.path.splitext(img_basename)[0]

                debug_log(f"Checking img tag {i+1}: {img_basename}")

                if (image_filename.lower() in img_basename.lower() or
                    image_name_base.lower() in img_name_no_ext.lower() or
                    img_basename.lower() in image_filename.lower()):
                    target_img = img
                    found_image_url = urljoin(url, img_src)
                    debug_log(f"Found matching image in img tag: {img_basename}")
                    debug_log(f"Image URL: {found_image_url}")
                    break

        # If not found in img tags, search in picture elements (if enabled)
        if not target_img and 'picture' in enabled_tags:
            picture_tags = soup.find_all('picture')
            debug_log(f"Image not found in img tags, searching {len(picture_tags)} picture elements")

            for i, picture in enumerate(picture_tags):
                # Check source elements within picture
                sources = picture.find_all('source')
                for source in sources:
                    src = get_image_url_from_element(source, enabled_attrs)

                    if src:
                        # srcset can have multiple URLs, check the first one
                        src_url = src.split(',')[0].split()[0]
                        img_path = urlparse(src_url).path
                        img_basename = os.path.basename(img_path)
                        img_name_no_ext = os.path.splitext(img_basename)[0]

                        debug_log(f"Checking picture source {i+1}: {img_basename}")

                        if (image_filename.lower() in img_basename.lower() or
                            image_name_base.lower() in img_name_no_ext.lower() or
                            img_basename.lower() in image_filename.lower()):
                            # Use the picture element's img child if available, otherwise the source
                            target_img = picture.find('img') or source
                            found_image_url = urljoin(url, src_url)
                            debug_log(f"Found matching image in picture element: {img_basename}")
                            debug_log(f"Image URL: {found_image_url}")
                            break

                if target_img:
                    break

        # If not found, search in div elements (if enabled)
        if not target_img and 'div' in enabled_tags:
            div_tags = soup.find_all('div')
            debug_log(f"Image not found in img/picture tags, searching {len(div_tags)} div elements")

            for i, div in enumerate(div_tags):
                div_src = get_image_url_from_element(div, enabled_attrs)

                if div_src:
                    img_path = urlparse(div_src).path
                    img_basename = os.path.basename(img_path)
                    img_name_no_ext = os.path.splitext(img_basename)[0]

                    debug_log(f"Checking div {i+1}: {img_basename}")

                    if (image_filename.lower() in img_basename.lower() or
                        image_name_base.lower() in img_name_no_ext.lower() or
                        img_basename.lower() in image_filename.lower()):
                        target_img = div
                        found_image_url = urljoin(url, div_src)
                        debug_log(f"Found matching image in div element: {img_basename}")
                        debug_log(f"Image URL: {found_image_url}")
                        break

        if not target_img:
            error_msg = f"Image '{image_filename}' not found on the page"
            debug_log(error_msg, "WARNING")
            return (None, None)
        
        debug_log("Starting context extraction...")
        context_text = []
        
        # Get alt text if available (store for return)
        current_alt_text = target_img.get('alt', '').strip()
        if current_alt_text:
            context_text.append(f"Alt text: {current_alt_text}")
            debug_log(f"Found current alt text: {current_alt_text}")
        else:
            current_alt_text = ""  # Empty string if no alt text found
        
        # Get title attribute if available
        title_text = target_img.get('title', '').strip()
        if title_text:
            context_text.append(f"Title: {title_text}")
            debug_log(f"Found title text: {title_text}")
        
        # Look for headings in parent elements
        current_element = target_img
        heading_count = 0
        debug_log(f"Searching up to {max_parent_levels} parent levels for context (max {max_headings} headings)")

        for level in range(max_parent_levels):
            if current_element.parent:
                current_element = current_element.parent
                debug_log(f"Checking parent level {level+1}: {current_element.name}")

                # Find headings (h1-h6) in this level
                headings = current_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for heading in headings:
                    # Stop if we've reached the max_headings limit
                    if heading_count >= max_headings:
                        debug_log(f"Reached max_headings limit ({max_headings}), stopping heading collection")
                        break

                    heading_text = heading.get_text().strip()
                    if heading_text and heading_text not in [c.split(': ', 1)[1] for c in context_text if c.startswith('Heading: ')]:
                        context_text.append(f"Heading: {heading_text}")
                        heading_count += 1
                        debug_log(f"Found heading: {heading_text}")

                # Break out of parent loop if we've hit the limit
                if heading_count >= max_headings:
                    break
                
                # Get text content from the section
                if current_element.name in ['section', 'article', 'div', 'main']:
                    section_text = current_element.get_text(separator=' ', strip=True)
                    section_text = ' '.join(section_text.split())
                    
                    if len(section_text) > max_text_length:
                        section_text = section_text[:max_text_length] + "..."
                        debug_log(f"Truncated section text to {max_text_length} characters")
                    
                    if section_text and len(section_text) > 50:
                        context_text.append(f"Section text: {section_text}")
                        debug_log(f"Found section text ({len(section_text)} chars)")
                        break
        
        # Look for captions or figure elements
        figure_parent = target_img.find_parent(['figure', 'figcaption'])
        if figure_parent:
            debug_log("Found figure parent element")
            caption = figure_parent.find('figcaption')
            if caption:
                caption_text = caption.get_text().strip()
                if caption_text:
                    context_text.append(f"Caption: {caption_text}")
                    debug_log(f"Found caption: {caption_text}")
        
        # Look for nearby text elements (siblings) - but avoid duplicates
        if target_img.parent:
            siblings = target_img.parent.find_all(['p', 'span', 'div'], limit=3)
            debug_log(f"Found {len(siblings)} sibling elements to check")

            # Get existing text normalized for comparison (remove extra whitespace)
            existing_text_normalized = " ".join("\n".join(context_text).split()).lower()

            for sibling in siblings:
                sibling_text = sibling.get_text().strip()
                # Normalize sibling text for comparison
                sibling_normalized = " ".join(sibling_text.split()).lower()

                # Check if text is new and not already in section text (allowing for whitespace differences)
                if (sibling_text and
                    len(sibling_text) > min_text_length and
                    len(sibling_text) < max_sibling_text_length and
                    sibling_normalized not in existing_text_normalized and
                    len(sibling_normalized) > 20):  # Ensure meaningful content
                    context_text.append(f"Nearby text: {sibling_text}")
                    existing_text_normalized += " " + sibling_normalized
                    debug_log(f"Found unique nearby text ({len(sibling_text)} chars)")

        if not context_text:
            context_text.append("No contextual text found around the image.")
            debug_log("No context found around the image", "WARNING")

        # Save to file with simplified format
        # Extract just the basename if image_filename contains a path or URL
        image_basename = os.path.basename(image_filename)
        context_filename = f"{os.path.splitext(image_basename)[0]}.txt"
        context_filepath = os.path.join(context_folder, context_filename)
        debug_log(f"Saving context to: {context_filepath}")

        # Create structured context text with "Part N:" labels
        structured_context_parts = []
        for idx, item in enumerate(context_text, 1):
            # Remove the prefix labels and add structured "Part N:" format
            if item.startswith("Alt text: "):
                content = item[10:]  # Remove "Alt text: " prefix
            elif item.startswith("Heading: "):
                content = item[9:]   # Remove "Heading: " prefix
            elif item.startswith("Section text: "):
                content = item[14:]  # Remove "Section text: " prefix
            elif item.startswith("Caption: "):
                content = item[9:]   # Remove "Caption: " prefix
            elif item.startswith("Nearby text: "):
                content = item[13:]  # Remove "Nearby text: " prefix
            elif item.startswith("Title: "):
                content = item[7:]   # Remove "Title: " prefix
            else:
                content = item

            # Add structured "Part N:" format
            structured_context_parts.append(f"Part {idx}: {content}.")

        with open(context_filepath, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(structured_context_parts))

        debug_log(f"Context extraction complete: {len(context_text)} items saved")
        if CONFIG.get('logging', {}).get('show_information', True):
            log_message(f"Context saved for '{image_filename}' -> {context_filepath}")

        return (context_filepath, found_image_url, current_alt_text)
        
    except requests.exceptions.RequestException as e:
        handle_exception(func_name, e, f"accessing URL: {url}")
        return (None, None, None)
    except IOError as e:
        handle_exception(func_name, e, f"writing context file")
        return (None, None, None)
    except Exception as e:
        handle_exception(func_name, e, f"extracting context for {image_filename}")
        return (None, None, None)


def clear_folders(folders=None):
    """
    Clears all files from the specified folders, preserving .gitkeep files.

    Args:
        folders (list): List of folder names to clear. If None, clears default folders.

    Returns:
        dict: Dictionary with folder names as keys and number of files deleted as values
    """
    func_name = "clear_folders"
    debug_log(f"Starting {func_name}")
    
    try:
        import shutil
        if folders is None:
            # Default to clearing the three main working folders
            folders = [
                get_absolute_folder_path('alt_text'),
                get_absolute_folder_path('context'),
                get_absolute_folder_path('images')
            ]
            debug_log("No folders specified, using default folders: alt-text, context, images")
        
        debug_log(f"Clearing folders: {folders}")
        deleted_counts = {}
        
        for folder in folders:
            debug_log(f"Processing folder: {folder}")
            deleted_count = 0
            
            if os.path.exists(folder):
                try:
                    for entry in os.scandir(folder):
                        name = entry.name
                        path = entry.path
                        # Skip .gitkeep files and report_template.html
                        if name == '.gitkeep' or name == 'report_template.html':
                            debug_log(f"Skipping preserved file: {path}")
                            continue

                        try:
                            if entry.is_dir(follow_symlinks=False):
                                shutil.rmtree(path)
                                deleted_count += 1
                                debug_log(f"Deleted folder: {path}")
                            else:
                                os.remove(path)
                                deleted_count += 1
                                debug_log(f"Deleted file: {path}")

                            if CONFIG.get('logging', {}).get('show_information', True):
                                log_message(f"Deleted: {path}", "INFORMATION")
                        except PermissionError as e:
                            handle_exception(func_name, e, f"permission denied for {path}")
                        except Exception as e:
                            handle_exception(func_name, e, f"deleting {path}")
                    
                    deleted_counts[folder] = deleted_count
                    debug_log(f"Cleared {deleted_count} items from '{folder}' folder")
                    
                    if CONFIG.get('logging', {}).get('show_information', True):
                        log_message(f"Cleared {deleted_count} items from '{folder}' folder")
                    
                except OSError as e:
                    handle_exception(func_name, e, f"accessing folder '{folder}'")
                    deleted_counts[folder] = 0
                except Exception as e:
                    handle_exception(func_name, e, f"processing folder '{folder}'")
                    deleted_counts[folder] = 0
            else:
                debug_log(f"Folder '{folder}' does not exist", "WARNING")
                if CONFIG.get('logging', {}).get('show_warnings', True):
                    log_message(f"Folder '{folder}' does not exist", "WARNING")
                deleted_counts[folder] = 0
        
        total_deleted = sum(deleted_counts.values())
        debug_log(f"Clear operation complete: {total_deleted} total files deleted")
        
        if CONFIG.get('logging', {}).get('show_information', True):
            log_message(f"Total files deleted: {total_deleted}", "INFORMATION")
        
        return deleted_counts
        
    except Exception as e:
        handle_exception(func_name, e, "general error in clear_folders")
        return {}


def clear_session_subfolders(base_folders=None):
    """
    Removes session subfolders under the given base folders.
    Session folders have the format: YYYYMMDD-HHMMSS-uuid
    Also supports legacy web-* and cli-* prefixed folders for backward compatibility.

    Args:
        base_folders (list): List of base folder paths to scan for session subfolders

    Returns:
        dict: Dictionary with base folder as key and number of deleted subfolders as value
    """
    func_name = "clear_session_subfolders"
    debug_log(f"Starting {func_name}")

    if base_folders is None:
        base_folders = []

    def is_session_folder(name):
        """Check if folder name matches session pattern (YYYYMMDD-HHMMSS-uuid or legacy web-/cli- prefix)"""
        if name.startswith("web-") or name.startswith("cli-"):
            return True
        # Check for timestamp-uuid format: YYYYMMDD-HHMMSS-uuid
        if len(name) > 15 and name[8] == '-' and name[0:8].isdigit():
            return True
        return False

    deleted = {}
    try:
        import shutil
        for base in base_folders:
            count = 0
            if os.path.exists(base):
                for name in os.listdir(base):
                    if is_session_folder(name):
                        path = os.path.join(base, name)
                        if os.path.isdir(path):
                            try:
                                shutil.rmtree(path)
                                count += 1
                                debug_log(f"Deleted session folder: {path}")
                            except Exception as e:
                                handle_exception(func_name, e, f"deleting session folder {path}")
            else:
                debug_log(f"Base folder '{base}' does not exist", "WARNING")
            deleted[base] = count
        return deleted
    except Exception as e:
        handle_exception(func_name, e, "general error in clear_session_subfolders")
        return deleted


def generate_alt_text_json(image_filename, images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, language=None, url=None, image_url=None, image_tag_attribute=None, page_title=None, current_alt_text=None, languages=None, use_geo_boost=False):
    """
    Generates a JSON file with alt-text for an image using its context and a prompt template.

    Args:
        image_filename (str): Name of the image file
        images_folder (str): Folder where images are stored (uses config default if None)
        context_folder (str): Folder where context files are stored (uses config default if None)
        prompt_folder (str): Folder where prompt template is stored (uses config default if None)
        alt_text_folder (str): Folder to save the JSON file (uses config default if None)
        language (str): ISO language code for alt-text generation (e.g., 'en', 'es', 'fr', 'de')
        url (str): The source webpage URL (for backward compatibility in context)
        image_url (str): The actual URL of the image file
        image_tag_attribute (dict): Dict with 'tag' and 'attribute' keys describing HTML source
        page_title (str): The title of the source webpage (for HTML report generation only)
        current_alt_text (str): The existing alt text from the HTML (if any)
        languages (list): List of ISO language codes for multilingual alt-text (overrides language if provided)

    Returns:
        tuple: (json_path, success) where json_path is the path to the JSON file (or None),
               and success is True if generation succeeded, False if generation_error occurred
    """
    func_name = "generate_alt_text_json"
    debug_log(f"Starting {func_name} for image: {image_filename}")

    # Start timing
    start_time = time.time()

    try:
        # Determine which languages to generate alt-text for
        target_languages = []

        if languages:
            # Multiple languages requested - validate all
            debug_log(f"Multiple languages requested: {languages}")
            for lang in languages:
                is_valid, message = validate_language(lang)
                if not is_valid:
                    error_msg = f"Language validation failed for '{lang}': {message}"
                    debug_log(error_msg, "ERROR")
                    return (None, False)
                target_languages.append(lang)
                debug_log(message)
        elif language:
            # Single language specified
            is_valid, message = validate_language(language)
            if not is_valid:
                error_msg = f"Language validation failed: {message}"
                debug_log(error_msg, "ERROR")
                return (None, False)
            target_languages = [language]
            debug_log(message)
        else:
            # Use default language if not specified
            default_lang = CONFIG.get('languages', {}).get('default', 'en')
            target_languages = [default_lang]
            debug_log(f"No language specified, using default: {default_lang}")

        is_multilingual = len(target_languages) > 1
        debug_log(f"Target languages: {target_languages}, multilingual mode: {is_multilingual}")

        # Use config values - resolve to absolute paths
        if images_folder is None:
            images_folder = get_absolute_folder_path('images')
        if context_folder is None:
            context_folder = get_absolute_folder_path('context')
        if prompt_folder is None:
            prompt_folder = get_absolute_folder_path('prompt_processing')
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')

        debug_log(f"Using folders - images: {images_folder}, context: {context_folder}, processing prompts: {prompt_folder}, alt-text: {alt_text_folder}")
        
        # Create alt-text folder if it doesn't exist
        if not os.path.exists(alt_text_folder):
            os.makedirs(alt_text_folder)
            debug_log(f"Created directory: {alt_text_folder}")
        
        # Get base filename without extension
        base_filename = os.path.splitext(image_filename)[0]
        debug_log(f"Base filename: {base_filename}")
        
        # Check if image exists
        image_path = os.path.join(images_folder, image_filename)
        debug_log(f"Checking for image at: {image_path}")
        
        if not os.path.exists(image_path):
            error_msg = f"Error: Image file '{image_filename}' not found in '{images_folder}' folder"
            debug_log(error_msg, "ERROR")
            return (None, False)
        
        # Look for context file
        context_filename = f"{base_filename}.txt"
        context_path = os.path.join(context_folder, context_filename)
        debug_log(f"Looking for context file at: {context_path}")
        
        context_text = ""
        if os.path.exists(context_path):
            try:
                with open(context_path, 'r', encoding='utf-8') as f:
                    context_text = f.read().strip()
                debug_log(f"Found context file: {context_filename}")
                if CONFIG.get('logging', {}).get('show_information', True):
                    log_message(f"Found context file: {context_filename}")
            except Exception as e:
                handle_exception(func_name, e, f"reading context file {context_path}")
        else:
            debug_log(f"Context file '{context_filename}' not found", "WARNING")
            if CONFIG.get('logging', {}).get('show_warnings', True):
                log_message(f"Context file '{context_filename}' not found in '{context_folder}' folder")
        
        # Load and merge prompt files
        prompt_text, loaded_prompt_files = load_and_merge_prompts(prompt_folder)
        if not prompt_text:
            error_msg = f"Error: No prompt files could be loaded from '{prompt_folder}' folder"
            debug_log(error_msg, "ERROR")
            return (None, False)

        debug_log("Creating JSON structure...")

        # Store base prompt template (will replace {LANGUAGE} per-language later)
        prompt_template = prompt_text
        processing_prompts_used = []
        translation_prompts_used = []
        vision_prompt_used = None
        try:
            vision_prompt_folder = get_absolute_folder_path('prompt_vision')
            vision_prompt_used = load_vision_prompt(vision_prompt_folder)
        except Exception as e:
            debug_log(f"Could not load vision prompt for JSON: {str(e)}", "WARNING")
            vision_prompt_used = None

        # Helper function to create language-specific prompt
        language_map = {
            'bg': 'Bulgarian', 'cs': 'Czech', 'da': 'Danish', 'de': 'German', 'el': 'Greek',
            'en': 'English', 'es': 'Spanish', 'et': 'Estonian', 'fi': 'Finnish', 'fr': 'French',
            'ga': 'Irish', 'hr': 'Croatian', 'hu': 'Hungarian', 'it': 'Italian', 'lt': 'Lithuanian',
            'lv': 'Latvian', 'mt': 'Maltese', 'nl': 'Dutch', 'pl': 'Polish', 'pt': 'Portuguese',
            'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sv': 'Swedish'
        }

        def create_prompt_for_language(lang_code):
            """Create combined prompt with language placeholder replaced and GEO instructions injected if needed."""
            lang_name = language_map.get(lang_code, lang_code)
            # Calculate max characters based on GEO boost setting
            max_chars = get_max_chars(use_geo_boost)
            lang_prompt = prompt_template.replace('{LANGUAGE}', lang_name)
            lang_prompt = lang_prompt.replace('{MAX_CHARS}', str(max_chars))

            # Inject GEO instructions if use_geo_boost is True
            if use_geo_boost:
                geo_who_you_are = "\n* You are an accessibility and Generative Engine Optimization (GEO) optimization expert."
                geo_boost_content = f"""
#### GEO OPTIMIZATION CONSTRAINTS:
When GEO boost is enabled, apply these additional constraints to alt-text generation:
- Write alt text as if it may be extracted and reused by AI systems
- Ensure alt text is semantically complete when read in isolation
- Place the primary subject in the first 5–7 words
- Prefer noun-first, entity-explicit phrasing
- Avoid pronouns, deixis, or page-dependent references
- Allow limited redundancy if it improves standalone clarity
- Use all the {max_chars} characters to maximize information density
"""
                # Inject WHO YOU ARE enhancement after first occurrence of "WHO YOU ARE:"
                if "WHO YOU ARE:" in lang_prompt:
                    # Find the end of the first line after "WHO YOU ARE:"
                    parts = lang_prompt.split("WHO YOU ARE:", 1)
                    if len(parts) == 2:
                        # Find the end of the WHO YOU ARE paragraph (next empty line or next section)
                        who_you_are_parts = parts[1].split('\n\n', 1)
                        lang_prompt = parts[0] + "WHO YOU ARE:" + who_you_are_parts[0] + geo_who_you_are + '\n\n' + (who_you_are_parts[1] if len(who_you_are_parts) > 1 else '')

                # Inject GEO boost content - replace {GEO_BOOST} placeholder or insert before LOGOS section
                if "{GEO_BOOST}" in lang_prompt:
                    lang_prompt = lang_prompt.replace("{GEO_BOOST}", geo_boost_content)
                elif "### FOR INFORMATIVE IMAGES:" in lang_prompt:
                    lang_prompt = lang_prompt.replace("#### 2.1 LOGOS:", geo_boost_content + "\n#### 2.1 LOGOS:")
            else:
                # When GEO boost is disabled, remove the placeholder
                if "{GEO_BOOST}" in lang_prompt:
                    lang_prompt = lang_prompt.replace("{GEO_BOOST}", "")

            if context_text and lang_prompt:
                return f"{lang_prompt}\n\nContext about the image:\n{context_text}\n\nImage filename: {image_filename}"
            elif lang_prompt:
                return f"{lang_prompt}\n\nImage filename: {image_filename}"
            else:
                return f"Analyze this image and provide: image_type (decorative/informative/functional), image_description, reasoning, and alt_text (max {max_chars} chars).\n\nImage filename: {image_filename}"

        # Try LLM analysis (OpenAI or ECB-LLM based on configuration)
        translation_method = None  # Track translation method used
        models_used = None  # Track which models were used for generation

        # Determine translation method based on language configuration
        if not is_multilingual and len(target_languages) == 1:
            # Single language mode - check if it's non-English
            single_lang = target_languages[0]
            if single_lang != 'en':
                # Non-English single language - LLM will be prompted to generate directly in that language
                translation_method = "direct"
                debug_log(f"Single non-English language ({single_lang}) - translation_method set to 'direct'")
            else:
                # English - no translation needed
                translation_method = "none"
                debug_log(f"Single English language - translation_method set to 'none'")

        # Check translation mode from config (needed for both single and multilingual)
        # Support both new format ('fast'/'accurate') and legacy format (True/False)
        translation_mode_config = CONFIG.get('translation_mode', CONFIG.get('full_translation_mode', 'fast'))

        # Convert boolean legacy format to string format
        if isinstance(translation_mode_config, bool):
            translation_mode_config = 'accurate' if translation_mode_config else 'fast'

        # Calculate max characters based on GEO boost setting (used for validation)
        max_chars_limit = get_max_chars(use_geo_boost)

        if is_multilingual:
            # Generate alt-text for multiple languages
            debug_log(f"Generating alt-text for {len(target_languages)} languages: {target_languages}")

            if translation_mode_config == 'accurate':
                # ACCURATE MODE: Generate new alt-text for each language
                debug_log(f"Translation mode: ACCURATE (generate for each language)")
                translation_method = "accurate"

                multilingual_results = []
                multilingual_reasoning = []
                image_type = None
                image_description = ""
                reasoning = ""

                # Generate alt-text for each language separately
                for lang in target_languages:
                    debug_log(f"Generating alt-text for language: {lang}")
                    # Create language-specific prompt
                    lang_prompt = create_prompt_for_language(lang)
                    debug_log(f"Created prompt for {lang} ({language_map.get(lang, lang)})")
                    llm_result = analyze_image_with_ai(image_path, lang_prompt, None, lang, vision_prompt=vision_prompt_used)
                    processing_prompts_used.append({"language": lang.upper(), "prompt": lang_prompt})

                    if llm_result:
                        # Store metadata from first language analysis
                        if image_type is None:
                            image_type = llm_result.get("image_type", "informative")
                            # Get vision model output (Step 1 description)
                            image_description = llm_result.get("vision_model_output", llm_result.get("image_description", ""))
                            # Extract model information from first language analysis
                            models_used = llm_result.get("_models_used")

                        lang_alt_text = llm_result.get("alt_text", "")
                        lang_reasoning = llm_result.get("reasoning", "")

                        # Ensure alt_text compliance
                        if len(lang_alt_text) > max_chars_limit:
                            lang_alt_text = lang_alt_text[:max_chars_limit - 3] + "..."
                        if lang_alt_text and not lang_alt_text.endswith('.'):
                            lang_alt_text += "."

                        multilingual_results.append((lang.upper(), lang_alt_text))
                        multilingual_reasoning.append((lang.upper(), lang_reasoning))
                        debug_log(f"Generated alt-text for {lang}: {lang_alt_text}")
                    else:
                        debug_log(f"LLM analysis failed for language {lang}", "ERROR")
                        if image_type is None:
                            image_type = "generation_error"
                            image_description = "LLM analysis failed"
                            reasoning = "Failed to connect to LLM service"
                        multilingual_results.append((lang.upper(), "Generation error"))
                        multilingual_reasoning.append((lang.upper(), reasoning if reasoning else "Generation error"))

                alt_text = multilingual_results
                reasoning = multilingual_reasoning
                debug_log(f"Multilingual generation complete (ACCURATE mode) - Type: {image_type}, {len(multilingual_results)} languages")

            else:
                # FAST MODE: Generate once, then translate
                debug_log(f"Translation mode: FAST (generate once, then translate)")
                translation_method = "fast"

                multilingual_results = []
                multilingual_reasoning = []
                image_type = None
                image_description = ""
                reasoning = ""
                first_lang_alt_text = None
                first_lang_reasoning = ""

                # Step 1: Analyze image for FIRST language only
                first_lang = target_languages[0]
                debug_log(f"Analyzing image in first language: {first_lang}")
                # Create language-specific prompt for first language
                first_lang_prompt = create_prompt_for_language(first_lang)
                debug_log(f"Created prompt for {first_lang} ({language_map.get(first_lang, first_lang)})")
                llm_result = analyze_image_with_ai(image_path, first_lang_prompt, None, first_lang, vision_prompt=vision_prompt_used)
                processing_prompts_used.append({"language": first_lang.upper(), "prompt": first_lang_prompt})

                if llm_result:
                    # Store all metadata from first language analysis
                    image_type = llm_result.get("image_type", "informative")
                    # Get vision model output (Step 1 description)
                    image_description = llm_result.get("vision_model_output", llm_result.get("image_description", ""))
                    first_lang_reasoning = llm_result.get("reasoning", "")
                    first_lang_alt_text = llm_result.get("alt_text", "")

                    # Extract model information if available
                    models_used = llm_result.get("_models_used")

                    # Ensure alt_text compliance
                    if len(first_lang_alt_text) > max_chars_limit:
                        first_lang_alt_text = first_lang_alt_text[:max_chars_limit - 3] + "..."
                    if first_lang_alt_text and not first_lang_alt_text.endswith('.'):
                        first_lang_alt_text += "."

                    # Store first language results
                    multilingual_results.append((first_lang.upper(), first_lang_alt_text))
                    multilingual_reasoning.append((first_lang.upper(), first_lang_reasoning))
                    debug_log(f"Generated alt-text for {first_lang}: {first_lang_alt_text}")
                else:
                    debug_log(f"LLM analysis failed for first language {first_lang}", "ERROR")
                    image_type = "generation_error"
                    image_description = "LLM analysis failed"
                    first_lang_reasoning = "Failed to connect to LLM service"
                    multilingual_results.append((first_lang.upper(), "Generation error"))
                    multilingual_reasoning.append((first_lang.upper(), first_lang_reasoning))

                # Step 2: Translate to remaining languages (if first language succeeded)
                if first_lang_alt_text and image_type != "generation_error":
                    for lang in target_languages[1:]:
                        debug_log(f"Translating alt-text and reasoning to language: {lang}")

                        # Translate alt-text
                        translated_alt_text, translation_prompt_info = translate_alt_text(
                            first_lang_alt_text,
                            first_lang,
                            lang,
                            return_prompt=True
                        )
                        if translation_prompt_info:
                            translation_prompts_used.append({
                                "language": lang.upper(),
                                "system": translation_prompt_info.get("system", ""),
                                "user": translation_prompt_info.get("user", "")
                            })
                        # Translate reasoning
                        translated_reasoning = translate_text(first_lang_reasoning, first_lang, lang, "reasoning")

                        if translated_alt_text:
                            multilingual_results.append((lang.upper(), translated_alt_text))
                            debug_log(f"Translated alt-text for {lang}: {translated_alt_text}")
                        else:
                            debug_log(f"Translation failed for language {lang}", "ERROR")
                            multilingual_results.append((lang.upper(), "Translation error"))

                        if translated_reasoning:
                            multilingual_reasoning.append((lang.upper(), translated_reasoning))
                        else:
                            multilingual_reasoning.append((lang.upper(), "Translation error"))
                else:
                    # First language failed, mark all remaining as failed
                    for lang in target_languages[1:]:
                        multilingual_results.append((lang.upper(), "Generation error"))
                        multilingual_reasoning.append((lang.upper(), "Generation error"))

                alt_text = multilingual_results  # Array of tuples
                reasoning = multilingual_reasoning  # Array of tuples
                debug_log(f"Multilingual generation complete (FAST mode) - Type: {image_type}, {len(multilingual_results)} languages")

        if not is_multilingual:
            # Single language mode (existing behavior)
            lang = target_languages[0] if not is_multilingual else target_languages[0]
            debug_log(f"Language specified: {lang}")
            # Create language-specific prompt
            lang_prompt = create_prompt_for_language(lang)
            debug_log(f"Created prompt for {lang} ({language_map.get(lang, lang)})")
            llm_result = analyze_image_with_ai(image_path, lang_prompt, None, lang, vision_prompt=vision_prompt_used)
            processing_prompts_used.append({"language": lang.upper(), "prompt": lang_prompt})

            if llm_result:
                # Use LLM results
                image_type = llm_result.get("image_type", "informative")
                # Get vision model output (Step 1 description)
                image_description = llm_result.get("vision_model_output", llm_result.get("image_description", ""))
                reasoning = llm_result.get("reasoning", "")
                alt_text = llm_result.get("alt_text", "")

                # Extract model information if available
                models_used = llm_result.get("_models_used")

                # Ensure alt_text compliance
                if len(alt_text) > max_chars_limit:
                    alt_text = alt_text[:max_chars_limit - 3] + "..."
                if alt_text and not alt_text.endswith('.'):
                    alt_text += "."

                debug_log(f"LLM analysis successful - Type: {image_type}, Alt-text: {alt_text}")
            else:
                # LLM analysis failed - mark as generation error
                debug_log("LLM analysis failed, marking as generation error", "ERROR")

                # Get the configured LLM provider for error message
                llm_provider = CONFIG.get('llm_provider', 'LLM')

                image_type = "generation_error"
                image_description = f"{llm_provider} analysis failed - LLM not available or credentials invalid"
                reasoning = f"Failed to connect to {llm_provider} service. Please check configuration and credentials."
                alt_text = "Generation error"

        # Create final JSON structure according to specifications
        # Calculate characters field based on alt_text type
        if isinstance(alt_text, list):
            # Multilingual mode: normalize entries to (lang, text) tuples to avoid unpack errors
            normalized_alt_text = []
            for entry in alt_text:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    normalized_alt_text.append((str(entry[0]), str(entry[1])))
                elif isinstance(entry, dict):
                    lang_key = entry.get('language') or entry.get('lang') or next(iter(entry.keys()), None)
                    text_val = entry.get('text')
                    if lang_key and text_val:
                        normalized_alt_text.append((str(lang_key), str(text_val)))
                elif isinstance(entry, str):
                    parts = entry.split(':', 1)
                    if len(parts) == 2 and len(parts[0].strip()) <= 5:
                        normalized_alt_text.append((parts[0].strip(), parts[1].strip()))

            if image_type != "decorative" and image_type != "generation_error":
                characters = [[lang_code.upper(), len(text)] for lang_code, text in normalized_alt_text] if normalized_alt_text else []
                proposed_alt_text = normalized_alt_text if normalized_alt_text else []
            else:
                characters = []
                proposed_alt_text = []
        else:
            # Single language mode: string
            characters = len(alt_text) if alt_text and image_type != "decorative" and image_type != "generation_error" else 0
            proposed_alt_text = alt_text if image_type != "decorative" and image_type != "generation_error" else ""

        # Determine severity level based on image_type (for logging only)
        if image_type == "generation_error":
            severity = "CRITICAL"
        elif image_type == "decorative":
            severity = "INFORMATION"
        elif "Translation error" in str(alt_text) or "error" in str(reasoning).lower():
            severity = "WARNING"
        else:
            severity = "INFORMATION"

        # Calculate processing time
        processing_time = round(time.time() - start_time, 2)

        json_data = {
            "generated_timestamp": datetime.now().isoformat(),
            "web_site_url": url if url else "",
            "page_title": page_title if page_title else "",
            "image_id": image_filename,
            "image_type": image_type,
            "image_context": context_text if context_text else "",
            "image_URL": image_url if image_url else "",
            "image_tag_attribute": image_tag_attribute if image_tag_attribute else {"tag": "unknown", "attribute": "unknown"},
            "language": target_languages if is_multilingual else target_languages[0],
            "geo_boost_status": bool(use_geo_boost),
            "reasoning": reasoning,
            "extended_description": image_description,
            "current_alt_text": current_alt_text if current_alt_text else "",
            "proposed_alt_text": proposed_alt_text,
            "proposed_alt_text_length": characters,
            "prompts_used": {
                "vision": vision_prompt_used or "",
                "processing": processing_prompts_used,
                "translation": translation_prompts_used
            },
            "ai_model": {
                "vision_provider": models_used.get('vision_provider') if (models_used and models_used.get('vision_provider')) else CONFIG.get('steps', {}).get('vision', {}).get('provider', 'Unknown'),
                "vision_model": models_used.get('vision_model') if (models_used and models_used.get('vision_model')) else CONFIG.get('steps', {}).get('vision', {}).get('model', 'Unknown'),
                "processing_provider": models_used.get('processing_provider') if (models_used and models_used.get('processing_provider')) else CONFIG.get('steps', {}).get('processing', {}).get('provider', 'Unknown'),
                "processing_model": models_used.get('processing_model') if (models_used and models_used.get('processing_model')) else CONFIG.get('steps', {}).get('processing', {}).get('model', 'Unknown'),
                "translation_provider": models_used.get('translation_provider') if (models_used and models_used.get('translation_provider')) else CONFIG.get('steps', {}).get('translation', {}).get('provider', 'Unknown'),
                "translation_model": models_used.get('translation_model') if (models_used and models_used.get('translation_model')) else CONFIG.get('steps', {}).get('translation', {}).get('model', 'Unknown')
            },
            "processing_time_seconds": processing_time
        }

        # Add translation_mode only for multilingual scenarios (fast or accurate)
        if translation_method in ["fast", "accurate"]:
            json_data["translation_mode"] = translation_method

        debug_log(f"Final result - Type: {image_type}, Severity: {severity}, Alt-text: {alt_text}")

        # Log full JSON output
        debug_log(f"Full JSON output:\n{json.dumps(json_data, indent=2, ensure_ascii=False)}")

        log_message(f"Generated: {image_type} ({severity}) - {alt_text}", "INFORMATION")

        # Save JSON file
        json_filename = f"{base_filename}.json"
        json_path = os.path.join(alt_text_folder, json_filename)
        debug_log(f"Saving JSON to: {json_path}")

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        debug_log(f"JSON file generated successfully: {json_path}")
        log_message(f"Generated JSON file: {json_path}", "INFORMATION")

        # Return tuple: (path, success_flag)
        # Success is False only if image_type is "generation_error"
        success = (image_type != "generation_error")
        return (json_path, success)
        
    except FileNotFoundError as e:
        handle_exception(func_name, e, f"file not found")
        return (None, False)
    except IOError as e:
        handle_exception(func_name, e, f"file I/O error")
        return (None, False)
    except json.JSONDecodeError as e:
        handle_exception(func_name, e, f"JSON encoding error")
        return (None, False)
    except Exception as e:
        handle_exception(func_name, e, f"generating JSON for {image_filename}")
        return (None, False)


def process_all_images(images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, language=None, url=None, image_metadata=None, page_title=None, languages=None, max_images=None, use_geo_boost=False, image_files_list=None):
    """
    Processes all images in the images folder, looks for corresponding context files,
    and generates JSON files for each image in the alt-text folder.

    Args:
        images_folder (str): Folder containing images (uses config default if None)
        context_folder (str): Folder containing context files (uses config default if None)
        prompt_folder (str): Folder containing prompt template (uses config default if None)
        alt_text_folder (str): Folder to save JSON files (uses config default if None)
        language (str): ISO language code for alt-text generation (single language)
        url (str): The source webpage URL (for backward compatibility)
        image_metadata (dict): Dictionary mapping filenames to {tag, attribute, url} metadata
        page_title (str): The title of the source webpage (for HTML report generation only)
        languages (list): List of ISO language codes for multilingual alt-text (overrides language if provided)
        max_images (int): Optional limit on number of images to process
        use_geo_boost (bool): Enable GEO (Generative Engine Optimization) boost for AI-friendly alt-text
        image_files_list (list): Optional list of image filenames to process (skips folder scan if provided)

    Returns:
        dict: Results summary with counts of processed, successful, and failed images
    """
    func_name = "process_all_images"
    debug_log(f"Starting {func_name}")

    try:
        # Use config values - resolve to absolute paths
        if images_folder is None:
            images_folder = get_absolute_folder_path('images')
        if context_folder is None:
            context_folder = get_absolute_folder_path('context')
        if prompt_folder is None:
            prompt_folder = get_absolute_folder_path('prompt_processing')
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')
        
        debug_log(f"Processing images from: {images_folder}")
        debug_log(f"Using folders - context: {context_folder}, prompt: {prompt_folder}, alt-text: {alt_text_folder}")
        
        # Check if images folder exists
        if not os.path.exists(images_folder):
            error_msg = f"Images folder '{images_folder}' does not exist"
            debug_log(error_msg, "ERROR")
            return {"processed": 0, "successful": 0, "failed": 0, "error": error_msg}

        # Get image files - either from provided list or by scanning folder
        if image_files_list is not None:
            # Use the provided list of image files (e.g., from download_results)
            image_files = image_files_list
            debug_log(f"Using provided image list with {len(image_files)} files")
        else:
            # Scan folder for image files
            try:
                all_files = os.listdir(images_folder)
                # Filter for common image extensions
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.tiff'}
                image_files = [f for f in all_files
                              if os.path.isfile(os.path.join(images_folder, f)) and
                              os.path.splitext(f.lower())[1] in image_extensions]

                debug_log(f"Found {len(image_files)} image files in {images_folder}")

                # Apply max_images limit if provided (only when scanning folder)
                if max_images is not None:
                    image_files = image_files[:max_images]
                    debug_log(f"Limiting processing to first {len(image_files)} images (max_images={max_images})")

            except OSError as e:
                handle_exception(func_name, e, f"accessing images folder '{images_folder}'")
                return {"processed": 0, "successful": 0, "failed": 0, "error": str(e)}

        if len(image_files) == 0:
            warning_msg = f"No image files found in '{images_folder}' folder"
            debug_log(warning_msg, "WARNING")
            return {"processed": 0, "successful": 0, "failed": 0, "warning": warning_msg}
        
        # Process each image
        results = {
            "processed": len(image_files),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        if CONFIG.get('logging', {}).get('show_information', True):
            log_message(f"Processing {len(image_files)} images...", "INFORMATION")
        
        for i, image_filename in enumerate(image_files, 1):
            debug_log(f"Processing image {i}/{len(image_files)}: {image_filename}")

            if CONFIG.get('logging', {}).get('show_information', True):
                log_message(f"[{i}/{len(image_files)}] Processing: {image_filename}", "INFORMATION")

            # Report processing progress (30-90% range for processing phase)
            process_percent = 30 + int(((i - 1) / len(image_files)) * 60)
            write_progress(
                process_percent,
                f"Processing image {i} of {len(image_files)}: {image_filename}",
                phase="processing",
                current_image=i,
                total_images=len(image_files)
            )

            try:
                # Get image metadata (URL, tag/attribute info, and current alt text) if available
                image_url = None
                image_tag_attribute = None
                current_alt_text = None

                if image_metadata and image_filename in image_metadata:
                    metadata = image_metadata[image_filename]
                    image_url = metadata.get('url')
                    image_tag_attribute = {
                        'tag': metadata.get('tag', 'unknown'),
                        'attribute': metadata.get('attribute', 'unknown')
                    }
                    current_alt_text = metadata.get('current_alt_text', '')
                    debug_log(f"Using metadata for {image_filename}: tag={metadata.get('tag')}, attr={metadata.get('attribute')}")
                    if current_alt_text:
                        debug_log(f"Found current alt text: {current_alt_text}")

                # Generate JSON for this image
                result = generate_alt_text_json(
                    image_filename,
                    images_folder,
                    context_folder,
                    prompt_folder,
                    alt_text_folder,
                    language,
                    url,
                    image_url,
                    image_tag_attribute,
                    page_title,
                    current_alt_text,
                    languages,
                    use_geo_boost
                )

                # Unpack tuple result (json_path, success)
                json_path, success = result if result and isinstance(result, tuple) else (None, False)

                if json_path and success:
                    # True success: JSON created AND no generation error
                    results["successful"] += 1
                    results["details"].append({
                        "image": image_filename,
                        "status": "success",
                        "json_file": json_path
                    })
                    debug_log(f"Successfully processed: {image_filename}")
                else:
                    # Failed: either no JSON created OR generation_error occurred
                    results["failed"] += 1
                    error_reason = "Generation error occurred" if json_path and not success else "JSON generation returned None"
                    results["details"].append({
                        "image": image_filename,
                        "status": "failed",
                        "error": error_reason,
                        "json_file": json_path if json_path else None
                    })
                    debug_log(f"Failed to process: {image_filename} - {error_reason}", "WARNING")
                
            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)
                results["details"].append({
                    "image": image_filename,
                    "status": "failed", 
                    "error": error_msg
                })
                handle_exception(func_name, e, f"processing image {image_filename}")
        
        # Summary
        debug_log(f"Batch processing complete: {results['successful']} successful, {results['failed']} failed")
        
        if CONFIG.get('logging', {}).get('show_information', True):
            log_message("Batch processing complete:", "INFORMATION")
            log_message(f"  Total images: {results['processed']}", "INFORMATION")
            log_message(f"  Successful: {results['successful']}", "INFORMATION")
            log_message(f"  Failed: {results['failed']}", "INFORMATION")
            
            if results['failed'] > 0:
                print(f"\nFailed images:")
                for detail in results['details']:
                    if detail['status'] == 'failed':
                        print(f"  - {detail['image']}: {detail.get('error', 'Unknown error')}")
        
        return results
        
    except Exception as e:
        handle_exception(func_name, e, "general error in batch processing")
        return {"processed": 0, "successful": 0, "failed": 0, "error": str(e)}


def MyAccessibilityBuddy(url, images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, clear_all=False, max_images=None, languages=None, use_geo_boost=False):
    """
    Complete MyAccessibilityBuddy workflow: downloads images, extracts context, and generates JSON files.

    Args:
        url (str): The URL to download images from and extract context
        images_folder (str): Folder to save images (uses config default if None)
        context_folder (str): Folder to save context files (uses config default if None)
        prompt_folder (str): Folder containing prompt template (uses config default if None)
        alt_text_folder (str): Folder to save JSON files (uses config default if None)
        clear_all (bool): If True, automatically clear all folders (including reports) without prompting
        max_images (int): Maximum number of images to download and process (None for all)
        languages (list): List of ISO language codes for multilingual alt-text (e.g., ['en', 'it', 'es'])
        use_geo_boost (bool): Enable GEO (Generative Engine Optimization) boost for AI-friendly alt-text

    Returns:
        dict: Complete workflow results with all operation summaries
    """
    func_name = "AutoAltText"

    try:
        # Use config values - resolve to absolute paths
        if images_folder is None:
            images_folder = get_absolute_folder_path('images')
        if context_folder is None:
            context_folder = get_absolute_folder_path('context')
        if prompt_folder is None:
            prompt_folder = get_absolute_folder_path('prompt_processing')
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')

        # Check existing files in folders
        folders_to_check = [images_folder, context_folder, alt_text_folder]
        existing_files = {}
        total_existing = 0

        for folder in folders_to_check:
            if os.path.exists(folder):
                try:
                    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
                    existing_files[folder] = len(files)
                    total_existing += len(files)
                except OSError as e:
                    existing_files[folder] = 0
            else:
                existing_files[folder] = 0

        # Handle clear-all operation BEFORE initializing log file
        if clear_all:
            if CONFIG.get('logging', {}).get('show_information', True):
                log_message("Auto-clearing all working folders (images, context, alt-text, reports, logs)...")

            # Include reports and logs folders when using --clear-all
            folders_to_clear_all = folders_to_check + [get_absolute_folder_path('reports'), get_absolute_folder_path('logs')]
            clear_results = clear_folders(folders_to_clear_all)

            if CONFIG.get('logging', {}).get('show_information', True):
                log_message(f"Auto-cleared {sum(clear_results.values())} files/folders from all targets")

            # Also remove session subfolders under images/context/alt-text/reports
            session_bases = [
                get_absolute_folder_path('images'),
                get_absolute_folder_path('context'),
                get_absolute_folder_path('alt_text'),
                get_absolute_folder_path('reports')
            ]
            session_deleted = clear_session_subfolders(session_bases)
            if CONFIG.get('logging', {}).get('show_information', True):
                for base, count in session_deleted.items():
                    log_message(f"Deleted {count} session folders under '{base}'", "INFORMATION")

        # Initialize log file AFTER clear operation (so it doesn't get deleted)
        log_file = initialize_log_file(url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting {func_name} for URL: {url}")
        debug_log(f"Using folders - images: {images_folder}, context: {context_folder}, prompt: {prompt_folder}, alt-text: {alt_text_folder}")

        # Skip clearing prompt - just continue with existing files
        if total_existing > 0 and not clear_all:
            debug_log(f"Found {total_existing} existing files, continuing without clearing")
            if CONFIG.get('logging', {}).get('show_information', True):
                log_message(f"Found {total_existing} existing files in folders, continuing...")
        
        # Initialize results tracking
        workflow_results = {
            "url": url,
            "status": "in_progress",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "folders": {
                "images": images_folder,
                "context": context_folder,
                "alt_text": alt_text_folder
            },
            "steps": {}
        }
        
        # Step 1: Download images
        write_progress(5, "Step 1/3: Downloading images from web page...", phase="downloading")

        if CONFIG.get('logging', {}).get('show_information', True):
            if max_images:
                print(f"\nStep 1/3: Downloading images (max {max_images})...")
            else:
                print("\nStep 1/3: Downloading images...")

        debug_log("Starting image download step")
        if max_images:
            debug_log(f"Maximum images to download: {max_images}")
        download_results, image_metadata, page_title = download_images_from_url(url, images_folder, max_images)

        workflow_results["steps"]["download"] = {
            "status": "completed" if download_results else "failed",
            "images_downloaded": len(download_results) if download_results else 0,
            "images": download_results if download_results else []
        }

        if not download_results:
            error_msg = "Failed to download any images"
            debug_log(error_msg, "ERROR")
            workflow_results["status"] = "failed"
            workflow_results["error"] = error_msg
            if CONFIG.get('logging', {}).get('show_errors', True):
                print(f"ERROR: {error_msg}")

            # Close log file before returning
            close_log_file()
            return workflow_results

        if CONFIG.get('logging', {}).get('show_information', True):
            print(f"Downloaded {len(download_results)} images")
        
        # Step 2: Extract context for all images
        write_progress(30, f"Step 2/3: Extracting context for {len(download_results)} images...", phase="context")

        if CONFIG.get('logging', {}).get('show_information', True):
            print(f"\nStep 2/3: Extracting context for {len(download_results)} images...")

        debug_log("Starting context extraction step")
        context_results = {"successful": 0, "failed": 0, "details": []}

        for i, image_filename in enumerate(download_results, 1):
            debug_log(f"Extracting context for image {i}/{len(download_results)}: {image_filename}")

            if CONFIG.get('logging', {}).get('show_information', True):
                print(f"[{i}/{len(download_results)}] Extracting context: {image_filename}")

            try:
                context_result = grab_context(image_filename, url, context_folder)

                # Handle tuple return: (context_path, image_url, current_alt_text)
                if isinstance(context_result, tuple):
                    if len(context_result) == 3:
                        context_path, image_url, current_alt_text = context_result
                    elif len(context_result) == 2:
                        # Backward compatibility
                        context_path, image_url = context_result
                        current_alt_text = ""
                    else:
                        context_path = context_result[0]
                        image_url = None
                        current_alt_text = ""
                else:
                    # Backward compatibility: if it returns just a path
                    context_path = context_result
                    image_url = None
                    current_alt_text = ""

                if context_path:
                    context_results["successful"] += 1
                    context_results["details"].append({
                        "image": image_filename,
                        "status": "success",
                        "context_file": context_path
                    })
                    # Update image_metadata with URL and current alt text from context
                    if image_filename in image_metadata:
                        if image_url:
                            image_metadata[image_filename]['url'] = image_url
                            debug_log(f"Updated image URL for {image_filename} from context: {image_url}")
                        if current_alt_text:
                            image_metadata[image_filename]['current_alt_text'] = current_alt_text
                            debug_log(f"Stored current alt text for {image_filename}: {current_alt_text}")
                else:
                    context_results["failed"] += 1
                    context_results["details"].append({
                        "image": image_filename,
                        "status": "failed",
                        "error": "Context extraction returned None"
                    })

            except Exception as e:
                context_results["failed"] += 1
                context_results["details"].append({
                    "image": image_filename,
                    "status": "failed",
                    "error": str(e)
                })
                handle_exception(func_name, e, f"extracting context for {image_filename}")
        
        workflow_results["steps"]["context"] = context_results
        debug_log(f"Context extraction complete: {context_results['successful']} successful, {context_results['failed']} failed")
        
        if CONFIG.get('logging', {}).get('show_information', True):
            print(f"Context extracted: {context_results['successful']} successful, {context_results['failed']} failed")
        
        # Step 3: Generate JSON files for all images
        write_progress(35, "Step 3/3: Generating alt-text for all images...", phase="processing")

        if CONFIG.get('logging', {}).get('show_information', True):
            print(f"\nStep 3/3: Generating JSON files for all images...")

        debug_log("Starting JSON generation step")
        json_results = process_all_images(images_folder, context_folder, prompt_folder, alt_text_folder, None, url, image_metadata, page_title, languages, max_images, use_geo_boost, image_files_list=download_results)

        workflow_results["steps"]["json_generation"] = json_results
        debug_log(f"JSON generation complete: {json_results.get('successful', 0)} successful, {json_results.get('failed', 0)} failed")
        
        # Final summary
        workflow_results["status"] = "completed"
        workflow_results["page_title"] = page_title  # Store page title for HTML report generation
        workflow_results["summary"] = {
            "images_downloaded": len(download_results),
            "context_extracted": context_results["successful"],
            "json_files_generated": json_results.get("successful", 0),
            "total_failures": context_results["failed"] + json_results.get("failed", 0)
        }
        
        debug_log(f"AutoAltText workflow complete: {workflow_results['summary']}")

        # Report completion progress
        write_progress(95, "Finalizing results...", phase="finalizing")

        if CONFIG.get('logging', {}).get('show_information', True):
            print(f"\nAutoAltText Complete!")
            print(f"  Images downloaded: {workflow_results['summary']['images_downloaded']}")
            print(f"  Context extracted: {workflow_results['summary']['context_extracted']}")
            print(f"  JSON files generated: {workflow_results['summary']['json_files_generated']}")
            if workflow_results['summary']['total_failures'] > 0:
                print(f"  Total failures: {workflow_results['summary']['total_failures']}")
            print(f"  Output folder: {alt_text_folder}")

        # Close log file
        close_log_file()

        return workflow_results

    except Exception as e:
        error_result = {
            "url": url,
            "status": "error",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        handle_exception(func_name, e, f"AutoAltText workflow for {url}")

        # Close log file even on error
        close_log_file()

        return error_result

def main():
    # Load configuration first
    load_config()

    parser = argparse.ArgumentParser(
        prog='MyAccessibilityBuddy',
        description='ECB Accessibility Tool - Automated WCAG 2.2 compliant alt-text generation'
    )

    # Positional arguments (optional, used by different actions)
    # Note: For --generate-json and --process-all, url is treated as image_filename if no second arg provided
    parser.add_argument('url', nargs='?', help='URL to process (required for -d, -c, -w actions) OR image filename for -g action')
    parser.add_argument('image_filename', nargs='?', help='Image filename (required for -c action when URL is provided)')
    parser.add_argument('-u', '--url', dest='url_option', help='URL to process (alias for positional URL argument)')
    parser.add_argument('--image-name', dest='image_name', help='Image filename (alias for positional image_filename for --context)')

    # Action flags (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument('--help-topic', type=str, metavar='TOPIC',
                            help='Show detailed help (topics: workflow, download, context, languages, examples)')
    # Note: -h/--help is provided by argparse and will appear first; keep help-topic near the top for visibility.
    action_group.add_argument('-d', '--download', action='store_true',
                            help='Download all images from URL')
    action_group.add_argument('-c', '--context', action='store_true',
                            help='Extract context for specific image from URL')
    action_group.add_argument('-g', '--generate-json', action='store_true',
                            help='Generate JSON file for specific image')
    action_group.add_argument('-p', '--process-all', action='store_true',
                            help='Process all images in batch')
    action_group.add_argument('-w', '--workflow', action='store_true',
                            help='Complete workflow (download → context → JSON)')
    action_group.add_argument('-al', '--all-languages', action='store_true',
                            help='List all supported languages')
    action_group.add_argument('--list-sessions', action='store_true',
                            help='List all CLI sessions')
    action_group.add_argument('--clear-session', type=str, metavar='SESSION_ID',
                            help='Clear data for a specific session')

    # Common options
    parser.add_argument('--folder', default=None, help='Folder for images or context (used with -d or -c)')
    parser.add_argument('--images-folder', default=None, help='Folder for images (default: from config)')
    parser.add_argument('--context-folder', default=None, help='Folder for context files (default: from config)')
    parser.add_argument('--prompt-folder', default=None, help='Folder for prompt templates (default: from config)')
    parser.add_argument('--alt-text-folder', default=None, help='Folder for JSON output (default: from config)')
    parser.add_argument('--language', nargs='+', default=None, help='One or more ISO language codes for alt-text (e.g. en es fr de)')
    parser.add_argument('--num-images', type=int, default=None, help='Maximum number of images to download')
    parser.add_argument('--geo', action='store_true', help='Enable GEO (Generative Engine Optimization) boost for AI-friendly alt-text')
    parser.add_argument('--geo-boost', action='store_true', help='Alias for --geo to enable GEO (Generative Engine Optimization) boost')
    parser.add_argument('--vision-provider', help='Override vision provider (OpenAI, Claude, ECB-LLM, Ollama, Gemini)')
    parser.add_argument('--vision-model', help='Override vision model name')
    parser.add_argument('--processing-provider', help='Override processing provider (OpenAI, Claude, ECB-LLM, Ollama, Gemini)')
    parser.add_argument('--processing-model', help='Override processing model name')
    parser.add_argument('--translation-provider', help='Override translation provider (OpenAI, Claude, ECB-LLM, Ollama, Gemini)')
    parser.add_argument('--translation-model', help='Override translation model name')
    parser.add_argument('--advanced-translation', action='store_true', help='Generate fresh alt-text per language (sets translation_mode=accurate)')
    parser.add_argument('--translation-mode', choices=['fast', 'accurate'], help='Set translation mode for multilingual generation')

    # Session management options
    parser.add_argument('--session', nargs='?', const='__SESSION_NEW__', default=None,
                        help='Use specific CLI session ID (omit value to create a new session)')
    parser.add_argument('--shared', action='store_true', help='Use shared folder (input/images/shared, output/shared)')
    parser.add_argument('--legacy', action='store_true', help='Use legacy flat folder structure (backward compatible)')

    # Clear operations
    parser.add_argument('--clear-all', action='store_true', help='Clear all sessions (prompts for confirmation)')
    parser.add_argument('--clear-inputs', action='store_true', help='Clear input folders (images, context) without prompting')
    parser.add_argument('--clear-outputs', action='store_true', help='Clear output folders (alt-text, reports) without prompting')
    parser.add_argument('--clear-reports', action='store_true', help='Clear reports folder only')
    parser.add_argument('--clear-log', action='store_true', help='Clear log files without prompting')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompts (use with --clear-all or --clear-session)')

    parser.add_argument('--report', action='store_true', help='Generate accessible HTML report after processing')

    # Progress reporting (for async API calls)
    parser.add_argument('--progress-file', type=str, default=None,
                        help='Path to JSON file for writing progress updates (used by async API)')

    # Parse arguments
    args = parser.parse_args()

    # Normalize URL: allow -u/--url as alias for positional URL
    if getattr(args, 'url_option', None):
        args.url = args.url_option
    # Normalize image filename alias
    if getattr(args, 'image_name', None) and not getattr(args, 'image_filename', None):
        args.image_filename = args.image_name
    # Normalize session: --session with no value means create new
    SESSION_NEW_SENTINEL = "__SESSION_NEW__"
    if getattr(args, 'session', None) == SESSION_NEW_SENTINEL:
        args.session = SESSION_NEW_SENTINEL

    # Set up progress file for async API polling
    global PROGRESS_FILE_PATH
    if getattr(args, 'progress_file', None):
        PROGRESS_FILE_PATH = args.progress_file
        write_progress(0, "Initializing...", phase="init")

    # Handle session management commands FIRST (before other operations)
    if args.list_sessions:
        list_cli_sessions()
        import sys
        sys.exit(0)

    if args.clear_session:
        clear_cli_session(args.clear_session, force=args.force)
        import sys
        sys.exit(0)

    # Handle clear operations FIRST (before main actions)
    # These are modifier flags that should run before the main action
    clear_operation_performed = False

    if args.clear_all:
        # Clear all CLI sessions with confirmation (unless --force is used)
        clear_all_cli_sessions(force=args.force)

        # Clear all working folders (images, context, alt-text, reports, logs)
        folders_to_clear = [
            get_absolute_folder_path('images'),
            get_absolute_folder_path('context'),
            get_absolute_folder_path('alt_text'),
            get_absolute_folder_path('reports'),
            get_absolute_folder_path('logs')
        ]
        print("Clearing all folders (inputs, outputs, reports, logs)...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} files (report_template.html preserved)")

        # Remove session-specific subfolders under input/output
        session_bases = [
            get_absolute_folder_path('images'),
            get_absolute_folder_path('output')
        ]
        session_deleted = clear_session_subfolders(session_bases)
        if CONFIG.get('logging', {}).get('show_information', True):
            for base, count in session_deleted.items():
                log_message(f"Deleted {count} session folders under '{base}'", "INFORMATION")

        clear_operation_performed = True

    elif args.clear_inputs:
        # Clear input folders (images, context) without prompting
        folders_to_clear = [
            get_absolute_folder_path('images'),
            get_absolute_folder_path('context')
        ]
        print("Clearing input folders (images, context)...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} files from input folders")
        clear_operation_performed = True

    elif args.clear_outputs:
        # Clear output folders (alt-text, reports) without prompting
        folders_to_clear = [
            get_absolute_folder_path('alt_text'),
            get_absolute_folder_path('reports')
        ]
        print("Clearing output folders (alt-text, reports)...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} files from output folders")
        clear_operation_performed = True

    elif args.clear_reports:
        # Clear only reports folder without prompting
        folders_to_clear = [
            get_absolute_folder_path('reports')
        ]
        print("Clearing reports folder...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} files from reports folder")
        clear_operation_performed = True

    elif args.clear_log:
        # Clear log files without prompting
        folders_to_clear = [
            get_absolute_folder_path('logs')
        ]
        print("Clearing log files...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} log files")
        clear_operation_performed = True

    # Resolve session folders based on session mode flags
    # Only create session folders when needed to avoid unnecessary cli-/web- folders
    session_folders = None
    global CURRENT_SESSION_LOGS
    CURRENT_SESSION_LOGS = None

    # Normalize provider names from CLI (match internal casing)
    def normalize_provider_name(provider_name):
        provider_map = {
            'openai': 'OpenAI',
            'claude': 'Claude',
            'ecb-llm': 'ECB-LLM',
            'ollama': 'Ollama',
            'gemini': 'Gemini'
        }
        if not provider_name:
            return None
        return provider_map.get(provider_name, provider_name)

    # Apply step-specific overrides from CLI flags
    def apply_step_override(step, provider_value, model_value):
        if not provider_value and not model_value:
            return
        if 'steps' not in CONFIG:
            CONFIG['steps'] = {}
        if step not in CONFIG['steps']:
            CONFIG['steps'][step] = {}
        if provider_value:
            CONFIG['steps'][step]['provider'] = normalize_provider_name(provider_value)
        if model_value:
            CONFIG['steps'][step]['model'] = model_value

    apply_step_override('vision', getattr(args, 'vision_provider', None), getattr(args, 'vision_model', None))
    apply_step_override('processing', getattr(args, 'processing_provider', None), getattr(args, 'processing_model', None))
    apply_step_override('translation', getattr(args, 'translation_provider', None), getattr(args, 'translation_model', None))

    # Override translation mode when requested
    if getattr(args, 'translation_mode', None):
        CONFIG['translation_mode'] = args.translation_mode
    elif getattr(args, 'advanced_translation', False):
        CONFIG['translation_mode'] = 'accurate'

    # Support --geo-boost as alias for --geo
    if getattr(args, 'geo_boost', False):
        args.geo = True

    # Explicit session modes
    if getattr(args, 'legacy', False):
        session_folders = get_cli_session_folders(legacy=True)
        print("Using legacy folder structure (backward compatibility mode)")
    elif getattr(args, 'shared', False):
        session_folders = get_cli_session_folders(shared=True)
        print("Using shared folder for collaboration")
    elif getattr(args, 'session', None):
        if args.session == "__SESSION_NEW__":
            import uuid
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            new_session_id = f"{timestamp}-{uuid.uuid4()}"
            session_folders = get_cli_session_folders(session_id=new_session_id)
            print(f"Created new session: {new_session_id}")
        else:
            session_folders = get_cli_session_folders(session_id=args.session)
            print(f"Using session: {args.session}")
    # Default session creation for actions that need it (but not for download-only with explicit folder)
    elif args.generate_json or args.process_all or args.workflow:
        session_folders = get_cli_session_folders()
        if session_folders['mode'] == 'session':
            print(f"Using session: {session_folders['session_id']}")

    # Track session-specific logs folder if available
    if session_folders and session_folders.get('logs'):
        CURRENT_SESSION_LOGS = session_folders['logs']

    # Handle main actions based on flags
    if args.download:
        # Download images action
        if not args.url:
            print("ERROR: --download requires a URL argument")
            print("Usage: python3 app.py --download <URL|--url URL> [OPTIONS]")
            import sys
            sys.exit(1)

        # Initialize log file for this operation
        log_file = initialize_log_file(args.url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting download from URL: {args.url}")
        # Determine download folder priority: explicit args > session > default
        folder = args.folder or args.images_folder
        if not folder and session_folders:
            folder = session_folders.get('images')

        # If no folder is specified at all, create a default session for images
        if not folder:
            session_folders = get_cli_session_folders(required_keys=['images'])
            folder = session_folders['images']

        debug_log(f"Download folder: {folder if folder else 'images (default)'}")
        if args.num_images:
            print(f"Downloading images from: {args.url} (max {args.num_images})")
            debug_log(f"Max images: {args.num_images}")
        else:
            print(f"Downloading images from: {args.url}")

        filenames, metadata, page_title = download_images_from_url(args.url, folder, args.num_images)

        print(f"Downloaded {len(filenames)} images with tag/attribute metadata")
        debug_log(f"Downloaded {len(filenames)} images")
        if page_title:
            print(f"Page title: {page_title}")
            debug_log(f"Page title: {page_title}")

        close_log_file()

    elif args.context:
        # Extract context action
        if not args.url:
            print("ERROR: --context requires a URL argument")
            print("Usage: python3 app.py --context <URL|--url URL> <IMAGE_FILENAME> [OPTIONS]")
            import sys
            sys.exit(1)
        if not args.image_filename:
            print("ERROR: --context requires an image filename argument")
            print("Usage: python3 app.py --context <URL|--url URL> <IMAGE_FILENAME> [OPTIONS]")
            import sys
            sys.exit(1)

        # Initialize log file for this operation
        log_file = initialize_log_file(args.url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting context extraction for image: {args.image_filename}")
        debug_log(f"URL: {args.url}")

        # Choose context folder: explicit --folder > session context > default
        if args.folder:
            folder = args.folder
        elif session_folders:
            folder = session_folders.get('context')
        else:
            folder = None

        debug_log(f"Context folder: {folder if folder else 'context (default)'}")
        print(f"Extracting context for '{args.image_filename}' from: {args.url}")
        result = grab_context(args.image_filename, args.url, folder)
        if isinstance(result, tuple):
            if len(result) == 3:
                context_path, image_url, current_alt_text = result
            elif len(result) == 2:
                context_path, image_url = result
                current_alt_text = ""
            else:
                context_path = result[0]
                image_url = None
                current_alt_text = ""

            if context_path:
                print(f"Context saved to: {context_path}")
                debug_log(f"Context saved to: {context_path}")
            if image_url:
                print(f"Image URL: {image_url}")
                debug_log(f"Image URL: {image_url}")
            if current_alt_text:
                print(f"Current alt text: {current_alt_text}")
                debug_log(f"Current alt text: {current_alt_text}")
        elif result:
            print(f"Context saved to: {result}")
            debug_log(f"Context saved to: {result}")

        close_log_file()

    elif args.help_topic is not None:
        # Help topic action
        topic = args.help_topic.lower() if args.help_topic else None

        if topic == 'workflow':
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AutoAltText - Complete Workflow Help                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    The -w/--workflow flag runs the complete workflow: downloads images from a
    URL, extracts context, and generates WCAG 2.2 compliant JSON files with
    AI-powered alt-text analysis.

BASIC USAGE:
    python3 app.py -w <URL> [OPTIONS]
    python3 app.py --workflow <URL> [OPTIONS]

REQUIRED:
    <URL>                    Webpage URL to download images from

OPTIONAL FLAGS:
    --clear-all             Clear all folders (images, context, alt-text, reports) without prompting
    --clear-inputs          Clear input folders (images, context) without prompting
    --clear-outputs         Clear output folders (alt-text, reports) without prompting
    --num-images <N>        Limit number of images to download (default: all)
    --report                Generate accessible HTML report after processing
    --images-folder <path>  Custom folder for downloaded images
    --context-folder <path> Custom folder for context files
    --alt-text-folder <path> Custom folder for JSON output
    --prompt-folder <path>  Custom folder for prompt templates

EXAMPLES:
    # Basic workflow
    python3 app.py -w https://www.example.com
    python3 app.py --workflow https://www.example.com

    # With automatic cleanup and limited images
    python3 app.py -w https://www.example.com --clear-all --num-images 10

    # Clear only input folders
    python3 app.py --clear-inputs

    # Clear only output folders
    python3 app.py --clear-outputs

    # Generate HTML report
    python3 app.py --workflow https://www.example.com --report

    # Complete workflow with all options
    python3 app.py -w https://www.example.com --clear-all --num-images 20 --report

OUTPUT:
    - Downloaded images in images/ folder
    - Context files in context/ folder
    - JSON files in alt-text/ folder
    - HTML report in alt-text/alt-text-report.html (if --report flag used)

For more examples: python3 app.py --help-topic examples
            """)

        elif topic == 'download':
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        Download Images Command Help                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    Downloads all images from a webpage, including images from:
    - <img> tags (standard images)
    - <picture> elements (responsive images)
    - <div> elements (background images)
    - <link> tags (favicons, touch icons)
    - <meta> tags (Open Graph, Twitter Card images)

USAGE:
    python3 app.py -d <URL> [OPTIONS]
    python3 app.py --download <URL> [OPTIONS]

OPTIONS:
    --folder <name>         Folder to save images (default: images)
    --num-images <N>        Maximum number of images to download

EXAMPLES:
    # Download all images
    python3 app.py -d https://www.example.com
    python3 app.py --download https://www.example.com

    # Download up to 15 images
    python3 app.py -d https://www.example.com --num-images 15

    # Download to custom folder
    python3 app.py --download https://www.example.com --folder my-images

OUTPUT:
    - Images saved to specified folder
    - Displays page title
    - Shows count of downloaded images
            """)

        elif topic == 'context':
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       Context Extraction Command Help                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    Extracts surrounding contextual information for a specific image from a
    webpage, including headings, captions, alt text, and nearby text.

USAGE:
    python3 app.py -c <URL> <IMAGE_FILENAME> [OPTIONS]
    python3 app.py --context <URL> <IMAGE_FILENAME> [OPTIONS]

OPTIONS:
    --folder <name>         Folder to save context files (default: context)

EXAMPLES:
    # Extract context for logo image
    python3 app.py -c https://www.example.com logo.png
    python3 app.py --context https://www.example.com logo.png

    # Extract context to custom folder
    python3 app.py -c https://www.example.com banner.jpg --folder my-context

OUTPUT:
    - Context file saved as .txt file
    - Displays image URL if found
            """)

        elif topic == 'languages':
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         Language Support Help                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    MyAccessibilityBuddy supports generating alt-text in 24 EU official languages.
    The --language flag works with -g, -p, and -w actions and supports multiple languages.

SUPPORTED LANGUAGES:
    Use 'python3 app.py -al' or 'python3 app.py --all-languages' to see the complete list.

USAGE:
    --language <code> [<code> ...]     One or more ISO language codes (e.g., en es fr de)

EXAMPLES:
    # Generate Spanish alt-text
    python3 app.py -g logo.png --language es

    # Generate alt-text in multiple languages
    python3 app.py -g logo.png --language en es fr

    # Process all with French alt-text
    python3 app.py -p --language fr

    # Complete workflow in multiple languages
    python3 app.py -w https://www.example.com --language en it de

NOTE:
    - Alt-text will be generated in the specified language(s)
    - Multiple languages can be specified with a single --language flag
    - Other fields (reasoning, description) remain in English
    - Default language is English (en) if not specified
            """)

        elif topic == 'examples':
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          Usage Examples & Workflows                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

BASIC WORKFLOW (Recommended):
    # Download, extract context, generate JSON, create HTML report
    python3 app.py -w https://www.ecb.europa.eu --clear-all --report
    python3 app.py --workflow https://www.ecb.europa.eu --clear-all --report

LIMIT NUMBER OF IMAGES:
    # Process only first 10 images
    python3 app.py -w https://www.example.com --num-images 10

MULTILINGUAL ALT-TEXT:
    # Spanish alt-text
    python3 app.py -w https://www.example.com --language es

    # German alt-text with limited images
    python3 app.py --workflow https://www.example.com --language de --num-images 15

STEP-BY-STEP WORKFLOW:
    # 1. Download images
    python3 app.py -d https://www.example.com
    python3 app.py --download https://www.example.com

    # 2. Extract context for each image
    python3 app.py -c https://www.example.com logo.png
    python3 app.py --context https://www.example.com logo.png

    # 3. Generate JSON for specific image
    python3 app.py -g logo.png --url https://www.example.com
    python3 app.py --generate-json logo.png --url https://www.example.com

    # 4. Or process all images at once
    python3 app.py -p --url https://www.example.com
    python3 app.py --process-all --url https://www.example.com

UTILITY COMMANDS:
    # List supported languages
    python3 app.py -al
    python3 app.py --all-languages

CUSTOM FOLDERS:
    python3 app.py -w https://www.example.com \\
        --images-folder custom-images \\
        --context-folder custom-context \\
        --alt-text-folder custom-output

For detailed help on actions: python3 app.py --help-topic <topic>
            """)

        else:
            # General help
            print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         MyAccessibilityBuddy - ECB Accessibility Tool                 ║
║                                   v1.2.0                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    Automated tool for generating WCAG 2.2 compliant alternative text for web
    images. Downloads images, extracts context, and creates AI-ready JSON files
    with support for 24 EU official languages.

ACTIONS:
    -w, --workflow <URL>    Complete workflow (download → context → JSON)
    -d, --download <URL>    Download all images from a webpage
    -c, --context <URL> <IMG>  Extract context for a specific image
    -g, --generate-json <IMG>  Generate JSON file with alt-text analysis
    -p, --process-all       Process all images in batch
    -al, --all-languages    List all supported languages
    --help-topic <TOPIC>    Show detailed help for specific topic

QUICK START:
    # Complete workflow with HTML report
    python3 app.py -w https://www.example.com --clear-all --report
    python3 app.py --workflow https://www.example.com --clear-all --report

    # Multilingual workflow
    python3 app.py -w https://www.example.com --language es --num-images 10

GET HELP:
    python3 app.py --help-topic workflow   # Help for workflow action
    python3 app.py --help-topic download   # Help for download action
    python3 app.py --help-topic context    # Help for context extraction
    python3 app.py --help-topic languages  # Language support information
    python3 app.py --help-topic examples   # Usage examples and workflows

    python3 app.py -h                      # Show basic usage help
    python3 app.py --help                  # Show basic usage help

FEATURES:
    ✓ Supports 5 HTML tag types (img, picture, div, link, meta)
    ✓ 24 EU official languages for alt-text generation
    ✓ Accessible HTML report generation
    ✓ Source URL and page title tracking
    ✓ WCAG 2.2 compliant output
    ✓ OpenAI GPT-4 and ECB-LLM GPT-5 support

CONFIGURATION:
    Edit config.json to customize:
    - LLM provider (OpenAI or ECB-LLM)
    - Image extraction settings
    - Language preferences
    - Folder paths
            """)

    elif args.all_languages:
        # List all supported languages action
        print("\nSupported languages for alt-text generation:")
        print("=" * 60)
        languages_config = CONFIG.get('languages', {}).get('allowed', [])
        default_lang = CONFIG.get('languages', {}).get('default', 'en')

        if languages_config:
            # Group languages in columns for better display
            for i, lang in enumerate(languages_config, 1):
                code = lang['code']
                name = lang['name']
                default_marker = " (default)" if code == default_lang else ""
                print(f"{code:4s} - {name:20s}{default_marker}")
        else:
            print("No languages configured in config.json")

        print("=" * 60)
        print(f"\nTo use a language, specify --language <code> (e.g., --language es)")

    elif args.generate_json:
        # Generate JSON action
        # If image_filename is not provided, check if url arg contains the image filename
        image_file = args.image_filename if args.image_filename else args.url

        if not image_file:
            print("ERROR: --generate-json requires an image filename argument")
            print("Usage: python3 app.py --generate-json <IMAGE_FILENAME> [OPTIONS]")
            import sys
            sys.exit(1)

        # Check if image file exists
        # Determine folder paths with priority: explicit args > session > default
        images_folder = args.images_folder or (session_folders.get('images') if session_folders else None) or get_absolute_folder_path('images')
        context_folder = args.context_folder or (session_folders.get('context') if session_folders else None)
        alt_text_folder = args.alt_text_folder or (session_folders.get('alt_text') if session_folders else None)

        result = generate_alt_text_json(
            image_file,
            images_folder=images_folder,
            context_folder=context_folder,
            prompt_folder=args.prompt_folder,
            alt_text_folder=alt_text_folder,
            language=None,  # language (single) - not used when languages is provided
            url=None,  # No URL for standalone generate-json
            languages=args.language,
            use_geo_boost=args.geo
        )

        # Check result and exit with error code if generation failed
        if result:
            json_path, success = result
            if not success:
                print("WARNING: JSON file created but contains generation error")
                debug_log("JSON generation completed with errors")
                close_log_file()
                import sys
                sys.exit(1)
            else:
                debug_log("JSON generation completed successfully")
                if args.report:
                    print("\nGenerating HTML report...")
                    report_path = generate_html_report(alt_text_folder, images_folder)
                    if report_path:
                        print(f"HTML report generated: {report_path}")
                    else:
                        print("WARNING: Failed to generate HTML report")
        else:
            debug_log("JSON generation failed")

        close_log_file()
        if not result or not result[1]:
            import sys
            sys.exit(1)

    elif args.process_all:
        # Process all images action
        # Initialize log file for this operation
        log_file = initialize_log_file()
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log("Starting process-all for batch image processing")

        # Determine folder paths with priority: explicit args > session > default
        images_folder = args.images_folder or (session_folders.get('images') if session_folders else None) or get_absolute_folder_path('images')
        context_folder = args.context_folder or (session_folders.get('context') if session_folders else None)
        alt_text_folder = args.alt_text_folder or (session_folders.get('alt_text') if session_folders else None)

        debug_log(f"Images folder: {images_folder}")

        print("Processing all images in folder...")
        if args.language:
            if len(args.language) > 1:
                print(f"Languages: {', '.join(args.language)}")
                debug_log(f"Languages: {args.language}")
            else:
                print(f"Language: {args.language[0]}")
                debug_log(f"Language: {args.language[0]}")

        results = process_all_images(
            images_folder,
            context_folder,
            args.prompt_folder,
            alt_text_folder,
            None,  # language (single) - not used when languages is provided
            args.url,
            None,  # image_metadata
            None,  # page_title
            args.language,  # languages
            args.num_images,  # max_images
            args.geo  # use_geo_boost
        )

        # Log results
        debug_log(f"Batch processing complete: {results.get('successful', 0)} successful, {results.get('failed', 0)} failed")

        # Generate HTML report if requested
        if args.report and results.get('successful', 0) > 0:
            print("\nGenerating HTML report...")
            report_path = generate_html_report(alt_text_folder, images_folder)
            if report_path:
                print(f"HTML report generated: {report_path}")
            else:
                print("WARNING: Failed to generate HTML report")

        close_log_file()

        # Return non-zero exit code if there were failures
        if results.get('failed', 0) > 0:
            import sys
            sys.exit(1)

    elif args.workflow:
        # Complete workflow action
        if not args.url:
            print("ERROR: --workflow requires a URL argument")
            print("Usage: python3 app.py --workflow <URL|--url URL> [OPTIONS]")
            import sys
            sys.exit(1)

        if args.num_images:
            log_message(f"Starting MyAccessibilityBuddy complete workflow (max {args.num_images} images)...", "INFORMATION")
        else:
            log_message("Starting MyAccessibilityBuddy complete workflow...", "INFORMATION")

        # Display language info
        if args.language:
            if len(args.language) > 1:
                log_message(f"Generating alt-text in multiple languages: {', '.join(args.language)}", "INFORMATION")
            else:
                log_message(f"Language: {args.language[0]}", "INFORMATION")

        # Determine folder paths with priority: explicit args > session > default
        auto_images = args.images_folder or (session_folders.get('images') if session_folders else None)
        auto_context = args.context_folder or (session_folders.get('context') if session_folders else None)
        auto_alt_text = args.alt_text_folder or (session_folders.get('alt_text') if session_folders else None)

        results = MyAccessibilityBuddy(
            url=args.url,
            images_folder=auto_images,
            context_folder=auto_context,
            prompt_folder=args.prompt_folder,
            alt_text_folder=auto_alt_text,
            clear_all=args.clear_all,
            max_images=args.num_images,
            languages=args.language,
            use_geo_boost=args.geo
        )

        # Generate HTML report if requested
        if args.report and results.get('status') == 'completed':
            print("\nGenerating HTML report...")
            page_title = results.get('page_title', '')
            report_path = generate_html_report(auto_alt_text, images_folder=auto_images, page_title=page_title)
            if report_path:
                print(f"HTML report generated: {report_path}")
            else:
                print("WARNING: Failed to generate HTML report")

        # Return appropriate exit code based on results
        if results.get('status') == 'error':
            import sys
            sys.exit(1)
        elif results.get('status') == 'cancelled':
            import sys
            sys.exit(2)
        elif results.get('summary', {}).get('total_failures', 0) > 0:
            import sys
            sys.exit(3)

    else:
        # No action specified - show help (unless a clear operation was performed)
        if not clear_operation_performed:
            parser.print_help()

if __name__ == "__main__":
    main()
