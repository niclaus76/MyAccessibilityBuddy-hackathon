# My Accessibility Buddy

![MyAccessibilityBuddy logo](frontend/assets/banner.png)

**AI-powered WCAG 2.2 compliant alternative text generator for web images**

MyAccessibilityBuddy helps create clear, inclusive, and WCAG 2.2-compliant content by automatically generating high-quality alternative text and accessibility-ready descriptions, supporting more inclusive digital communication for everyone.

## Features

### Three Main Use Cases
- 👨‍💼 **[For Webmasters](#for-webmasters-generate-wcag-compliant-alternate-text-for-images)**: Generate WCAG-compliant alt-text for individual images via Web UI or CLI
- 🔍 **[For Accessibility Compliance](#for-accessibility-compliance-test-generate-complete-alternative-text-reports-of-web-pages)**: Analyze entire websites and generate comprehensive accessibility reports
- 🔬 **[For AI Engineers](#for-ai-engineers-batch-prompt-comparison-tool)**: Compare and optimize prompt templates with batch testing tools

### Core Capabilities
- 🧠 **Context aware**: Uses page context to refine descriptions
- 📍 **GEO boost**: Handles geo-tagged or location-specific cues
- 🔒 **Privacy**: Use local AI models trough Ollama 
- 🤖 **AI providers**: OpenAI GPT-4o/5.1/5.2, Claude Sonnet-4/Opus-4, ECB-LLM, or Ollama (local)
- ♿ **WCAG 2.2 compliant**: Follows accessibility standards
- 🖼️ **Multi-format support**: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- 🌍 **24 EU languages**: Multilingual alt-text generation
- 🔄 **Multiple interfaces**: CLI, Web UI, REST API


## Quick Start with Docker 🐳

```bash
# 1. Setup credentials
cp backend/.env.example backend/.env
# Edit backend/.env and add your LLM keys

# 2. Start with Docker
docker compose up -d

# 3. Open in browser
# Web UI: http://localhost:8080/home.html
# API Docs: http://localhost:8000/api/docs
```

See [docs/DOCKER_QUICKSTART.md](docs/DOCKER_QUICKSTART.md) for a 3-minute guide.

## Documentation

- **[docs/DOCKER_QUICKSTART.md](docs/DOCKER_QUICKSTART.md)** - Get started in 3 minutes with Docker
- **[docs/DOCKER.md](docs/DOCKER.md)** - Complete Docker deployment guide
- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Developer guide and architecture
- **[docs/MyAccessibilityBuddy.md](docs/MyAccessibilityBuddy.md)** - Quick start examples

## Use cases

### For webmasters: generate WCAG compliant alternate text for images

Generate compliant alt-text for single images using the web interface or API. Perfect for content creators and webmasters who need quick, accessible descriptions.

#### Quick Start

```bash
# For web masters, using Web UI:
Open http://localhost:8080/home.html
1. Upload image (drag & drop or browse)
2. Select language(s)
3. Click "Generate Alt Text"

# To clean all temporary files 
docker exec myaccessibilitybuddy python3 backend/app.py --clear-all --force

Open browser DevTools (F12)
Go to Storage tab → Cookies
Delete the web_session_id cookie
Refresh the page

# To clean a spcific session
To see all available sessions:
docker exec myaccessibilitybuddy python3 backend/app.py --list-session

# For accessibility compliance tests, using CLI (Docker)
1) Download images from a URL into a folder
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -d --url https://ecb.europa.eu --images-folder /app/input/images --num-images 2 --clear-all --force

2) Extract context for a specific image from a URL
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -c --url https://ecb.europa.eu --image-name ECB_Eurosystem_OneLineLogo_Mobile_EN.svg --clear-all --force

3) Generate a JSON description starting from an image and its context
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py --legacy -g 1.png --images-folder /app/test/input/images --context-folder /app/test/input/context --language en --report --clear-all --force

4) Process all images in a folder using the context stored in another folder
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py --legacy -p --images-folder /app/test/input/images --num-images 2 --context-folder /app/test/input/context --language en --report --clear-all --force

5) Full workflow: download images and context from a given URL and generates the report
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -w --url https://ecb.europa.eu --num-images 2 --language en --report --clear-all --force 

# For AI engineers: Batch Prompt Comparison Tool
# Run with default config (compares prompts v0-v4 on test images)
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py
```

#### Configuration

Edit `backend/config/config.json` for provider and model selection:

```json
{
  "steps": {
    "vision": {"provider": "OpenAI", "model": "gpt-4o"},
    "processing": {"provider": "OpenAI", "model": "gpt-4o"}
  }
}
```

#### Example Output

```json
{
  "alt_text": "Chart showing ECB interest rates at 2.5% from 2023-2025",
  "image_type": "informative",
  "reasoning": "Chart conveys specific economic data requiring description"
}
```

### For accessibility compliance test: generate complete alternative text reports of web pages

Analyze entire websites by scraping images and generating comprehensive accessibility reports. Ideal for compliance audits and testing.

#### Quick Start

```bash
# Using CLI (Docker)
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py --url https://example.com --language en --generate-report

# Output appears in output/reports/
```

#### Configuration

Edit `backend/config/config.advanced.json` for advanced settings.

#### Example Output

**HTML Report** (`output/reports/accessibility_report_[timestamp].html`):
- Image analysis overview with statistics
- Image type distribution (decorative/informative/functional)
- Current vs. proposed alt-text comparison
- WCAG compliance recommendations
- Visual previews and detailed reasoning

### For AI engineers: Batch Prompt Comparison Tool

Compare multiple prompt templates to optimize your alt-text quality. The batch comparison tool systematically tests different prompts against test images and generates detailed comparison reports.

#### Quick Start

```bash
# Run with default config (compares prompts v0-v4 on test images)
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py

# Compare specific prompts (edit config first)
# Edit backend/config/config.advanced.json -> testing.batch_comparison.prompts
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py

# Test with more images (add to config.advanced.json)
# testing.batch_comparison.test_images: ["1.png", "2.png", "3.png", "4.png"]
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py
```

#### Configuration

Edit `backend/config/config.advanced.json` to customize your test:

```json
{
  "testing": {
    "batch_comparison": {
      "prompts": [
        {"file": "processing_prompt_v0.txt", "label": "v0: base prompt"},
        {"file": "processing_prompt_v3.txt", "label": "v3: WCAG focused"}
      ],
      "test_images": ["1.png", "2.png"],
      "test_context": ["1.txt", "2.txt"],
      "language": "en"
    }
  }
}
```

#### Example Output

The tool generates two reports:

**CSV Report** (`test/output/reports/prompt_comparison_[timestamp].csv`):
```
Image Filename,Alt Text (v0: base prompt),Alt Text (v2: WCAG focused)
1.png,"Monetary policy graphic","Illustration showing ECB monetary policy with 2% inflation target"
2.png,"Interest rate chart","Chart displaying key ECB interest rates over time"
```

**HTML Report** (`test/output/reports/prompt_comparison_[timestamp].html`):
- Side-by-side comparison of all prompts
- Accessible HTML format
- Visual preview of test images
- Character count and reasoning for each result

## Overview

### Technological innovation
The innovation lies in **rule-constrained AI orchestration** rather than model novelty.  
Accessibility standards actively guide language generation and quality control, producing outputs that are both human-readable and machine-readable.  
This approach improves consistency and quality compared to unstructured AI-generated descriptions.

### Business model
MyAccessibilityBuddy is designed to be delivered as:
- a SaaS tool for editorial and communication teams  
- an API for integration into CMSs, DAMs, and digital platforms  

Target users include **public institutions and large content publishers** subject to WCAG and European Accessibility Act requirements.  
By automating repetitive accessibility tasks while preserving human oversight, the solution reduces editorial effort, lowers compliance costs, and supports sustainable adoption at scale.

### Social impact
The tool reduces exclusion caused by missing or poor alternative text, improving access to digital content for people using assistive technologies.  
By enabling accessibility at scale, it supports participation, autonomy, and equal access to information in digital communication.

### Social innovation
MyAccessibilityBuddy reframes accessibility from a compliance obligation to **shared digital infrastructure**.  
By improving both human accessibility and machine interpretability, it aligns inclusive design with the future of AI-mediated information access.


## License

Copyright 2025 by <TEAM NAME>. All rights reserved.

## Project Information

**Created for**: Innovate for Inclusion Hackathon
**Version**: 1.0.0
**Last Updated**: January 2025
