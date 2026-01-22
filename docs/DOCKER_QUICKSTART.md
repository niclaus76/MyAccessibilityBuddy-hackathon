# Docker Quick Start Guide

**MyAccessibilityBuddy** - Get started in 3 minutes with Docker!

## Prerequisites

- Docker with Compose V2 installed ([Get Docker](https://docs.docker.com/get-docker/))
- **One of**: OpenAI API key ([Get API Key](https://platform.openai.com/api-keys)), ECB-LLM credentials, or local Ollama server

```bash
sudo apt install docker.io
sudo usermod -aG docker $USER
newgrp docker
groups
# docker should be in the list
```

## Step 1: Setup Configuration (30 seconds)

### Option A: OpenAI (Recommended for getting started)
```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-your-actual-api-key-here" > backend/.env

# Configure to use OpenAI (edit backend/config/config.json)
# Set "llm_provider": "OpenAI"
```

### Option B: Ollama (Free, runs locally)
```bash
# No .env file needed for Ollama

# Configure to use Ollama (edit backend/config/config.json)
# Set "llm_provider": "Ollama"
# Set "ollama": { "base_url": "http://YOUR_IP:11434" }
```

### Option C: ECB-LLM (ECB internal only)
```bash
# Add ECB credentials to backend/.env
echo "CLIENT_ID_U2A=your-client-id" > backend/.env
echo "CLIENT_SECRET_U2A=your-secret" >> backend/.env

# Configure to use ECB-LLM (edit backend/config/config.json)
# Set "llm_provider": "ECB-LLM"
```

## Step 2: Start Application (2 minutes)

```bash
# Build and start (first time takes ~2 minutes to download dependencies)
docker compose up -d

# Watch startup logs
docker compose logs -f
```
Application starts: `MyAccessibilityBuddy Starting...'
Wait for: `✓ Starting FastAPI backend...`

**Note**: Use `docker compose` (with space), not `docker-compose` (with hyphen). Docker Compose V2 uses the space syntax.

## Step 3: Use the Application (30 seconds)

Open in your browser:
- **Web UI**: http://localhost:8000/home.html
- **API Docs**: http://localhost:8000/api/docs

### Try the Web UI:
1. Click "Choose File" and select an image from `test/images/`
2. Select language: "English"
3. Click "Generate Alt Text"
4. Done! Copy the generated alt-text

### Try the CLI:
```bash
# Copy test image (from the project root)
cp test/images/1.png input/images/

# Generate alt-text
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en

# View output
cat output/alt-text/1.json
```

## Stop Application

```bash
docker compose down
```

## Common Issues

**"Failed to fetch" error in browser?**
- Use http://localhost:8000/home.html (NOT file://)

**"No .env file found" in logs?**
- For OpenAI/ECB-LLM: Make sure you created `backend/.env` with credentials
- For Ollama: No .env file needed

**"Command 'docker-compose' not found"?**
- Use `docker compose` (with space) instead of `docker-compose` (with hyphen)
- Docker Compose V2 is the current version

**Want to rebuild after changing code?**
```bash
docker compose up -d --build
```

## Configuration Options

### Two-Step Processing (Advanced)

MyAccessibilityBuddy supports two processing modes in `backend/config/config.json`:

- **Two-step** (`"two_step_processing": true`):
  - Step 1: Vision model analyzes image → generates description
  - Step 2: Processing model → generates WCAG alt-text from description
  - Works with all providers (OpenAI, ECB-LLM, Ollama)
  - Better results for complex images

- **Single-step** (`"two_step_processing": false`):
  - Legacy mode: Vision model does everything in one call
  - Faster but may be less accurate

### Customizing Models

Edit `backend/config/config.json`:

```json
{
  "openai": {
    "vision_model": "gpt-4o",
    "processing_model": "gpt-4o-mini"  // Use cheaper model for step 2
  },
  "ollama": {
    "vision_model": "llama3.2-vision",  // Or granite3.2-vision
    "processing_model": "phi3"           // Or llama3.2, granite3.2
  }
}
```

## Next Steps

- Read [CLAUDE.md](CLAUDE.md) for full application features and configuration
- Read [DOCKER.md](DOCKER.md) for detailed Docker documentation
- Customize prompts in `prompt/vision/` and `prompt/processing/`
- Edit `backend/config/config.json` for advanced settings

## Support

- Check logs: `docker compose logs -f`
- API health: http://localhost:8000/api/health
- Full docs: [CLAUDE.md](CLAUDE.md)
