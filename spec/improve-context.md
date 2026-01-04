# Improve Context with HTML Tags

## Why

Currently, the context provided to the AI for alt text generation may not include the HTML structure surrounding images. This limitation prevents the AI from accurately determining the **semantic role** of an image:

- **Functional images**: Images used as links, buttons, or interactive elements (e.g., `<a><img></a>`, `<button><img></button>`)
- **Informative images**: Images that convey content or information within the page flow
- **Decorative images**: Images used purely for visual design with no semantic meaning

According to WCAG guidelines, each image type requires different alt text treatment:
- Functional: Describe the action/destination (e.g., "Search", "Home page")
- Informative: Describe the content conveyed
- Decorative: Empty alt text (`alt=""`)

By including HTML tags in the context, the AI can:
1. Identify the image's semantic role based on parent/ancestor elements
2. Generate contextually appropriate alt text
3. Follow WCAG best practices more accurately
4. Reduce hallucinated or inferred content
5. Distinguish between identical images used in different contexts

---

## Expected Behavior

### Context Extraction Enhancement

When analyzing a webpage or processing images:

1. **Extract HTML Context**
   - Capture the complete HTML structure surrounding each image
   - Include parent elements (at least 2-3 levels up)
   - Include sibling elements for additional context
   - Preserve semantic HTML tags (links, buttons, headings, lists, etc.)

2. **Provide Structured Context to AI**
   - Pass HTML structure along with text content
   - Clearly indicate the image's position in the DOM tree
   - Include relevant attributes (class, id, role, aria-*)

3. **AI Analysis Enhancement**
   - AI evaluates HTML structure to determine image type
   - AI generates alt text appropriate for the semantic role
   - AI provides reasoning based on HTML context

### Example Context Format

**Before (current):**
```
Image: logo.png
Page text: "Welcome to MyAccessibilityBuddy. Navigate to Home About Contact"
```

**After (improved):**
```
Image: logo.png
HTML Context:
<header>
  <nav class="navbar">
    <a href="/" class="navbar-brand">
      <img src="logo.png" /> <!-- TARGET IMAGE -->
    </a>
    <ul class="nav">
      <li><a href="/">Home</a></li>
      <li><a href="/about">About</a></li>
      <li><a href="/contact">Contact</a></li>
    </ul>
  </nav>
</header>

Analysis: Image is inside <a> tag (functional), serves as site logo/home link
Recommended alt text: "MyAccessibilityBuddy Home"
```

---

## Acceptance Criteria

### Functional Requirements
- [ ] HTML context is extracted for each image during analysis
- [ ] Context includes parent elements (minimum 2 levels up in DOM tree)
- [ ] Context includes sibling elements when relevant
- [ ] Target image is clearly marked in the HTML context
- [ ] HTML structure is preserved (not just text content)
- [ ] Context is passed to the AI model in the analysis prompt
- [ ] AI response includes semantic role determination (functional/informative/decorative)

### Technical Requirements
- [ ] HTML parsing extracts clean, well-formed context
- [ ] Context extraction handles malformed HTML gracefully
- [ ] Context size is optimized (relevant elements only, avoid excessive nesting)
- [ ] Sensitive attributes are sanitized (onclick, onerror, etc.)
- [ ] Context includes relevant ARIA attributes
- [ ] Implementation works with both webmaster tool and single image analysis

### Accessibility Requirements
- [ ] AI correctly identifies functional images (in links, buttons)
- [ ] AI correctly identifies informative images (content images)
- [ ] AI correctly identifies decorative images (pure design)
- [ ] Alt text recommendations follow WCAG 2.1 Level AA guidelines
- [ ] AI avoids hallucinating content not present in context
- [ ] Different alt text is suggested for identical images in different contexts

### Quality Requirements
- [ ] Unit tests for HTML context extraction
- [ ] Integration tests for end-to-end flow
- [ ] Test cases cover all three image types (functional, informative, decorative)
- [ ] Validation with real-world webpage examples
- [ ] Documentation updated with new context format

---

## Implementation Notes

### HTML Context Extraction

```python
from bs4 import BeautifulSoup

def extract_html_context(html_content, image_src):
    """
    Extract HTML context surrounding an image

    Args:
        html_content: Full HTML of the page
        image_src: Source attribute of target image

    Returns:
        dict with HTML context and metadata
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the target image
    img_tag = soup.find('img', src=image_src)
    if not img_tag:
        return None

    # Get parent hierarchy (2-3 levels)
    parents = []
    current = img_tag.parent
    levels = 3
    while current and levels > 0:
        parents.append(current.name)
        current = current.parent
        levels -= 1

    # Extract relevant context (parent + siblings)
    context_element = img_tag.parent.parent if img_tag.parent.parent else img_tag.parent

    # Clone and mark the target image
    context_html = str(context_element)
    context_html = context_html.replace(str(img_tag), f'{str(img_tag)} <!-- TARGET IMAGE -->')

    return {
        'html_context': context_html,
        'parent_chain': parents,
        'is_in_link': img_tag.find_parent('a') is not None,
        'is_in_button': img_tag.find_parent('button') is not None,
        'aria_attributes': {k: v for k, v in img_tag.attrs.items() if k.startswith('aria-')},
        'image_role': img_tag.get('role', None)
    }
```

### Enhanced Prompt Structure

```python
def build_enhanced_prompt(image_path, html_context, page_text):
    """
    Build prompt with HTML context for better image classification
    """
    prompt = f"""
# Image Alt Text Analysis

## Image Information
- Path: {image_path}
- Current alt text: {html_context.get('current_alt', 'none')}

## HTML Context
The image appears in the following HTML structure:
```html
{html_context['html_context']}
```

## Semantic Analysis
- Parent chain: {' > '.join(html_context['parent_chain'])}
- Inside link: {html_context['is_in_link']}
- Inside button: {html_context['is_in_button']}
- ARIA attributes: {html_context['aria_attributes']}

## Page Text Content
{page_text}

## Task
Based on the HTML context, determine:
1. Image type (functional/informative/decorative)
2. Semantic role in the page
3. Appropriate alt text following WCAG 2.1 guidelines

## Guidelines
- Functional images (links, buttons): Describe the action/destination
- Informative images: Describe the content conveyed
- Decorative images: Suggest empty alt text (alt="")
- Do not infer content not visible in context
- Consider the parent HTML elements to understand purpose

Please provide:
1. Image type classification
2. Reasoning based on HTML structure
3. Recommended alt text
"""
    return prompt
```

### Image Type Detection Logic

```python
def classify_image_type(html_context):
    """
    Classify image as functional, informative, or decorative
    based on HTML context
    """
    # Functional: Inside interactive elements
    if html_context['is_in_link'] or html_context['is_in_button']:
        return 'functional'

    # Functional: Has role="button" or similar
    if html_context.get('image_role') in ['button', 'link']:
        return 'functional'

    # Check for decorative indicators
    parent_chain = html_context['parent_chain']
    decorative_contexts = ['aside', 'footer', 'header']

    # More sophisticated logic needed here
    # This is a simplified example

    # Default to informative
    return 'informative'
```

### Integration Points

#### Webmaster Tool
```python
# In webmaster analysis flow
for image in images:
    html_context = extract_html_context(webpage_html, image['src'])
    enhanced_prompt = build_enhanced_prompt(
        image['src'],
        html_context,
        page_text
    )
    alt_text = generate_alt_text(image, enhanced_prompt)
```

#### Single Image Analysis
```python
# In single image upload
if webpage_url_provided:
    webpage_html = fetch_webpage(webpage_url)
    html_context = extract_html_context(webpage_html, uploaded_image)
    enhanced_prompt = build_enhanced_prompt(
        uploaded_image,
        html_context,
        extract_text(webpage_html)
    )
else:
    # Fallback to current behavior if no webpage context
    enhanced_prompt = build_basic_prompt(uploaded_image)
```

---

## Example Scenarios

### Scenario 1: Logo as Link (Functional)

**HTML Context:**
```html
<header class="site-header">
  <a href="/" class="logo-link">
    <img src="logo.png" width="200" height="60" /> <!-- TARGET IMAGE -->
  </a>
  <nav>...</nav>
</header>
```

**AI Analysis:**
- Type: Functional
- Reasoning: Image is inside `<a>` tag linking to home page
- Recommended alt: "MyAccessibilityBuddy Home"

### Scenario 2: Content Image (Informative)

**HTML Context:**
```html
<article>
  <h2>Accessibility Features</h2>
  <p>Our tool provides comprehensive accessibility analysis...</p>
  <img src="dashboard-screenshot.png" /> <!-- TARGET IMAGE -->
  <p>The dashboard shows real-time compliance metrics...</p>
</article>
```

**AI Analysis:**
- Type: Informative
- Reasoning: Image within article content, illustrates text
- Recommended alt: "Dashboard displaying accessibility compliance metrics with graphs and statistics"

### Scenario 3: Decorative Border (Decorative)

**HTML Context:**
```html
<div class="card-decoration">
  <img src="corner-ornament.svg" class="decoration" /> <!-- TARGET IMAGE -->
  <div class="card-content">
    <h3>Features</h3>
    <p>Content here...</p>
  </div>
</div>
```

**AI Analysis:**
- Type: Decorative
- Reasoning: Image has class "decoration", no semantic purpose
- Recommended alt: "" (empty)

### Scenario 4: Same Image, Different Contexts

**Context A - Functional:**
```html
<button onclick="openSettings()">
  <img src="gear-icon.png" /> <!-- TARGET IMAGE -->
</button>
```
Recommended alt: "Settings"

**Context B - Informative:**
```html
<p>Click the <img src="gear-icon.png" /> icon to access settings.</p>
```
Recommended alt: "gear icon"

---

## Data Flow

```
Webpage URL
    ↓
Fetch Full HTML
    ↓
Parse HTML (BeautifulSoup)
    ↓
For Each Image:
    ├─ Extract HTML Context (parent elements, siblings)
    ├─ Identify Parent Chain
    ├─ Detect Interactive Elements (links, buttons)
    ├─ Extract ARIA Attributes
    ↓
Build Enhanced Prompt
    ├─ Include HTML Structure
    ├─ Include Semantic Metadata
    ├─ Include Page Text
    ↓
Send to AI Model
    ↓
AI Analyzes:
    ├─ HTML Structure
    ├─ Semantic Role
    ├─ Context Clues
    ↓
Generate Response:
    ├─ Image Type Classification
    ├─ Reasoning
    ├─ Recommended Alt Text
```

---

## Prompt Template Enhancement

### Current Prompt (Simplified)
```
Analyze this image and suggest alt text.
Image: {image_path}
Context: {text_content}
```

### Enhanced Prompt
```
# Alt Text Generation Task

## Image Details
Path: {image_path}
Current alt: {current_alt}

## HTML Structure Context
```html
{html_context}
```

## Semantic Information
- Parent elements: {parent_chain}
- Interactive context: {is_functional}
- ARIA labels: {aria_attributes}

## Surrounding Text
{page_text}

## WCAG Guidelines Reminder
1. Functional images: Describe action/destination
2. Informative images: Convey content meaning
3. Decorative images: Use empty alt=""

## Task
Classify image type and provide appropriate alt text.
Include reasoning based on HTML context.
```

---

## Testing Strategy

### Unit Tests
```python
def test_extract_html_context_functional():
    html = '<a href="/"><img src="logo.png" /></a>'
    context = extract_html_context(html, 'logo.png')
    assert context['is_in_link'] == True
    assert 'functional' in classify_image_type(context)

def test_extract_html_context_informative():
    html = '<article><p>Text</p><img src="chart.png" /></article>'
    context = extract_html_context(html, 'chart.png')
    assert context['is_in_link'] == False
    assert 'informative' in classify_image_type(context)

def test_extract_html_context_decorative():
    html = '<div class="bg"><img src="pattern.png" class="decoration" /></div>'
    context = extract_html_context(html, 'pattern.png')
    # Test decorative detection logic
```

### Integration Tests
- Test with real webpage HTML
- Verify correct context extraction for various page structures
- Validate AI responses with HTML context vs. without
- Ensure WCAG compliance in generated alt text

### Accessibility Validation
- Run against WCAG test suite
- Validate functional image detection accuracy
- Verify decorative image handling
- Test with screen reader to confirm alt text quality

---

## Performance Considerations

- HTML parsing should not significantly increase processing time
- Context extraction should be optimized for large pages
- Consider caching parsed HTML for multiple images on same page
- Limit context depth to avoid excessive token usage in AI prompts
- Implement timeout for HTML fetching and parsing

---

## Security Considerations

- Sanitize HTML to prevent XSS in context display
- Remove dangerous attributes (onclick, onerror, etc.)
- Validate URLs before fetching HTML
- Limit HTML context size to prevent prompt injection
- Ensure temporary HTML storage is properly cleaned up

---

## Related Issues

This feature relates to:
- WCAG compliance and accessibility standards
- Image classification accuracy
- Prompt engineering and AI model effectiveness
- Webmaster tool and single image analysis

---

## Labels

- `feature`
- `accessibility`
- `enhancement`
- `wcag-compliance`

---

## Dependencies

### Required Libraries
```
# Add to requirements.txt
beautifulsoup4>=4.12.0
lxml>=4.9.0  # Fast HTML parser
html5lib>=1.1  # Fallback parser for malformed HTML
```

---

## ADR Reference

Decisions requiring ADR documentation:
- HTML context depth (how many parent levels to include)
- Context size limits and truncation strategy
- HTML parser selection (lxml vs html5lib vs html.parser)
- Image type classification algorithm
- Integration approach (when to include HTML context)

Create ADRs in `/development/05-decisions/` addressing these choices.

---

## Migration Strategy

### Phase 1: Add HTML Context Extraction
- Implement HTML parsing and context extraction
- Add to backend API as optional parameter
- No changes to existing behavior

### Phase 2: Update Prompts
- Enhance prompt templates to include HTML context
- A/B test with and without HTML context
- Measure accuracy improvements

### Phase 3: Full Integration
- Make HTML context default for all tools
- Update UI to show HTML context in reports
- Update documentation and examples

### Phase 4: Optimization
- Refine context extraction based on usage data
- Optimize context size and structure
- Enhance AI prompt based on results

---

## Success Metrics

- Improved accuracy in image type classification (target: >90%)
- Reduced hallucinated content in alt text
- Higher WCAG compliance scores
- Positive user feedback on alt text quality
- Reduced manual corrections needed
