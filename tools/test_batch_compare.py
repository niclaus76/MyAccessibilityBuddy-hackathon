#!/usr/bin/env python3
"""
Quick test of batch comparison with just 2 prompts
"""
import json
import csv
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from the main script
from tools.batch_compare_prompts import (
    Colors, BACKEND_DIR, CONFIG_FILE, IMAGES_DIR, OUTPUT_DIR, PROMPT_DIR,
    print_header, print_success, print_error, print_info, print_warning,
    check_environment, backup_config, restore_config, update_config_prompt,
    clear_output_directory, run_batch_processing, extract_results, generate_csv
)

# Test with only 2 prompts
TEST_PROMPTS = [
    {"file": "processing_prompt_v0.txt", "label": "v0: base prompt"},
    {"file": "processing_prompt_v2.txt", "label": "v2: With image classification and workflow"}
]

def main():
    print_header("Quick Test - Batch Prompt Comparison (2 prompts only)")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Create output directory
    output_csv_dir = Path("output")
    output_csv_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = output_csv_dir / f"prompt_comparison_test_{timestamp}.csv"
    
    # Backup configuration
    backup_path = backup_config()
    
    # Store all results
    all_results = {}
    
    try:
        # Process with each test prompt
        for i, prompt in enumerate(TEST_PROMPTS, 1):
            print_header(f"Processing with: {prompt['label']} ({i}/{len(TEST_PROMPTS)})")
            
            # Update configuration
            update_config_prompt(prompt['file'])
            
            # Clear previous output
            clear_output_directory()
            
            # Run batch processing
            if not run_batch_processing():
                print_error(f"Failed to process with {prompt['label']}")
                continue
            
            # Extract results
            print_info("Extracting results...")
            results = extract_results()
            all_results[prompt['label']] = results
            print_success(f"Extracted {len(results)} results for {prompt['label']}")
        
        # Generate CSV report
        print_header("Generating CSV Report")
        
        # Get all unique image filenames
        all_images = set()
        for prompt_results in all_results.values():
            all_images.update(prompt_results.keys())
        
        sorted_images = sorted(all_images)
        
        # Write CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            
            # Write header
            header = ['Image Filename']
            for prompt in TEST_PROMPTS:
                header.append(f"Alt Text ({prompt['label']})")
            writer.writerow(header)
            
            # Write data rows
            for image in sorted_images:
                row = [image]
                for prompt in TEST_PROMPTS:
                    alt_text = all_results.get(prompt['label'], {}).get(image, '')
                    row.append(alt_text)
                writer.writerow(row)
        
        print_success(f"CSV file created: {output_csv}")
        print_success(f"Total images: {len(sorted_images)}")
        
        # Summary
        print_header("Test Complete!")
        print_success(f"Results saved to: {output_csv}")
        
        total_images = len(all_images)
        print(f"\n{Colors.BLUE}Statistics:{Colors.NC}")
        print(f"  Total images processed: {total_images}")
        for prompt in TEST_PROMPTS:
            count = len(all_results.get(prompt['label'], {}))
            print(f"  {prompt['label']}: {count} alt-texts generated")
        
        print(f"\n{Colors.YELLOW}Open the CSV file to compare results{Colors.NC}\n")
        
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
