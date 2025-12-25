# MyAccessibilityBuddy - Complete Documentation

**Version:** 1.0.0  
**Last Updated:** December 2025  
**Copyright:** 2025 by Nicola.Caione@bancaditalia.it

## Overview

MyAccessibilityBuddy is an AI-powered tool for generating WCAG 2.2 compliant alternative text for web images. It provides multiple interfaces (Web UI, CLI, REST API) and supports 24 EU languages with flexible OpenAI GPT 4o and ECB-LLM GPT-4o to GPT-5.1 provider integration.

⚠️ For testing purposes only: Use with non confidential images. Avoid uploading personal or sensitive data. AI suggestions require human review before use.⚠️

---

## Table of Contents

1. [Overview](#overview)
2. [Installation & Setup](#installation--setup)
3. [Quick Start Guide](#quick-start-guide)
4. [Configuration](#configuration)
5. [Authentication](#authentication)
6. [Usage - Web UI](#usage---web-ui)
7. [Usage - CLI](#usage---cli)
8. [Usage - API](#usage---api)
9. [Batch Processing](#batch-processing)
10. [Advanced Features](#advanced-features)
11. [Troubleshooting](#troubleshooting)
12. [API Reference](#api-reference)
13. [Development Guide](#development-guide)

---


### Key Features

- **🖼️ Multi-Format Image Support**: JPG, JPEG, PNG, GIF, WEBP, SVG, BMP, TIFF
- **🌍 24 EU Languages**: All official European Union languages
- **🔐 Flexible Authentication**: U2A (User-to-Application) OAuth2
- **📊 Batch Processing**: Compare multiple prompts simultaneously
- **🌐 Modern Web UI**: Bootstrap Italia design system
- **📝 Context Extraction**: Automatic web page context discovery
- **📈 Accessible Reports**: HTML reports with ARIA markup
- **🚀 REST API**: FastAPI with OpenAPI documentation
- **🤖 LLM Support**: OpenAI GPT-4o or ECB-LLMs GPT-4o, GPT-5.0 and GPT-5.1

### Architecture

```
┌──────────────────────────────────────────────────┐
│           Frontend (Bootstrap Italia)            │
│  file:///AutoAltText/frontend/home.html         │
└───────────────────┬──────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────┐
│        FastAPI Server (Port 8000)               │
│  - Alt-text generation API                      │
│  - Authentication endpoints                     │
│  - OAuth2 redirect handler                      │
└───────────────────┬──────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐      ┌────────────────┐
│ OAuth Callback│      │   LLM Provider │
│  (Port 3001)  │      │  ECB-LLM/OpenAI│
└───────────────┘      └────────────────┘
```

---

## Installation & Setup

### Prerequisites

- Python 3.12 or higher
- Chrome/Chromium browser (for auto-login feature)
- Internet connection
- ECB credentials (for ECB-LLM) or OpenAI API key

### Step 1: Environment Setup

```bash
cd /home/developer/AutoAltText

# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configuration
Add credentials in .env environment file:

# For ECB-LLM with U2A OAuth2
CLIENT_ID_U2A=ap-AutoAltText82ad91cd-960a-4e8b-aa22-8
CLIENT_SECRET_U2A=your-client-secret

# OR for OpenAI
OPENAI_API_KEY=sk-your-api-key-here
```

### Step 3: Verify Installation

```bash
# Test CLI
cd backend
python3 app.py --help

# Start servers
cd ..
./start_MyAccessibilityBuddy.sh
```

---

## Quick Start Guide

### Web UI (Recommended for Beginners)

1. **Start the server:**
   ```bash
   ./start_MyAccessibilityBuddy.sh
   ```
   Frontend opens automatically in browser

2. **Upload an image** (drag & drop or click)

3. **Select language** from dropdown (default: English)

4. **Optionally upload context file** (.txt with surrounding text)

5. **Click "Generate Alt Text"**

6. **Authenticate** (first time only - OAuth2 redirect)

7. **Copy the result** using the copy button

### CLI (Quick Single Image)

```bash
cd backend
source venv/bin/activate

# Add image
cp ~/my-image.png ../input/images/

# Generate alt-text
python3 app.py -g my-image.png --language en

# View result
cat output/alt-text/my-image.json
```

### API (For Integration)

```bash
# Start server
./start_MyAccessibilityBuddy.sh

# Call API
curl -F "image=@test.png" -F "language=en" \
  http://localhost:8000/api/generate-alt-text
```

---

## Configuration

Configuration file: `backend/config/config.json`

### Essential Settings

```json
{
  "llm_provider": "ECB-LLM",
  "model": "gpt-5.1",
  "authentication_mode": "U2A",
  "prompt": {
    "files": ["alt-text-improved.txt"]
  },
  "download": {
    "delay_between_requests": 3
  }
}
```

### LLM Provider Options

**ECB-LLM (Default):**
```json
{
  "llm_provider": "ECB-LLM",
  "model": "gpt-5.1",
  "ecb_llm": {
    "endpoint": "https://api-int.azure.ecb.de/gateway/LLM-API/1.0/deployments/gpt-5/chat/completions",
    "api_version": "2025-01-01-preview",
    "scope": "openid profile LLM.api.read"
  }
}
```

**OpenAI:**
```json
{
  "llm_provider": "OpenAI",
  "model": "gpt-4o"
}
```

### Authentication Modes

**U2A (User-to-Application):**
- Users authenticate with their credentials
- Uses redirect mode with OAuth2 authorization code flow
- Requires ECB credentials for authentication

### Translation Modes

When generating alt-text in multiple languages, you can choose between two modes:

**Fast Mode (Default):**
```json
{
  "full_translation_mode": false
}
```
- Generates alt-text once in the first language
- Translates to other languages using AI translation
- **Advantages:** Faster processing, lower API costs, consistent translations
- **Best for:** Batch processing, similar languages (EN→ES→IT), simple content
- **Processing:** 1 image analysis + N-1 translations

**Accurate Mode:**
```json
{
  "full_translation_mode": true
}
```
- Generates fresh alt-text for each language independently
- Each language gets full AI image analysis
- **Advantages:** More natural translations, better cultural context, language-specific idioms
- **Best for:** Critical content, dissimilar languages (EN→FI→HU), public-facing content
- **Processing:** N image analyses (one per language)

**Example:**
```bash
# With fast mode (false): 3 languages in ~5 seconds
# With accurate mode (true): 3 languages in ~15 seconds
python3 app.py -g image.png --language en it es
```

The HTML report will display which translation method was used in the "Translation Method" field.

### Context Extraction Detail Levels

When extracting context from web pages, you can control how much surrounding information is captured to help the AI generate better alt-text. The system analyzes the HTML structure around each image to understand its purpose and context.

**Configuration:**
```json
{
  "context": {
    "detail_level": "medium"
  }
}
```

**Low Detail Level:**
```json
{
  "context": {
    "detail_level": "low"
  }
}
```
- **Parent Levels:** 1 (only immediate parent element)
- **Max Headings:** 1 (only the closest heading)
- **Use Case:** Logo images, icons, decorative elements
- **Processing:** Fastest, minimal context
- **Example:** For `blog_logo.png`, captures only "The ECB Blog" heading, ignoring all blog post titles

**Advantages:**
- Minimal noise in context
- Fastest processing
- Best for simple, self-contained images
- Reduces API token usage

**Limitations:**
- May miss important surrounding context
- Less suitable for complex informative images

**Medium Detail Level (Default):**
```json
{
  "context": {
    "detail_level": "medium"
  }
}
```
- **Parent Levels:** 3 (searches 3 levels up the DOM tree)
- **Max Headings:** 3 (first 3 relevant headings)
- **Use Case:** Most images, balanced approach
- **Processing:** Moderate speed, relevant context
- **Example:** For `blog_logo.png`, captures "The ECB Blog" + first 2-3 blog post titles

**Advantages:**
- Balanced between speed and context richness
- Filters out excessive noise (e.g., stops after 3 headings instead of collecting all 76)
- Suitable for 90% of use cases
- Good context without overwhelming the AI

**Limitations:**
- May not capture all relevant context for deeply nested images

**High Detail Level:**
```json
{
  "context": {
    "detail_level": "high"
  }
}
```
- **Parent Levels:** 5 (searches 5 levels up the DOM tree)
- **Max Headings:** Unlimited (all headings found)
- **Use Case:** Complex informative images, charts, infographics requiring extensive context
- **Processing:** Slower, comprehensive context
- **Example:** For `blog_logo.png`, captures "The ECB Blog" + ALL 76 blog post titles (may hit 1000 char limit)

**Advantages:**
- Most comprehensive context extraction
- Captures all surrounding information
- Best for complex, context-dependent images

**Limitations:**
- Slower processing
- More API tokens used
- May include irrelevant information
- Can overwhelm the AI with too much context

**How It Works:**

The context extraction algorithm:
1. Starts at the `<img>` tag
2. Traverses **up** the DOM tree (parent levels: 1, 2, 3, 4, 5)
3. At each parent level, extracts:
   - Headings (`<h1>` through `<h6>`)
   - Section text (if parent is `<section>`, `<article>`, `<div>`, `<main>`)
   - Captions (`<figcaption>`)
   - Sibling text elements
4. **Stops** when:
   - Max parent levels reached
   - Max headings collected
   - Max text length (1000 chars) reached

**Example Comparison:**

For an image on https://www.ecb.europa.eu/press/blog/:

**Low Detail:**
```
Context: "The ECB Blog"
Result: "ECB Blog logo"
```

**Medium Detail:**
```
Context: "The ECB Blog | 9 December 2025 | A digital euro for the digital age | 28 November 2025"
Result: "ECB Blog logo"
```

**High Detail:**
```
Context: "The ECB Blog | 9 December 2025 | A digital euro for the digital age | 28 November 2025 | From headlines to hard data... [+73 more blog titles]"
Result: "ECB Blog logo" (same, but with more processing time)
```

**Recommendation:**
- **Start with `medium`** (default) - works well for most cases
- **Use `low`** if you notice too much irrelevant context in logs or for simple images
- **Use `high`** only for complex images where extensive context is critical (charts, infographics embedded in rich content)

**Debug Logs:**

When running with `debug_mode: true`, you'll see:
```
[DEBUG] Context detail level: medium (max_parent_levels=3, max_headings=3)
[DEBUG] Searching up to 3 parent levels for context (max 3 headings)
[DEBUG] Found heading: The ECB Blog
[DEBUG] Found heading: 9 December 2025
[DEBUG] Found heading: A digital euro for the digital age
[DEBUG] Reached max_headings limit (3), stopping heading collection
```

This helps you tune the `detail_level` setting for your specific use case.

### Prompt Configuration

Available prompts in `prompt/`:
- `base_prompt.txt` - Basic alt-text
- `alt-text-improved.txt` - Enhanced WCAG compliance (recommended)
- `main_prompt.txt` - Comprehensive analysis

```json
{
  "prompt": {
    "files": ["alt-text-improved.txt"],
    "default_prompt": "base_prompt.txt"
  }
}
```

---

## Authentication

### U2A OAuth2 Redirect (Current Setup)

**Flow:**
1. User triggers alt-text generation
2. Frontend detects no session → redirects to `/api/auth/redirect`
3. Backend generates OAuth2 URL with state token
4. User redirected to ECB login page
5. User enters credentials on ECB's official page
6. ECB redirects back to `http://localhost:3001/callback?code=XXX`
7. Backend validates state, exchanges code for token
8. Token stored in session (HTTP-only cookie, 1 hour)
9. User redirected back to frontend
10. Alt-text generation proceeds

**OAuth Configuration:**
- Client ID: `ap-AutoAltText82ad91cd-960a-4e8b-aa22-8`
- Grant Types: AUTHORIZATION_CODE, REFRESH_TOKEN
- Redirect URI: `http://localhost:3001/callback`
- Scopes: `openid profile LLM.api.read`

---

## Usage - Web UI

### Starting the UI

```bash
./start_MyAccessibilityBuddy.sh
```

Server starts on port 8000, OAuth callback on port 3001. Frontend opens automatically.

### UI Features

**Image Upload:**
- Drag & drop support
- Click to browse
- Preview before processing
- Multi-format support

**Context Upload:**
- Optional .txt file
- Provides surrounding text context
- Improves alt-text relevance

**Language Selection:**
- 24 EU languages
- Dropdown with native names
- Default: English

**Results:**
- Editable output text
- Copy button for quick copying
- Decorative image detection
- Visual feedback during processing

### Authentication Flow

1. First access triggers OAuth2 redirect
2. Browser navigates to ECB login
3. User enters credentials
4. Automatic return to application
5. Session persists for 1 hour
6. Seamless subsequent requests

---

## Usage - CLI

### Command Structure

```bash
python3 app.py [action] [arguments] [options]
```

### Examples
**Clear Input and output folders:**
```bash
cd backend
python3 app.py --clear-all
```

**Download Images:**
```bash
cd backend
# Download all images from a webpage
python3 app.py -d <URL>
python3 app.py --download <URL>

# Example: Download from ECB website
python3 app.py -d https://www.ecb.europa.eu/home/html/index.en.html
# Output: Images saved to input/images/
```

**Extract Context:**
```bash
# Extract context text for a specific image from a webpage
python3 app.py -c <URL> <image_filename>
python3 app.py --context <URL> <image_filename>

# Example: Extract context for an image
python3 app.py -c https://www.ecb.europa.eu logo_only.svg
# Output: Context saved to input/context/ogo_only.svg
```

**Generate Alt-Text:**
```bash
# Generate alt-text for a single image
python3 app.py -g <image_filename> --language en
python3 app.py --generate-json <image_filename> --language en

# Example: Generate alt-text for test image (using test files)
cd backend
cp ../test/images/1.png ../input/images/
cp ../test/context/1.txt ../input/context/
python3 app.py -g 1.png --language en
# Output: output/alt-text/1.json

# Example: Generate alt-text in Italian
python3 app.py -g 1.png --language it
# Output: Alt-text in Italian

# Example: Generate for image without context
cp ../test/images/11.png ../input/images/
python3 app.py -g 11.png
```

**Process All Images:**
```bash
# Process all images in input/images/ folder
python3 app.py -p --language en
python3 app.py --process-all --language en --report

# Example: Process all test images with HTML report
cd backend
cp ../test/images/*.png ../input/images/
cp ../test/context/*.txt ../input/context/
python3 app.py -p --language en --report
# Output:
#   - output/alt-text/*.json (one per image)
#   - output/reports/*.html (accessibility report)

# Example: Process in multiple languages
python3 app.py -p --language de --report
```

**Complete Workflow:**
```bash
# Download images, extract context, and generate alt-text in one command
python3 app.py -w <URL> --language en
python3 app.py --workflow <URL> --language it --report

# Example: Complete workflow for ECB website
python3 app.py -w https://www.ecb.europa.eu/home/html/index.en.html --language en --report
# Output:
#   - input/images/*.{jpg,png,svg} (downloaded images)
#   - input/context/*.txt (extracted context)
#   - output/alt-text/*.json (generated alt-text)
#   - output/reports/*.html (accessibility report)

# Example: Workflow with different language
python3 app.py -w https://example.com --language fr --report
```

### Options

**Language:**
```bash
--language en
--languages en it fr de  # Multiple languages
```

**Report Generation:**
```bash
--report  # Generate HTML accessibility report
```

**Folder Management:**
```bash
--clear-all       # Clear all folders
--clear-inputs    # Clear input folders
--clear-outputs   # Clear output folders
```

### Examples

**Single image from web:**
```bash
python3 app.py -w https://example.com --num-images 1 --language en
```

**Batch process with multiple languages:**
```bash
python3 app.py -p --languages en it de fr --report
```

**Download and extract context:**
```bash
python3 app.py -d https://example.com
python3 app.py -c https://example.com image.jpg
```

---

## Usage - API

### Starting the API Server

```bash
./start_MyAccessibilityBuddy.sh
```

API available at: `http://localhost:8000`
Documentation: `http://localhost:8000/api/docs`

### Endpoints

**Generate Alt-Text:**
```bash
POST /api/generate-alt-text

# Form data
image: <file>
language: "en"
context: "optional context text"

# Response
{
  "success": true,
  "alt_text": "Description of the image",
  "is_decorative": false,
  "language": "en",
  "model": "gpt-5.1",
  "timestamp": "2025-12-08T15:30:00Z"
}
```

**Authentication Status:**
```bash
GET /api/auth/status

# Response
{
  "authenticated": true,
  "requires_u2a": true,
  "has_credentials": true
}
```

**Health Check:**
```bash
GET /api/health

# Response
{
  "status": "healthy",
  "timestamp": "2025-12-08T15:30:00Z"
}
```

### Example Usage

**curl:**
```bash
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@photo.jpg" \
  -F "language=en" \
  -F "context=Product image for website"
```

**Python:**
```python
import requests

url = "http://localhost:8000/api/generate-alt-text"
files = {"image": open("photo.jpg", "rb")}
data = {"language": "en", "context": "Product photo"}

response = requests.post(url, files=files, data=data)
print(response.json()["alt_text"])
```

**JavaScript:**
```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('language', 'en');

fetch('http://localhost:8000/api/generate-alt-text', {
  method: 'POST',
  body: formData
})
.then(r => r.json())
.then(data => console.log(data.alt_text));
```

---

## Batch Processing

### Prompt Comparison Script

Compare alt-text quality across three different prompts:

```bash
# Add images
cp ~/images/*.png ../input/images/

# Run comparison
python3 batch_compare_prompts.py

# Output
output/prompt_comparison_TIMESTAMP.csv
```

### CSV Output Format

| Image Filename | Alt Text (base_prompt) | Alt Text (alt-text-improved) | Alt Text (main_prompt) |
|----------------|------------------------|------------------------------|------------------------|
| logo.png       | A blue logo            | Blue circular company logo   | Professional circular logo in corporate blue with gradient |
| chart.jpg      | Bar chart              | Bar chart showing Q3 sales   | Detailed bar chart illustrating Q3 2024 sales performance with annotations |

### Features

- Processes all images in `input/images/`
- Uses context files from `input/context/` if available
- Runs sequentially with three prompts
- Automatic configuration backup/restore
- Progress indicators
- Error handling and recovery

### Configuration

Prompts tested:
1. `prompt/base_prompt.txt`
2. `prompt/alt-text-improved.txt`
3. `prompt/main_prompt.txt`

Processing time: ~5-10 minutes per prompt per 10 images

---

## Advanced Features

### Context Extraction

Automatically extracts surrounding text from web pages to provide context for AI alt-text generation.

#### How It Works

**Extraction Order (Priority):**

1. **Alt text** from `<img alt="...">` tag
2. **Title attribute** from `<img title="...">`
3. **Headings** (h1-h6) from parent elements
4. **Section text** from `<section>`, `<article>`, `<div>`, `<main>`
5. **Captions** from `<figcaption>`
6. **Nearby text** from sibling `<p>`, `<span>`, `<div>` elements

#### Structured Format with "Part N:" Labels

**Code Location:** [app.py:2031-2054](../backend/app.py#L2031-L2054)

Each extracted context element is:
- **Numbered sequentially** (Part 1:, Part 2:, Part 3:, etc.)
- **Ends with a period** (.)
- **Separated by double newlines** (blank line between parts)

**Example Context File:**

```
Part 1: Digital euro concept.

Part 2: A digital euro for the digital age.

Part 3: THE ECB BLOG 9 December 2025 A digital euro for the digital age.

Part 4: The digital euro is not just the next step in the evolution of our money.

Part 5: Read The ECB Blog.
```

#### Usage

**Extract Context from URL:**
```bash
python3 app.py -c <URL> <image_filename>
```

**Example:**
```bash
python3 app.py -c https://www.ecb.europa.eu/press/blog/ logo.png
```

**Output:** `input/context/logo.txt` with structured "Part N:" format

#### Benefits

- **Clear Organization** - Distinct, numbered context pieces
- **AI-Friendly** - LLM can reference specific parts
- **Human-Readable** - Easy to review and verify
- **Consistent Format** - Same structure regardless of complexity

#### Test Examples

Check test files for real examples:
- `test/context/1.txt` - "Part 1: Our monetary policy statement at a glance - September 2025."
- `test/context/3.txt` - "Part 1: The economy is navigating difficulties..."

### Rate Limiting Protection

Configure delays to avoid 429 errors:

```json
{
  "download": {
    "delay_between_requests": 3,
    "timeout": 30
  }
}
```

### Decorative Image Detection

AI automatically identifies decorative images:

```json
{
  "alt_text": "",
  "is_decorative": true,
  "reason": "Background pattern with no informational content"
}
```

### HTML Report Generation

Creates accessible HTML summaries:

```bash
python3 app.py -p --language en --report
```

Output: `output/reports/accessibility_report_TIMESTAMP.html`

Features:
- ARIA landmarks
- Screen reader compatible
- Bootstrap Italia styling
- Image thumbnails
- Metadata display

---

## Troubleshooting

### Authentication Issues

**Problem: "unauthorized_client" error**

Solution:
- OAuth client lacks PASSWORD grant
- Use redirect authentication instead
- Or request PASSWORD grant from administrator

**Problem: Redirect fails**

Check:
```bash
# Verify servers running
lsof -ti:8000,3001

# Test auth endpoint
curl http://localhost:8000/api/auth/status

# Check redirect URL
curl -I http://localhost:8000/api/auth/redirect
```

**Problem: Cross-port cookie issues**

- Cookies set with `domain=localhost`
- Should work across ports 8000 and 3001
- Clear browser cookies and retry
- Check browser console for errors

### Rate Limiting

**Problem: 429 Too Many Requests**

Solutions:
1. Increase delay in config.json:
   ```json
   {"download": {"delay_between_requests": 5}}
   ```

2. Wait 5-10 minutes before retrying

3. Use manual context extraction

### Image Issues

**Problem: No images found**

```bash
# Check directory
ls -la input/images/

# Verify permissions
chmod 755 input/images/

# Add test image
cp ~/test.png ../input/images/
```

**Problem: Unsupported format**

Supported: JPG, JPEG, PNG, GIF, WEBP, SVG, BMP, TIFF

For SVG support:
```bash
pip install cairosvg
```

### API Issues

**Problem: Server not starting**

```bash
# Check port availability
lsof -ti:8000

# Kill existing process
lsof -ti:8000 | xargs kill

# Check logs
tail -f logs/*.log
```

**Problem: CORS errors**

- API configured to allow all origins
- Check browser console
- Verify API_BASE_URL in frontend

---

## API Reference

### REST Endpoints

#### POST /api/generate-alt-text

Generate alt-text for an image.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body:
  - `image` (file, required): Image file
  - `language` (string, required): ISO language code
  - `context` (string, optional): Context text

**Response:**
```json
{
  "success": true,
  "alt_text": "Generated description",
  "is_decorative": false,
  "language": "en",
  "model": "gpt-5.1",
  "timestamp": "2025-12-08T15:30:00Z"
}
```

#### GET /api/auth/status

Check authentication status.

**Response:**
```json
{
  "authenticated": true,
  "requires_u2a": true,
  "has_credentials": true,
  "login_url": "/auth/redirect"
}
```

#### GET /api/auth/redirect

Initiate OAuth2 authorization code flow.

**Response:** HTTP 307 redirect to ECB login

#### GET /callback

OAuth2 callback endpoint (port 3001).

**Parameters:**
- `code`: Authorization code
- `state`: CSRF token

**Response:** HTML page with session cookie and redirect

#### GET /api/health

Server health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-08T15:30:00Z"
}
```

### Error Responses

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Detailed error information"
}
```

HTTP Status Codes:
- 200: Success
- 400: Bad request
- 401: Unauthorized
- 429: Too many requests
- 500: Server error

---

## Development Guide

### Project Structure

```
MyAccessibilityBuddy/
├── backend/
│   ├── app.py                 # CLI entry point
│   ├── api.py                 # FastAPI server
│   ├── config/
│   │   ├── config.json        # Configuration
│   │   └── settings.py        # Config loader
│   ├── services/              # Business logic
│   │   ├── download_service.py
│   │   ├── context_service.py
│   │   ├── image_service.py
│   │   └── llm_service.py
│   └── venv/                  # Virtual environment
├── frontend/
│   ├── home.html              # Web UI
│   └── assets/                # Static files
├── input/
│   ├── images/                # Input images
│   └── context/               # Context files
├── output/
│   ├── alt-text/              # JSON outputs
│   └── reports/               # HTML reports
├── prompt/                    # LLM prompts
├── logs/                      # Application logs
└── docs/                      # Documentation
```

### Adding New LLM Provider

1. Create provider class in `backend/services/llm_service.py`
2. Implement `generate_alt_text()` method
3. Update config.json with provider settings
4. Add provider to `get_llm_provider()` factory

### Custom Prompts

Create new file in `prompt/`:

```txt
You are an accessibility expert. Analyze this image and provide:
1. Concise description
2. Key visual elements
3. Purpose/function
4. WCAG 2.2 compliance

Output in {language}.
```

Update config.json:
```json
{
  "prompt": {
    "files": ["my-custom-prompt.txt"]
  }
}
```

### Testing

```bash
# Unit tests
cd backend
python3 -m pytest tests/

# Integration tests
python3 -m pytest tests/integration/

# API tests
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@tests/fixtures/test.png" \
  -F "language=en"
```

### Dependencies

Core:
- fastapi, uvicorn - Web framework
- requests, beautifulsoup4 - Web scraping
- openai - LLM integration
- python-dotenv - Environment variables

Optional:
- selenium - Auto-login
- cairosvg - SVG support
- ecb_llm_client - ECB-LLM provider

---

## Supported Languages

All 24 official EU languages:

| Code | Language | Native Name |
|------|----------|-------------|
| bg | Bulgarian | Български |
| cs | Czech | Čeština |
| da | Danish | Dansk |
| de | German | Deutsch |
| el | Greek | Ελληνικά |
| en | English | English |
| es | Spanish | Español |
| et | Estonian | Eesti keel |
| fi | Finnish | Suomi |
| fr | French | Français |
| ga | Irish | Gaeilge |
| hr | Croatian | Hrvatski |
| hu | Hungarian | Magyar |
| it | Italian | Italiano |
| lt | Lithuanian | Lietuvių |
| lv | Latvian | Latviešu |
| mt | Maltese | Malti |
| nl | Dutch | Nederlands |
| pl | Polish | Polski |
| pt | Portuguese | Português |
| ro | Romanian | Română |
| sk | Slovak | Slovenčina |
| sl | Slovenian | Slovenščina |
| sv | Swedish | Svenska |

---

## License

Copyright 2025 by EXDI, European Central Bank.

All rights reserved.

---

## Support & Resources

**Documentation:**
- [CLAUDE.md](CLAUDE.md) - Developer guide
- [README.md](../README.md) - Quick start
- [U2A_AUTHENTICATION.md](U2A_AUTHENTICATION.md) - U2A auth
- [BATCH_PROCESSING_README.md](BATCH_PROCESSING_README.md) - Batch processing
- [AUTO_LOGIN_SETUP.md](AUTO_LOGIN_SETUP.md) - Auto-login
- [FASTAPI_IMPLEMENTATION.md](FASTAPI_IMPLEMENTATION.md) - API details

**Getting Help:**
1. Check documentation in `docs/` folder
2. Review logs in `logs/` directory
3. Verify configuration in `backend/config/config.json`
4. Test authentication: `curl http://localhost:8000/api/auth/status`
5. Check environment variables: `env | grep -E "CLIENT_ID|OPENAI"`

**Common Commands:**
```bash
# Server management
./start_MyAccessibilityBuddy.sh              # Start
lsof -ti:8000,3001                            # Check status
lsof -ti:8000,3001 | xargs kill              # Stop

# Testing
curl http://localhost:8000/api/health         # Health check
curl http://localhost:8000/api/auth/status    # Auth status

# Logs
tail -f logs/app.log                          # Application logs
tail -f logs/api.log                          # API logs
```

---

## Development Roadmap
This roadmap outlines planned bug fixes, functional improvements, accessibility enhancements,
testing activities, and quality validation steps for **MyAccessibilityBuddy**.

### 1. Parsing & Prompt Handling

- [ ] Fix response format parsing  
  - Properly handle cases where the response is extracted as plain text
  - Known issue:
    - ECB_Eurosystem_OneLineLogo_Mobile_EN.svg  
      https://www.ecb.europa.eu/home/html/index.en.html

- [ ] Allow multiple prompts  
  - Enable support for multiple prompts within the same workflow
  - Ensure prompt selection and ordering are explicit and traceable

- [ ] Remove hard truncation rule  
  - Remove the prompt rule that automatically truncates alt text over 125 characters
  - Delegate length control to validation and reporting layers

---

### 2. Report Generation & Filtering

- [ ] Report content filtering  
  - Allow selection of which sections are included in the final report

- [ ] Fix Summary section deletion  
  - Bug: the Summary section cannot currently be removed correctly

- [ ] Highlight alt text over 125 characters  
  - In the report, visually highlight (in red) any portion of alt text exceeding 125 characters

---

### 3. Web Interface

- [ ] Editable context metadata  
  - In the Web version, allow users to edit the context file information before generation

- [ ] Accessibility improvements (Web UI)  
  - WCAG 2.2 compliance review of the Web Interface
  - Focus areas:
    - Focus management
    - Keyboard navigation
    - Screen reader compatibility

---

### 4. Accessibility – Report Structure & Semantics

#### 4.1 Report Index & Navigation
- [ ] Generate an H2-based index
- [ ] Index container must use `aria-labelledby`
- [ ] Index links must use `<a>` elements pointing to internal section anchors

---

#### 4.2 Metadata Summary
- [ ] Replace metadata blocks with a semantic `<ul><li>` list
- [ ] Required metadata items:
  - Page Title
  - Source URL
  - AI Model
  - Total Images Analyzed
  - Total Processing Time
  - Generated timestamp  
    - Dates must use dots instead of slashes (e.g. `2025.12.10 10:16:34`)

---

#### 4.3 Image Type Distribution
- [ ] Remove `<h3>` heading
- [ ] Use plain text followed by a semantic `<ul><li>` list
- [ ] Replace visual grids or stat cards with list-based data
- [ ] Ensure data does not rely on layout or color alone

---

#### 4.4 Detailed Analysis Section
- [ ] Insert a `<section>` immediately after:
  ```html
  <h2>Detailed Analysis</h2>

**End of Documentation** 
