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

**Option 1: Docker (Recommended)**

```bash
# 1. Create .env file with your API credentials
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY or ECB-LLM credentials

# 2. Configure LLM provider in backend/config/config.json
# Set "llm_provider": "OpenAI" or "ECB-LLM"

# 3. Build and start with Docker Compose
docker-compose up -d

# Access the application
# Frontend: http://localhost:8080/home.html
# API Docs: http://localhost:8000/api/docs

# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

**Option 2: Local Development (Traditional)**

```bash
# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure .env file (in backend/ directory)
cp .env.example .env
# Edit .env and add:
# For OpenAI: OPENAI_API_KEY=sk-your-api-key-here
# For ECB-LLM: CLIENT_ID_U2A=... and CLIENT_SECRET_U2A=...
```

### Running the Application

**Docker Mode (Recommended):**
```bash
# Start all services
docker-compose up -d

# Frontend: http://localhost:8080/home.html
# API docs: http://localhost:8000/api/docs
# OAuth (ECB-LLM): Port 3001 automatically used when needed

# Stop services
docker-compose down

# Run batch processing with test images
docker-compose --profile test run myaccessibilitybuddy-test
```

**Local Mode:**
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

The batch prompt comparison tool helps you evaluate and optimize your prompt templates by systematically testing them against a set of test images.

**Docker Mode (Recommended):**
```bash
# Run batch comparison
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py
```

**Local Mode:**
```bash
cd backend
source venv/bin/activate
cd ..
python3 tools/batch_compare_prompts.py
```

**Configuration:**
Test parameters are defined in `backend/config/config.advanced.json`:
```json
{
  "testing": {
    "folders": {
      "test_images": "test/input/images",
      "test_context": "test/input/context",
      "test_reports": "test/output/reports"
    },
    "batch_comparison": {
      "test_name": "Prompt Comparison Test",
      "prompts": [
        {"file": "processing_prompt_v0.txt", "label": "v0: base prompt"},
        {"file": "processing_prompt_v2.txt", "label": "v2: WCAG focused"}
      ],
      "test_images": ["1.png", "2.png", "3.png"],
      "language": "en"
    }
  }
}
```

**Output:**
- CSV: `test/output/reports/prompt_comparison_[timestamp].csv`
- HTML: `test/output/reports/prompt_comparison_[timestamp].html`

**Example Results:**
```csv
Image Filename,Alt Text (v0),Alt Text (v2)
1.png,"Monetary policy graphic","Illustration showing ECB monetary policy with 2% inflation target"
2.png,"Interest rate chart","Chart displaying key ECB interest rates over time"
```

## Configuration

MyAccessibilityBuddy uses a split configuration system for better usability:

- **[config.json](backend/config/config.json)** - Basic settings (LLM, logging, prompts)
- **[config.advanced.json](backend/config/config.advanced.json)** - Advanced settings (folders, scraping, context extraction, languages)

Both files are automatically loaded and merged at startup. Basic config takes precedence for overlapping keys.

### Basic Configuration (config.json)

Settings that users commonly adjust:

#### LLM Provider Settings
```json
{
  "llm_provider": "Ollama",        // Options: "OpenAI", "ECB-LLM", or "Ollama"
  "two_step_processing": true,     // Enable two-step processing (recommended)
  "translation_mode": "fast",      // "fast" or "accurate"

  "openai": {
    "vision_model": "gpt-4o",      // Step 1: Image description
    "processing_model": "gpt-4o"   // Step 2: WCAG alt-text generation
  },

  "ecb_llm": {
    "vision_model": "gpt-4o",      // Can use gpt-4o or gpt-5.1
    "processing_model": "gpt-4o"
  },

  "ollama": {
    "base_url": "http://192.168.64.1:11434",
    "vision_model": "granite3.2-vision",
    "processing_model": "phi3"
  }
}
```

**LLM Providers:**
- **OpenAI**: Cloud-based GPT-4o (requires `OPENAI_API_KEY` in `.env`)
- **ECB-LLM**: ECB internal service (requires `CLIENT_ID_U2A` and `CLIENT_SECRET_U2A` in `.env`)
- **Ollama**: Local models via Ollama server (free, runs locally, no API key needed)

**Processing Workflow:**
When `two_step_processing: true` (recommended), all providers use a multi-step workflow:
1. **Step 1 - Vision**: Vision model analyzes image → generates detailed description (uses prompts from `prompt/vision/`)
2. **Step 2 - Processing**: Processing model → generates WCAG-compliant alt-text (uses prompts from `prompt/processing/`)
3. **Step 3 - Translation** (optional): Translation model translates alt-text to target language(s) in "fast" multilingual mode (uses prompts from `prompt/translation/`)

When `two_step_processing: false`, uses legacy single-step mode (vision model does everything).

**Translation Step Behavior:**
- **Single language**: Translation step is skipped (alt-text generated directly in target language)
- **Multiple languages (fast mode)**: Generate once in first language, then translate to others using Step 3
- **Multiple languages (accurate mode)**: Generate fresh alt-text for each language (no translation step)

**Model Flexibility:**
You can mix and match models within the same provider:
```json
{
  "openai": {
    "vision_model": "gpt-4o",       // High-quality image analysis
    "processing_model": "gpt-4o-mini"  // Cheaper model for text processing
  },
  "ollama": {
    "vision_model": "llama3.2-vision",  // Or granite3.2-vision, moondream
    "processing_model": "phi3"           // Or llama3.2, granite3.2
  }
}
```

**Translation Modes:**
- **"fast"**: Generate once in first language, then translate others (faster, cheaper)
- **"accurate"**: Generate fresh alt-text for each language (better quality, slower)

**Setting up Ollama:**
```bash
# Install Ollama: https://ollama.ai
# Pull required models
ollama pull granite3.2-vision  # Or llama3.2-vision
ollama pull phi3               # Or llama3.2, granite3.2

# Configure in config.json
"llm_provider": "Ollama"
```

#### Logging Settings
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

#### Prompt Selection
```json
{
  "prompt": {
    "processing_files": ["processing_prompt_v0.txt"],
    "default_processing_prompt": "processing_prompt_v0.txt",
    "vision_files": ["vision_prompt_v0.txt"],
    "default_vision_prompt": "vision_prompt_v0.txt",
    "translation_files": ["translation_prompt_v0.txt"],
    "default_translation_prompt": "translation_prompt_v0.txt",
    "translation_system_files": ["translation_system_prompt_v0.txt"],
    "default_translation_system_prompt": "translation_system_prompt_v0.txt"
  }
}
```

**Prompt Organization:**
Prompts are organized into three categories based on the processing workflow:

```
prompt/
├── vision/                              # Step 1: Image description
│   └── vision_prompt_v0.txt            # "Describe this image in detail."
├── processing/                          # Step 2: WCAG alt-text generation
│   ├── processing_prompt_v0.txt        # Minimal baseline with JSON output
│   ├── processing_prompt_v1.txt        # Basic classification
│   ├── processing_prompt_v2.txt        # WCAG 2.2 focused (recommended)
│   ├── processing_prompt_v3.txt        # Comprehensive
│   └── processing_prompt_v4.txt        # Advanced multi-file modular system
└── translation/                         # Step 3: Translation (multilingual mode)
    ├── translation_prompt_v0.txt        # User prompt for translation
    └── translation_system_prompt_v0.txt # System prompt (provider-specific)
```

**Available Processing Prompts** in `prompt/processing/`:
- `processing_prompt_v0.txt` - Minimal baseline with JSON output
- `processing_prompt_v1.txt` - Basic classification (decorative/informative/functional)
- `processing_prompt_v2.txt` - WCAG 2.2 focused with decision tree (recommended)
- `processing_prompt_v3.txt` - Comprehensive with phased execution and optimization
- `processing_prompt_v4.txt` - Advanced multi-file modular system
- `processing_prompt_v4-*.txt` - Supporting files for prompt_v4

**Customizing Prompts:**
- **Vision prompts** (`prompt/vision/`): Control how the image is analyzed in Step 1
- **Processing prompts** (`prompt/processing/`): Control WCAG alt-text generation in Step 2
- **Translation prompts** (`prompt/translation/`): Control how alt-text is translated in multilingual mode (Step 3)

**Translation Prompts** (used only in multilingual "fast" mode):
- `translation_prompt_v0.txt` - Main user prompt sent to the translation model with the text to translate
- `translation_system_prompt_v0.txt` - System-level instructions for the translation model (used by providers like Claude that support separate system prompts)

Both translation prompts support the `{TARGET_LANGUAGE}` placeholder which is replaced with the target language name at runtime.

**Language Placeholders**:
- Processing and vision prompts use `{LANGUAGE}` - replaced with target language name (e.g., "Italian", "German")
- Translation prompts use `{TARGET_LANGUAGE}` - replaced with target language for translation
These placeholders ensure alt-text is generated in the correct language for multilingual workflows.

### Advanced Configuration (config.advanced.json)

Technical settings rarely modified by most users:

#### Folder Paths
All paths are relative to project root. Accessed via `config.settings.get_folder_path(name)`:
```json
{
  "folders": {
    "images": "input/images",
    "context": "input/context",
    "alt_text": "output/alt-text",
    "reports": "output/reports",
    "prompt": "prompt",
    "prompt_processing": "prompt/processing",
    "prompt_vision": "prompt/vision",
    "prompt_translation": "prompt/translation",
    "logs": "logs"
  }
}
```

#### Supported Languages
```json
{
  "languages": {
    "allowed": [
      {"code": "bg", "name": "Български"},
      {"code": "en", "name": "English"},
      ...24 EU languages total
    ],
    "default": "en"
  }
}
```

View full list with: `python3 app.py -al`

#### Web Scraping Configuration
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

**Note**: These settings are read from `config.advanced.json` during HTML report generation. The `html_display` field is NOT included in generated JSON files.

#### Context Extraction
```json
{
  "context": {
    "max_text_length": 1000,       // Max chars per text element
    "max_parent_levels": 5,        // DOM levels to traverse
    "min_text_length": 20,         // Minimum chars to include
    "max_sibling_text_length": 500 // Max chars from sibling elements
  }
}
```

#### ECB-LLM OAuth2 Configuration
```json
{
  "ecb_llm": {
    "token_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/token",
    "scope": "openid profile LLM.api.read",
    "authorize_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/authorize"
  }
}
```

**Note**: These OAuth2 endpoints should rarely need modification.

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
# Edit backend/config/config.json: "translation_mode": "accurate"

# 3. Test with multiple languages
python3 app.py -g test.png --language en it de
```

### Rate limiting (429 errors)
Edit `backend/config/config.advanced.json` → `download.delay_between_requests` → increase to 5+ seconds

### SVG support not working
```bash
pip install cairosvg
```

### Logs
Debug logs (when `debug_mode: true`) are written to `logs/` with timestamps.
```bash
# Local mode
tail -f logs/*.log

# Docker mode
docker-compose logs -f
```

### Docker-specific issues

**Container won't start:**
```bash
# Check logs for errors
docker-compose logs

# Verify .env file exists and is mounted
docker-compose config

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

**Permission errors in Docker:**
```bash
# The container runs as user 'appuser' (UID 1000)
# If you have permission errors with mounted volumes, check ownership:
ls -la input/ output/ logs/

# Fix ownership if needed (Linux/Mac)
sudo chown -R 1000:1000 input/ output/ logs/
```

**Cannot access OAuth callback (ECB-LLM):**
```bash
# Port 3001 must be accessible from your browser
# Check if port is exposed in docker-compose.yml
# For ECB-LLM, the OAuth flow requires browser access to localhost:3001
```

**Changes to code not reflected:**
```bash
# Rebuild the Docker image after code changes
docker-compose up -d --build

# Or rebuild specific service
docker-compose build myaccessibilitybuddy
docker-compose up -d
```

## Docker Deployment

### Container Architecture

The Docker setup includes:
- **Dockerfile**: Multi-stage Python 3.12 slim image with all dependencies
- **docker-compose.yml**: Orchestrates frontend (8080) and backend (8000) services
- **docker-entrypoint.sh**: Startup script managing both servers
- **Volumes**: Persistent data for input/, output/, logs/, config.json, and .env

### Production Considerations

**Security:**
- Container runs as non-root user (appuser, UID 1000)
- .env file never included in image (mounted as volume)
- Minimal base image (python:3.12-slim) reduces attack surface
- Health checks monitor API availability

**Volumes:**
```yaml
# docker-compose.yml mounts these directories:
- ./input:/app/input           # Image input files
- ./output:/app/output         # Generated alt-text and reports
- ./logs:/app/logs             # Application logs
- ./backend/config/config.json:/app/backend/config/config.json
- ./backend/.env:/app/backend/.env
```

**Environment Variables:**
All configuration via `backend/.env`:
- `OPENAI_API_KEY` - For OpenAI provider
- `CLIENT_ID_U2A` / `CLIENT_SECRET_U2A` - For ECB-LLM provider

**Scaling:**
Current setup runs both frontend and backend in single container. For production:
1. Separate frontend static files → nginx
2. Run multiple API containers behind load balancer
3. External volume/object storage for input/output
4. Centralized logging (stdout/stderr captured by Docker)

### Docker Commands Reference

```bash
# Build and start
docker-compose up -d

# View logs (follow)
docker-compose logs -f

# Restart services
docker-compose restart

# Stop services (keep volumes)
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild after code changes
docker-compose up -d --build

# Run CLI commands inside container
docker-compose exec myaccessibilitybuddy bash
# Then inside container:
cd /app/backend
python3 app.py -g /app/input/images/1.png --language en

# Run test suite
docker-compose --profile test run myaccessibilitybuddy-test

# Check container health
docker-compose ps
docker inspect myaccessibilitybuddy | grep -A 10 Health
```

## Dependencies (requirements.txt)

**Core:**
- fastapi, uvicorn - Web server
- beautifulsoup4, requests - Web scraping
- openai - OpenAI API client
- ollama - Ollama client for local models
- Pillow - Image processing
- python-dotenv - Environment variables

**Optional:**
- CairoSVG - SVG to PNG conversion
- ecb_llm_client - ECB-LLM provider (ECB internal package)

**Installing Ollama:**
```bash
# 1. Install Ollama from https://ollama.ai
# 2. Install Python client
pip install ollama

# 3. Pull required models
ollama pull granite3.2-vision  # Vision model
ollama pull phi3               # Processing model

# 4. Verify Ollama is running
curl http://localhost:11434/api/tags
```

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
