#!/usr/bin/env python3
"""
MyAccessibilityBuddy - Batch Prompt Comparison Script

This script systematically tests multiple prompt templates against a set of test images
to evaluate and compare the quality of generated alt-text. It helps you:

1. Compare different prompt engineering approaches
2. Identify which prompts produce better WCAG-compliant alt-text
3. Optimize your prompt templates based on quantitative results
4. Track improvements across prompt versions

Features:
- Processes test images with multiple prompt configurations
- Generates side-by-side comparison reports (CSV + HTML)
- Preserves configuration state between runs
- Provides detailed progress feedback

Configuration:
Test parameters are defined in backend/config/config.json under batch_comparison:
  - batch_comparison.prompts: List of prompt files to compare
  - batch_comparison.test_images: Images to process
  - batch_comparison.language: Language for alt-text generation
  - batch_comparison.test_geo_boost: If true, tests BOTH GEO and non-GEO modes for each image+prompt

Output:
- CSV report: test/output/reports/prompt_comparison_{timestamp}.csv
- HTML report: test/output/reports/prompt_comparison_{timestamp}.html
- If test_geo_boost=true: Each prompt generates TWO columns (standard + GEO) for comparison

Example Usage:
  # Docker (recommended)
  docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py

  # Local environment
  python3 tools/batch_compare_prompts.py

Example Configuration (config.json):
  "batch_comparison": {
    "prompts": [
      {"file": "processing_prompt_v3.txt", "label": "v3: WCAG focused"},
      {"file": "processing_prompt_v5.txt", "label": "v5: enhanced WCAG"}
    ],
    "test_images": ["1.png", "2.png"],
    "language": "en",
    "test_geo_boost": false
  }

Note: test_geo_boost=true generates BOTH standard and GEO-optimized versions for comprehensive comparison

Example Output (CSV):
  Image Filename | Alt Text (v0) | Alt Text (v2)
  1.png          | Simple desc   | Detailed WCAG-compliant description
  2.png          | Basic text    | Contextual informative description
"""

import json
import argparse
import csv
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# ANSI color codes
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
CONFIG_FILE = BACKEND_DIR / "config" / "config.json"
CONFIG_ADVANCED_FILE = BACKEND_DIR / "config" / "config.advanced.json"
PROMPT_DIR = PROJECT_ROOT / "prompt" / "processing"

def resolve_project_path(path: Path) -> Path:
    """Resolve paths relative to project root when not absolute."""
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

# These will be loaded from config.json
PROMPTS = []
TEST_IMAGES = []
TEST_LANGUAGES = ["en"]  # Support multiple languages
TEST_GEO_BOOST = False  # If true, test BOTH GEO and non-GEO modes

# Paths that will be set from config.advanced.json
IMAGES_DIR = None
CONTEXT_DIR = None
OUTPUT_DIR = None
OUTPUT_REPORTS_DIR = None
OVERRIDE_VISION_PROVIDER = None
OVERRIDE_VISION_MODEL = None
OVERRIDE_PROCESSING_PROVIDER = None
OVERRIDE_PROCESSING_MODEL = None
OVERRIDE_TRANSLATION_PROVIDER = None
OVERRIDE_TRANSLATION_MODEL = None
OVERRIDE_ADVANCED_TRANSLATION = False

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}{text.center(70)}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")

def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.NC}")

def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}→ {text}{Colors.NC}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")

def load_test_config(args=None):
    """Load test configuration from config.json and config.advanced.json."""
    global PROMPTS, TEST_IMAGES, TEST_LANGUAGES, TEST_GEO_BOOST
    global IMAGES_DIR, CONTEXT_DIR, OUTPUT_DIR, OUTPUT_REPORTS_DIR
    global OVERRIDE_VISION_PROVIDER, OVERRIDE_VISION_MODEL
    global OVERRIDE_PROCESSING_PROVIDER, OVERRIDE_PROCESSING_MODEL
    global OVERRIDE_TRANSLATION_PROVIDER, OVERRIDE_TRANSLATION_MODEL
    global OVERRIDE_ADVANCED_TRANSLATION

    if not CONFIG_FILE.exists():
        print_error(f"Configuration file not found: {CONFIG_FILE}")
        print_info("Please ensure backend/config/config.json exists")
        return False

    try:
        # Load main config for batch_comparison settings
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        batch_comparison = config.get('batch_comparison', {})

        PROMPTS = batch_comparison.get('prompts', [])
        TEST_IMAGES = batch_comparison.get('test_images', [])
        # Support both 'language' (single) and 'languages' (array) in config
        config_lang = batch_comparison.get('languages', batch_comparison.get('language', 'en'))
        TEST_LANGUAGES = config_lang if isinstance(config_lang, list) else [config_lang]
        TEST_GEO_BOOST = batch_comparison.get('test_geo_boost', False)

        # Load advanced config for folder paths
        if CONFIG_ADVANCED_FILE.exists():
            with open(CONFIG_ADVANCED_FILE, 'r', encoding='utf-8') as f:
                advanced_config = json.load(f)
            test_folders = advanced_config.get('testing', {}).get('folders', {})
        else:
            test_folders = {}

        # Set folder paths from configuration
        IMAGES_DIR = resolve_project_path(Path(test_folders.get('test_images', 'test/input/images')))
        CONTEXT_DIR = resolve_project_path(Path(test_folders.get('test_context', 'test/input/context')))
        OUTPUT_REPORTS_DIR = resolve_project_path(Path(test_folders.get('test_reports', 'test/output/reports')))
        OUTPUT_DIR = resolve_project_path(Path("output/alt-text"))  # Keep original output for intermediate results

        # CLI overrides (used by web app)
        if args:
            if args.images_folder:
                IMAGES_DIR = resolve_project_path(Path(args.images_folder))
            if args.context_folder:
                CONTEXT_DIR = resolve_project_path(Path(args.context_folder))
            if args.prompts:
                PROMPTS = []
                for prompt in args.prompts:
                    if prompt.endswith('.txt'):
                        prompt_file = prompt
                        label = Path(prompt).stem.replace('processing_prompt_', '')
                    else:
                        prompt_file = f"processing_prompt_{prompt}.txt"
                        label = prompt
                    PROMPTS.append({
                        "file": prompt_file,
                        "label": label,
                        "description": ""
                    })
            if args.language:
                TEST_LANGUAGES = args.language  # Use all provided languages
            if args.geo_boost:
                TEST_GEO_BOOST = True

            OVERRIDE_VISION_PROVIDER = args.vision_provider
            OVERRIDE_VISION_MODEL = args.vision_model
            OVERRIDE_PROCESSING_PROVIDER = args.processing_provider
            OVERRIDE_PROCESSING_MODEL = args.processing_model
            OVERRIDE_TRANSLATION_PROVIDER = args.translation_provider
            OVERRIDE_TRANSLATION_MODEL = args.translation_model
            OVERRIDE_ADVANCED_TRANSLATION = bool(args.advanced_translation)

            # For app usage, keep reports in output/reports
            OUTPUT_REPORTS_DIR = resolve_project_path(Path("output/reports"))

        print_success("Loaded batch comparison configuration from config.json")
        print_info(f"Test mode: {'GEO Boost Comparison (both modes)' if TEST_GEO_BOOST else 'Standard WCAG only'}")
        print_info(f"Languages: {', '.join(TEST_LANGUAGES)}")
        print_info(f"Prompts to test: {len(PROMPTS)}")
        print_info(f"Test images: {len(TEST_IMAGES)} images")
        print_info(f"Test images folder: {IMAGES_DIR}")
        print_info(f"Test context folder: {CONTEXT_DIR}")
        print_info(f"Output reports folder: {OUTPUT_REPORTS_DIR}")

        return True
    except Exception as e:
        print_error(f"Error loading test configuration: {e}")
        return False

def check_environment():
    """Check if the environment is set up correctly."""
    print_header("Environment Check")

    # Check if we're in project root
    if not CONFIG_FILE.exists():
        print_error(f"Configuration file not found: {CONFIG_FILE}")
        print_error("Please run this script from the project root directory")
        return False

    print_success("Project root directory verified")

    # Check test images from configuration
    if not IMAGES_DIR.exists():
        print_error(f"Images directory not found: {IMAGES_DIR}")
        return False

        # Determine test images if not explicitly configured
        if not TEST_IMAGES:
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            TEST_IMAGES = sorted([
                p.name for p in IMAGES_DIR.iterdir()
                if p.is_file() and p.suffix.lower() in image_extensions
            ])

        # Validate test images exist
        missing_images = []
        for image in TEST_IMAGES:
            image_path = IMAGES_DIR / image
            if not image_path.exists():
                missing_images.append(image)

        if missing_images:
            print_error(f"Test images not found: {', '.join(missing_images)}")
            return False

        print_success(f"Found all {len(TEST_IMAGES)} test images configured")

    # Check context directory
    if CONTEXT_DIR.exists():
        contexts = list(CONTEXT_DIR.glob("*.txt"))
        print_success(f"Found {len(contexts)} context files")
    else:
        print_warning("No context directory found - processing without context")

    # Check prompt files
    print_info("Checking prompt files...")
    for prompt in PROMPTS:
        prompt_path = PROMPT_DIR / prompt['file']
        if not prompt_path.exists():
            print_error(f"Prompt file not found: {prompt_path}")
            return False
        print_success(f"  {prompt['file']}")

    return True

def backup_config():
    """Backup the configuration file."""
    backup_path = CONFIG_FILE.with_suffix('.json.backup')
    shutil.copy2(CONFIG_FILE, backup_path)
    print_success(f"Configuration backed up to {backup_path}")
    return backup_path

def restore_config(backup_path: Path):
    """Restore the configuration file from backup."""
    if backup_path.exists():
        shutil.copy2(backup_path, CONFIG_FILE)
        backup_path.unlink()
        print_success("Configuration restored")

def update_config_prompt(prompt_file: str):
    """Update the configuration to use a specific prompt file."""
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    # Update the processing_files and default_processing_prompt
    config['prompt']['processing_files'] = [prompt_file]
    config['prompt']['default_processing_prompt'] = prompt_file

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    print_info(f"Updated configuration to use: {prompt_file}")

def clear_output_directory(session_id=None):
    """Clear the output directory.

    Args:
        session_id (str, optional): If provided, clears only that session's folder.
                                   If None, clears all session folders and base directory.
    """
    if OUTPUT_DIR.exists():
        if session_id:
            # Clear specific session folder
            session_dir = OUTPUT_DIR / session_id
            if session_dir.exists():
                for file in session_dir.glob("*.json"):
                    file.unlink()
                print_success(f"Cleared session directory: {session_id}")
        else:
            # Clear all JSON files in base directory
            for file in OUTPUT_DIR.glob("*.json"):
                file.unlink()
            # Clear all session-specific directories (cli-*, web-*)
            for session_dir in OUTPUT_DIR.iterdir():
                if session_dir.is_dir() and (session_dir.name.startswith('cli-') or session_dir.name.startswith('web-')):
                    for file in session_dir.glob("*.json"):
                        file.unlink()
                    # Optionally remove empty session directories
                    try:
                        session_dir.rmdir()
                    except OSError:
                        # Directory not empty, that's okay
                        pass
            print_success("Cleared output directory and all session folders")

def run_batch_processing(use_geo=False):
    """Run the batch processing command with optional GEO boost.

    Args:
        use_geo (bool): If True, adds --geo flag for GEO-optimized alt-text

    Returns:
        str or None: Session ID if successful, None if failed
    """
    mode_label = "GEO-optimized" if use_geo else "standard WCAG"
    print_info(f"Running batch processing ({mode_label})...")

    try:
        # Build command with test folders (without --legacy to use session-based folders)
        cmd = [
            "python3", "app.py", "-p",
            "--images-folder", str(IMAGES_DIR)
        ]

        # If images folder contains a session ID (web- or cli-), also set alt-text-folder
        # to prevent creating a new CLI session
        images_folder_str = str(IMAGES_DIR)
        if '/web-' in images_folder_str or '/cli-' in images_folder_str:
            # Extract session ID from path like /path/to/input/images/web-xxx or /path/to/input/images/cli-xxx
            import re
            session_match = re.search(r'/(web-[^/]+|cli-[^/]+)', images_folder_str)
            if session_match:
                session_id = session_match.group(1)
                # Construct alt-text folder path for the same session
                alt_text_folder = images_folder_str.replace('/input/images/', '/output/alt-text/')
                cmd.extend(["--alt-text-folder", alt_text_folder])
                print_info(f"Using session folders for: {session_id}")

        # Add all languages in a single --language argument
        # Note: app.py expects --language en it (not --language en --language it)
        if TEST_LANGUAGES:
            cmd.append("--language")
            cmd.extend(TEST_LANGUAGES)

        if CONTEXT_DIR and CONTEXT_DIR.exists():
            cmd.extend(["--context-folder", str(CONTEXT_DIR)])

        # Add --geo flag if requested
        if use_geo:
            cmd.append("--geo")
            print_info("GEO boost enabled - adding --geo flag")

        if OVERRIDE_VISION_PROVIDER:
            cmd.extend(["--vision-provider", OVERRIDE_VISION_PROVIDER])
        if OVERRIDE_VISION_MODEL:
            cmd.extend(["--vision-model", OVERRIDE_VISION_MODEL])
        if OVERRIDE_PROCESSING_PROVIDER:
            cmd.extend(["--processing-provider", OVERRIDE_PROCESSING_PROVIDER])
        if OVERRIDE_PROCESSING_MODEL:
            cmd.extend(["--processing-model", OVERRIDE_PROCESSING_MODEL])
        if OVERRIDE_TRANSLATION_PROVIDER:
            cmd.extend(["--translation-provider", OVERRIDE_TRANSLATION_PROVIDER])
        if OVERRIDE_TRANSLATION_MODEL:
            cmd.extend(["--translation-model", OVERRIDE_TRANSLATION_MODEL])
        if OVERRIDE_ADVANCED_TRANSLATION:
            cmd.append("--advanced-translation")

        # Change to backend directory and run the command
        result = subprocess.run(
            cmd,
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode != 0:
            print_error(f"Batch processing failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error output: {result.stderr}")
            return None

        # Extract session ID from output (looks for "Using session: cli-xxxxx")
        session_id = None
        for line in result.stdout.split('\n'):
            if 'Using session:' in line:
                session_id = line.split('Using session:')[1].strip()
                break

        print_success(f"Batch processing completed ({mode_label})")
        if session_id:
            print_info(f"Session ID: {session_id}")
        return session_id

    except subprocess.TimeoutExpired:
        print_error("Batch processing timed out (1 hour limit)")
        return None
    except Exception as e:
        print_error(f"Error running batch processing: {e}")
        return None

def extract_results(session_id=None) -> Dict[str, Dict[str, str]]:
    """Extract alt-text results from JSON files, supporting multilingual output.

    Args:
        session_id (str, optional): CLI session ID to extract results from.
                                   If provided, looks in output/alt-text/{session_id}/
                                   If None, looks directly in output/alt-text/

    Returns:
        Dict[str, Dict[str, str]]: Mapping of image filename to {language: alt-text}
        Example: {"image1.png": {"EN": "alt text in English", "IT": "alt text in Italian"}}
    """
    results = {}

    # Determine which directory to search
    if session_id:
        search_dir = OUTPUT_DIR / session_id
        if not search_dir.exists():
            print_warning(f"Session directory not found: {search_dir}")
            return results
    else:
        search_dir = OUTPUT_DIR

    for json_file in search_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Use image_id from JSON, or fallback to filename
                image_file = data.get('image_id', json_file.stem)
                # The field is 'proposed_alt_text' not 'alt_text'
                alt_text_raw = data.get('proposed_alt_text', data.get('alt_text', ''))
                language_raw = data.get('language', 'en')

                # Handle multilingual output (array of [lang, text] pairs)
                if isinstance(alt_text_raw, list):
                    # Multilingual: [["EN", "text"], ["IT", "testo"]]
                    lang_texts = {}
                    for item in alt_text_raw:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            lang_code = item[0].upper()
                            text = item[1]
                            lang_texts[lang_code] = text
                    results[image_file] = lang_texts
                else:
                    # Single language: string
                    lang_code = language_raw.upper() if isinstance(language_raw, str) else 'EN'
                    results[image_file] = {lang_code: alt_text_raw}
        except Exception as e:
            print_warning(f"Error reading {json_file.name}: {e}")

    return results

def generate_csv(all_results: Dict[str, Dict[str, Dict[str, str]]], output_path: Path):
    """Generate CSV comparison file with multilingual support.

    Args:
        all_results: Dict[prompt_label, Dict[image_filename, Dict[language, alt_text]]]
        output_path: Path to write the CSV file
    """
    print_header("Generating CSV Report")

    # Get all unique image filenames
    all_images = set()
    for prompt_results in all_results.values():
        all_images.update(prompt_results.keys())

    sorted_images = sorted(all_images)

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)

        # Build header with language columns
        header = ['Image Filename']
        if TEST_GEO_BOOST:
            # Dual-mode: create columns for both standard and GEO for each prompt and language
            for prompt in PROMPTS:
                for lang in TEST_LANGUAGES:
                    header.append(f"{prompt['label']} ({lang.upper()}) Standard")
                    header.append(f"{prompt['label']} ({lang.upper()}) GEO")
        else:
            # Standard mode: one column per prompt per language
            for prompt in PROMPTS:
                for lang in TEST_LANGUAGES:
                    header.append(f"{prompt['label']} ({lang.upper()})")
        writer.writerow(header)

        # Write data rows
        for image in sorted_images:
            row = [image]
            if TEST_GEO_BOOST:
                # Dual-mode: add both standard and GEO results for each language
                for prompt in PROMPTS:
                    for lang in TEST_LANGUAGES:
                        lang_upper = lang.upper()
                        standard_result = all_results.get(prompt['label'], {}).get(image, {})
                        geo_result = all_results.get(f"{prompt['label']} (GEO)", {}).get(image, {})
                        standard_alt = standard_result.get(lang_upper, '') if isinstance(standard_result, dict) else standard_result
                        geo_alt = geo_result.get(lang_upper, '') if isinstance(geo_result, dict) else geo_result
                        row.append(standard_alt)
                        row.append(geo_alt)
            else:
                # Standard mode: one result per prompt per language
                for prompt in PROMPTS:
                    for lang in TEST_LANGUAGES:
                        lang_upper = lang.upper()
                        result = all_results.get(prompt['label'], {}).get(image, {})
                        alt_text = result.get(lang_upper, '') if isinstance(result, dict) else result
                        row.append(alt_text)
            writer.writerow(row)

    print_success(f"CSV file created: {output_path}")
    print_success(f"Total images: {len(sorted_images)}")

def generate_html_report(all_results: Dict[str, Dict[str, Dict[str, str]]], output_path: Path):
    """Generate HTML comparison report with multilingual support.

    Args:
        all_results: Dict[prompt_label, Dict[image_filename, Dict[language, alt_text]]]
        output_path: Path to write the HTML file
    """
    print_header("Generating HTML Report")

    # Get all unique image filenames
    all_images = set()
    for prompt_results in all_results.values():
        all_images.update(prompt_results.keys())

    sorted_images = sorted(all_images)

    # Load and encode logo
    logo_html = ""
    try:
        logo_path = PROJECT_ROOT / "frontend" / "assets" / "MyAccessibilityBuddy-logo.png"
        if logo_path.exists():
            import base64
            with open(logo_path, 'rb') as logo_file:
                logo_base64 = base64.b64encode(logo_file.read()).decode('utf-8')
                logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="My Accessibility Buddy logo" class="logo">'
    except Exception as e:
        print(f"Warning: Could not load logo: {e}")

    # Build HTML with same structure as webmaster report
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Prompt comparison report generated by My Accessibility Buddy - AI-powered image accessibility analysis">
    <meta name="theme-color" content="#0066cc">
    <meta name="msapplication-TileColor" content="#0066cc">
    <title>My Accessibility Buddy - Prompt Comparison Report</title>
    <style>
        /* Visually hidden content for screen readers */
        .visually-hidden {{
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }}

        /* Skip to main content link */
        .skip-link {{
            position: absolute;
            top: -40px;
            left: 0;
            background: #0066cc;
            color: white;
            padding: 8px;
            text-decoration: none;
            z-index: 100;
            font-weight: bold;
        }}
        .skip-link:focus {{
            top: 0;
            outline: 3px solid #ffdd00;
            outline-offset: 2px;
        }}
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
            line-height: 1.5;
        }}
        /* Focus indicators for better keyboard navigation */
        a:focus, button:focus {{
            outline: 3px solid #0066cc;
            outline-offset: 2px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            max-width: 200px;
            height: auto;
            margin-bottom: 20px;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #0066cc;
            margin-top: 30px;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 10px;
        }}
        .summary {{
            background-color: #e8f4f8;
            padding: 15px;
            border-left: 4px solid #0066cc;
            margin-bottom: 30px;
        }}
        .image-preview {{
            max-width: 400px;
            max-height: 200px;
            height: auto;
            display: block;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .image-card {{
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .image-card h3 {{
            color: #0066cc;
            margin-top: 0;
            font-size: 1.3em;
            border-bottom: none;
        }}
        .field {{
            margin-bottom: 15px;
        }}
        .field-label {{
            font-weight: bold;
            color: #595959;
            display: block;
            margin-bottom: 5px;
        }}
        .field-value {{
            color: #333;
            padding: 10px;
            background-color: #f9f9f9;
            border-left: 3px solid #0066cc;
        }}
        .stats-section {{
            margin: 20px 0;
        }}
        .stats-section h3 {{
            color: #0066cc;
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }}
        .stat-item {{
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 5px;
            border-left: 3px solid #0066cc;
        }}
        .stat-label {{
            font-weight: bold;
            color: #595959;
            display: block;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 1.3em;
            color: #333;
        }}
        /* Comparison table styles */
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .comparison-table th {{
            background-color: #0066cc;
            color: white;
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
        }}
        .comparison-table td {{
            padding: 12px;
            border: 1px solid #ddd;
            vertical-align: top;
        }}
        .comparison-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .alt-text-cell {{
            font-style: italic;
            line-height: 1.6;
        }}
        .char-count {{
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }}
        .char-ok {{
            color: #155724;
        }}
        .char-warning {{
            color: #856404;
        }}
        .char-error {{
            color: #721c24;
        }}
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            .image-card {{
                padding: 15px;
            }}
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            .comparison-table {{
                font-size: 0.9em;
            }}
            .comparison-table th, .comparison-table td {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <header class="header">
        {logo_html}
        <h1>My Accessibility Buddy</h1>
        <h2>Prompt Comparison Report</h2>
    </header>
    <main id="main-content">
    <h2>Summary</h2>
    <section class="summary" role="region" aria-label="Summary">
        <div class="stats-section">
            <h3>Test Overview</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <span class="stat-label">Images Analyzed</span>
                    <span class="stat-value">{len(sorted_images)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Prompts Tested</span>
                    <span class="stat-value">{len(PROMPTS)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Languages</span>
                    <span class="stat-value">{len(TEST_LANGUAGES)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Alt-Texts Generated</span>
                    <span class="stat-value">{len(sorted_images) * len(PROMPTS) * len(TEST_LANGUAGES) * (2 if TEST_GEO_BOOST else 1)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Testing Mode</span>
                    <span class="stat-value">{'Dual (Standard + GEO)' if TEST_GEO_BOOST else 'Standard'}</span>
                </div>
            </div>
        </div>

        <p><strong>Languages:</strong> {', '.join(TEST_LANGUAGES)}</p>
        <p><strong>Test Images:</strong> {', '.join(TEST_IMAGES)}</p>
        <p><strong>GEO Boost Testing:</strong> {'Enabled (both modes tested)' if TEST_GEO_BOOST else 'Disabled (standard only)'}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="stats-section">
            <h3>Prompts Tested</h3>
"""

    for prompt in PROMPTS:
        html_content += f"""            <div class="stat-item">
                <span class="stat-label">{prompt['label']}</span>
                <span class="stat-value" style="font-size: 0.9em;">{prompt['file']}</span>
            </div>
"""

    html_content += """        </div>
    </section>

    <h2>Detailed Comparison</h2>
"""

    # Generate comparison for each image
    for image in sorted_images:
        # Try to embed image as base64 for self-contained report
        image_html = ""
        image_file_path = IMAGES_DIR / image
        if image_file_path.exists():
            try:
                import base64
                import mimetypes
                mime_type, _ = mimetypes.guess_type(str(image_file_path))
                if mime_type and mime_type.startswith('image/'):
                    with open(image_file_path, 'rb') as img_file:
                        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        image_html = f'<img src="data:{mime_type};base64,{img_base64}" alt="Test image: {image}" class="image-preview">'
            except Exception as e:
                print(f"Warning: Could not embed image {image}: {e}")
                # Fallback to relative path
                image_html = f'<img src="../../input/images/{image}" alt="Test image: {image}" class="image-preview" onerror="this.style.display=\'none\'">'
        else:
            # Fallback to relative path if file not found
            image_html = f'<img src="../../input/images/{image}" alt="Test image: {image}" class="image-preview" onerror="this.style.display=\'none\'">'

        html_content += f"""
    <article class="image-card" role="article" aria-labelledby="image-{image.replace('.', '-')}">
        <h3 id="image-{image.replace('.', '-')}">{image}</h3>

        <div class="field">
            {image_html}
        </div>

        <table class="comparison-table">
            <thead>
                <tr>
                    <th scope="col">Prompt Version</th>
                    <th scope="col">Prompt File</th>
                    <th scope="col">Language</th>
"""

        if TEST_GEO_BOOST:
            html_content += """                    <th scope="col">Standard Alt-Text</th>
                    <th scope="col">GEO-Optimized Alt-Text</th>
"""
        else:
            html_content += """                    <th scope="col">Generated Alt-Text</th>
"""

        html_content += """                </tr>
            </thead>
            <tbody>
"""

        for prompt in PROMPTS:
            # Get the results for this prompt and image
            prompt_results = all_results.get(prompt['label'], {}).get(image, {})
            geo_results = all_results.get(f"{prompt['label']} (GEO)", {}).get(image, {}) if TEST_GEO_BOOST else {}

            # Ensure we have a dict (handle legacy single-string format)
            if isinstance(prompt_results, str):
                prompt_results = {'EN': prompt_results}
            if isinstance(geo_results, str):
                geo_results = {'EN': geo_results}

            # Get all languages to display (from config or from results)
            languages_to_show = [lang.upper() for lang in TEST_LANGUAGES]
            # Also include any languages found in results that weren't in config
            for lang in prompt_results.keys():
                if lang.upper() not in languages_to_show:
                    languages_to_show.append(lang.upper())

            first_row = True
            for lang in languages_to_show:
                lang_upper = lang.upper()

                if TEST_GEO_BOOST:
                    # Dual-mode: show both standard and GEO results
                    standard_alt = prompt_results.get(lang_upper, '')
                    geo_alt = geo_results.get(lang_upper, '')

                    standard_count = len(standard_alt) if standard_alt else 0
                    geo_count = len(geo_alt) if geo_alt else 0

                    standard_class = "char-ok" if 0 < standard_count <= 125 else ("char-warning" if standard_count > 125 else "char-error")
                    geo_class = "char-ok" if 0 < geo_count <= 125 else ("char-warning" if geo_count > 125 else "char-error")

                    standard_status = "✓" if 0 < standard_count <= 125 else ("⚠" if standard_count > 125 else "✗")
                    geo_status = "✓" if 0 < geo_count <= 125 else ("⚠" if geo_count > 125 else "✗")

                    if first_row:
                        html_content += f"""                <tr>
                    <td rowspan="{len(languages_to_show)}"><strong>{prompt['label']}</strong></td>
                    <td rowspan="{len(languages_to_show)}"><code>{prompt['file']}</code></td>
                    <td><strong>{lang_upper}</strong></td>
                    <td class="alt-text-cell">
                        {standard_alt if standard_alt else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {standard_class}">{standard_status} {standard_count} characters</div>
                    </td>
                    <td class="alt-text-cell">
                        {geo_alt if geo_alt else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {geo_class}">{geo_status} {geo_count} characters</div>
                    </td>
                </tr>
"""
                    else:
                        html_content += f"""                <tr>
                    <td><strong>{lang_upper}</strong></td>
                    <td class="alt-text-cell">
                        {standard_alt if standard_alt else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {standard_class}">{standard_status} {standard_count} characters</div>
                    </td>
                    <td class="alt-text-cell">
                        {geo_alt if geo_alt else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {geo_class}">{geo_status} {geo_count} characters</div>
                    </td>
                </tr>
"""
                else:
                    # Standard mode: show single result per language
                    alt_text = prompt_results.get(lang_upper, '')
                    char_count = len(alt_text) if alt_text else 0
                    char_class = "char-ok" if 0 < char_count <= 125 else ("char-warning" if char_count > 125 else "char-error")
                    char_status = "✓" if 0 < char_count <= 125 else ("⚠" if char_count > 125 else "✗")

                    if first_row:
                        html_content += f"""                <tr>
                    <td rowspan="{len(languages_to_show)}"><strong>{prompt['label']}</strong></td>
                    <td rowspan="{len(languages_to_show)}"><code>{prompt['file']}</code></td>
                    <td><strong>{lang_upper}</strong></td>
                    <td class="alt-text-cell">
                        {alt_text if alt_text else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {char_class}">{char_status} {char_count} characters</div>
                    </td>
                </tr>
"""
                    else:
                        html_content += f"""                <tr>
                    <td><strong>{lang_upper}</strong></td>
                    <td class="alt-text-cell">
                        {alt_text if alt_text else '<em style="color: #999;">No alt-text generated</em>'}
                        <div class="char-count {char_class}">{char_status} {char_count} characters</div>
                    </td>
                </tr>
"""
                first_row = False

        html_content += """            </tbody>
        </table>
    </article>
"""

    html_content += """
    </main>

    <footer style="margin-top: 40px; padding: 20px; border-top: 2px solid #0066cc; width: 100%;">
        <p style="text-align: left; line-height: 1.6;">
            MyAccessibilityBuddy is an AI-powered tool for generating WCAG 2.2 compliant alternative text for web images. It supports 24 EU languages with enterprise LLM (ECB-LLM with GPT-4o and GPT-5.1), commercial LLMs (OpenAI GPT-4o/5.1/5.2 and Claude Sonnet/Opus/Haiku), or local models from Ollama.
        </p>
        <p style="text-align: left; padding: 10px; background-color: #fff3cd; border-left: 4px solid #ffc107; line-height: 1.6;">
            ⚠️ <strong>For testing purposes only:</strong> Use with non confidential images. Avoid uploading personal or sensitive data. AI suggestions require human review before use. ⚠️
        </p>
    </footer>

</body>
</html>
"""

    # Write HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print_success(f"HTML report created: {output_path}")
    print_success(f"Total images: {len(sorted_images)}")

def parse_args():
    parser = argparse.ArgumentParser(description="Batch prompt comparison runner")
    parser.add_argument('--images-folder', help='Folder with test images')
    parser.add_argument('--context-folder', help='Folder with context .txt files')
    parser.add_argument('--language', action='append', help='Language code (can be repeated)')
    parser.add_argument('--prompts', nargs='+', help='Prompt versions or files (e.g., v0 v1 or processing_prompt_v0.txt)')
    parser.add_argument('--geo-boost', action='store_true', help='Enable GEO boost comparison')
    parser.add_argument('--advanced-translation', action='store_true', help='Use advanced translation mode')
    parser.add_argument('--vision-provider', help='Vision provider override')
    parser.add_argument('--vision-model', help='Vision model override')
    parser.add_argument('--processing-provider', help='Processing provider override')
    parser.add_argument('--processing-model', help='Processing model override')
    parser.add_argument('--translation-provider', help='Translation provider override')
    parser.add_argument('--translation-model', help='Translation model override')
    return parser.parse_args()

def main():
    """Main execution function."""
    print_header("MyAccessibilityBuddy - Batch Prompt Comparison")

    args = parse_args()

    # Load test configuration
    if not load_test_config(args):
        sys.exit(1)

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Create output directory for reports
    OUTPUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Clear all previous session results at the start
    print_info("Cleaning up previous test sessions...")
    clear_output_directory()

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    geo_suffix = "_geo_comparison" if TEST_GEO_BOOST else ""
    output_csv = OUTPUT_REPORTS_DIR / f"prompt_comparison_{timestamp}{geo_suffix}.csv"

    # Backup configuration
    backup_path = backup_config()

    # Store all results
    # Structure: all_results[label] = {image_filename: alt_text}
    all_results = {}

    try:
        # Determine which modes to test
        modes_to_test = [(False, ""), (True, " (GEO)")] if TEST_GEO_BOOST else [(False, "")]

        # Process with each prompt
        for i, prompt in enumerate(PROMPTS, 1):
            total_prompts = len(PROMPTS)

            # Test each mode (standard and/or GEO)
            for mode_idx, (use_geo, mode_suffix) in enumerate(modes_to_test, 1):
                mode_label = f"{prompt['label']}{mode_suffix}"
                mode_info = f"GEO-optimized" if use_geo else "standard"

                if TEST_GEO_BOOST:
                    print_header(f"Processing: {prompt['label']} - {mode_info} ({i}/{total_prompts}, mode {mode_idx}/{len(modes_to_test)})")
                else:
                    print_header(f"Processing with: {prompt['label']} ({i}/{total_prompts})")

                # Update configuration
                update_config_prompt(prompt['file'])

                # Clear previous output before processing
                print_info(f"Clearing previous results before processing {mode_label}...")
                clear_output_directory()

                # Run batch processing with appropriate GEO flag
                session_id = run_batch_processing(use_geo=use_geo)
                if not session_id:
                    print_error(f"Failed to process {mode_label}")
                    continue

                # Extract results from the session-specific folder
                print_info("Extracting results...")
                results = extract_results(session_id=session_id)
                all_results[mode_label] = results
                print_success(f"Extracted {len(results)} results for {mode_label}")

                # Clean up this session's results after extraction to prevent accumulation
                print_info(f"Cleaning up session {session_id} after extraction...")
                clear_output_directory(session_id=session_id)

        # Generate CSV report
        generate_csv(all_results, output_csv)

        # Generate HTML report
        output_html = OUTPUT_REPORTS_DIR / f"prompt_comparison_{timestamp}{geo_suffix}.html"
        generate_html_report(all_results, output_html)

        # Summary
        print_header("Processing Complete!")
        print_success(f"CSV results saved to: {output_csv}")
        print_success(f"HTML report saved to: {output_html}")

        # Show statistics
        total_images = len(set().union(*[set(r.keys()) for r in all_results.values()]))
        print(f"\n{Colors.BLUE}Statistics:{Colors.NC}")
        print(f"  Total images processed: {total_images}")

        if TEST_GEO_BOOST:
            # Dual-mode statistics
            print(f"  Testing mode: Dual-mode (Standard + GEO)")
            for prompt in PROMPTS:
                standard_count = len(all_results.get(prompt['label'], {}))
                geo_count = len(all_results.get(f"{prompt['label']} (GEO)", {}))
                print(f"  {prompt['label']}:")
                print(f"    - Standard: {standard_count} alt-texts")
                print(f"    - GEO: {geo_count} alt-texts")
        else:
            # Standard mode statistics
            print(f"  Testing mode: Standard mode")
            for prompt in PROMPTS:
                count = len(all_results.get(prompt['label'], {}))
                print(f"  {prompt['label']}: {count} alt-texts generated")

        print(f"\n{Colors.YELLOW}Open the CSV or HTML report to compare alt-text generated by different prompts{Colors.NC}\n")

    except KeyboardInterrupt:
        print_error("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Restore configuration
        restore_config(backup_path)

if __name__ == "__main__":
    main()
