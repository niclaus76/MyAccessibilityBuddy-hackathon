# Docker Quick Start Guide

**MyAccessibilityBuddy** - Get started in 3 minutes with Docker!

## Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- An OpenAI API key ([Get API Key](https://platform.openai.com/api-keys))

```bash
sudo apt  install docker.io
sudo apt  install docker-compose
sudo usermod -aG docker $USER
newgrp docker
groups
# docker is in the list
```

## Step 1: Setup Credentials (30 seconds)

```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Add your OpenAI API key
echo "OPENAI_API_KEY=sk-your-actual-api-key-here" > backend/.env
```

## Step 2: Start Application (2 minutes)

```bash
# Build and start (first time takes ~2 minutes to download dependencies)
docker-compose up -d

# Watch startup logs
docker-compose logs -f
```
Application starts: `MyAccessibilityBuddy Starting...'
Wait for: `✓ Starting FastAPI backend...`

## Step 3: Use the Application (30 seconds)

Open in your browser:
- **Web UI**: http://localhost:8080/home.html
- **API Docs**: http://localhost:8000/api/docs

### Try the Web UI:
1. Click "Choose File" and select an image from `test/images/`
2. Select language: "English"
3. Click "Generate Alt Text"
4. Done! Copy the generated alt-text

### Try the CLI:
```bash
# Copy test image
cp test/images/1.png input/images/

# Generate alt-text
docker-compose exec myaccessibilitybuddy bash -c "cd /app/backend && python3 app.py -g 1.png --language en"

# View output
cat output/alt-text/1.json
```

## Stop Application

```bash
docker-compose down
```

## Common Issues

**"Failed to fetch" error in browser?**
- Use http://localhost:8080/home.html (NOT file://)

**"No .env file found" in logs?**
- Make sure you created `backend/.env` with your API key

**Want to rebuild after changing code?**
```bash
docker-compose up -d --build
```

## Next Steps

- Read [DOCKER.md](DOCKER.md) for detailed documentation
- Read [CLAUDE.md](CLAUDE.md) for application features and configuration
- Edit `backend/config/config.json` to customize settings

## Support

- Check logs: `docker-compose logs -f`
- API health: http://localhost:8000/api/health
- Full docs: [DOCKER.md](DOCKER.md)
