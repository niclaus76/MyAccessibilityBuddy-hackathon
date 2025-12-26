# MyAccessibilityBuddy

**AI-powered WCAG 2.2 compliant alternative text generator for web images**

MyAccessibilityBuddy helps create clear, inclusive, and WCAG 2.2-compliant content by automatically generating high-quality alternative text and accessibility-ready descriptions, supporting more inclusive digital communication for everyone.

## Quick Start with Docker 🐳

```bash
# 1. Setup credentials
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY

# 2. Start with Docker
docker-compose up -d

# 3. Open in browser
# Web UI: http://localhost:8080/home.html
# API Docs: http://localhost:8000/api/docs
```

See [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) for a 3-minute guide.

## Features

- 🖼️ **Multi-format support**: JPG, PNG, GIF, WEBP, SVG, BMP, TIFF
- 🌍 **24 EU languages**: Multilingual alt-text generation
- 🔄 **Multiple interfaces**: CLI, Web UI, REST API
- 🤖 **AI providers**: OpenAI GPT-4o or ECB-LLM GPT-4o/5.1
- 📊 **Batch processing**: Process multiple images at once
- 📈 **HTML reports**: Accessible reports with detailed analysis
- 🌐 **Web scraping**: Extract images and context from websites
- ♿ **WCAG 2.2 compliant**: Follows accessibility standards

## Documentation

- **[DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)** - Get started in 3 minutes with Docker
- **[DOCKER.md](DOCKER.md)** - Complete Docker deployment guide
- **[CLAUDE.md](CLAUDE.md)** - Developer guide and architecture
- **[MyAccessibilityBuddy.md](MyAccessibilityBuddy.md)** - Quick start examples

## Installation Options

### Option 1: Docker (Recommended)

See [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) for step-by-step instructions.

### Option 2: Local Development

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
```

See [CLAUDE.md](CLAUDE.md) for detailed setup instructions.

## License

Copyright 2025 by European Central Bank. All rights reserved.

## Project Information

**Created for**: Innovate for Inclusion Hackathon
**Version**: 1.0.0
**Last Updated**: December 2025
