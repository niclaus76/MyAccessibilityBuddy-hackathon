# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MyAccessibilityBuddy** is a Python tool for generating WCAG 2.2 compliant alternative text for web images. It supports multiple interfaces (CLI, Web UI, REST API), works with OpenAI GPT-4o or ECB-LLM GPT-4o/5.1 providers, and handles 24 EU languages.

### Key Capabilities
- Multi-format image support: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- 24 EU languages with two translation modes (fast/accurate)
- Web scraping with context extraction
- OAuth2 U2A authentication for ECB-LLM
- Batch processing and HTML report generation
- FastAPI REST API with auto-generated docs

## Architecture

### Project Structure
```
AutoAltText/
├── backend/
│   ├── app.py                  # 3,476 lines - CLI application entry point
│   ├── api.py                  # 596 lines - FastAPI web server
│   ├── config/
│   │   ├── config.json         # Main configuration file
│   │   └── settings.py         # Configuration loader module
│   ├── services/               # Reserved for future modularization
│   └── requirements.txt        # Python dependencies
├── frontend/
│   └── home.html               # Bootstrap Italia single-page web UI
├── input/
│   ├── images/                 # Place images here for processing
│   └── context/                # Optional context files (image_name.txt)
├── output/
│   ├── alt-text/               # Generated JSON files
│   └── reports/                # HTML accessibility reports
├── prompt/                     # LLM prompt templates
├── logs/                       # Debug logs (when debug_mode: true)
├── test/                       # Test images and context files
├── tools/
│   └── batch_compare_prompts.py   # Batch prompt comparison tool
├── batch_compare_prompts.sh       # Shell wrapper for prompt comparison
└── start_MyAccessibilityBuddy.sh  # Start servers (ports 8080, 8000)
```

### Core Application Flow

**app.py** is the monolithic CLI application containing all core logic:

1. **Image Download** (`download_images_from_url` at line 1300)
   - Scrapes images from web pages via BeautifulSoup
   - Supports img, picture, div backgrounds, link, meta tags
   - Configurable via `config.json` → `image_extraction` section
   - Returns: (image_filenames, metadata_dict, page_title)

2. **Context Extraction** (`grab_context`)
   - Extracts surrounding text from webpage where image appears
   - Traverses DOM tree for headings, captions, paragraphs
   - Configurable depth via `context.max_parent_levels`
   - Rate limiting via `download.delay_between_requests`

3. **Image Processing** (`local_image_to_data_url`)
   - Converts images to base64 data URLs for LLM API
   - Auto-detects MIME types
   - SVG → PNG conversion via CairoSVG (optional dependency)

4. **LLM Analysis** (`analyze_image_with_openai` at line 1095)
   - Supports OpenAI (via openai package) or ECB-LLM (via ecb_llm_client)
   - System message sets target language for alt_text field
   - Uses vision API with image data URL + text prompt
   - Returns structured JSON: {image_type, image_description, reasoning, alt_text}

5. **Alt-Text Generation** (`generate_alt_text_json` at line 2013)
   - Orchestrates entire generation workflow
   - Handles multilingual output with translation modes:
     - **"fast"** (default): Generate once in first language, then translate
     - **"accurate"**: Generate fresh alt-text for each language
   - Saves structured JSON with metadata to `output/alt-text/`

6. **HTML Reports** (`generate_html_report`)
   - Creates accessible HTML summaries
   - Includes image previews, metadata, source URLs
   - ARIA-compliant markup

**api.py** is the FastAPI server providing REST endpoints and OAuth2 flows.

## Common Commands

### Development Setup
```bash
# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure .env file (in backend/ directory)
# For OpenAI:
OPENAI_API_KEY=sk-your-api-key-here

# For ECB-LLM:
CLIENT_ID_U2A=your-client-id
CLIENT_SECRET_U2A=your-client-secret
```

### Running the Application

**Web UI Mode:**
```bash
# Start servers (8080 for frontend, 8000 for API)
./start_MyAccessibilityBuddy.sh

# Opens browser automatically to http://localhost:8080/home.html
# Frontend: http://localhost:8080/home.html
# API docs: http://localhost:8000/api/docs

# Important: Access via http://localhost:8080, NOT file:// (CORS issue)
# Note: Port 3001 is used automatically by ecb_llm_client for OAuth when needed

# Stop servers
lsof -ti:8080,8000 | xargs kill
```

**CLI Mode:**
```bash
cd backend
source venv/bin/activate

# Single image generation
python3 app.py -g image.png --language en

# Multiple languages
python3 app.py -g image.png --language en it de

# Complete workflow: download → extract context → generate
python3 app.py -w https://example.com/page.html --language en --report

# Batch process all images in input/images/
python3 app.py -p --language en --report

# List all supported languages
python3 app.py -al

# Clear output folders
python3 app.py --clear-all

# Get detailed help
python3 app.py --help
python3 app.py --help-topic workflow
```

### Testing with Test Data
```bash
cd backend
source venv/bin/activate

# Copy test files (13 images, 7 with context)
cp ../test/images/1.png ../input/images/
cp ../test/context/1.txt ../input/context/

# Generate alt-text
python3 app.py -g 1.png --language en

# View output
cat ../output/alt-text/1.json
```

### Batch Prompt Comparison
```bash
# Compare multiple prompts on all test images
./batch_compare_prompts.sh

# Or directly:
cd backend
source venv/bin/activate
cd ..
python3 tools/batch_compare_prompts.py

# Output: output/prompt_comparison_TIMESTAMP.csv
```

## Configuration (backend/config/config.json)

### LLM Provider Settings
```json
{
  "llm_provider": "OpenAI",    // or "ECB-LLM"
  "model": "gpt-4o",           // or "gpt-5.1" for ECB-LLM
  "translation_mode": "accurate"  // "fast" or "accurate"
}
```

**Translation Modes:**
- **"fast"**: Generate once in first language, then translate others (faster, cheaper)
- **"accurate"**: Generate fresh alt-text for each language (better quality, slower)

Note: Legacy config used `full_translation_mode: boolean`. Code at line 2161 handles backward compatibility.

### Folder Paths
All paths are relative to project root. Accessed via `config.settings.get_folder_path(name)`:
```json
{
  "folders": {
    "images": "input/images",
    "context": "input/context",
    "alt_text": "output/alt-text",
    "reports": "output/reports",
    "prompt": "prompt",
    "logs": "logs"
  }
}
```

### Prompt Templates
```json
{
  "prompt": {
    "files": ["prompt_v0.txt"],  // List of prompts to merge
    "merge_separator": "\n\n---\n\n",
    "default_prompt": "prompt_v0.txt"   // Fallback
  }
}
```

Available prompts in `prompt/`:
- `prompt_v0.txt` - Minimal baseline with JSON output
- `prompt_v1.txt` - Basic classification (decorative/informative/functional)
- `prompt_v2.txt` - WCAG 2.2 focused with decision tree (recommended)
- `prompt_v3.txt` - Comprehensive with phased execution and optimization
- `prompt_v4.txt` - Advanced multi-file modular system
- `prompt_v4-*.txt` - Supporting files for prompt_v4

**Language Placeholder**: All prompts support the `{LANGUAGE}` placeholder which is automatically replaced with the target language name (e.g., "Italian", "German") at runtime. This ensures alt-text is generated in the correct language for multilingual workflows.

### Web Scraping Configuration
```json
{
  "download": {
    "timeout": 30,
    "delay_between_requests": 3,  // Seconds between downloads (avoid rate limits)
    "user_agent": "Mozilla/5.0..."
  },
  "image_extraction": {
    "tags": {"img": true, "picture": true, "div": true},
    "attributes": {"src": true, "data-src": true, "srcset": true},
    "css_background_images": true
  }
}
```

### HTML Report Display Settings
```json
{
  "html_report_display": {
    "display_image_analysis_overview": true,
    "display_image_type_distribution": true,
    "display_html_tags_used": true,
    "display_html_attributes_used": true,
    "display_image_preview": true,
    "display_image_type": true,
    "display_current_alt_text": true,
    "display_proposed_alt_text": true,
    "display_image_tag_attribute": true,
    "display_reasoning": true,
    "display_context": true
  }
}
```

**Purpose**: Control which fields appear in generated HTML reports. Set any field to `false` to hide it from the report. Fields are ordered as they appear in the report.

**Report Summary Section**:
- `display_image_analysis_overview`: Show/hide "Image Analysis Overview" heading at the top of summary section (also controls the statistics subsections heading)
- `display_image_type_distribution`: Show/hide image type statistics (decorative/informative/functional counts)
- `display_html_tags_used`: Show/hide HTML tag usage statistics
- `display_html_attributes_used`: Show/hide HTML attribute usage statistics

**Per-Image Fields** (applied to each image card in Detailed Analysis):
- `display_image_preview`: Show/hide embedded image previews
- `display_image_type`: Show/hide image classification (decorative/informative/functional)
- `display_current_alt_text`: Show/hide existing alt-text from the webpage
- `display_proposed_alt_text`: Show/hide the AI-generated alt-text
- `display_image_tag_attribute`: Show/hide HTML tag and attribute information
- `display_reasoning`: Show/hide AI's explanation for classification
- `display_context`: Show/hide extracted webpage context

**Note**: These settings are embedded in each JSON file's `html_display` object and read during report generation. Changes to config.json only affect newly generated JSON files.

### Logging
```json
{
  "debug_mode": true,  // Enables file logging to logs/
  "logging": {
    "show_debug": true,     // Technical details
    "show_progress": true,  // Progress updates
    "show_warnings": true,  // Potential issues
    "show_errors": true     // Failures
  }
}
```

## Authentication (ECB-LLM only)

When `llm_provider: "ECB-LLM"`, the application uses U2A OAuth2 via the `ecb_llm_client` library:

1. User initiates generation via Web UI or API
2. The `ecb_llm_client` library automatically handles OAuth2 flow
3. Opens browser to ECB OAuth2 login page
4. User authenticates on ECB login page
5. ECB redirects to `http://localhost:3001/callback` (managed by ecb_llm_client)
6. Library exchanges code for access token and caches it
7. Subsequent requests use cached token

**Note**: Port 3001 is managed entirely by the `ecb_llm_client` library. Do not run a separate OAuth server on this port.

**OAuth2 Configuration:**
```json
{
  "ecb_llm": {
    "token_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/token",
    "scope": "openid profile LLM.api.read",
    "authorize_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/authorize"
  }
}
```

**Required environment variables:**
```bash
CLIENT_ID_U2A=ap-AutoAltText82ad91cd-960a-4e8b-aa22-8
CLIENT_SECRET_U2A=your-secret-here
```

**Note:** OpenAI provider requires only `OPENAI_API_KEY` in .env file.

## API Endpoints (api.py)

### Health & Auth
- `GET /api/health` - Server status
- `GET /api/auth/status` - Check authentication state
- `GET /api/auth/redirect` - Initiate OAuth2 flow (ECB-LLM)
- `GET /callback` - OAuth2 callback handler (port 3001)

### Alt-Text Generation
- `POST /api/generate-alt-text`
  - Form data: `image` (file), `language` (string), `context` (optional string)
  - Response: `{success: bool, alt_text: string, image_type: string, reasoning: string, character_count: int}`

### Documentation
- `GET /api/docs` - Swagger UI
- `GET /api/redoc` - ReDoc UI

## Key Functions in app.py

All functions are in the monolithic `app.py` file:

- `load_config(config_file)` - Load config.json, populate global CONFIG dict
- `get_llm_credentials()` - Return (provider, credentials) based on env vars
- `validate_language(lang_code)` - Check if language is in allowed list
- `load_and_merge_prompts(prompt_folder)` - Load and combine prompt templates
- `local_image_to_data_url(image_path)` - Convert image to base64 data URL
- `analyze_image_with_openai(image_path, combined_prompt, language)` - Call LLM vision API
- `generate_alt_text_json(...)` - Main orchestration function
- `download_images_from_url(url, images_folder, max_images)` - Web scraping
- `grab_context(url, image_filenames, context_folder, images_folder)` - Context extraction
- `process_all_images(...)` - Batch processing
- `generate_html_report(...)` - Create accessible HTML report
- `clear_folders(folders_to_clear)` - Cleanup utility

## Supported Languages

24 EU languages configured in `config.json`:
```
bg, cs, da, de, el, en, es, et, fi, fr, ga, hr, hu, it, lt, lv, mt, nl, pl, pt, ro, sk, sl, sv
```

View full list with: `python3 app.py -al`

## Troubleshooting

### "Failed to fetch" error in Web UI
**Symptom:** Browser console shows CORS error: "Access to fetch has been blocked by CORS policy"

**Cause:** Opening HTML file via `file://` protocol instead of HTTP

**Solution:** Access the frontend via HTTP server:
```bash
# Make sure you're accessing http://localhost:8080/home.html
# NOT file:///home/developer/AutoAltText/frontend/home.html

# The startup script automatically opens the correct URL
./start_MyAccessibilityBuddy.sh
```

### No images found
```bash
ls -la input/images/
cp test/images/*.png input/images/
```

### Authentication errors (ECB-LLM)
```bash
# Verify environment variables
env | grep -E "CLIENT_ID|CLIENT_SECRET"

# Check config
cat backend/config/config.json | grep llm_provider

# Test auth endpoint
curl http://localhost:8000/api/auth/status | python3 -m json.tool

# Verify only main API server is running (ecb_llm_client manages port 3001)
lsof -ti:8000,8080
```

**Port 3001 conflict**: If you see "Address already in use" on port 3001, stop any manual OAuth servers. The `ecb_llm_client` library manages this port automatically.

### Multilingual alt-text in wrong language
**Symptom:** All languages get alt-text in the first language only (e.g., `--language lv it` generates Latvian for both)

**Cause:** Prompt file doesn't have `{LANGUAGE}` placeholder, or translation_mode is misconfigured

**Solution:**
```bash
# 1. Verify prompt has {LANGUAGE} placeholder
grep "{LANGUAGE}" prompt/prompt_v0.txt

# 2. Use "accurate" mode for multilingual (generates fresh alt-text per language)
# Edit config.json: "translation_mode": "accurate"

# 3. Test with multiple languages
python3 app.py -g test.png --language en it de
```

### Rate limiting (429 errors)
Edit `config.json` → `download.delay_between_requests` → increase to 5+ seconds

### SVG support not working
```bash
pip install cairosvg
```

### Logs
Debug logs (when `debug_mode: true`) are written to `logs/` with timestamps.
```bash
tail -f logs/*.log
```

## Dependencies (requirements.txt)

**Core:**
- fastapi, uvicorn - Web server
- beautifulsoup4, requests - Web scraping
- openai - OpenAI API client
- Pillow - Image processing
- python-dotenv - Environment variables

**Optional:**
- CairoSVG - SVG to PNG conversion
- ecb_llm_client - ECB-LLM provider (ECB internal package)

## Development Notes

- **Code style**: Python 3.12+, docstrings for public functions
- **Monolithic structure**: Most logic in `app.py` (3,476 lines). Future refactoring would move modules to `backend/services/`
- **Configuration access**: Use `config.settings.get()` and `config.settings.get_nested()` instead of direct CONFIG dict access
- **Absolute paths**: Always resolve relative paths via `get_absolute_folder_path()` to support different working directories
- **Error handling**: All exceptions logged via `debug_log()` and `handle_exception()`
- **WCAG 2.2 focus**: Alt-text generation prioritizes accessibility compliance

## Testing Strategy

**Manual testing:**
```bash
# Test with known images
cp test/images/1.png input/images/
cp test/context/1.txt input/context/
python3 app.py -g 1.png --language en
```

**Batch testing:**
```bash
# Process all 13 test images
cp test/images/*.png input/images/
cp test/context/*.txt input/context/
python3 app.py -p --language en --report
```

**Prompt comparison:**
```bash
# Compare multiple prompt templates
python3 tools/batch_compare_prompts.py
# Output: CSV with side-by-side results
```

**API testing:**
```bash
# Start server
./start_MyAccessibilityBuddy.sh

# Test with curl
curl -F "image=@test/images/1.png" -F "language=en" \
  http://localhost:8000/api/generate-alt-text | python3 -m json.tool
```
