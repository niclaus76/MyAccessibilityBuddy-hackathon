import ollama
import argparse

# Two-step processing configuration
#VISION_MODEL = 'moondream'  # Vision model for initial image description
VISION_MODEL = 'granite3.2-vision'
#VISION_MODEL = 'llama3.2-vision' 

#PROCESSING_MODEL = 'llama3.2'    # Text model for refining the description
PROCESSING_MODEL = 'phi3'    # Text model for refining the description

VISION_PROMPT = 'Describe this image in detail.'

#DESCRIPTION_PROMPT = '''Describe this image in detail.
#Include all important visual elements, objects, people, actions, colors, and context.
#Be thorough and descriptive.'''

PROCESSING_PROMPT = '''Based on the following image description, generate WCAG 2.2 compliant alt text.
Be concise but descriptive. Focus on the essential information and respect the 125 characters limit.
Do not include phrases like "image of" or "picture of".

Image description: {description}

Alt text:'''

PROCESSING_PROMPT_WITH_CONTEXT = '''Based on the following image description and additional context, generate WCAG 2.2 compliant alt text.
Be concise but descriptive. Focus on the essential information and respect the 125 characters limit.
Do not include phrases like "image of" or "picture of".

Image description: {description}

Additional context: {context}

Alt text:'''

def test_ollama_connection(model):
    """Test if Ollama is running and the model is available."""
    try:
        print(f"Testing connection to Ollama with model '{model}'...")
        response = ollama.chat(
            model=model,
            messages=[{
                'role': 'user',
                'content': 'Say "Hello" if you are working.'
            }]
        )
        print(f"✓ Connection successful! Model response: {response['message']['content']}")
        return True
    except Exception as e:
        print(f"✗ Connection failed: {str(e)}")
        return False

def find_context_file(image_path):
    """Find a context file with the same name as the image in the context folder."""
    import os

    # Get the filename without extension
    image_filename = os.path.basename(image_path)
    image_name_no_ext = os.path.splitext(image_filename)[0]

    # Get the directory of the image
    image_dir = os.path.dirname(image_path)
    if not image_dir:
        image_dir = '.'

    # Get the parent directory (same level as images folder)
    parent_dir = os.path.dirname(image_dir)
    if not parent_dir:
        parent_dir = '.'

    # Look for context folder at the same level as images folder
    context_dir = os.path.join(parent_dir, 'context')

    if not os.path.exists(context_dir):
        return None

    # Search for any file with the same base name
    for filename in os.listdir(context_dir):
        file_no_ext = os.path.splitext(filename)[0]
        if file_no_ext == image_name_no_ext:
            context_path = os.path.join(context_dir, filename)
            return context_path

    return None

def generate_alt_text(image_path):
    import os

    # Verify the image file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Check for context file
    context_path = find_context_file(image_path)
    context_content = None

    if context_path:
        try:
            with open(context_path, 'r', encoding='utf-8') as f:
                context_content = f.read()
            print(f"✓ Found context file: {context_path}")
            print(f"Context: {context_content}\n")
        except Exception as e:
            print(f"⚠ Warning: Could not read context file: {e}\n")
            context_content = None
    else:
        print(f"⚠ Warning: No context file found for this image\n")

    print(f"Step 1: Generating detailed description with {VISION_MODEL}...")
    print(f"Analyzing image: {image_path}\n")

    # Step 1: Generate detailed description using vision model
    description_response = ollama.chat(
        model=VISION_MODEL,
        messages=[{
            'role': 'user',
            'content': VISION_PROMPT,
            'images': [image_path]
        }]
    )
    description = description_response['message']['content']
    print(f"Description generated:\n{description}\n")

    print(f"Step 2: Processing description into alt text with {PROCESSING_MODEL}...")

    # Step 2: Process description into concise alt text using text model
    # Use context-aware prompt if context is available
    if context_content:
        print(f"Using additional context from file\n")
        prompt = PROCESSING_PROMPT_WITH_CONTEXT.format(
            description=description,
            context=context_content
        )
    else:
        prompt = PROCESSING_PROMPT.format(description=description)

    processing_response = ollama.chat(
        model=PROCESSING_MODEL,
        messages=[{
            'role': 'user',
            'content': prompt
        }]
    )
    alt_text = processing_response['message']['content']

    return alt_text, description, context_content

# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate alt text for images using Ollama vision models with two-step processing')
    parser.add_argument('-t', '--test', action='store_true', help='Test connection only without processing image')
    parser.add_argument('-i', '--image', type=str, default='images/1.png', help='Path to image file (default: images/1.png)')

    args = parser.parse_args()

    # Display which models are being used
    print(f"Two-step processing:")
    print(f"  Step 1 - Vision model: {VISION_MODEL}")
    print(f"  Step 2 - Processing model: {PROCESSING_MODEL}\n")

    if args.test:
        # Test mode - only test connection
        all_passed = True

        for model in [VISION_MODEL, PROCESSING_MODEL]:
            if not test_ollama_connection(model):
                all_passed = False
                print(f"\n✗ Connection test failed for model: {model}")
                print(f"To install the model, run: ollama pull {model}")

        if all_passed:
            print("\n✓ All connection tests passed! Ready to use.")
    else:
        # Normal mode - process image without testing
        print("\n" + "="*50)
        print("Running two-step alt text generation...")
        print("="*50 + "\n")
        try:
            alt_text, description, context = generate_alt_text(args.image)
            print(f"\n" + "="*50)
            print("RESULTS")
            print("="*50)
            if context:
                print(f"\nContext used:\n{context}")
            else:
                print(f"\nContext used: None")
            print(f"\nDetailed description:\n{description}")
            print(f"\nFinal alt text:\n{alt_text}")
        except FileNotFoundError as e:
            print(f"\n✗ Error: {e}")
        except Exception as e:
            print(f"\n✗ Error generating alt text: {e}")
            print(f"\nMake sure Ollama is running and both models are installed:")
            print(f"  ollama pull {VISION_MODEL}")
            print(f"  ollama pull {PROCESSING_MODEL}")