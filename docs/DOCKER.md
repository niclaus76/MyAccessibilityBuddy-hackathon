# Docker Setup for MyAccessibilityBuddy

This guide covers running MyAccessibilityBuddy using Docker containers.

## Prerequisites

- Docker Engine 20.10+ ([Install Docker](https://docs.docker.com/engine/install/))
- Docker Compose V2 ([Install Docker Compose](https://docs.docker.com/compose/install/))

Verify installation:
```bash
docker --version
docker compose version
```

## Quick Start

### 1. Prepare Environment

```bash
# Create .env file from template
cp backend/.env.example backend/.env

# Edit backend/.env and add your API credentials
nano backend/.env
```

Add one of the following to `backend/.env`:

**For OpenAI (recommended for testing):**
```bash
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**For ECB-LLM (ECB internal only):**
```bash
CLIENT_ID_U2A=your-client-id
CLIENT_SECRET_U2A=your-client-secret
```

### 2. Configure LLM Provider

Edit `backend/config/config.json` to match your .env file:

```json
{
  "llm_provider": "OpenAI",    // or "ECB-LLM"
  "model": "gpt-4o",           // or "gpt-5.1" for ECB-LLM
  "translation_mode": "fast"   // or "accurate"
}
```

### 3. Build and Run

```bash
# Build and start containers in detached mode
docker-compose up -d

# View startup logs
docker-compose logs -f
```

### 4. Access the Application

- **Web UI**: http://localhost:8080/home.html
- **API Documentation**: http://localhost:8000/api/docs
- **API Alternative Docs**: http://localhost:8000/api/redoc

### 5. Stop Services

```bash
# Stop containers (keeps volumes)
docker-compose down

# Stop and remove volumes (clears output/logs)
docker-compose down -v
```

## Usage Examples

### Web UI Workflow

1. Open http://localhost:8080/home.html
2. Upload an image from `test/images/` folder
3. Optionally upload corresponding context file from `test/context/`
4. Select target language (e.g., English)
5. Click "Generate Alt Text"
6. Copy the generated alt-text

### CLI Workflow in Container

```bash
# Copy test images to input folder
cp test/images/1.png input/images/
cp test/context/1.txt input/context/

# Execute CLI command inside container
docker-compose exec myaccessibilitybuddy bash -c "cd /app/backend && python3 app.py -g 1.png --language en"

# View output
cat output/alt-text/1.json
```

### Batch Processing

```bash
# Copy all test images
cp test/images/*.png input/images/
cp test/context/*.txt input/context/

# Process all images with report generation
docker-compose exec myaccessibilitybuddy bash -c "cd /app/backend && python3 app.py -p --language en --report"

# View HTML report
xdg-open output/reports/MyAccessibilityBuddy-AltTextReport.html
```

### Using Test Profile

The docker-compose includes a test profile for automated testing:

```bash
# Run batch test automatically
docker-compose --profile test run myaccessibilitybuddy-test

# This copies all test images, processes them, and generates a report
```

## Architecture

### Container Structure

```
myaccessibilitybuddy container
├── Frontend server (port 8080) - Serves static HTML/CSS/JS
├── Backend API (port 8000) - FastAPI application
└── OAuth callback (port 3001) - For ECB-LLM authentication
```

### Volumes (Persistent Data)

```yaml
./input:/app/input                         # Input images and context files
./output:/app/output                       # Generated alt-text JSON and HTML reports
./logs:/app/logs                           # Application logs
./backend/config/config.json:/app/backend/config/config.json
./backend/.env:/app/backend/.env           # API credentials (never committed)
```

**Important**: Files in mounted volumes persist after container stops.

### Network

All services run in the same container and communicate via localhost.

## Configuration

### Environment Variables (backend/.env)

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# ECB-LLM (alternative to OpenAI)
CLIENT_ID_U2A=ap-...
CLIENT_SECRET_U2A=...
```

### Application Config (backend/config/config.json)

Key settings:
- `llm_provider`: "OpenAI" or "ECB-LLM"
- `model`: "gpt-4o" or "gpt-5.1"
- `translation_mode`: "fast" or "accurate"
- `debug_mode`: true/false (enables file logging)

See CLAUDE.md for complete configuration options.

## Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker-compose logs

# Verify .env file exists
ls -la backend/.env

# Verify config is valid JSON
cat backend/config/config.json | python3 -m json.tool

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Permission errors with volumes

The container runs as user `appuser` (UID 1000). If you have permission errors:

```bash
# Check ownership
ls -la input/ output/ logs/

# Fix ownership (Linux/Mac)
sudo chown -R 1000:1000 input/ output/ logs/

# Or use current user
sudo chown -R $USER:$USER input/ output/ logs/
```

### "Failed to fetch" in Web UI

Make sure you're accessing via HTTP, not file://
- **Correct**: http://localhost:8080/home.html
- **Wrong**: file:///path/to/frontend/home.html

### OAuth not working (ECB-LLM)

Port 3001 must be accessible from your browser:
```bash
# Check if port is exposed
docker-compose ps
# Should show 3001->3001

# Test if port is accessible
curl http://localhost:3001
```

### Changes not reflected after rebuild

```bash
# Clear Docker build cache
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Container uses too much disk space

```bash
# Remove old images and volumes
docker system prune -a --volumes

# View disk usage
docker system df
```

## Advanced Usage

### Custom Docker Build

```bash
# Build specific platform (e.g., for Apple Silicon)
docker build --platform linux/amd64 -t myaccessibilitybuddy .

# Build with custom tag
docker build -t myaccessibilitybuddy:v1.0.0 .
```

### Interactive Shell Access

```bash
# Start a bash shell inside the container
docker-compose exec myaccessibilitybuddy bash

# Inside container, you can run any CLI command
cd /app/backend
python3 app.py --help
python3 app.py -al  # List all languages
```

### View Container Logs

```bash
# All logs
docker-compose logs

# Follow logs (tail -f style)
docker-compose logs -f

# Specific service logs
docker-compose logs myaccessibilitybuddy

# Last 100 lines
docker-compose logs --tail=100
```

### Health Check Status

```bash
# Check container health
docker-compose ps

# Detailed health check info
docker inspect myaccessibilitybuddy | grep -A 10 Health
```

### Resource Limits

Add to docker-compose.yml under `myaccessibilitybuddy` service:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 1G
```

## Production Deployment

### Security Checklist

- [ ] Never commit `.env` file (already in .gitignore)
- [ ] Use secrets management (Docker Secrets, Kubernetes Secrets, etc.)
- [ ] Run behind reverse proxy (nginx, Traefik) with HTTPS
- [ ] Enable firewall rules (only expose necessary ports)
- [ ] Keep base image updated (`docker-compose pull`)
- [ ] Use specific image tags instead of `latest`
- [ ] Implement rate limiting on API endpoints
- [ ] Review and minimize exposed ports

### Reverse Proxy Example (nginx)

```nginx
server {
    listen 80;
    server_name myaccessibilitybuddy.example.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Scaling Considerations

For high-traffic deployments:

1. **Separate services**: Split frontend (nginx) and backend (FastAPI)
2. **Load balancing**: Run multiple backend containers behind load balancer
3. **Shared storage**: Use network storage (NFS, S3) for input/output
4. **Caching**: Add Redis for API response caching
5. **Monitoring**: Add Prometheus + Grafana for metrics

## Maintenance

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose up -d --build
```

### Backup Data

```bash
# Backup output and logs
tar -czf backup-$(date +%Y%m%d).tar.gz output/ logs/

# Restore
tar -xzf backup-20250101.tar.gz
```

### Cleaning Up

```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune

# Remove all unused resources
docker system prune -a
```

## Support

For issues specific to Docker setup:
1. Check this guide's Troubleshooting section
2. Review Docker logs: `docker-compose logs -f`
3. Verify configuration files are valid
4. Check main CLAUDE.md for application-specific issues

For general application support, see [CLAUDE.md](CLAUDE.md).
