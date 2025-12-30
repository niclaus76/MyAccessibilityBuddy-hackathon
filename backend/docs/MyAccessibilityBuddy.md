# MyAccessibilityBuddy - Complete Documentation

**Version:** 1.0.0  
**Last Updated:** December 2025  
**Copyright:** 2025 by Nicola.Caione@bancaditalia.it

## Overview

MyAccessibilityBuddy is an AI-powered tool that generates WCAG 2.2 Level AA compliant alternative text for web images. It automates the creation of accessible alt-text using OpenAI GPT-4o or ECB-LLM GPT-5.1, supporting all 24 official EU languages.

⚠️ **For testing purposes only**: Use with non-confidential images. Avoid uploading personal or sensitive data. AI-generated alt-text suggestions require human review before production use. ⚠️

### Key Features

- **🖼️ Multi-Format Image Support**: JPG, JPEG, PNG, GIF, WEBP, SVG, BMP, TIFF
- **🌍 24 EU Languages**: All official European Union languages with dual translation modes
- **🔐 Flexible Authentication**: U2A OAuth2 for ECB-LLM, API key for OpenAI
- **📊 Intelligent Image Classification**: Informative, Decorative, or Functional
- **📝 Context-Aware Analysis**: Automatic web page context extraction
- **📈 Accessible HTML Reports**: WCAG-compliant reports with ARIA markup
- **🚀 RESTful API**: FastAPI with OpenAPI/Swagger documentation
- **🤖 Dual LLM Support**: OpenAI GPT-4o or ECB-LLM GPT-5.1

### Architecture

```
┌──────────────────────────────────────────────────┐
│           Frontend (Bootstrap Italia)            │
│  file:///AutoAltText/frontend/home.html         │
└───────────────────┬──────────────────────────────┘
                    │ HTTP/REST API
                    ▼
┌──────────────────────────────────────────────────┐
│        FastAPI Server (Port 8000)               │
│  ├─ Alt-text generation endpoint                │
│  ├─ Authentication & session management         │
│  └─ OAuth2 redirect handler                     │
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

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Configuration](#configuration)
3. [Core Functions](#core-functions)
4. [CLI Usage](#cli-usage)
5. [Web UI Usage](#web-ui-usage)
6. [API Usage](#api-usage)
7. [Translation Modes](#translation-modes)
8. [Context Extraction](#context-extraction)
9. [Batch Processing](#batch-processing)
10. [HTML Report Generation](#html-report-generation)
11. [Troubleshooting](#troubleshooting)
12. [API Reference](#api-reference)
13. [Development Roadmap](#development-roadmap)
---

## Installation & Setup

### Prerequisites

- **Python 3.12+** (tested on 3.12.7)
- **Internet connection** for LLM API access
- **OpenAI API key** OR **ECB credentials** (for ECB-LLM)
- **Optional**: Chrome/Chromium browser (no longer required as A2A auto-login removed)

### Step 1: Clone and Setup Environment

```bash
cd /path/to/AutoAltText

# Create virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create `.env` file in `backend/` directory:

```bash
# backend/.env

# For OpenAI (recommended for testing)
OPENAI_API_KEY=sk-proj-your-api-key-here

# OR for ECB-LLM (requires ECB credentials)
CLIENT_ID_U2A=ap-AutoAltText82ad91cd-960a-4e8b-aa22-8
CLIENT_SECRET_U2A=your-client-secret
ECB_USERNAME=your-ecb-username
ECB_PASSWORD=your-ecb-password
```

### Step 3: Configure Application

Edit `backend/config/config.json`:

```json
{
  "debug_mode": false,
  "logging": {
    "show_debug": false,
    "show_information": false,
    "show_warnings": true,
    "show_errors": true
  },
  "llm_provider": "OpenAI",
  "model": "gpt-4o",
  "translation_mode": "fast"
}
```

### Step 4: Verify Installation

```bash
cd backend
python3 app.py --help

# Expected output: Help message with all commands

# Test with single image
cp ../test/images/1.png ../input/images/
python3 app.py -g 1.png --language en
```

---

## Configuration

Configuration file: `backend/config/config.json`

### Essential Settings

```json
{
  "_comment_debug": "true or false - enables detailed debug logging to files",
  "debug_mode": false,
  
  "_comment_logging": "Control console output by log level: DEBUG (technical details), INFORMATION (informational messages), WARNING (warnings/potential issues), ERROR (errors/failures)",
  "logging": {
    "show_debug": false,         // DEBUG level: Technical details for debugging
    "show_information": false,   // INFORMATION level: Progress updates and informational messages
    "show_warnings": true,       // WARNING level: Potential issues
    "show_errors": true          // ERROR level: Failures and errors
  },
  
  "_comment_llm": "llm_provider: OpenAI or ECB-LLM (U2A OAuth2 authentication only)",
  "llm_provider": "OpenAI",
  
  "_comment_model": "model: gpt-4o (for OpenAI) or gpt-5.1 (for ECB-LLM only)",
  "model": "gpt-4o",
  
  "_comment_translation_mode": "translation_mode: 'fast' (generate once in first language, then translate) or 'accurate' (generate fresh alt-text for each language). 'fast' is recommended for cost/speed.",
  "translation_mode": "fast",
  
  "_comment_ecb_llm": "ECB-LLM U2A OAuth2 configuration: token_url, scope, login_url (used by Web UI FastAPI)",
  "ecb_llm": {
    "token_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/token",
    "scope": "openid profile LLM.api.read",
    "login_url": "https://igam.escb.eu/oamsso-bin/login.pl"
  },
  
  "folders": {
    "images": "input/images",
    "context": "input/context",
    "alt_text": "output/alt-text",
    "reports": "output/reports",
    "prompt": "prompt",
    "logs": "logs"
  },
  
  "download": {
    "_comment": "timeout: request timeout in seconds, delay_between_requests: delay between image downloads to avoid rate limiting",
    "timeout": 30,
    "delay_between_requests": 3,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  },
  
  "context": {
    "_comment": "Context extraction configuration",
    "max_text_length": 1000,
    "max_parent_levels": 5,
    "min_text_length": 20,
    "max_sibling_text_length": 500
  },
  
  "prompt": {
    "_comment": "Prompt template configuration",
    "files": ["alt-text-improved.txt"],
    "merge_separator": "\n\n---\n\n",
    "default_prompt": "base_prompt.txt"
  },
  
  "languages": {
    "_comment": "Supported languages for alt-text generation (EU official languages)",
    "allowed": [
      {"code": "en", "name": "English"},
      {"code": "de", "name": "Deutsch"},
      // ... 22 more languages
    ],
    "default": "en"
  }
}
```

### LLM Provider Options

**OpenAI Configuration:**
```json
{
  "llm_provider": "OpenAI",
  "model": "gpt-4o"
}
```
- **Authentication**: API key via `OPENAI_API_KEY` environment variable
- **Model**: gpt-4o (recommended), gpt-4-turbo, gpt-3.5-turbo
- **Cost**: Pay-per-token pricing
- **Setup**: Quick, only requires API key

**ECB-LLM Configuration:**
```json
{
  "llm_provider": "ECB-LLM",
  "model": "gpt-5.1",
  "ecb_llm": {
    "token_url": "https://igam.escb.eu/igam-oauth/oauth2/rest/token",
    "scope": "openid profile LLM.api.read",
    "login_url": "https://igam.escb.eu/oamsso-bin/login.pl"
  }
}
```
- **Authentication**: U2A OAuth2 with ECB credentials
- **Models**: gpt-4o, gpt-5, gpt-5-mini, gpt-5.1
- **Cost**: Internal ECB quota system
- **Setup**: Requires ECB credentials and client registration

---

## Core Functions

### 1. Image Download (`download_images_from_url`)

**Location**: `backend/app.py:1397-1514`

**Purpose**: Downloads images from a webpage URL for processing.

**How it works**:
1. Fetches HTML content from provided URL
2. Parses HTML with BeautifulSoup4
3. Searches for images in configured tags and attributes:
   - `<img src="...">`, `<img data-src="...">`
   - `<picture>` elements
   - `<div>` with data-image attributes
   - `<link rel="icon">` (favicons)
   - `<meta property="og:image">` (Open Graph)
   - CSS background images
4. Filters out small images, favicons, and icons
5. Downloads images with configurable delay between requests
6. Saves to `input/images/` folder
7. Stores metadata (URL, tag, attribute) for context extraction

**Parameters**:
- `url` (str): Web page URL to scrape
- `output_folder` (str): Destination folder (default: from config)
- `max_images` (int): Maximum images to download (default: unlimited)

**Configuration**:
```json
{
  "download": {
    "timeout": 30,                    // HTTP request timeout
    "delay_between_requests": 3       // Delay between downloads (avoid rate limiting)
  },
  "image_extraction": {
    "tags": {
      "img": true,
      "picture": true,
      "div": true,
      "link": true,
      "meta": true
    },
    "attributes": {
      "src": true,
      "data-src": true,
      "srcset": true,
      "href": true,
      "content": true
    },
    "css_background_images": true
  }
}
```

**Example**:
```bash
# Download all images from ECB homepage
python3 app.py -d https://www.ecb.europa.eu/home/html/index.en.html

# Download max 5 images
python3 app.py -d https://example.com --num-images 5
```

**Output**: Images saved to `input/images/` with metadata stored internally

---

### 2. Context Extraction (`grab_context`)

**Location**: `backend/app.py:1517-1708`

**Purpose**: Extracts surrounding context from webpage to help AI understand image purpose.

**How it works**:
1. Fetches webpage HTML
2. Locates the specific `<img>` tag by matching image filename
3. Traverses up the DOM tree (parent elements) configurable levels
4. Collects contextual information:
   - **Alt text** from `<img alt="...">`
   - **Title** from `<img title="...">`
   - **Headings** (h1-h6) from parent containers
   - **Section text** from `<section>`, `<article>`, `<main>`, `<div>`
   - **Captions** from `<figcaption>`
   - **Sibling text** from adjacent `<p>`, `<span>` elements
5. Formats context with "Part N:" labels
6. Saves to `input/context/<filename>.txt`

**Structured Context Format**:
```
Part 1: Current alt text from img tag.

Part 2: Heading from parent section.

Part 3: Surrounding paragraph text.

Part 4: Caption from figcaption element.
```

**Parameters**:
- `url` (str): Webpage URL
- `image_filename` (str): Image filename to find
- `output_folder` (str): Destination for context file

**Configuration**:
```json
{
  "context": {
    "max_text_length": 1000,          // Max chars per context element
    "max_parent_levels": 5,           // How far up DOM tree to search
    "min_text_length": 20,            // Minimum text length to include
    "max_sibling_text_length": 500   // Max text from sibling elements
  }
}
```

**Example**:
```bash
# Extract context for specific image
python3 app.py -c https://www.ecb.europa.eu/press/blog/ blog_logo.png

# Context saved to: input/context/blog_logo.txt
```

**Output**: Text file with structured context in `input/context/`

---

### 3. Alt-Text Generation (`generate_alt_text_json`)

**Location**: `backend/app.py:2013-2280`

**Purpose**: Generates WCAG 2.2 compliant alt-text using AI vision models.

**How it works**:
1. Loads image from `input/images/`
2. Loads context file from `input/context/` (if exists)
3. Loads prompt template from `prompt/`
4. Determines language mode (single or multilingual)
5. For **single language**:
   - Sends image + context + prompt to LLM
   - Receives structured JSON response
   - Extracts alt-text, image type, reasoning
6. For **multilingual** (see Translation Modes section)
7. Validates alt-text (max 125 characters, ends with period)
8. Creates comprehensive JSON output
9. Saves to `output/alt-text/<filename>.json`

**AI Image Classification**:
- **Informative**: Conveys information (charts, diagrams, logos with text)
- **Decorative**: Purely aesthetic (background patterns, decorative borders)
  - Alt-text = empty string `""`
- **Functional**: Interactive elements (buttons, links as images)

**Parameters**:
- `image_filename` (str): Image to process
- `target_languages` (list): ISO language codes (e.g., ['en', 'it', 'de'])
- `url` (str, optional): Source webpage URL
- `page_title` (str, optional): Page title for metadata

**Output JSON Structure**:
```json
{
  "web_site_url": "https://example.com",
  "page_title": "Example Page",
  "image_id": "logo.png",
  "image_type": "informative",
  "image_context": "Part 1: Company logo...",
  "image_URL": "https://example.com/logo.png",
  "image_tag_attribute": {
    "tag": "img",
    "attribute": "src"
  },
  "language": ["en", "it"],
  "reasoning": [
    ["EN", "This logo identifies the organization..."],
    ["IT", "Questo logo identifica l'organizzazione..."]
  ],
  "extended_description": "Detailed description if needed",
  "current_alt_text": "Current alt text from webpage",
  "proposed_alt_text": [
    ["EN", "Company logo."],
    ["IT", "Logo aziendale."]
  ],
  "proposed_alt_text_length": [
    ["EN", 13],
    ["IT", 17]
  ],
  "ai_model": {
    "provider": "OpenAI",
    "model": "gpt-4o"
  },
  "translation_method": "fast",
  "processing_time_seconds": 5.2
}
```

**Example**:
```bash
# Single language
python3 app.py -g logo.png --language en

# Multiple languages (uses translation_mode from config)
python3 app.py -g chart.png --language en de fr it
```

---

### 4. Batch Processing (`process_all_images`)

**Location**: `backend/app.py:1877-1955`

**Purpose**: Processes all images in `input/images/` folder in one operation.

**How it works**:
1. Scans `input/images/` for all image files
2. For each image:
   - Checks for matching context file
   - Loads context if available
   - Calls `generate_alt_text_json()`
   - Saves JSON output
3. Tracks success/failure counts
4. Optionally generates HTML report at end
5. Provides progress updates during processing

**Features**:
- Automatic context matching by filename
- Graceful error handling (continues on failures)
- Progress indicators with counters
- Summary statistics at completion
- Optional HTML report generation

**Example**:
```bash
# Process all with English alt-text
python3 app.py -p --language en

# Process with multiple languages and report
python3 app.py -p --language en it de --report

# Process all test images
cp test/images/*.png input/images/
cp test/context/*.txt input/context/
python3 app.py -p --language en --report
```

**Output**: 
- `output/alt-text/*.json` - One JSON per image
- `output/reports/*.html` - HTML report (if `--report` flag used)

---

### 5. Complete Workflow (`workflow`)

**Location**: `backend/app.py:1958-2010`

**Purpose**: Executes full pipeline: download → context extraction → alt-text generation.

**How it works**:
1. **Download phase**: Downloads images from URL
2. **Context extraction phase**: Extracts context for each downloaded image
3. **Generation phase**: Generates alt-text for all images
4. **Report phase** (optional): Creates HTML summary

**Steps**:
```
URL Input
   │
   ▼
Download Images ──> input/images/*.{jpg,png,svg}
   │
   ▼
Extract Context ──> input/context/*.txt
   │
   ▼
Generate Alt-Text ──> output/alt-text/*.json
   │
   ▼
Generate Report ──> output/reports/*.html
```

**Example**:
```bash
# Full workflow with report
python3 app.py -w https://www.ecb.europa.eu/press/blog/ --language en --report

# Workflow with multiple languages, limit 10 images
python3 app.py -w https://example.com --language en it --num-images 10 --report
```

**Output**: Complete set of downloaded images, context files, JSON outputs, and HTML report

---

### 6. HTML Report Generation (`generate_html_report`)

**Location**: `backend/app.py:382-646`

**Purpose**: Creates accessible HTML summary report of all processed images.

**How it works**:
1. Loads template from `output/reports/report_template.html`
2. Scans `output/alt-text/` for all JSON files
3. For each JSON:
   - Reads all metadata
   - Loads corresponding image for preview
   - Converts image to base64 data URI
   - Generates HTML card with all details
4. Compiles statistics:
   - Image type distribution (informative/decorative/functional)
   - HTML tag usage (img/picture/div/etc.)
   - Attribute distribution (src/data-src/etc.)
5. Creates accessible HTML with:
   - Skip-to-content link
   - ARIA landmarks
   - Semantic headings
   - Embedded image previews
6. Saves to `output/reports/MyAccessibilityBuddy-AltTextReport.html`

**Report Contents**:
- **Header**: Logo, page title, source URL
- **Summary Section**: AI model used, processing time, translation method
- **Statistics**: Image type counts, tag/attribute breakdown
- **Detailed Analysis**: For each image:
  - Image preview (embedded base64)
  - Image type badge
  - Proposed alt-text (all languages)
  - Current alt-text from webpage
  - HTML tag and attribute
  - Reasoning (why this classification)
  - Context (surrounding page text)

**Accessibility Features**:
- WCAG 2.2 Level AA compliant
- Semantic HTML5 structure
- ARIA landmarks (`<main>`, `<nav>`, roles)
- Skip-to-content link for keyboard users
- Proper heading hierarchy
- High contrast colors
- Focus indicators

**Example**:
```bash
# Generate report from existing JSON files
python3 app.py -p --language en --report

# Report location
xdg-open output/reports/MyAccessibilityBuddy-AltTextReport.html
```

**Output**: Fully accessible HTML report with embedded images and complete metadata

---

## CLI Usage

### Command Structure

```bash
python3 app.py [ACTION] [ARGUMENTS] [OPTIONS]
```

### Actions (Mutually Exclusive)

| Flag | Action | Description |
|------|--------|-------------|
| `-d` | Download | Download images from URL |
| `-c` | Context | Extract context for specific image |
| `-g` | Generate | Generate alt-text for single image |
| `-p` | Process All | Batch process all images in folder |
| `-w` | Workflow | Complete pipeline (download→context→generate) |
| `-al` | List Languages | Show all 24 supported languages |
| `--help-topic` | Help | Show detailed help for specific topic |

### Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `--language LANG [LANG...]` | One or more ISO language codes | `--language en it de` |
| `--num-images N` | Max images to download | `--num-images 10` |
| `--report` | Generate HTML report after processing | `--report` |
| `--clear-all` | Clear all folders (input + output + logs) | `--clear-all` |
| `--clear-inputs` | Clear input folders (images, context) | `--clear-inputs` |
| `--clear-outputs` | Clear output folders (alt-text, reports) | `--clear-outputs` |
| `--clear-log` | Clear log files | `--clear-log` |

### Folder Override Options

| Option | Description | Default |
|--------|-------------|---------|
| `--images-folder PATH` | Custom images folder | `input/images` |
| `--context-folder PATH` | Custom context folder | `input/context` |
| `--prompt-folder PATH` | Custom prompt folder | `prompt` |
| `--alt-text-folder PATH` | Custom output folder | `output/alt-text` |

### Detailed Examples

**Download Images**:
```bash
# Download all images
python3 app.py -d https://www.ecb.europa.eu

# Download max 5 images
python3 app.py -d https://example.com --num-images 5

# Download to custom folder
python3 app.py -d https://example.com --images-folder /tmp/myimages
```

**Extract Context**:
```bash
# Extract context for one image
python3 app.py -c https://www.ecb.europa.eu logo.svg

# With custom output folder
python3 app.py -c https://example.com photo.jpg --context-folder /tmp/context
```

**Generate Alt-Text**:
```bash
# Single language (English)
python3 app.py -g image.png --language en

# Multiple languages
python3 app.py -g chart.jpg --language en de fr it es

# Without context file (image only)
python3 app.py -g icon.png --language en
```

**Batch Processing**:
```bash
# Process all images with English
python3 app.py -p --language en

# Multiple languages with report
python3 app.py -p --language en it de --report

# Custom folders
python3 app.py -p --language en \
  --images-folder /data/images \
  --alt-text-folder /data/output \
  --report
```

**Complete Workflow**:
```bash
# Standard workflow
python3 app.py -w https://www.ecb.europa.eu --language en --report

# Limit images, multiple languages
python3 app.py -w https://example.com \
  --language en de fr \
  --num-images 10 \
  --report
```

**Utilities**:
```bash
# List all supported languages
python3 app.py -al

# Get detailed help on workflow
python3 app.py --help-topic workflow

# Clear everything
python3 app.py --clear-all

# Clear only outputs
python3 app.py --clear-outputs
```

---

## Web UI Usage

### Starting the Web UI

```bash
# Start both API server (8000) and OAuth callback (3001)
./start_MyAccessibilityBuddy.sh

# Browser opens automatically to frontend/home.html
# API docs available at: http://localhost:8000/api/docs
```

### Features

**Image Upload**:
- Drag & drop or click to browse
- Real-time preview before processing
- Supported formats: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- Max file size: Configurable (default: reasonable limits)

**Context Upload** (Optional):
- Upload `.txt` file with surrounding page context
- Improves AI understanding of image purpose
- Format: Plain text or "Part N:" structured format

**Language Selection**:
- Dropdown with all 24 EU languages
- Shows native language names
- Default: English
- Supports multiple selections (future enhancement)

**Results Display**:
- Editable text area with generated alt-text
- Copy button for quick clipboard copy
- Decorative image detection (shows "Empty alt-text recommended")
- Visual feedback during processing (loading spinner)
- Error handling with user-friendly messages

### Authentication Flow (ECB-LLM Only)

For ECB-LLM provider, first-time users go through OAuth2 flow:

1. User clicks "Generate Alt Text"
2. Frontend detects no session
3. Redirects to `/api/auth/redirect`
4. Backend generates OAuth2 URL with state token
5. User redirected to ECB login page (IGAM)
6. User enters ECB credentials
7. ECB redirects to `http://localhost:3001/callback?code=XXX`
8. Backend validates state, exchanges code for token
9. Token stored in session cookie (HTTP-only, 1 hour expiry)
10. User redirected back to frontend
11. Frontend retries alt-text generation (now authenticated)

**Session Duration**: 1 hour (sliding window with token refresh)

**For OpenAI**: No authentication UI needed - uses API key from environment

---

## Translation Modes

MyAccessibilityBuddy supports two translation strategies for multilingual alt-text generation.

### Fast Mode (Default - Recommended)

**Configuration**:
```json
{
  "translation_mode": "fast"
}
```

**How it works**:
1. Analyze image **once** in first language (e.g., English)
2. Generate full alt-text with reasoning
3. For each additional language:
   - Translate alt-text via LLM translation API
   - Translate reasoning via LLM translation API
4. Return all languages in single JSON

**Process Flow**:
```
Image + Context
      │
      ▼
[LLM Analysis in EN] ──> "ECB logo."
      │
      ├──> [Translate to IT] ──> "Logo ECB."
      │
      ├──> [Translate to DE] ──> "EZB-Logo."
      │
      └──> [Translate to FR] ──> "Logo BCE."
```

**Advantages**:
- **Faster**: 1 image analysis + N-1 translations
- **Cheaper**: Translation costs less than image analysis
- **Consistent**: Same core meaning across languages
- **Efficient**: Best for similar languages (EN, ES, IT, FR, DE)

**LLM API Calls**:
- For 3 languages: 1 analysis + 4 translations = **5 API calls**
- For 5 languages: 1 analysis + 8 translations = **9 API calls**

**Example**:
```bash
# config.json: "translation_mode": "fast"
python3 app.py -g logo.png --language en it de

# Processing time: ~5 seconds
# Cost: Low (1 vision call + 4 text calls)
```

### Accurate Mode

**Configuration**:
```json
{
  "translation_mode": "accurate"
}
```

**How it works**:
1. Analyze image **separately for each language**
2. Each analysis is independent with full context
3. LLM generates culturally appropriate alt-text per language
4. No translation needed - native generation

**Process Flow**:
```
Image + Context
      │
      ├──> [LLM Analysis in EN] ──> "ECB logo."
      │
      ├──> [LLM Analysis in IT] ──> "Logo della Banca Centrale Europea."
      │
      ├──> [LLM Analysis in DE] ──> "Logo der Europäischen Zentralbank."
      │
      └──> [LLM Analysis in FR] ──> "Logo de la Banque Centrale Européenne."
```

**Advantages**:
- **Better Quality**: Native generation per language
- **Cultural Adaptation**: Idioms and cultural context
- **Language-Specific**: Different phrasing conventions
- **Best for**: Dissimilar languages (EN, FI, HU, EL)

**LLM API Calls**:
- For 3 languages: 3 image analyses = **3 API calls**
- For 5 languages: 5 image analyses = **5 API calls**

**Example**:
```bash
# config.json: "translation_mode": "accurate"
python3 app.py -g infographic.png --language en fi hu

# Processing time: ~15 seconds
# Cost: Higher (3 vision calls)
```

### Comparison Table

| Aspect | Fast Mode | Accurate Mode |
|--------|-----------|---------------|
| **Speed** | ⚡ Fast (5s for 3 langs) | 🐌 Slower (15s for 3 langs) |
| **Cost** | 💰 Low | 💰💰 Higher |
| **Quality** | ✅ Good for similar langs | ✅✅ Excellent for all langs |
| **API Calls** | 1 vision + 2N text | N vision calls |
| **Use Case** | Batch processing, similar languages | Critical content, dissimilar languages |
| **Consistency** | Same meaning across langs | May vary slightly per language |

### Recommendation

- **Start with `"fast"`** - Works well for most European languages
- **Switch to `"accurate"`** for:
  - High-profile public content
  - Languages with different script/structure (Greek, Hungarian)
  - Cultural idioms matter
  - Quality over speed/cost

---

## Context Extraction

Context extraction helps the AI understand the purpose and function of an image by analyzing surrounding webpage content.

### How It Works

**DOM Traversal Algorithm**:
1. Start at `<img>` tag
2. Traverse **upward** through parent elements
3. At each parent level, collect:
   - Headings (h1-h6)
   - Section text (<section>, <article>, <main>)
   - Captions (<figcaption>)
   - Adjacent text from siblings
4. Stop when limits reached:
   - Max parent levels
   - Max text length (1000 chars)
   - Max headings collected

**Extraction Priority** (order of importance):
1. Current alt text (`<img alt="...">`)
2. Image title (`<img title="...">`)
3. Parent headings (h1-h6)
4. Section/article text
5. Figcaption
6. Sibling paragraphs

### Structured Output Format

Context files use "Part N:" labeling for clarity:

```
Part 1: Current alt text from img tag.

Part 2: Heading from parent section.

Part 3: Surrounding paragraph text with relevant info.

Part 4: Caption text if figcaption exists.
```

**Benefits**:
- AI can reference specific parts
- Human-readable for review
- Consistent format regardless of complexity

### Configuration

```json
{
  "context": {
    "max_text_length": 1000,          // Max chars per element
    "max_parent_levels": 5,           // How far up DOM tree
    "min_text_length": 20,            // Ignore short text
    "max_sibling_text_length": 500   // Max from siblings
  }
}
```

### Example

**HTML Structure**:
```html
<article>
  <h1>The ECB Blog</h1>
  <section>
    <h2>December 2025</h2>
    <p>Latest updates on monetary policy.</p>
    <figure>
      <img src="blog_logo.png" alt="Blog logo">
      <figcaption>Official ECB Blog logo</figcaption>
    </figure>
  </section>
</article>
```

**Extracted Context** (`input/context/blog_logo.txt`):
```
Part 1: Blog logo.

Part 2: The ECB Blog.

Part 3: December 2025.

Part 4: Latest updates on monetary policy.

Part 5: Official ECB Blog logo.
```

**CLI Usage**:
```bash
python3 app.py -c https://www.ecb.europa.eu/press/blog/ blog_logo.png

# Output: input/context/blog_logo.txt
```

---

## HTML Report Generation

### Report Contents

The HTML report (`output/reports/MyAccessibilityBuddy-AltTextReport.html`) provides a comprehensive, accessible summary of all processed images.

**Sections**:

1. **Header**
   - Logo (if available)
   - Page title
   - Source URL (clickable link)

2. **Summary**
   - AI Provider and Model used
   - Translation Method (Fast/Accurate/None)
   - Total Images Processed
   - Total Processing Time
   - Generation Timestamp (CET)

3. **Statistics**
   - Image Type Distribution:
     - Informative: N images
     - Decorative: N images
     - Functional: N images
     - Generation Errors: N images
   - HTML Tag Usage:
     - <img>: N images
     - <picture>: N images
     - <div>: N images
   - Attribute Distribution:
     - src: N images
     - data-src: N images
     - srcset: N images

4. **Detailed Analysis** (Per Image)
   - Image Preview (embedded base64)
   - Image Filename
   - Image Type badge (color-coded)
   - **Proposed Alt-Text** (all languages if multilingual)
   - **Current Alt-Text** (from webpage)
   - **Image HTML Tag or Attribute** (e.g., "Tag: <img>, Attribute: src")
   - **Reasoning** (AI explanation for classification)
   - **Context** (surrounding page text, truncated to 500 chars)

### Accessibility Features

**WCAG 2.2 Level AA Compliance**:
- ✅ Skip-to-content link (keyboard navigation)
- ✅ Semantic HTML5 structure
- ✅ ARIA landmarks (`<main>`, `<nav>`, `role="article"`)
- ✅ Proper heading hierarchy (h1→h2→h3)
- ✅ High contrast text (4.5:1 minimum)
- ✅ Focus indicators for interactive elements
- ✅ Descriptive link text
- ✅ Alt text for all embedded images
- ✅ Responsive design (mobile-friendly)

**Styling**:
- Bootstrap Italia color scheme
- Color-coded image type badges:
  - 🟢 Informative (green)
  - 🔴 Decorative (red)
  - 🔵 Functional (blue)
  - 🟡 Generation Error (yellow)
- Embedded image previews (max 400px width)
- Scrollable context sections (max 150px height)
- Print-friendly layout

### Generation

**Automatic**:
```bash
# Report generated automatically with --report flag
python3 app.py -w https://example.com --language en --report
python3 app.py -p --language en it --report
```

**Manual**:
```bash
# Generate report from existing JSON files
python3 app.py -p --report  # No processing, just report
```

**Output Location**:
- Default: `output/reports/MyAccessibilityBuddy-AltTextReport.html`
- With page title: `output/reports/MyAccessibilityBuddy-AltTextReport-The-ECB-Blog.html`

### Viewing

```bash
# Linux
xdg-open output/reports/MyAccessibilityBuddy-AltTextReport.html

# macOS
open output/reports/MyAccessibilityBuddy-AltTextReport.html

# Windows
start output/reports/MyAccessibilityBuddy-AltTextReport.html
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Errors

**Problem**: "CLIENT_ID_U2A not found in environment variables"

**Solution**:
```bash
# Check if .env file exists
ls -la backend/.env

# Verify environment variables are loaded
cd backend
source venv/bin/activate
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('CLIENT_ID_U2A'))"

# If None, create/edit .env file
nano backend/.env
```

**Problem**: "OpenAI API key not found"

**Solution**:
```bash
# Set environment variable
export OPENAI_API_KEY="sk-your-api-key"

# Or add to backend/.env
echo "OPENAI_API_KEY=sk-your-api-key" >> backend/.env
```

#### 2. Image Processing Errors

**Problem**: "No images found in input/images/"

**Solution**:
```bash
# Check directory exists
ls -la input/images/

# Copy test images
cp test/images/*.png input/images/

# Verify permissions
chmod 755 input/images/
```

**Problem**: "SVG conversion failed"

**Solution**:
```bash
# Install cairosvg for SVG support
pip install cairosvg

# Or convert SVG to PNG manually
convert logo.svg logo.png  # Using ImageMagick
```

#### 3. Rate Limiting

**Problem**: "429 Too Many Requests"

**Solution**:
```json
// Increase delay in config.json
{
  "download": {
    "delay_between_requests": 5  // Increase from 3 to 5 seconds
  }
}
```

#### 4. Empty or Invalid Responses

**Problem**: "ECB-LLM returned None response" or "Translation error"

**Check logs**:
```bash
tail -f logs/*.log

# Look for lines like:
# [ERROR] ECB-LLM returned None response
# [ERROR] Full API response: ...
```

**Solutions**:
- Verify ECB-LLM credentials are correct
- Check if ECB-LLM service is available
- Try switching to OpenAI temporarily:
  ```json
  {"llm_provider": "OpenAI", "model": "gpt-4o"}
  ```
- Check model compatibility (gpt-5.1 vs gpt-4o)

#### 5. Server Issues

**Problem**: "Address already in use" (port 8000 or 3001)

**Solution**:
```bash
# Find process using port
lsof -ti:8000

# Kill process
lsof -ti:8000 | xargs kill

# Or kill both ports
lsof -ti:8000,3001 | xargs kill
```

**Problem**: "CORS errors" in browser console

**Solution**:
- API already configured to allow all origins
- Check browser console for specific error
- Verify API_BASE_URL in frontend matches server
- Clear browser cache and retry

#### 6. Context Extraction Issues

**Problem**: Context file is empty or too large

**Solution**:
```json
// Adjust context extraction limits in config.json
{
  "context": {
    "max_text_length": 500,        // Reduce if too large
    "max_parent_levels": 3,        // Reduce if getting too much
    "min_text_length": 10          // Lower to capture more
  }
}
```

### Debug Mode

Enable detailed logging for troubleshooting:

```json
{
  "debug_mode": true,
  "logging": {
    "show_debug": true,
    "show_information": true,
    "show_warnings": true,
    "show_errors": true
  }
}
```

**View debug logs**:
```bash
tail -f logs/20251212_*.log

# Logs show:
# - HTTP requests and responses
# - LLM API calls and responses
# - Image processing steps
# - Context extraction details
# - Translation attempts
```

---

## API Reference

Complete REST API documentation available at: `http://localhost:8000/api/docs`

### Base URL

```
http://localhost:8000
```

### Authentication

**For OpenAI**: No API-level authentication required (uses environment variable)

**For ECB-LLM**: Session-based OAuth2 authentication
- First request redirects to OAuth2 flow
- Session cookie stored for 1 hour
- Automatic token refresh

### Endpoints

#### 1. Generate Alt-Text

**Endpoint**: `POST /api/generate-alt-text`

**Description**: Generate WCAG-compliant alt-text for an uploaded image.

**Request**:
- Method: POST
- Content-Type: `multipart/form-data`
- Body Parameters:
  - `image` (file, required): Image file to analyze
  - `language` (string, required): ISO language code (e.g., "en", "it")
  - `context` (string, optional): Surrounding text context

**Example Request** (curl):
```bash
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@test/images/1.png" \
  -F "language=en" \
  -F "context=ECB homepage logo"
```

**Example Request** (Python):
```python
import requests

url = "http://localhost:8000/api/generate-alt-text"
files = {"image": open("test/images/1.png", "rb")}
data = {"language": "en", "context": "Homepage banner"}

response = requests.post(url, files=files, data=data)
print(response.json())
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "alt_text": "European Central Bank logo.",
  "is_decorative": false,
  "language": "en",
  "model": "gpt-4o",
  "provider": "OpenAI",
  "timestamp": "2025-12-12T14:30:00Z",
  "processing_time": 4.2
}
```

**Error Response** (400/401/500):
```json
{
  "success": false,
  "error": "Error message",
  "detail": "Detailed error information"
}
```

#### 2. Check Authentication Status

**Endpoint**: `GET /api/auth/status`

**Description**: Check if user is authenticated and what auth is required.

**Example Request**:
```bash
curl http://localhost:8000/api/auth/status
```

**Response**:
```json
{
  "authenticated": true,
  "requires_u2a": false,
  "llm_provider": "OpenAI",
  "has_credentials": true
}
```

#### 3. Initiate OAuth2 Login

**Endpoint**: `GET /api/auth/redirect`

**Description**: Redirects to ECB OAuth2 login page (ECB-LLM only).

**Example**:
```bash
# Browser navigation
http://localhost:8000/api/auth/redirect

# Returns: HTTP 307 redirect to ECB IGAM login
```

#### 4. OAuth2 Callback

**Endpoint**: `GET /callback` (Port 3001)

**Description**: Receives OAuth2 authorization code and exchanges for token.

**Parameters**:
- `code` (query): Authorization code from OAuth2 provider
- `state` (query): CSRF protection token

**Response**: HTML page with session cookie set, redirects to frontend

#### 5. Health Check

**Endpoint**: `GET /api/health`

**Description**: Server health status.

**Example**:
```bash
curl http://localhost:8000/api/health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-12T14:30:00Z",
  "version": "1.0.0"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid parameters (missing image, invalid language) |
| 401 | Unauthorized | Authentication required (ECB-LLM only) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (check logs) |

---

## License

Copyright 2025 by European Central Bank.

All rights reserved.

---

## Support

**Documentation**:
- [README.md](../README.md) - Quick start guide
- [CLAUDE.md](CLAUDE.md) - Developer reference

**Common Commands**:
```bash
# Server management
./start_MyAccessibilityBuddy.sh              # Start
lsof -ti:8000,3001                            # Check status
lsof -ti:8000,3001 | xargs kill              # Stop

# Testing
curl http://localhost:8000/api/health         # Health check
curl http://localhost:8000/api/auth/status    # Auth status
python3 app.py --help                          # CLI help

# Logs
tail -f logs/*.log                             # Live logs
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