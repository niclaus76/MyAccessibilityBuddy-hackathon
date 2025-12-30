# Testing Guide for MyAccessibilityBuddy

This guide provides comprehensive testing scenarios for all features, including the new translation prompts and Ollama integration.

## Prerequisites

- Docker container running: `docker compose up -d`
- Ollama server running at http://192.168.64.1:11434 (for Ollama tests)
- Test images available in `test/images/` (13 test images included)

## Test Images Available

The `test/images/` folder contains 13 test images (1.png through 13.png):
- Images 1-7 have corresponding context files in `test/context/`
- Images 8-13 have no context files

## Testing Scenarios

### 1. Web Interface Testing

**Access the web interface:**
```bash
# Open in browser: http://localhost:8080/home.html
```

#### Test Case 1.1: Use Config (Default Provider)
1. Select model: **"Use Config (config.json)"** (default)
2. Upload test image: `test/images/1.png`
3. Optionally upload context: `test/context/1.txt`
4. Select language: **English**
5. Click **"Generate Alt Text"**
6. Expected: Uses Ollama (current config setting) with granite3.2-vision + phi3

#### Test Case 1.2: Force Ollama Provider
1. Select model: **"Ollama (local models)"**
2. Upload test image: `test/images/2.png`
3. Select language: **English**
4. Click **"Generate Alt Text"**
5. Expected: Uses Ollama even if config has different provider

#### Test Case 1.3: OpenAI Provider (requires API key)
1. Select model: **"OpenAI GPT-4o"**
2. Upload test image: `test/images/3.png`
3. Select language: **English**
4. Click **"Generate Alt Text"**
5. Expected: Uses OpenAI GPT-4o (requires OPENAI_API_KEY in .env)

#### Test Case 1.4: Multilingual Generation
1. Select model: **"Use Config (config.json)"**
2. Upload test image: `test/images/4.png`
3. Select language: **Italian** or **German**
4. Click **"Generate Alt Text"**
5. Expected: Alt-text generated in selected language

### 2. CLI Testing

#### Test Case 2.1: Single Image with Ollama
```bash
# Copy test image to input folder
cp test/images/1.png input/images/

# Generate alt-text using CLI
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en

# View output
cat output/alt-text/1.json
```

**Expected Output:**
- JSON file with Ollama provider
- Vision model: granite3.2-vision
- Processing model: phi3
- Translation model: phi3
- Alt-text in English

#### Test Case 2.2: Multilingual Generation (Fast Mode)
```bash
# Generate alt-text in multiple languages
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en it de

# Check output - should have all 3 languages
cat output/alt-text/1.json | grep -A 2 "proposed_alt_text"
```

**Expected Output:**
- Single JSON file with alt-text in all 3 languages
- `translation_method`: "fast" (generated once, then translated)
- All translations under 125 characters

#### Test Case 2.3: Batch Processing with Context
```bash
# Copy test images and context files
cp test/images/1.png test/images/2.png test/images/3.png input/images/
cp test/context/1.txt test/context/2.txt test/context/3.txt input/context/

# Process all images in batch
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -p --language en

# Check results
ls -la output/alt-text/
```

**Expected Output:**
- 3 JSON files created (1.json, 2.json, 3.json)
- Each includes context information
- Processing time summary

#### Test Case 2.4: Web Scraping Workflow
```bash
# Download images from webpage and generate alt-text
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py \
  -w https://www.ecb.europa.eu/home/html/index.en.html \
  --language en \
  --num-images 2 \
  --report

# Check output
ls -la output/alt-text/
ls -la output/reports/
```

**Expected Output:**
- Downloaded images in `input/images/`
- Context files in `input/context/`
- JSON files in `output/alt-text/`
- HTML report in `output/reports/`

#### Test Case 2.5: HTML Report Generation
```bash
# Generate alt-text with HTML report
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en --report

# Open the report (from host machine)
# The report will be in output/reports/ folder
```

**Expected Report Content:**
- AI Provider: Ollama
- Vision Model: granite3.2-vision
- Processing Model: phi3
- Translation Model: phi3
- Translation Method: Fast (generated once, then translated)
- Image preview
- Proposed alt-text
- Reasoning
- Context (if provided)

### 3. Translation System Testing

#### Test Case 3.1: Test Translation Prompts
```bash
# Generate alt-text in English, then in Italian (fast mode)
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en it

# Check that translation used the new translation prompts
docker compose exec myaccessibilitybuddy cat /app/logs/*.log | grep "translation_prompt"
```

**Expected:**
- Translation prompt loaded from `prompt/translation/translation_prompt_v0.txt`
- Translation system prompt loaded from `prompt/translation/translation_system_prompt_v0.txt`

#### Test Case 3.2: Custom Translation Prompt
```bash
# Create a custom translation prompt
cat > prompt/translation/translation_prompt_custom.txt << 'EOF'
Translate this alt-text to {TARGET_LANGUAGE}: "{ALT_TEXT}"
Keep it under 125 characters and end with a period.
EOF

# Update config.json to use custom prompt
# Edit backend/config/config.json:
# "translation_files": ["translation_prompt_custom.txt"]

# Rebuild and test
docker compose up -d --build
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en it
```

### 4. SVG Support Testing

#### Test Case 4.1: SVG to PNG Conversion
```bash
# Download SVG image and generate alt-text
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py \
  -w https://www.ecb.europa.eu/home/html/index.en.html \
  --language en \
  --num-images 1

# Check logs for SVG conversion
docker compose logs | grep -i "svg"
```

**Expected:**
- SVG detected and converted to PNG
- Ollama receives PNG data (base64-encoded)
- Alt-text generated successfully

### 5. API Testing

#### Test Case 5.1: API with Config Provider
```bash
# Test API endpoint with default config
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@test/images/1.png" \
  -F "language=en" \
  -F "model=config" | python3 -m json.tool
```

**Expected Response:**
```json
{
  "success": true,
  "alt_text": "Person using compass on snowy path.",
  "image_type": "informative",
  "reasoning": "...",
  "character_count": 35,
  "language": "en",
  "error": null
}
```

#### Test Case 5.2: API with Ollama Override
```bash
# Test API endpoint forcing Ollama
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@test/images/2.png" \
  -F "language=en" \
  -F "model=ollama" | python3 -m json.tool
```

#### Test Case 5.3: API with Context
```bash
# Test API with context
curl -X POST http://localhost:8000/api/generate-alt-text \
  -F "image=@test/images/1.png" \
  -F "language=en" \
  -F "model=config" \
  -F "context=A person navigating in winter conditions" | python3 -m json.tool
```

#### Test Case 5.4: API Documentation
```bash
# Open in browser: http://localhost:8000/api/docs
# Test the interactive API documentation
```

### 6. Provider Switching Tests

#### Test Case 6.1: Switch from Ollama to OpenAI
```bash
# Edit backend/config/config.json
# Change: "llm_provider": "OpenAI"
# Ensure OPENAI_API_KEY is set in backend/.env

# Restart container
docker compose restart

# Test
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en

# Check output uses OpenAI
cat output/alt-text/1.json | grep -A 3 "ai_model"
```

#### Test Case 6.2: Switch to ECB-LLM (requires credentials)
```bash
# Edit backend/config/config.json
# Change: "llm_provider": "ECB-LLM"
# Ensure CLIENT_ID_U2A and CLIENT_SECRET_U2A are set in backend/.env

# Restart container
docker compose restart

# Test
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en
```

### 7. Error Handling Tests

#### Test Case 7.1: Invalid Image Format
```bash
# Try to process a non-image file
echo "This is not an image" > /tmp/test.txt
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g /tmp/test.txt --language en
```

**Expected:** Error message about invalid image format

#### Test Case 7.2: Ollama Server Unavailable
```bash
# Stop Ollama server
# Edit config to use non-existent Ollama URL
# Test and verify graceful error handling
```

#### Test Case 7.3: Missing Translation Prompt
```bash
# Temporarily rename translation prompt file
mv prompt/translation/translation_prompt_v0.txt prompt/translation/translation_prompt_v0.txt.bak

# Test fallback to hardcoded prompt
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py -g 1.png --language en it

# Restore file
mv prompt/translation/translation_prompt_v0.txt.bak prompt/translation/translation_prompt_v0.txt
```

## Verification Checklist

After running tests, verify:

- [ ] All 3 providers work (OpenAI, ECB-LLM, Ollama)
- [ ] Translation prompts load from files
- [ ] Translation model is configurable per provider
- [ ] SVG images convert to PNG for Ollama
- [ ] Web interface shows all model options
- [ ] API supports all model selection modes
- [ ] HTML reports show vision/processing/translation models
- [ ] Multilingual generation works in fast and accurate modes
- [ ] Batch processing works correctly
- [ ] Web scraping workflow completes successfully

## Cleanup After Testing

```bash
# Clear all generated files
docker compose exec myaccessibilitybuddy python3 /app/backend/app.py --clear-all

# Or manually
rm -rf input/images/* input/context/* output/alt-text/* output/reports/*.html logs/*
```

## Troubleshooting

### Issue: "Failed to connect to Ollama"
**Solution:** Verify Ollama server is running and accessible at the configured URL

### Issue: "No prompt files could be loaded"
**Solution:** Check that prompt files exist in `prompt/processing/`, `prompt/vision/`, `prompt/translation/`

### Issue: "SVG conversion failed"
**Solution:** Ensure CairoSVG is installed (included in requirements.txt)

### Issue: "Translation model not shown in report"
**Solution:** Rebuild Docker container: `docker compose up -d --build`

## Additional Resources

- Full documentation: [CLAUDE.md](CLAUDE.md)
- Docker quickstart: [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)
- Configuration reference: `backend/config/config.json`
- Advanced configuration: `backend/config/config.advanced.json`
