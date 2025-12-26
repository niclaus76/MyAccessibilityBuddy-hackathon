import requests
import os
import sys
import argparse
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import base64
from mimetypes import guess_type
from openai import OpenAI

# Import ECB-LLM client if available
try:
    from ecb_llm_client import CredentialManager, ECBAzureOpenAI
    cm = CredentialManager()
    cm.set_credentials()
    ECB_LLM_AVAILABLE = True
except ImportError:
    ECB_LLM_AVAILABLE = False
    print("ecb_llm_client not installed. ECB-LLM provider will not be available.")
    print("To use ECB-LLM, install with: pip install ecb_llm_client")

# Import SVG conversion library if available
try:
    import cairosvg
    import io
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
    print("cairosvg not installed. SVG files will not be supported.")
    print("To enable SVG support, install with: pip install cairosvg")

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file")
except ImportError:
    print("python-dotenv not installed. Using system environment variables only.")
    print("To use .env files, install with: pip install python-dotenv")

# Import configuration management
from config import settings as config_settings

# Global configuration (for backward compatibility)
CONFIG = {}
DEBUG_MODE = True
CURRENT_LOG_FILE = None  # Track current log file for this session
LOG_START_TIME = None  # Track when the log session started

def get_cet_time():
    """Get current time in CET (Central European Time) timezone."""
    return datetime.now(ZoneInfo("Europe/Paris"))

def load_config(config_file=None):
    """Load configuration from JSON file with error handling."""
    global CONFIG, DEBUG_MODE
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
    except Exception as e:
        CONFIG = {}
        DEBUG_MODE = True
        debug_log(f"Error loading configuration: {str(e)}, using defaults")

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
        # Get logs folder path
        logs_folder = get_absolute_folder_path('logs')

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

def debug_log(message, level="DEBUG"):
    """Print debug messages if debug mode is enabled and write to log file."""
    if DEBUG_MODE:
        timestamp = get_cet_time().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {level}: {message}"

        # Print to console only if show_debug is true for DEBUG messages
        # For other levels (WARNING, ERROR, INFORMATION), check their respective settings
        should_print = False
        if level == "DEBUG":
            should_print = CONFIG.get('logging', {}).get('show_debug', False)
        elif level == "WARNING":
            should_print = CONFIG.get('logging', {}).get('show_warnings', True)
        elif level == "ERROR":
            should_print = CONFIG.get('logging', {}).get('show_errors', True)
        elif level == "INFORMATION":
            should_print = CONFIG.get('logging', {}).get('show_progress', False)
        else:
            should_print = True  # For any other level, show by default

        if should_print:
            print(log_line)

        # Always write to log file if initialized (regardless of console display setting)
        if CURRENT_LOG_FILE:
            try:
                with open(CURRENT_LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except Exception as e:
                # Don't fail if log write fails, just print warning once
                print(f"Warning: Could not write to log file: {e}")

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
            print(f"Warning: Could not close log file: {e}")

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

def get_llm_credentials():
    """
    Retrieve LLM credentials based on the configured provider.

    Returns:
        tuple: (provider, credentials_dict) where credentials_dict contains the necessary auth info
    """
    func_name = "get_llm_credentials"

    # Get LLM provider from config (options: 'OpenAI' or 'ECB-LLM')
    llm_provider = CONFIG.get('llm_provider', 'OpenAI')
    debug_log(f"LLM provider configured: {llm_provider}")

    if llm_provider == 'OpenAI':
        # Get OpenAI API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            debug_log("OPENAI_API_KEY not found in environment variables", "ERROR")
            return None, None

        debug_log("OpenAI credentials retrieved successfully")
        return 'OpenAI', {'api_key': api_key}

    elif llm_provider == 'ECB-LLM':
        # U2A: User-to-Application OAuth2 authentication
        # ECBAzureOpenAI client automatically reads CLIENT_ID_U2A and CLIENT_SECRET_U2A from environment
        if not ECB_LLM_AVAILABLE:
            debug_log("ECB-LLM client not installed. Install with: pip install ecb_llm_client", "ERROR")
            return None, None

        client_id = os.environ.get('CLIENT_ID_U2A')
        client_secret = os.environ.get('CLIENT_SECRET_U2A')

        if not client_id or not client_secret:
            debug_log("CLIENT_ID_U2A or CLIENT_SECRET_U2A not found in environment variables", "ERROR")
            debug_log("ECBAzureOpenAI requires these environment variables for U2A authentication", "ERROR")
            return None, None

        debug_log("ECB-LLM U2A credentials found in environment")
        return 'ECB-LLM', {'auth_mode': 'U2A'}

    else:
        debug_log(f"Unknown LLM provider: {llm_provider}", "ERROR")
        return None, None

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

def generate_html_report(alt_text_folder=None, output_filename="alt-text-report.html", page_title=None):
    """
    Generate an accessible HTML report summarizing all alt-text JSON files.

    Args:
        alt_text_folder (str): Folder containing JSON files (uses config default if None)
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
        ai_model = ""
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
                        ai_provider = ai_info.get('provider', 'Unknown')
                        ai_model = ai_info.get('model', 'Unknown')
                    # Extract translation method from first item (should be same for all)
                    if not translation_method:
                        translation_method = data.get('translation_method', 'none')
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
            logo_path = config_settings.PROJECT_ROOT / "frontend" / "assets" / "Buddy-Logo_no_text.png"
            if logo_path.exists():
                import base64
                with open(logo_path, 'rb') as logo_file:
                    logo_base64 = base64.b64encode(logo_file.read()).decode('utf-8')
        except Exception as e:
            debug_log(f"Could not load logo: {str(e)}", "WARNING")

        # Load HTML template from external file
        reports_folder = get_absolute_folder_path('reports')
        template_path = os.path.join(reports_folder, 'report_template.html')

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
        for idx, data in enumerate(image_data, 1):
            image_id = data.get('image_id', 'Unknown')
            images_folder = get_absolute_folder_path('images')
            image_type = data.get('image_type', 'unknown')
            image_url = data.get('image_URL', '')
            image_context = data.get('image_context', '')
            current_alt_text = data.get('current_alt_text', '')
            proposed_alt_text_raw = data.get('proposed_alt_text', '')
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

            # Handle both single language (string) and multilingual (array of tuples) formats
            if isinstance(proposed_alt_text_raw, list):
                # Multilingual format: array of tuples [("EN", "text"), ("IT", "text")]
                is_multilingual = True
                proposed_alt_text_items = proposed_alt_text_raw
            else:
                # Single language format: string
                is_multilingual = False
                lang = data.get('language', 'en')
                # Handle case where language is a list (shouldn't happen but defensive)
                if isinstance(lang, list):
                    lang = lang[0] if lang else 'en'
                proposed_alt_text_items = [(lang.upper(), proposed_alt_text_raw)]
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
        <h2 id="image-{idx}-title">{idx}. {image_id}</h2>
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
                image_cards_html += """
        <div class="field">
            <span class="field-label">Proposed Alt Text:</span>
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
        html_content = html_content.replace('{AI_MODEL}', ai_model)
        html_content = html_content.replace('{TRANSLATION_METHOD_TEXT}', translation_method_text)
        html_content = html_content.replace('{TOTAL_IMAGES}', str(len(image_data)))
        html_content = html_content.replace('{TOTAL_PROCESSING_TIME}', f"{total_processing_time:.2f}")
        html_content = html_content.replace('{GENERATION_TIMESTAMP}', get_cet_time().strftime('%Y-%m-%d %H:%M:%S CET'))
        html_content = html_content.replace('{IMAGE_ANALYSIS_OVERVIEW_HTML}', image_analysis_overview_html)
        html_content = html_content.replace('{IMAGE_CARDS_HTML}', image_cards_html)

        # Generate filename based on page title if available
        # Use report_page_title (from JSON) if available, otherwise use page_title (function parameter)
        title_for_filename = report_page_title or page_title

        # Check if user provided custom filename (not the default)
        is_default_filename = output_filename in ["alt-text-report.html", "MyAccessibilityBuddy-AltTextReport.html"]

        if title_for_filename and not is_default_filename:
            # User provided custom filename, use it
            final_filename = output_filename
        elif title_for_filename:
            # Clean page title for filename (remove invalid characters)
            clean_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title_for_filename)
            clean_title = clean_title.replace(' ', '-')[:50]  # Limit length
            final_filename = f"MyAccessibilityBuddy-AltTextReport-{clean_title}.html"
        else:
            # Use default filename without page title
            final_filename = "MyAccessibilityBuddy-AltTextReport.html"

        # Get reports folder from config
        reports_folder = get_absolute_folder_path('reports')

        # Ensure reports folder exists
        os.makedirs(reports_folder, exist_ok=True)

        # Write HTML file to reports folder
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
    Load and merge multiple prompt files based on configuration.

    Args:
        prompt_folder (str): Path to the folder containing prompt files

    Returns:
        tuple: (merged_prompt_text, list_of_loaded_files)
    """
    func_name = "load_and_merge_prompts"
    debug_log(f"Loading prompts from folder: {prompt_folder}")

    # Get prompt configuration
    prompt_config = CONFIG.get('prompt', {})
    prompt_files = prompt_config.get('files', ['alt-text.txt'])
    merge_separator = prompt_config.get('merge_separator', '\n\n---\n\n')
    default_prompt = prompt_config.get('default_prompt', 'alt-text.txt')

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
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Loaded prompt file(s): {', '.join(loaded_files)}")
    else:
        debug_log("No prompt files could be loaded", "WARNING")

    return merged_prompt, loaded_files

def translate_alt_text(alt_text, source_language, target_language):
    """
    Translate alt-text from source language to target language while maintaining 125 character limit.

    Args:
        alt_text (str): The alt-text to translate
        source_language (str): ISO language code of source text (e.g., 'en')
        target_language (str): ISO language code for translation (e.g., 'it', 'es')

    Returns:
        str: Translated alt-text (max 125 chars) or None if failed
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
        elif provider == 'ECB-LLM':
            client = ECBAzureOpenAI()
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
        translation_prompt = f"""Translate the following alternative text from {source_lang_name} to {target_lang_name}.

CRITICAL REQUIREMENTS:
1. The translation MUST be 125 characters or less (including spaces and punctuation)
2. Maintain the meaning and accessibility compliance
3. End with a period
4. Be concise and natural in the target language
5. If the direct translation exceeds 125 characters, use a shorter equivalent that preserves the core meaning

Source text ({source_lang_name}): "{alt_text}"

Provide ONLY the translated text in {target_lang_name}, nothing else. Do not include explanations or metadata."""

        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": f"You are a professional translator specializing in WCAG-compliant alternative text. Translate to {target_lang_name} while ensuring the output is exactly 125 characters or less."
            },
            {
                "role": "user",
                "content": translation_prompt
            }
        ]

        # Get model from config
        model = CONFIG.get('model', 'gpt-4o')

        # Prepare API request parameters
        api_params = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": 200
        }

        # Only add temperature for models that support it (gpt-5.1 doesn't support custom temperature)
        if not model.startswith('gpt-5'):
            api_params["temperature"] = 0.3  # Lower temperature for more consistent translations

        # Make API request
        response = client.chat.completions.create(**api_params)

        # Extract translated text
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

        # Ensure compliance
        if len(translated_text) > 125:
            debug_log(f"Translation exceeds 125 chars ({len(translated_text)}), truncating", "WARNING")
            translated_text = translated_text[:122] + "..."

        if translated_text and not translated_text.endswith('.'):
            translated_text += "."

        debug_log(f"Translation successful: {translated_text} ({len(translated_text)} chars)")
        return translated_text

    except Exception as e:
        handle_exception(func_name, e, f"translating alt-text to {target_language}")
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
        elif provider == 'ECB-LLM':
            client = ECBAzureOpenAI()
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

        # Get model from config
        model = CONFIG.get('model', 'gpt-4o')

        # Prepare API request parameters
        api_params = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": 500
        }

        # Only add temperature for models that support it
        if not model.startswith('gpt-5'):
            api_params["temperature"] = 0.3

        # Make API request
        response = client.chat.completions.create(**api_params)

        # Extract translated text
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


def analyze_image_with_openai(image_path, combined_prompt, language=None):
    """
    Analyze an image using configured LLM provider (OpenAI or ECB-LLM) and return structured JSON data.

    Args:
        image_path (str): Path to the image file
        combined_prompt (str): The combined prompt with context for analysis
        language (str): ISO language code for alt-text generation

    Returns:
        dict: Parsed response with image_type, image_description, reasoning, and alt_text
    """
    func_name = "analyze_image_with_openai"
    debug_log(f"Starting LLM analysis for: {image_path}")

    try:
        # Get credentials based on configured LLM provider
        provider, credentials = get_llm_credentials()
        if not provider or credentials is None:
            debug_log("Failed to retrieve LLM credentials", "ERROR")
            return None

        # Initialize client based on provider
        if provider == 'OpenAI':
            debug_log(f"Using LLM provider: {provider}")
            client = OpenAI(api_key=credentials['api_key'])
            debug_log("OpenAI client initialized")
        elif provider == 'ECB-LLM':
            # ECB-LLM with U2A authentication
            debug_log(f"Using LLM provider: {provider} (U2A OAuth2)")

            # Use ECBAzureOpenAI client (automatic U2A token refresh)
            if not ECB_LLM_AVAILABLE:
                debug_log("ECB-LLM client not available", "ERROR")
                return None

            client = ECBAzureOpenAI()
            debug_log("ECBAzureOpenAI client initialized (U2A mode)")
        else:
            debug_log(f"Unsupported provider: {provider}", "ERROR")
            return None

        # Convert image to data URL with proper MIME type detection
        image_data_url = local_image_to_data_url(image_path)
        debug_log(f"Image converted to data URL")

        # Prepare messages - no system message needed, prompt file has WHO YOU ARE section
        messages = []

        # Add user message with prompt and image
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": combined_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url
                    }
                }
            ]
        })
        debug_log(f"Added user message with prompt and image")

        # Get model from config
        model = CONFIG.get('model', 'gpt-4o')
        debug_log(f"Using model: {model}")

        # Make API request
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=1000
        )

        debug_log(f"{provider} API response received")

        # Parse the response
        response_text = response.choices[0].message.content

        # Check if response is None or empty
        if response_text is None:
            debug_log(f"{provider} returned None response", "ERROR")
            debug_log(f"Full API response object: {response}", "ERROR")
            return None

        if not response_text or len(response_text) == 0:
            debug_log(f"{provider} returned empty response (0 characters)", "ERROR")
            debug_log(f"Response object: {response}", "ERROR")
            debug_log(f"Message content type: {type(response.choices[0].message.content)}", "ERROR")
            return None

        debug_log(f"{provider} response (first 500 chars): {response_text[:500]}...")
        debug_log(f"Full response length: {len(response_text)} characters")
        
        # Try to extract JSON from response
        try:
            # Look for JSON block in the response
            import re

            # First, try to parse the entire response as JSON
            try:
                parsed_response = json.loads(response_text)
                # Ensure the response is a dictionary, not a string or other type
                if isinstance(parsed_response, dict):
                    debug_log("Successfully parsed entire response as JSON", "INFORMATION")
                    return parsed_response
                else:
                    debug_log(f"Response parsed as JSON but is not a dict (type: {type(parsed_response).__name__}), attempting to extract JSON object", "WARNING")
            except json.JSONDecodeError:
                debug_log("Response from LLM contains additional text, extracting JSON block", "INFORMATION")

            # If that fails, try to find JSON within the text (may be surrounded by explanation)
            # Look for content between first { and last }
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = response_text[first_brace:last_brace + 1]
                try:
                    parsed_response = json.loads(json_str)
                    debug_log("Successfully extracted and parsed JSON from response", "INFORMATION")
                    return parsed_response
                except json.JSONDecodeError as e:
                    debug_log(f"Extracted JSON is invalid: {str(e)}", "WARNING")

            # No valid JSON found - try to extract alt text from plain text response
            debug_log("No valid JSON found in response, attempting to extract alt text from plain text", "WARNING")

            # Try to find alt_text in the response (various common formats)
            import re

            # Pattern 1: "alt_text": "value" or alt_text: "value"
            alt_text_match = re.search(r'["\']?alt_text["\']?\s*:\s*["\']([^"\']+)["\']', response_text, re.IGNORECASE)
            if not alt_text_match:
                # Pattern 2: Alternative text: value
                alt_text_match = re.search(r'(?:Alternative text|Alt text)\s*:\s*["\']?([^"\'.\n]+)["\']?', response_text, re.IGNORECASE)
            if not alt_text_match:
                # Pattern 3: Just use the first sentence or up to 125 chars
                sentences = response_text.split('.')
                extracted_text = sentences[0].strip() if sentences else response_text[:125].strip()
            else:
                extracted_text = alt_text_match.group(1).strip()

            # Clean up the extracted text
            # Remove common prefixes
            for prefix in ['alt_text:', 'Alternative text:', 'Alt text:', '"', "'"]:
                if extracted_text.startswith(prefix):
                    extracted_text = extracted_text[len(prefix):].strip()

            # Ensure it ends with a period and is within limit
            if not extracted_text.endswith('.'):
                extracted_text += '.'
            if len(extracted_text) > 125:
                extracted_text = extracted_text[:122] + '...'

            debug_log(f"Extracted alt text from plain response: {extracted_text}")

            # Fallback: create structure from text response
            return {
                "image_type": "informative",
                "image_description": "AI-generated description not available in structured format",
                "reasoning": "Response format parsing failed - extracted from plain text",
                "alt_text": extracted_text
            }
        except json.JSONDecodeError as e:
            debug_log(f"JSON parsing failed: {str(e)}", "WARNING")
            # Fallback response
            return {
                "image_type": "informative", 
                "image_description": "AI analysis completed but format parsing failed",
                "reasoning": "JSON parsing error in AI response",
                "alt_text": "AI-analyzed image."
            }
            
    except Exception as e:
        handle_exception(func_name, e, f"analyzing image {image_path}")
        return None

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
            if CONFIG.get('logging', {}).get('show_progress', True):
                print(f"Downloaded direct image: {filename}")

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

        if CONFIG.get('logging', {}).get('show_progress', True):
            if max_images:
                print(f"Found {len(image_sources)} image sources on the page (will download max {max_images})")
            else:
                print(f"Found {len(image_sources)} image sources on the page")

        for i, img_data in enumerate(image_sources):
            # Check if we've reached the maximum number of images to download
            if max_images and len(downloaded_images) >= max_images:
                debug_log(f"Reached maximum number of images ({max_images}), stopping download")
                if CONFIG.get('logging', {}).get('show_progress', True):
                    print(f"Reached maximum number of images ({max_images}), stopping download")
                break

            debug_log(f"Processing image {i+1}/{len(image_sources)}")

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
                
                if CONFIG.get('logging', {}).get('show_progress', True):
                    print(f"Downloaded: {filename}")
                
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
    if CONFIG.get('logging', {}).get('show_progress', True):
        print(f"Successfully downloaded {len(downloaded_images)} images")

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
            if CONFIG.get('logging', {}).get('show_warnings', True):
                print(error_msg)
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
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Context saved for '{image_filename}' -> {context_filepath}")

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
                    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
                    debug_log(f"Found {len(files)} files in {folder}")

                    for filename in files:
                        # Skip .gitkeep files and report_template.html
                        if filename == '.gitkeep':
                            debug_log(f"Skipping .gitkeep file: {os.path.join(folder, filename)}")
                            continue
                        if filename == 'report_template.html':
                            debug_log(f"Skipping report template: {os.path.join(folder, filename)}")
                            continue

                        filepath = os.path.join(folder, filename)
                        try:
                            os.remove(filepath)
                            deleted_count += 1
                            debug_log(f"Deleted: {filepath}")

                            if CONFIG.get('logging', {}).get('show_progress', True):
                                print(f"Deleted: {filepath}")

                        except PermissionError as e:
                            handle_exception(func_name, e, f"permission denied for {filepath}")
                        except Exception as e:
                            handle_exception(func_name, e, f"deleting {filepath}")
                    
                    deleted_counts[folder] = deleted_count
                    debug_log(f"Cleared {deleted_count} files from '{folder}' folder")
                    
                    if CONFIG.get('logging', {}).get('show_progress', True):
                        print(f"Cleared {deleted_count} files from '{folder}' folder")
                    
                except OSError as e:
                    handle_exception(func_name, e, f"accessing folder '{folder}'")
                    deleted_counts[folder] = 0
                except Exception as e:
                    handle_exception(func_name, e, f"processing folder '{folder}'")
                    deleted_counts[folder] = 0
            else:
                debug_log(f"Folder '{folder}' does not exist", "WARNING")
                if CONFIG.get('logging', {}).get('show_warnings', True):
                    print(f"Folder '{folder}' does not exist")
                deleted_counts[folder] = 0
        
        total_deleted = sum(deleted_counts.values())
        debug_log(f"Clear operation complete: {total_deleted} total files deleted")
        
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"\nTotal files deleted: {total_deleted}")
        
        return deleted_counts
        
    except Exception as e:
        handle_exception(func_name, e, "general error in clear_folders")
        return {}


def generate_alt_text_json(image_filename, images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, language=None, url=None, image_url=None, image_tag_attribute=None, page_title=None, current_alt_text=None, languages=None):
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
                    if CONFIG.get('logging', {}).get('show_errors', True):
                        print(error_msg)
                    return (None, False)
                target_languages.append(lang)
                debug_log(message)
        elif language:
            # Single language specified
            is_valid, message = validate_language(language)
            if not is_valid:
                error_msg = f"Language validation failed: {message}"
                debug_log(error_msg, "ERROR")
                if CONFIG.get('logging', {}).get('show_errors', True):
                    print(error_msg)
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
            prompt_folder = get_absolute_folder_path('prompt')
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')

        debug_log(f"Using folders - images: {images_folder}, context: {context_folder}, prompt: {prompt_folder}, alt-text: {alt_text_folder}")
        
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
            if CONFIG.get('logging', {}).get('show_errors', True):
                print(error_msg)
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
                if CONFIG.get('logging', {}).get('show_progress', True):
                    print(f"Found context file: {context_filename}")
            except Exception as e:
                handle_exception(func_name, e, f"reading context file {context_path}")
        else:
            debug_log(f"Context file '{context_filename}' not found", "WARNING")
            if CONFIG.get('logging', {}).get('show_warnings', True):
                print(f"Warning: Context file '{context_filename}' not found in '{context_folder}' folder")
        
        # Load and merge prompt files
        prompt_text, loaded_prompt_files = load_and_merge_prompts(prompt_folder)
        if not prompt_text:
            error_msg = f"Error: No prompt files could be loaded from '{prompt_folder}' folder"
            debug_log(error_msg, "ERROR")
            if CONFIG.get('logging', {}).get('show_errors', True):
                print(error_msg)
            return (None, False)

        debug_log("Creating JSON structure...")

        # Store base prompt template (will replace {LANGUAGE} per-language later)
        prompt_template = prompt_text

        # Helper function to create language-specific prompt
        language_map = {
            'bg': 'Bulgarian', 'cs': 'Czech', 'da': 'Danish', 'de': 'German', 'el': 'Greek',
            'en': 'English', 'es': 'Spanish', 'et': 'Estonian', 'fi': 'Finnish', 'fr': 'French',
            'ga': 'Irish', 'hr': 'Croatian', 'hu': 'Hungarian', 'it': 'Italian', 'lt': 'Lithuanian',
            'lv': 'Latvian', 'mt': 'Maltese', 'nl': 'Dutch', 'pl': 'Polish', 'pt': 'Portuguese',
            'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sv': 'Swedish'
        }

        def create_prompt_for_language(lang_code):
            """Create combined prompt with language placeholder replaced."""
            lang_name = language_map.get(lang_code, lang_code)
            lang_prompt = prompt_template.replace('{LANGUAGE}', lang_name)

            if context_text and lang_prompt:
                return f"{lang_prompt}\n\nContext about the image:\n{context_text}\n\nImage filename: {image_filename}"
            elif lang_prompt:
                return f"{lang_prompt}\n\nImage filename: {image_filename}"
            else:
                return f"Analyze this image and provide: image_type (decorative/informative/functional), image_description, reasoning, and alt_text (max 125 chars).\n\nImage filename: {image_filename}"

        # Try LLM analysis (OpenAI or ECB-LLM based on configuration)
        translation_method = None  # Track translation method used
        if is_multilingual:
            # Generate alt-text for multiple languages
            debug_log(f"Generating alt-text for {len(target_languages)} languages: {target_languages}")

            # Check translation mode from config
            # Support both new format ('fast'/'accurate') and legacy format (True/False)
            translation_mode_config = CONFIG.get('translation_mode', CONFIG.get('full_translation_mode', 'fast'))

            # Convert boolean legacy format to string format
            if isinstance(translation_mode_config, bool):
                translation_mode_config = 'accurate' if translation_mode_config else 'fast'

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
                    llm_result = analyze_image_with_openai(image_path, lang_prompt, lang)

                    if llm_result:
                        # Store metadata from first language analysis
                        if image_type is None:
                            image_type = llm_result.get("image_type", "informative")
                            image_description = llm_result.get("image_description", "")

                        lang_alt_text = llm_result.get("alt_text", "")
                        lang_reasoning = llm_result.get("reasoning", "")

                        # Ensure alt_text compliance
                        if len(lang_alt_text) > 125:
                            lang_alt_text = lang_alt_text[:122] + "..."
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
                llm_result = analyze_image_with_openai(image_path, first_lang_prompt, first_lang)

                if llm_result:
                    # Store all metadata from first language analysis
                    image_type = llm_result.get("image_type", "informative")
                    image_description = llm_result.get("image_description", "")
                    first_lang_reasoning = llm_result.get("reasoning", "")
                    first_lang_alt_text = llm_result.get("alt_text", "")

                    # Ensure alt_text compliance
                    if len(first_lang_alt_text) > 125:
                        first_lang_alt_text = first_lang_alt_text[:122] + "..."
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
                        translated_alt_text = translate_alt_text(first_lang_alt_text, first_lang, lang)
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
        else:
            # Single language mode (existing behavior)
            lang = target_languages[0]
            debug_log(f"Language specified: {lang}")
            # Create language-specific prompt
            lang_prompt = create_prompt_for_language(lang)
            debug_log(f"Created prompt for {lang} ({language_map.get(lang, lang)})")
            llm_result = analyze_image_with_openai(image_path, lang_prompt, lang)

            if llm_result:
                # Use LLM results
                image_type = llm_result.get("image_type", "informative")
                image_description = llm_result.get("image_description", "")
                reasoning = llm_result.get("reasoning", "")
                alt_text = llm_result.get("alt_text", "")

                # Ensure alt_text compliance
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + "..."
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
            # Multilingual mode: array of tuples
            # Create list of [language, character_count] for each language
            characters = [[lang_code.upper(), len(text)] for lang_code, text in alt_text] if image_type != "decorative" and image_type != "generation_error" else []
            proposed_alt_text = alt_text if image_type != "decorative" and image_type != "generation_error" else []
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
            "web_site_url": url if url else "",
            "page_title": page_title if page_title else "",
            "image_id": image_filename,
            "image_type": image_type,
            "image_context": context_text if context_text else "",
            "image_URL": image_url if image_url else "",
            "image_tag_attribute": image_tag_attribute if image_tag_attribute else {"tag": "unknown", "attribute": "unknown"},
            "language": target_languages if is_multilingual else target_languages[0],
            "reasoning": reasoning,
            "extended_description": image_description,
            "current_alt_text": current_alt_text if current_alt_text else "",
            "proposed_alt_text": proposed_alt_text,
            "proposed_alt_text_length": characters,
            "ai_model": {
                "provider": CONFIG.get('llm_provider', 'Unknown'),
                "model": CONFIG.get('model', 'Unknown')
            },
            "translation_method": translation_method if translation_method else "none",
            "processing_time_seconds": processing_time
        }

        debug_log(f"Final result - Type: {image_type}, Severity: {severity}, Alt-text: {alt_text}")

        # Log full JSON output
        debug_log(f"Full JSON output:\n{json.dumps(json_data, indent=2, ensure_ascii=False)}")

        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Generated: {image_type} ({severity}) - {alt_text}")

        # Save JSON file
        json_filename = f"{base_filename}.json"
        json_path = os.path.join(alt_text_folder, json_filename)
        debug_log(f"Saving JSON to: {json_path}")

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        debug_log(f"JSON file generated successfully: {json_path}")
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Generated JSON file: {json_path}")

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


def process_all_images(images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, language=None, url=None, image_metadata=None, page_title=None, languages=None):
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
            prompt_folder = get_absolute_folder_path('prompt')
        if alt_text_folder is None:
            alt_text_folder = get_absolute_folder_path('alt_text')
        
        debug_log(f"Processing images from: {images_folder}")
        debug_log(f"Using folders - context: {context_folder}, prompt: {prompt_folder}, alt-text: {alt_text_folder}")
        
        # Check if images folder exists
        if not os.path.exists(images_folder):
            error_msg = f"Images folder '{images_folder}' does not exist"
            debug_log(error_msg, "ERROR")
            if CONFIG.get('logging', {}).get('show_errors', True):
                print(error_msg)
            return {"processed": 0, "successful": 0, "failed": 0, "error": error_msg}
        
        # Get all image files from images folder
        try:
            all_files = os.listdir(images_folder)
            # Filter for common image extensions
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.tiff'}
            image_files = [f for f in all_files 
                          if os.path.isfile(os.path.join(images_folder, f)) and 
                          os.path.splitext(f.lower())[1] in image_extensions]
            
            debug_log(f"Found {len(image_files)} image files in {images_folder}")
            
            if len(image_files) == 0:
                warning_msg = f"No image files found in '{images_folder}' folder"
                debug_log(warning_msg, "WARNING")
                if CONFIG.get('logging', {}).get('show_warnings', True):
                    print(warning_msg)
                return {"processed": 0, "successful": 0, "failed": 0, "warning": warning_msg}
            
        except OSError as e:
            handle_exception(func_name, e, f"accessing images folder '{images_folder}'")
            return {"processed": 0, "successful": 0, "failed": 0, "error": str(e)}
        
        # Process each image
        results = {
            "processed": len(image_files),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Processing {len(image_files)} images...")
        
        for i, image_filename in enumerate(image_files, 1):
            debug_log(f"Processing image {i}/{len(image_files)}: {image_filename}")
            
            if CONFIG.get('logging', {}).get('show_progress', True):
                print(f"[{i}/{len(image_files)}] Processing: {image_filename}")
            
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
                    languages
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
        
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"\nBatch processing complete:")
            print(f"  Total images: {results['processed']}")
            print(f"  Successful: {results['successful']}")
            print(f"  Failed: {results['failed']}")
            
            if results['failed'] > 0:
                print(f"\nFailed images:")
                for detail in results['details']:
                    if detail['status'] == 'failed':
                        print(f"  - {detail['image']}: {detail.get('error', 'Unknown error')}")
        
        return results
        
    except Exception as e:
        handle_exception(func_name, e, "general error in batch processing")
        return {"processed": 0, "successful": 0, "failed": 0, "error": str(e)}


def AutoAltText(url, images_folder=None, context_folder=None, prompt_folder=None, alt_text_folder=None, clear_all=False, max_images=None, languages=None):
    """
    Complete AutoAltText workflow: downloads images, extracts context, and generates JSON files.

    Args:
        url (str): The URL to download images from and extract context
        images_folder (str): Folder to save images (uses config default if None)
        context_folder (str): Folder to save context files (uses config default if None)
        prompt_folder (str): Folder containing prompt template (uses config default if None)
        alt_text_folder (str): Folder to save JSON files (uses config default if None)
        clear_all (bool): If True, automatically clear all folders (including reports) without prompting
        max_images (int): Maximum number of images to download and process (None for all)
        languages (list): List of ISO language codes for multilingual alt-text (e.g., ['en', 'it', 'es'])

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
            prompt_folder = get_absolute_folder_path('prompt')
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
        if total_existing > 0 and clear_all:
            if CONFIG.get('logging', {}).get('show_progress', True):
                print(f"Auto-clearing {total_existing} existing files (plus reports and logs folders)...")

            # Include reports and logs folders when using --clear-all
            folders_to_clear_all = folders_to_check + [get_absolute_folder_path('reports'), get_absolute_folder_path('logs')]
            clear_results = clear_folders(folders_to_clear_all)

            if CONFIG.get('logging', {}).get('show_progress', True):
                print(f"Auto-cleared {sum(clear_results.values())} files from all folders")

        # Initialize log file AFTER clear operation (so it doesn't get deleted)
        log_file = initialize_log_file(url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting {func_name} for URL: {url}")
        debug_log(f"Using folders - images: {images_folder}, context: {context_folder}, prompt: {prompt_folder}, alt-text: {alt_text_folder}")

        # Skip clearing prompt - just continue with existing files
        if total_existing > 0 and not clear_all:
            debug_log(f"Found {total_existing} existing files, continuing without clearing")
            if CONFIG.get('logging', {}).get('show_progress', True):
                print(f"Found {total_existing} existing files in folders, continuing...")
        
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
        if CONFIG.get('logging', {}).get('show_progress', True):
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

        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Downloaded {len(download_results)} images")
        
        # Step 2: Extract context for all images
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"\nStep 2/3: Extracting context for {len(download_results)} images...")
        
        debug_log("Starting context extraction step")
        context_results = {"successful": 0, "failed": 0, "details": []}

        for i, image_filename in enumerate(download_results, 1):
            debug_log(f"Extracting context for image {i}/{len(download_results)}: {image_filename}")

            if CONFIG.get('logging', {}).get('show_progress', True):
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
        
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"Context extracted: {context_results['successful']} successful, {context_results['failed']} failed")
        
        # Step 3: Generate JSON files for all images
        if CONFIG.get('logging', {}).get('show_progress', True):
            print(f"\nStep 3/3: Generating JSON files for all images...")

        debug_log("Starting JSON generation step")
        json_results = process_all_images(images_folder, context_folder, prompt_folder, alt_text_folder, None, url, image_metadata, page_title, languages)

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

        if CONFIG.get('logging', {}).get('show_progress', True):
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

    # Action flags (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
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
    action_group.add_argument('--help-topic', type=str, metavar='TOPIC',
                            help='Show detailed help (topics: workflow, download, context, languages, examples)')

    # Common options
    parser.add_argument('--folder', default=None, help='Folder for images or context (used with -d or -c)')
    parser.add_argument('--images-folder', default=None, help='Folder for images (default: from config)')
    parser.add_argument('--context-folder', default=None, help='Folder for context files (default: from config)')
    parser.add_argument('--prompt-folder', default=None, help='Folder for prompt templates (default: from config)')
    parser.add_argument('--alt-text-folder', default=None, help='Folder for JSON output (default: from config)')
    parser.add_argument('--language', nargs='+', default=None, help='One or more ISO language codes for alt-text (e.g. en es fr de)')
    parser.add_argument('--num-images', type=int, default=None, help='Maximum number of images to download')
    parser.add_argument('--clear-all', action='store_true', help='Clear all folders (images, context, alt-text, reports, logs) without prompting')
    parser.add_argument('--clear-inputs', action='store_true', help='Clear input folders (images, context) without prompting')
    parser.add_argument('--clear-outputs', action='store_true', help='Clear output folders (alt-text, reports) without prompting')
    parser.add_argument('--clear-log', action='store_true', help='Clear log files without prompting')
    parser.add_argument('--report', action='store_true', help='Generate accessible HTML report after processing')

    # Parse arguments
    args = parser.parse_args()

    # Handle clear operations FIRST (before main actions)
    # These are modifier flags that should run before the main action
    clear_operation_performed = False

    if args.clear_all:
        # Clear all folders (inputs + outputs + reports + logs) without prompting
        folders_to_clear = [
            get_absolute_folder_path('images'),
            get_absolute_folder_path('context'),
            get_absolute_folder_path('alt_text'),
            get_absolute_folder_path('reports'),
            get_absolute_folder_path('logs')
        ]
        print("Clearing all folders (images, context, alt-text, reports, logs)...")
        results = clear_folders(folders_to_clear)
        total_deleted = sum(results.values())
        print(f"Cleared {total_deleted} files from all folders")
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

    # Handle main actions based on flags
    if args.download:
        # Download images action
        if not args.url:
            print("ERROR: --download requires a URL argument")
            print("Usage: python3 app.py --download <URL> [OPTIONS]")
            import sys
            sys.exit(1)

        # Initialize log file for this operation
        log_file = initialize_log_file(args.url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting download from URL: {args.url}")
        folder = args.folder if args.folder else None
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
            print("Usage: python3 app.py --context <URL> <IMAGE_FILENAME> [OPTIONS]")
            import sys
            sys.exit(1)
        if not args.image_filename:
            print("ERROR: --context requires an image filename argument")
            print("Usage: python3 app.py --context <URL> <IMAGE_FILENAME> [OPTIONS]")
            import sys
            sys.exit(1)

        # Initialize log file for this operation
        log_file = initialize_log_file(args.url)
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting context extraction for image: {args.image_filename}")
        debug_log(f"URL: {args.url}")

        folder = args.folder if args.folder else None
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
    AutoAltText supports generating alt-text in 24 EU official languages.
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
║                         AutoAltText - ECB Accessibility Tool                 ║
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

For more information, see AutoAltText.md
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
        images_folder = args.images_folder if args.images_folder else get_absolute_folder_path('images')
        image_path = os.path.join(images_folder, image_file)
        if not os.path.exists(image_path):
            print(f"ERROR: File '{image_file}' not found in folder '{images_folder}'")
            import sys
            sys.exit(1)

        # Initialize log file for this operation
        log_file = initialize_log_file()
        if log_file:
            debug_log(f"Log file created: {log_file}")

        debug_log(f"Starting generate-json for image: {image_file}")
        debug_log(f"Images folder: {images_folder}")

        print(f"Generating JSON for image: {image_file}")
        if args.language:
            if len(args.language) > 1:
                print(f"Languages: {', '.join(args.language)}")
                debug_log(f"Languages: {args.language}")
            else:
                print(f"Language: {args.language[0]}")
                debug_log(f"Language: {args.language[0]}")

        result = generate_alt_text_json(
            image_file,
            images_folder=args.images_folder,
            context_folder=args.context_folder,
            prompt_folder=args.prompt_folder,
            alt_text_folder=args.alt_text_folder,
            language=None,  # language (single) - not used when languages is provided
            url=None,  # No URL for standalone generate-json
            languages=args.language
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
        images_folder = args.images_folder if args.images_folder else get_absolute_folder_path('images')
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
            args.images_folder,
            args.context_folder,
            args.prompt_folder,
            args.alt_text_folder,
            None,  # language (single) - not used when languages is provided
            args.url,
            None,  # image_metadata
            None,  # page_title
            args.language  # languages
        )

        # Log results
        debug_log(f"Batch processing complete: {results.get('successful', 0)} successful, {results.get('failed', 0)} failed")

        # Generate HTML report if requested
        if args.report and results.get('successful', 0) > 0:
            print("\nGenerating HTML report...")
            report_path = generate_html_report(args.alt_text_folder)
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
            print("Usage: python3 app.py --workflow <URL> [OPTIONS]")
            import sys
            sys.exit(1)

        if args.num_images:
            print(f"Starting AutoAltText complete workflow (max {args.num_images} images)...")
        else:
            print("Starting AutoAltText complete workflow...")

        # Display language info
        if args.language:
            if len(args.language) > 1:
                print(f"Generating alt-text in multiple languages: {', '.join(args.language)}")
            else:
                print(f"Language: {args.language[0]}")

        results = AutoAltText(
            args.url,
            args.images_folder,
            args.context_folder,
            args.prompt_folder,
            args.alt_text_folder,
            args.clear_all,
            args.num_images,
            args.language
        )

        # Generate HTML report if requested
        if args.report and results.get('status') == 'completed':
            print("\nGenerating HTML report...")
            page_title = results.get('page_title', '')
            report_path = generate_html_report(args.alt_text_folder, page_title=page_title)
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