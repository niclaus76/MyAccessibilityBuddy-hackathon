# MyAccessibilityBuddy - Quick Start

**Version:** 1.0.0
**Last Updated:** December 2025
**Copyright:** 2025 by Nicola.Caione@bancaditalia.it

## Overview

MyAccessibilityBuddy generates WCAG 2.2 compliant alternative text for web images using AI. Supports 24 EU languages with OpenAI GPT-4o or ECB-LLM GPT-40 or GPT-5.1.

⚠️ **For testing only**: Use with non-confidential images. AI suggestions require human review. ⚠️

## Installation

```bash
# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Setup

Create `.env` file in `backend/` directory:

```bash
# For OpenAI (recommended for testing)
OPENAI_API_KEY=sk-your-api-key-here

# OR for ECB-LLM (requires ECB OAuth2 credentials)
CLIENT_ID_U2A=your-client-id
CLIENT_SECRET_U2A=your-client-secret
```

Configure `backend/config/config.json`:

```json
{
  "llm_provider": "OpenAI",
  "model": "gpt-4o",
  "translation_mode": "fast"
}
```

## Quick Test Examples

### Example 1: Single Image (CLI)

```bash
cd backend
source venv/bin/activate

# Copy test files
cp ../test/images/1.png ../input/images/
cp ../test/context/1.txt ../input/context/

# Generate alt-text in English
python3 app.py -g 1.png --language en

# View result
cat ../output/alt-text/1.json
```

**Output**: JSON file with generated alt-text in `output/alt-text/1.json`

### Example 2: Multiple Languages

```bash
cd backend

# Use test image 3
cp ../test/images/3.png ../input/images/
cp ../test/context/3.txt ../input/context/

# Generate in 3 languages
python3 app.py -g 3.png --language en it de

# View multilingual result
cat ../output/alt-text/3.json
```

**Output**: Alt-text in English, Italian, and German

### Example 3: Batch Processing with Report

```bash
cd backend

# Copy all test files
cp ../test/images/*.png ../input/images/
cp ../test/context/*.txt ../input/context/

# Process all images and generate HTML report
python3 app.py -p --language en --report

# View report
xdg-open ../output/reports/MyAccessibilityBuddy-AltTextReport.html
```

**Outputs**:
- `output/alt-text/*.json` - Individual JSON files for each image
- `output/reports/*.html` - Accessible HTML summary report

### Example 4: Download from Web (Complete Workflow)

```bash
cd backend

# Download images, extract context, generate alt-text
python3 app.py -w https://www.ecb.europa.eu/home/html/index.en.html --language en --num-images 3 --report
```

**Outputs**:
- `input/images/*.{jpg,png,svg}` - Downloaded images
- `input/context/*.txt` - Extracted context from webpage
- `output/alt-text/*.json` - Generated alt-text
- `output/reports/*.html` - HTML report

### Example 5: Compare Translation Modes

**Fast Mode** (generate once, then translate):
```bash
cd backend
cp ../test/images/5.png ../input/images/
cp ../test/context/5.txt ../input/context/

# Edit config.json: "translation_mode": "fast"
python3 app.py -g 5.png --language en fr es

# Check processing time in output JSON
cat ../output/alt-text/5.json | grep processing_time
```

**Accurate Mode** (generate fresh for each language):
```bash
# Edit config.json: "translation_mode": "accurate"
python3 app.py -g 5.png --language en fr es

# Compare processing time (will be longer)
cat ../output/alt-text/5.json | grep processing_time
```

### Example 6: Web UI

```bash
# Start all servers (opens browser automatically to http://localhost:8080)
./start_MyAccessibilityBuddy.sh

# The browser will open to http://localhost:8080/home.html
# Important: Access via HTTP, not file:// (to avoid CORS errors)

# Upload test/images/2.png in browser
# Upload test/context/2.txt (optional)
# Select language: English
# Click "Generate Alt Text"
# Copy result
```

## Common Commands

```bash
# List supported languages
python3 app.py -al

# Clear all folders
python3 app.py --clear-all

# Get help
python3 app.py --help
python3 app.py --help-topic workflow

# Check server status
lsof -ti:8080,8000

# Stop servers
lsof -ti:8080,8000 | xargs kill
```

## Test Data Reference

Available test files in `test/` directory:

**Images** (`test/images/`):
- `1.png` to `13.png` - 13 test images from ECB website

**Context** (`test/context/`):
- `1.txt` to `7.txt` - Extracted context for images 1-7
- Images 8-13 have no context files (test without context)

**Usage**:
```bash
# With context
cp test/images/1.png test/context/1.txt input/

# Without context
cp test/images/10.png input/images/
```

## Configuration Quick Reference

Edit `backend/config/config.json`:

```json
{
  "llm_provider": "OpenAI",           // or "ECB-LLM"
  "model": "gpt-4o",                  // or "gpt-5.1" for ECB-LLM
  "translation_mode": "fast",         // or "accurate"
  "download": {
    "delay_between_requests": 3       // seconds (avoid rate limiting)
  }
}
```

**Translation Modes**:
- `"fast"` - Generate once, translate (faster, cheaper)
- `"accurate"` - Generate for each language (better quality)

## Features

- 🖼️ **Formats**: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- 🌍 **24 EU Languages**: bg, cs, da, de, el, en, es, et, fi, fr, ga, hr, hu, it, lt, lv, mt, nl, pl, pt, ro, sk, sl, sv
- 🔐 **Authentication**: U2A OAuth2 for ECB-LLM, API key for OpenAI
- 📊 **Batch Processing**: Process multiple images at once
- 📈 **HTML Reports**: Accessible summaries with all details
- 🚀 **REST API**: FastAPI with auto-docs at `/api/docs`

## Troubleshooting

### No images found
```bash
ls -la input/images/
cp test/images/*.png input/images/
```

### Authentication error
```bash
# Check .env file exists
ls -la backend/.env

# For OpenAI: verify API key
echo $OPENAI_API_KEY

# For ECB-LLM: verify credentials
env | grep -E "CLIENT_ID|ECB_USERNAME"
```

### Rate limiting (429 error)
```bash
# Increase delay in config.json
"delay_between_requests": 5
```

## Documentation

- **[docs/MyAccessibilityBuddy.md](docs/MyAccessibilityBuddy.md)** - Complete detailed documentation
- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Developer guide for contributors

## Support

1. Check logs: `tail -f logs/*.log`
2. Verify config: `cat backend/config/config.json`
3. Test auth: `curl http://localhost:8000/api/auth/status`

## License

Copyright 2025 by European Central Bank. All rights reserved.