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
BACKEND_DIR = Path("backend")
CONFIG_FILE = BACKEND_DIR / "config" / "config.json"
CONFIG_ADVANCED_FILE = BACKEND_DIR / "config" / "config.advanced.json"
PROMPT_DIR = Path("prompt/processing")

# These will be loaded from config.json
PROMPTS = []
TEST_IMAGES = []
TEST_LANGUAGE = "en"
TEST_GEO_BOOST = False  # If true, test BOTH GEO and non-GEO modes

# Paths that will be set from config.advanced.json
IMAGES_DIR = None
CONTEXT_DIR = None
OUTPUT_DIR = None
OUTPUT_REPORTS_DIR = None

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

def load_test_config():
    """Load test configuration from config.json and config.advanced.json."""
    global PROMPTS, TEST_IMAGES, TEST_LANGUAGE, TEST_GEO_BOOST
    global IMAGES_DIR, CONTEXT_DIR, OUTPUT_DIR, OUTPUT_REPORTS_DIR

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
        TEST_LANGUAGE = batch_comparison.get('language', 'en')
        TEST_GEO_BOOST = batch_comparison.get('test_geo_boost', False)

        # Load advanced config for folder paths
        if CONFIG_ADVANCED_FILE.exists():
            with open(CONFIG_ADVANCED_FILE, 'r', encoding='utf-8') as f:
                advanced_config = json.load(f)
            test_folders = advanced_config.get('testing', {}).get('folders', {})
        else:
            test_folders = {}

        # Set folder paths from configuration
        IMAGES_DIR = Path(test_folders.get('test_images', 'test/input/images'))
        CONTEXT_DIR = Path(test_folders.get('test_context', 'test/input/context'))
        OUTPUT_REPORTS_DIR = Path(test_folders.get('test_reports', 'test/output/reports'))
        OUTPUT_DIR = Path("output/alt-text")  # Keep original output for intermediate results

        print_success("Loaded batch comparison configuration from config.json")
        print_info(f"Test mode: {'GEO Boost Comparison (both modes)' if TEST_GEO_BOOST else 'Standard WCAG only'}")
        print_info(f"Language: {TEST_LANGUAGE}")
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

def clear_output_directory():
    """Clear the output directory."""
    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.glob("*.json"):
            file.unlink()
        print_success("Cleared output directory")

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
            "--images-folder", f"../{IMAGES_DIR}",
            "--context-folder", f"../{CONTEXT_DIR}",
            "--language", TEST_LANGUAGE
        ]

        # Add --geo flag if requested
        if use_geo:
            cmd.append("--geo")
            print_info("GEO boost enabled - adding --geo flag")

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

def extract_results(session_id=None) -> Dict[str, str]:
    """Extract alt-text results from JSON files.

    Args:
        session_id (str, optional): CLI session ID to extract results from.
                                   If provided, looks in output/alt-text/{session_id}/
                                   If None, looks directly in output/alt-text/

    Returns:
        Dict[str, str]: Mapping of image filename to alt-text
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
                alt_text = data.get('proposed_alt_text', data.get('alt_text', ''))
                results[image_file] = alt_text
        except Exception as e:
            print_warning(f"Error reading {json_file.name}: {e}")

    return results

def generate_csv(all_results: Dict[str, Dict[str, str]], output_path: Path):
    """Generate CSV comparison file."""
    print_header("Generating CSV Report")

    # Get all unique image filenames
    all_images = set()
    for prompt_results in all_results.values():
        all_images.update(prompt_results.keys())

    sorted_images = sorted(all_images)

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)

        # Write header - handle dual-mode testing
        header = ['Image Filename']
        if TEST_GEO_BOOST:
            # Dual-mode: create columns for both standard and GEO for each prompt
            for prompt in PROMPTS:
                header.append(f"{prompt['label']} (Standard)")
                header.append(f"{prompt['label']} (GEO)")
        else:
            # Standard mode: one column per prompt
            for prompt in PROMPTS:
                header.append(f"Alt Text ({prompt['label']})")
        writer.writerow(header)

        # Write data rows
        for image in sorted_images:
            row = [image]
            if TEST_GEO_BOOST:
                # Dual-mode: add both standard and GEO results
                for prompt in PROMPTS:
                    standard_alt = all_results.get(prompt['label'], {}).get(image, '')
                    geo_alt = all_results.get(f"{prompt['label']} (GEO)", {}).get(image, '')
                    row.append(standard_alt)
                    row.append(geo_alt)
            else:
                # Standard mode: single result per prompt
                for prompt in PROMPTS:
                    alt_text = all_results.get(prompt['label'], {}).get(image, '')
                    row.append(alt_text)
            writer.writerow(row)

    print_success(f"CSV file created: {output_path}")
    print_success(f"Total images: {len(sorted_images)}")

def generate_html_report(all_results: Dict[str, Dict[str, str]], output_path: Path):
    """Generate HTML comparison report using report_template style."""
    print_header("Generating HTML Report")

    # Get all unique image filenames
    all_images = set()
    for prompt_results in all_results.values():
        all_images.update(prompt_results.keys())

    sorted_images = sorted(all_images)

    # Read the template
    template_path = Path("output/reports/report_template.html")
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template_html = f.read()
        # Extract just the CSS from template
        css_start = template_html.find('<style>')
        css_end = template_html.find('</style>') + 8
        css_content = template_html[css_start:css_end] if css_start != -1 else ""
    else:
        css_content = "<style>body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }</style>"

    # Build HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt Comparison Report - MyAccessibilityBuddy</title>
    {css_content}
    <style>
        .prompt-comparison {{
            margin-bottom: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #f9f9f9;
        }}
        .prompt-header {{
            font-weight: bold;
            color: #0066cc;
            margin-bottom: 10px;
            padding: 10px;
            background-color: #e8f4f8;
            border-left: 4px solid #0066cc;
        }}
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
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <header class="header">
        <h1>Prompt Comparison Report</h1>
        <p>MyAccessibilityBuddy - Batch Prompt Analysis</p>
    </header>

    <main id="main-content">
        <section class="summary" role="region" aria-label="Summary">
            <h2>Summary</h2>
            <p><strong>Total Images Analyzed:</strong> {len(sorted_images)}</p>
            <p><strong>Prompts Tested:</strong> {len(PROMPTS)}</p>
            <p><strong>Testing Mode:</strong> {'Dual-mode (Standard + GEO) ✓' if TEST_GEO_BOOST else 'Standard mode'}</p>
            <p><strong>Total Alt-Texts Generated:</strong> {len(sorted_images) * len(PROMPTS) * (2 if TEST_GEO_BOOST else 1)}</p>
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <h3>Configuration:</h3>
            <ul>
                <li><strong>Language:</strong> {TEST_LANGUAGE}</li>
                <li><strong>Test Images:</strong> {', '.join(TEST_IMAGES)}</li>
                <li><strong>GEO Boost Testing:</strong> {'Enabled (both modes tested) ✓' if TEST_GEO_BOOST else 'Disabled (standard only)'}</li>
            </ul>

            <h3>Prompts Tested:</h3>
            <ul>
"""

    for prompt in PROMPTS:
        html_content += f"                <li><strong>{prompt['label']}</strong> - {prompt['file']}</li>\n"

    html_content += """            </ul>
        </section>

        <h2>Detailed Comparison</h2>
"""

    # Generate comparison for each image
    for image in sorted_images:
        # Construct image path for display
        image_path = f"../input/images/{image}"

        html_content += f"""
        <article class="image-card" role="article" aria-labelledby="image-{image.replace('.', '-')}">
            <h3 id="image-{image.replace('.', '-')}">{image}</h3>

            <div class="field">
                <img src="{image_path}" alt="{image}" class="image-preview" onerror="this.style.display='none'">
            </div>

            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Prompt Version</th>
                        <th>Prompt File</th>
"""

        if TEST_GEO_BOOST:
            html_content += """                        <th>Standard Alt-Text</th>
                        <th>GEO-Optimized Alt-Text</th>
"""
        else:
            html_content += """                        <th>Generated Alt-Text</th>
"""

        html_content += """                    </tr>
                </thead>
                <tbody>
"""

        for prompt in PROMPTS:
            if TEST_GEO_BOOST:
                # Dual-mode: show both standard and GEO results
                standard_alt = all_results.get(prompt['label'], {}).get(image, '')
                geo_alt = all_results.get(f"{prompt['label']} (GEO)", {}).get(image, '')

                standard_count = len(standard_alt) if standard_alt else 0
                geo_count = len(geo_alt) if geo_alt else 0

                standard_status = "✓" if 0 < standard_count <= 125 else ("⚠" if standard_count > 125 else "✗")
                geo_status = "✓" if 0 < geo_count <= 125 else ("⚠" if geo_count > 125 else "✗")

                html_content += f"""
                    <tr>
                        <td><strong>{prompt['label']}</strong></td>
                        <td><code>{prompt['file']}</code></td>
                        <td class="alt-text-cell">
                            {standard_alt if standard_alt else '<em style="color: #999;">No alt-text generated</em>'}
                            <div class="char-count">{standard_status} {standard_count} characters</div>
                        </td>
                        <td class="alt-text-cell">
                            {geo_alt if geo_alt else '<em style="color: #999;">No alt-text generated</em>'}
                            <div class="char-count">{geo_status} {geo_count} characters</div>
                        </td>
                    </tr>
"""
            else:
                # Standard mode: show single result
                alt_text = all_results.get(prompt['label'], {}).get(image, '')
                char_count = len(alt_text) if alt_text else 0
                char_status = "✓" if 0 < char_count <= 125 else ("⚠" if char_count > 125 else "✗")

                html_content += f"""
                    <tr>
                        <td><strong>{prompt['label']}</strong></td>
                        <td><code>{prompt['file']}</code></td>
                        <td class="alt-text-cell">
                            {alt_text if alt_text else '<em style="color: #999;">No alt-text generated</em>'}
                            <div class="char-count">{char_status} {char_count} characters</div>
                        </td>
                    </tr>
"""

        html_content += """
                </tbody>
            </table>
        </article>
"""

    html_content += """
    </main>
</body>
</html>
"""

    # Write HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print_success(f"HTML report created: {output_path}")
    print_success(f"Total images: {len(sorted_images)}")

def main():
    """Main execution function."""
    print_header("MyAccessibilityBuddy - Batch Prompt Comparison")

    # Load test configuration
    if not load_test_config():
        sys.exit(1)

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Create output directory for reports
    OUTPUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

                # Clear previous output
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
