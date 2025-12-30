# MyAccessibilityBuddy

**AI-powered WCAG 2.2 compliant alternative text generator for web images**

MyAccessibilityBuddy helps create clear, inclusive, and WCAG 2.2-compliant content by automatically generating high-quality alternative text and accessibility-ready descriptions, supporting more inclusive digital communication for everyone.

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

## Features

- 🖼️ **Multi-format support**: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- 🌍 **24 EU languages**: Multilingual alt-text generation
- 🔄 **Multiple interfaces**: CLI, Web UI, REST API
- 🤖 **AI providers**: OpenAI GPT-4o, ECB-LLM GPT-4o/5.1, or Ollama (local)
- 📊 **Batch processing**: Process multiple images at once
- 📈 **HTML reports**: Accessible reports with detailed analysis
- 🌐 **Web scraping**: Extract images and context from websites
- ♿ **WCAG 2.2 compliant**: Follows accessibility standards

## Documentation

- **[docs/DOCKER_QUICKSTART.md](docs/DOCKER_QUICKSTART.md)** - Get started in 3 minutes with Docker
- **[docs/DOCKER.md](docs/DOCKER.md)** - Complete Docker deployment guide
- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Developer guide and architecture
- **[docs/MyAccessibilityBuddy.md](docs/MyAccessibilityBuddy.md)** - Quick start examples

## Installation Options

### Option 1: Docker (Recommended)

See [docs/DOCKER_QUICKSTART.md](docs/DOCKER_QUICKSTART.md) for step-by-step instructions.

### Option 2: Local Development

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
```

See [docs/CLAUDE.md](docs/CLAUDE.md) for detailed setup instructions.

## Batch Prompt Comparison Tool

Compare multiple prompt templates to optimize your alt-text quality. The batch comparison tool systematically tests different prompts against test images and generates detailed comparison reports.

### Quick Start

```bash
# Using Docker (recommended)
docker compose exec myaccessibilitybuddy python3 /app/tools/batch_compare_prompts.py

# Or using local environment
python3 tools/batch_compare_prompts.py
```

### Configuration

Edit `backend/config/config.advanced.json` to customize your test:

```json
{
  "testing": {
    "batch_comparison": {
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

### Example Output

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

### Use Cases

1. **Prompt Optimization**: Test v0, v1, v2 prompts to find the best approach
2. **WCAG Compliance**: Verify prompts generate accessible alt-text
3. **Quality Assurance**: Ensure consistency across image types
4. **A/B Testing**: Compare different prompt engineering strategies

See [docs/CLAUDE.md](docs/CLAUDE.md) for detailed configuration options.

## License

Copyright 2025 by <TEAM NAME>. All rights reserved.

## Project Information

**Created for**: Innovate for Inclusion Hackathon
**Version**: 1.0.0
**Last Updated**: January 2025
