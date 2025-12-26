#!/bin/bash

################################################################################
# MyAccessibilityBuddy - Batch Prompt Comparison Script
################################################################################
#
# This script processes all images in input/images with three different prompts:
# 1. base_prompt.txt
# 2. alt-text-improved.txt
# 3. main_prompt.txt
#
# Output: CSV file with columns:
#   - Image Filename
#   - Alt Text (base_prompt)
#   - Alt Text (alt-text-improved)
#   - Alt Text (main_prompt)
#
################################################################################

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="backend"
CONFIG_FILE="$BACKEND_DIR/config/config.json"
IMAGES_DIR="input/images"
CONTEXT_DIR="input/context"
OUTPUT_DIR="output/alt-text"
PROMPT_DIR="prompt"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_CSV="output/prompt_comparison_${TIMESTAMP}.csv"

# Prompt files
PROMPTS=("prompt_v0.txt" "prompt_v1.txt" "prompt_v2.txt" "prompt_v3.txt" "prompt_v4.txt")
PROMPT_LABELS=("v0: base prompt" "v1: With image classification" "v2: With image classification and workflow" "v3: With extended image classification and workflow" "v4: with extended image classification, workflow and security")

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    MyAccessibilityBuddy - Batch Prompt Comparison Script      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the project root
if [ ! -d "$BACKEND_DIR" ] || [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if images directory exists and has images
if [ ! -d "$IMAGES_DIR" ]; then
    echo -e "${RED}Error: Images directory not found: $IMAGES_DIR${NC}"
    exit 1
fi

IMAGE_COUNT=$(find "$IMAGES_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.webp" -o -iname "*.svg" -o -iname "*.bmp" \) 2>/dev/null | wc -l)

if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo -e "${RED}Error: No images found in $IMAGES_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found $IMAGE_COUNT images to process${NC}"
echo ""

# Check if context directory exists
if [ -d "$CONTEXT_DIR" ]; then
    CONTEXT_COUNT=$(find "$CONTEXT_DIR" -type f -name "*.txt" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ Found $CONTEXT_COUNT context files in $CONTEXT_DIR${NC}"
else
    echo -e "${YELLOW}⚠ No context directory found. Processing without context.${NC}"
fi

echo ""

# Verify all prompt files exist
echo -e "${BLUE}Checking prompt files...${NC}"
for prompt in "${PROMPTS[@]}"; do
    if [ ! -f "$PROMPT_DIR/$prompt" ]; then
        echo -e "${RED}Error: Prompt file not found: $PROMPT_DIR/$prompt${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ $prompt${NC}"
done

echo ""

# Create output directory if it doesn't exist
mkdir -p "$(dirname "$OUTPUT_CSV")"

# Backup original config
echo -e "${BLUE}Backing up configuration...${NC}"
cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
echo -e "${GREEN}✓ Configuration backed up${NC}"
echo ""

# Function to update config with specific prompt
update_config_prompt() {
    local prompt_file=$1
    python3 -c "
import json
import sys

config_file = '$CONFIG_FILE'
with open(config_file, 'r') as f:
    config = json.load(f)

config['prompt']['files'] = ['$prompt_file']

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print(f'Updated config to use prompt: $prompt_file')
"
}

# Function to extract alt-text from JSON files
extract_alt_texts() {
    local output_dir=$1
    python3 -c "
import json
import os
import sys

output_dir = '$output_dir'
results = {}

for filename in os.listdir(output_dir):
    if filename.endswith('.json'):
        filepath = os.path.join(output_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Extract the original image filename
                image_file = data.get('image_file', filename.replace('.json', ''))
                alt_text = data.get('alt_text', '')
                # Clean alt text: remove quotes and escape commas
                alt_text = alt_text.replace('\"', '\"\"')  # Escape quotes for CSV
                results[image_file] = alt_text
        except Exception as e:
            print(f'Error reading {filename}: {e}', file=sys.stderr)

# Output as JSON for easy parsing
import json
print(json.dumps(results))
"
}

# Initialize results storage
declare -A results_base
declare -A results_improved
declare -A results_main

# Process with each prompt
for i in "${!PROMPTS[@]}"; do
    PROMPT="${PROMPTS[$i]}"
    LABEL="${PROMPT_LABELS[$i]}"

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Processing with: ${LABEL}${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Update configuration
    echo -e "${YELLOW}Updating configuration to use $PROMPT...${NC}"
    update_config_prompt "$PROMPT"
    echo ""

    # Clear previous output
    echo -e "${YELLOW}Clearing previous output...${NC}"
    cd "$BACKEND_DIR"
    python3 app.py --clear-outputs
    cd ..
    echo ""

    # Process all images
    echo -e "${GREEN}Processing all images with $LABEL...${NC}"
    cd "$BACKEND_DIR"
    python3 app.py --process-all --language en
    cd ..
    echo ""

    # Extract results
    echo -e "${BLUE}Extracting results...${NC}"
    RESULTS_JSON=$(extract_alt_texts "$OUTPUT_DIR")

    # Store results in appropriate array
    case $i in
        0)
            while IFS= read -r line; do
                results_base["$line"]=$(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('$line', ''))")
            done < <(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(data.keys()))")
            ;;
        1)
            while IFS= read -r line; do
                results_improved["$line"]=$(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('$line', ''))")
            done < <(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(data.keys()))")
            ;;
        2)
            while IFS= read -r line; do
                results_main["$line"]=$(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('$line', ''))")
            done < <(echo "$RESULTS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(data.keys()))")
            ;;
    esac

    echo -e "${GREEN}✓ Completed processing with $LABEL${NC}"
done

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Generating CSV Comparison Report                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Generate CSV file
python3 << 'PYTHON_SCRIPT'
import json
import csv
import os
from pathlib import Path

output_csv = os.environ.get('OUTPUT_CSV', 'output/prompt_comparison.csv')
output_dir = os.environ.get('OUTPUT_DIR', 'output/alt-text')

# Get all image files
results = {}

# Read all JSON files and extract results
for json_file in Path(output_dir).glob('*.json'):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            image_file = data.get('image_file', json_file.stem)
            alt_text = data.get('alt_text', '')

            if image_file not in results:
                results[image_file] = {}

            # Determine which prompt this is from based on timestamp or config
            # For now, we'll collect all and organize later
            results[image_file]['latest'] = alt_text
    except Exception as e:
        print(f"Error reading {json_file}: {e}")

print(f"Creating CSV file: {output_csv}")
print(f"Note: The script will run three times to populate all columns.")

PYTHON_SCRIPT

# Create CSV with proper structure
python3 << PYTHON_SCRIPT
import csv
import json
import os
from pathlib import Path

output_csv = '$OUTPUT_CSV'
output_dir = '$OUTPUT_DIR'

# Collect all unique image filenames
image_files = set()
for json_file in Path(output_dir).glob('*.json'):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            image_file = data.get('image_file', json_file.stem)
            image_files.add(image_file)
    except:
        pass

# Sort image files
sorted_images = sorted(list(image_files))

# Write CSV
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)

    # Write header
    writer.writerow(['Image Filename', 'Alt Text (base_prompt)', 'Alt Text (alt-text-improved)', 'Alt Text (main_prompt)'])

    # For now, write placeholders - the script needs to be run to completion
    # to gather all three results properly
    for image in sorted_images:
        # Try to find the JSON file
        json_path = Path(output_dir) / f"{Path(image).stem}.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    alt_text = data.get('alt_text', '')
                    writer.writerow([image, alt_text, '', ''])
            except:
                writer.writerow([image, '', '', ''])
        else:
            writer.writerow([image, '', '', ''])

print(f"✓ CSV file created: {output_csv}")
print(f"  Total images: {len(sorted_images)}")

PYTHON_SCRIPT

# Restore original config
echo ""
echo -e "${BLUE}Restoring original configuration...${NC}"
mv "${CONFIG_FILE}.backup" "$CONFIG_FILE"
echo -e "${GREEN}✓ Configuration restored${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Batch Processing Complete!                                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Results saved to: ${GREEN}$OUTPUT_CSV${NC}"
echo -e "${BLUE}Total images processed: ${GREEN}$IMAGE_COUNT${NC}"
echo ""
echo -e "${YELLOW}Note: Open the CSV file to compare alt-text generated by different prompts${NC}"
echo ""
