#!/usr/bin/env python3
"""
Test script to verify Ollama integration
"""
import sys
import os
sys.path.insert(0, '/app/backend')

# Set Ollama as provider temporarily
os.environ['TEST_OLLAMA'] = '1'

from backend import app

# Override config to use Ollama
app.CONFIG['llm_provider'] = 'Ollama'

print("="*60)
print("Testing Ollama Integration")
print("="*60)

# Test 1: Get credentials
print("\n1. Testing get_llm_credentials()...")
provider, credentials = app.get_llm_credentials()
print(f"   Provider: {provider}")
print(f"   Credentials: {credentials}")

# Test 2: Test image analysis
print("\n2. Testing analyze_image_with_ollama()...")
test_image = "/app/test/images/1.png"
if os.path.exists(test_image):
    print(f"   Test image: {test_image}")

    # Load prompt
    prompt_folder = app.get_absolute_folder_path('prompt')
    combined_prompt = app.load_and_merge_prompts(prompt_folder)

    print(f"   Prompt loaded: {len(combined_prompt)} chars")
    print("\n   Starting analysis...")

    result = app.analyze_image_with_ollama(
        test_image,
        combined_prompt,
        credentials,
        language='en'
    )

    if result:
        print("\n   ✓ Success!")
        print(f"   Image type: {result.get('image_type')}")
        print(f"   Alt text: {result.get('alt_text')}")
        print(f"   Reasoning: {result.get('reasoning', '')[:100]}...")
    else:
        print("\n   ✗ Failed - no result returned")
else:
    print(f"   ✗ Test image not found: {test_image}")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
