# Two-Step Alt Text Generation Approach

## Why

A bug has been identified in the current single-step alt text generation process when using Claude API. The issue manifests as:

1. **Inconsistent Output Quality**: Claude may produce varying quality alt text in a single generation attempt
2. **Context Understanding Issues**: Complex images may not be fully analyzed in one pass
3. **Hallucination Risk**: Single-step processing may lead to inferred or imagined content
4. **Missing WCAG Compliance Checks**: Quality validation happens after generation, not during

### The Multi-Step Approach Solution

A two-step approach addresses these issues by:

**Step 1: Analysis Phase**
- Examine the image thoroughly
- Identify image type (functional/informative/decorative)
- Extract key elements and context
- Determine WCAG requirements
- Document findings in structured format

**Step 2: Generation Phase**
- Use analysis from Step 1 as input
- Generate alt text based on verified analysis
- Apply appropriate WCAG rules for image type
- Ensure consistency with analyzed content
- Produce final, validated alt text

### Benefits

- **Higher Quality**: Separate analysis from generation improves focus
- **Better Context Understanding**: Analysis phase can be thorough without rushing to output
- **Reduced Hallucination**: Analysis is verified before alt text generation
- **WCAG Compliance**: Image type determination happens before alt text creation
- **Debuggability**: Can inspect intermediate analysis for issues
- **Consistency**: Alt text directly reflects the documented analysis

---

## Expected Behavior

### Current Single-Step Process (Problematic)

```
Image + Context → [Claude API] → Alt Text
```

Issues:
- Claude must analyze and generate simultaneously
- No intermediate verification
- Difficult to debug quality issues
- Inconsistent results

### Proposed Two-Step Process

```
Step 1 (Analysis):
Image + Context → [Claude API] → Structured Analysis
                                  ├─ Image type
                                  ├─ Key elements
                                  ├─ Purpose/function
                                  ├─ WCAG requirements
                                  └─ Context summary

Step 2 (Generation):
Structured Analysis → [Claude API] → Alt Text
                                     (validated against analysis)
```

### User Experience

From the user's perspective:
1. **No Change in Interface**: User submits images as before
2. **Slightly Longer Processing**: Two API calls instead of one (minimal delay)
3. **Higher Quality Output**: More consistent, accurate alt text
4. **Optional Analysis View**: Advanced users can view Step 1 analysis
5. **Better Error Messages**: Specific feedback if analysis or generation fails

---

## Acceptance Criteria

### Functional Requirements
- [ ] Step 1 analyzes image and produces structured output
- [ ] Step 2 generates alt text based on Step 1 analysis
- [ ] Both steps complete successfully for image processing
- [ ] Analysis includes: image type, key elements, purpose, WCAG requirements
- [ ] Generated alt text aligns with Step 1 analysis
- [ ] Process works for all image types (functional/informative/decorative)
- [ ] Fallback to single-step if two-step fails

### Technical Requirements
- [ ] Step 1 prompt produces valid JSON or structured text
- [ ] Step 2 prompt consumes Step 1 output correctly
- [ ] Error handling for each step independently
- [ ] Timeout handling for multi-step process
- [ ] Logging of both steps for debugging
- [ ] Performance acceptable (total time < 10 seconds typical)
- [ ] Configuration option to enable/disable two-step approach

### Quality Requirements
- [ ] Alt text quality improves compared to single-step
- [ ] Reduced hallucination/inference rate
- [ ] Higher WCAG compliance rate
- [ ] Consistent image type identification
- [ ] A/B testing shows improvement in quality metrics

### Testing Requirements
- [ ] Unit tests for Step 1 analysis parsing
- [ ] Unit tests for Step 2 generation
- [ ] Integration tests for complete two-step flow
- [ ] Comparison tests: single-step vs two-step
- [ ] Edge case testing (ambiguous images, missing context)
- [ ] Performance testing for processing time

### Documentation Requirements
- [ ] Document the two-step process architecture
- [ ] Explain why two-step is better than single-step
- [ ] Provide examples of Step 1 analysis output
- [ ] Update API documentation
- [ ] Add troubleshooting guide for multi-step issues

---

## Implementation Notes

### Step 1: Analysis Prompt

```python
ANALYSIS_PROMPT = """
You are an expert in web accessibility and WCAG compliance.

Analyze the following image to prepare for alt text generation.

IMAGE CONTEXT:
{context}

HTML STRUCTURE:
{html_context}

TASK: Provide a structured analysis covering:

1. IMAGE TYPE:
   - Functional (button, link, interactive element)
   - Informative (conveys content or information)
   - Decorative (purely visual, no semantic meaning)

2. KEY ELEMENTS:
   - List the main visual elements visible in the image
   - Identify any text present in the image
   - Note colors, shapes, or patterns if relevant

3. PURPOSE/FUNCTION:
   - What is the primary purpose of this image?
   - How does it serve the user or page content?
   - What information or action does it convey?

4. WCAG REQUIREMENTS:
   - Based on the image type, what WCAG rules apply?
   - Should alt text be descriptive, action-oriented, or empty?
   - Any specific considerations for this image?

5. CONTEXT SUMMARY:
   - How does the surrounding content inform the image meaning?
   - Are there captions, headings, or nearby text that provide context?

OUTPUT FORMAT:
Return your analysis as JSON:
{{
  "image_type": "functional|informative|decorative",
  "key_elements": ["element1", "element2", ...],
  "text_in_image": "any text visible in the image",
  "purpose": "description of purpose",
  "wcag_requirements": "applicable WCAG guidance",
  "context_summary": "how context informs meaning",
  "recommended_approach": "brief guidance for alt text"
}}

Be objective. Do not infer content not visible in the image.
"""
```

### Step 2: Generation Prompt

```python
GENERATION_PROMPT = """
You are an expert in web accessibility and WCAG compliance.

Based on the following analysis, generate appropriate alt text.

ANALYSIS FROM STEP 1:
{analysis_json}

GUIDELINES:
- Image type: {image_type}
- If functional: Describe the action/destination
- If informative: Describe the content conveyed
- If decorative: Return empty alt text (alt="")

- Be as concise as possible while fully conveying the purpose
- Use natural language
- Do not infer content beyond the analysis
- Follow WCAG 2.1 Level AA guidelines

{geo_boost_guidance}

TASK:
Generate the alt text based on the analysis above.
Return ONLY the alt text, nothing else.

If the image is decorative, return exactly: alt=""
"""
```

### Backend Implementation

```python
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TwoStepAltTextGenerator:
    """
    Two-step alt text generation:
    1. Analyze image and context
    2. Generate alt text from analysis
    """

    def __init__(self, claude_client, config):
        self.client = claude_client
        self.config = config
        self.use_two_step = config.get('use_two_step_approach', True)

    def generate_alt_text(self, image_path: str, context: str,
                          html_context: str = "") -> Dict[str, Any]:
        """
        Generate alt text using two-step approach

        Returns:
            {
                'alt_text': str,
                'analysis': dict,  # Step 1 output
                'confidence': float,
                'method': 'two-step' | 'single-step'
            }
        """
        if not self.use_two_step:
            # Fallback to single-step
            return self._generate_single_step(image_path, context)

        try:
            # Step 1: Analyze
            analysis = self._analyze_image(image_path, context, html_context)

            # Step 2: Generate
            alt_text = self._generate_from_analysis(analysis)

            return {
                'alt_text': alt_text,
                'analysis': analysis,
                'confidence': self._calculate_confidence(analysis, alt_text),
                'method': 'two-step'
            }

        except Exception as e:
            logger.error(f"Two-step generation failed: {e}")
            logger.info("Falling back to single-step approach")
            return self._generate_single_step(image_path, context)

    def _analyze_image(self, image_path: str, context: str,
                       html_context: str) -> Dict[str, Any]:
        """
        Step 1: Analyze image and return structured data
        """
        prompt = ANALYSIS_PROMPT.format(
            context=context,
            html_context=html_context or "No HTML context provided"
        )

        response = self.client.generate(
            prompt=prompt,
            image_path=image_path,
            temperature=0.3,  # Lower temp for consistent analysis
            max_tokens=1000
        )

        # Parse JSON response
        try:
            analysis = json.loads(response)
            self._validate_analysis(analysis)
            return analysis
        except json.JSONDecodeError:
            # Fallback: extract JSON from markdown code block
            return self._extract_json_from_response(response)

    def _generate_from_analysis(self, analysis: Dict[str, Any]) -> str:
        """
        Step 2: Generate alt text from analysis
        """
        # Add GEO boost guidance if enabled
        geo_guidance = ""
        if self.config.get('GEO_boost', False):
            geo_guidance = """
- Use search-relevant but natural terms
- Optimize for assistive technologies and AI indexing
"""

        prompt = GENERATION_PROMPT.format(
            analysis_json=json.dumps(analysis, indent=2),
            image_type=analysis['image_type'],
            geo_boost_guidance=geo_guidance
        )

        alt_text = self.client.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=300
        )

        return alt_text.strip()

    def _validate_analysis(self, analysis: Dict[str, Any]) -> None:
        """Validate that analysis has required fields"""
        required_fields = [
            'image_type', 'key_elements', 'purpose',
            'wcag_requirements', 'recommended_approach'
        ]

        for field in required_fields:
            if field not in analysis:
                raise ValueError(f"Missing required field: {field}")

        # Validate image_type
        valid_types = ['functional', 'informative', 'decorative']
        if analysis['image_type'] not in valid_types:
            raise ValueError(f"Invalid image_type: {analysis['image_type']}")

    def _calculate_confidence(self, analysis: Dict[str, Any],
                               alt_text: str) -> float:
        """
        Calculate confidence score for generated alt text
        Based on analysis completeness and alt text quality
        """
        confidence = 0.5  # Base confidence

        # Boost for complete analysis
        if len(analysis.get('key_elements', [])) > 0:
            confidence += 0.1
        if analysis.get('purpose'):
            confidence += 0.1
        if analysis.get('wcag_requirements'):
            confidence += 0.1

        # Boost for appropriate alt text length
        if analysis['image_type'] == 'decorative':
            confidence += 0.2 if alt_text == 'alt=""' else -0.3
        elif analysis['image_type'] == 'functional':
            confidence += 0.1 if 10 < len(alt_text) < 100 else -0.1
        elif analysis['image_type'] == 'informative':
            confidence += 0.1 if 30 < len(alt_text) < 300 else -0.1

        return max(0.0, min(1.0, confidence))

    def _generate_single_step(self, image_path: str,
                               context: str) -> Dict[str, Any]:
        """
        Fallback: single-step generation
        """
        # Use existing single-step prompt
        alt_text = self.client.generate_alt_text_legacy(image_path, context)

        return {
            'alt_text': alt_text,
            'analysis': None,
            'confidence': 0.5,
            'method': 'single-step'
        }

    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """
        Extract JSON from markdown code blocks if present
        """
        import re

        # Try to find JSON in markdown code block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```',
                          response, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try to find raw JSON
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("Could not extract JSON from response")
```

### Frontend Integration

No changes required to frontend UI. Backend handles the two-step process transparently.

Optional: Add debug view for analysis

```html
<!-- Optional: Advanced users can view analysis -->
<div class="analysis-debug" style="display: none;">
    <h4>Analysis (Step 1)</h4>
    <pre id="analysis-output"></pre>

    <h4>Generated Alt Text (Step 2)</h4>
    <pre id="alttext-output"></pre>
</div>

<script>
// Show analysis in debug mode
if (config.debug_mode) {
    document.querySelector('.analysis-debug').style.display = 'block';
    document.getElementById('analysis-output').textContent =
        JSON.stringify(result.analysis, null, 2);
    document.getElementById('alttext-output').textContent = result.alt_text;
}
</script>
```

---

## Configuration

Add to `config.json`:

```json
{
  "use_two_step_approach": true,
  "two_step_config": {
    "analysis_temperature": 0.3,
    "generation_temperature": 0.5,
    "analysis_max_tokens": 1000,
    "generation_max_tokens": 300,
    "fallback_to_single_step": true,
    "save_analysis_to_report": true
  }
}
```

---

## Example Outputs

### Example 1: Button Icon (Functional)

**Step 1 Analysis:**
```json
{
  "image_type": "functional",
  "key_elements": ["magnifying glass icon", "circular shape", "handle"],
  "text_in_image": "",
  "purpose": "Interactive search button to open search functionality",
  "wcag_requirements": "Alt text should describe the action, not appearance",
  "context_summary": "Button in navigation header, labeled 'Search'",
  "recommended_approach": "Use action verb like 'Search' or 'Open search'"
}
```

**Step 2 Generated Alt Text:**
```
"Search"
```

---

### Example 2: Data Chart (Complex Informative)

**Step 1 Analysis:**
```json
{
  "image_type": "informative",
  "key_elements": [
    "bar chart",
    "four colored bars per quarter",
    "x-axis showing Q1-Q4 2024",
    "y-axis showing revenue in millions",
    "legend showing four product categories"
  ],
  "text_in_image": "Q1, Q2, Q3, Q4, Electronics, Home Goods, Apparel, Accessories",
  "purpose": "Convey quarterly sales performance across product categories",
  "wcag_requirements": "Describe data trends and key values, sufficient for user to understand the chart content",
  "context_summary": "Article about 2024 sales performance, referenced in paragraph discussing growth trends",
  "recommended_approach": "Include specific values for each category and highlight trends"
}
```

**Step 2 Generated Alt Text:**
```
"Bar chart showing quarterly sales for 2024 across four product categories:
Electronics grew from $2.5M in Q1 to $4.2M in Q4, Home Goods increased from
$2.1M to $3.1M, Apparel remained steady at $2.8M, and Accessories declined
from $2.0M to $1.9M, demonstrating strong growth in Electronics and Home Goods"
```

---

### Example 3: Decorative Background (Decorative)

**Step 1 Analysis:**
```json
{
  "image_type": "decorative",
  "key_elements": ["abstract gradient pattern", "blue to purple colors", "soft blur effect"],
  "text_in_image": "",
  "purpose": "Visual design element, no informational or functional purpose",
  "wcag_requirements": "Should have empty alt text (alt=\"\") as it's purely decorative",
  "context_summary": "Background image in hero section, content is in text overlay",
  "recommended_approach": "Return empty alt text"
}
```

**Step 2 Generated Alt Text:**
```
alt=""
```

---

## Testing Strategy

### A/B Comparison Testing

```python
def test_two_step_vs_single_step():
    """
    Compare quality of two-step vs single-step approach
    """
    test_images = [
        'functional_button.png',
        'informative_chart.png',
        'complex_infographic.svg',
        'decorative_pattern.jpg',
        'ambiguous_image.png'
    ]

    results = []

    for image in test_images:
        # Single-step
        single_result = generator_single.generate(image)

        # Two-step
        two_step_result = generator_two_step.generate(image)

        # Compare
        results.append({
            'image': image,
            'single_step': {
                'alt_text': single_result['alt_text'],
                'quality_score': assess_quality(single_result['alt_text'])
            },
            'two_step': {
                'alt_text': two_step_result['alt_text'],
                'analysis': two_step_result['analysis'],
                'quality_score': assess_quality(two_step_result['alt_text'])
            }
        })

    # Aggregate results
    single_avg = sum(r['single_step']['quality_score'] for r in results) / len(results)
    two_step_avg = sum(r['two_step']['quality_score'] for r in results) / len(results)

    print(f"Single-step average quality: {single_avg}")
    print(f"Two-step average quality: {two_step_avg}")

    assert two_step_avg > single_avg, "Two-step should improve quality"
```

### Quality Assessment Criteria

| Criterion | Weight | Measurement |
|-----------|--------|-------------|
| WCAG Compliance | 30% | Follows appropriate rules for image type |
| Accuracy | 25% | Describes actual content without hallucination |
| Completeness | 20% | Includes all essential information |
| Conciseness | 15% | As brief as possible while being complete |
| Context Alignment | 10% | Reflects surrounding page context |

### Edge Cases to Test

1. **Ambiguous Images**: Images that could be functional or decorative
2. **No Context**: Images uploaded without webpage context
3. **Poor Quality Images**: Blurry or low-resolution images
4. **Complex Compositions**: Images with multiple distinct elements
5. **Text-Heavy Images**: Screenshots with significant text content
6. **API Failures**: Step 1 succeeds but Step 2 fails, or vice versa

---

## Performance Considerations

### Expected Timing

- **Single-step**: 2-4 seconds average
- **Two-step**: 4-7 seconds average
- **Overhead**: ~2-3 seconds additional

### Optimization Strategies

1. **Parallel Processing**: When processing multiple images, parallelize Step 1 for all images
2. **Caching**: Cache Step 1 analysis for identical images
3. **Smart Fallback**: If Step 1 takes >5 seconds, timeout and use single-step
4. **Batch Mode**: Process Step 1 for all images, then Step 2 for all

```python
def batch_two_step_process(images: list) -> list:
    """
    Optimized batch processing with parallelization
    """
    # Step 1: Analyze all images in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        analyses = list(executor.map(
            lambda img: generator._analyze_image(img['path'], img['context']),
            images
        ))

    # Step 2: Generate all alt texts in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        alt_texts = list(executor.map(
            generator._generate_from_analysis,
            analyses
        ))

    return [
        {'image': img, 'analysis': analysis, 'alt_text': alt_text}
        for img, analysis, alt_text in zip(images, analyses, alt_texts)
    ]
```

---

## Error Handling

### Step 1 Failures

```python
try:
    analysis = self._analyze_image(image_path, context, html_context)
except Exception as e:
    logger.error(f"Step 1 analysis failed: {e}")
    # Fallback to single-step
    return self._generate_single_step(image_path, context)
```

### Step 2 Failures

```python
try:
    alt_text = self._generate_from_analysis(analysis)
except Exception as e:
    logger.error(f"Step 2 generation failed: {e}")
    # Use recommended_approach from analysis as fallback
    alt_text = analysis.get('recommended_approach', '[Alt text generation failed]')
```

### Invalid Analysis JSON

```python
try:
    analysis = json.loads(response)
except json.JSONDecodeError:
    # Try to extract from markdown
    analysis = self._extract_json_from_response(response)
    if not analysis:
        # Fallback to single-step
        return self._generate_single_step(image_path, context)
```

---

## Debugging and Logging

```python
import logging

logger = logging.getLogger('two_step_generator')

# Log Step 1
logger.info(f"Step 1 Analysis for {image_path}")
logger.debug(f"Analysis result: {json.dumps(analysis, indent=2)}")

# Log Step 2
logger.info(f"Step 2 Generation for {image_path}")
logger.debug(f"Generated alt text: {alt_text}")

# Log confidence
logger.info(f"Confidence score: {confidence:.2f}")

# Log fallback
if method == 'single-step':
    logger.warning(f"Fell back to single-step for {image_path}")
```

---

## Migration Plan

### Phase 1: Development and Testing (Week 1-2)
- Implement two-step approach in development environment
- Run A/B comparison tests
- Validate quality improvements
- Identify and fix edge cases

### Phase 2: Beta Testing (Week 3)
- Deploy to beta environment
- Enable for opt-in beta users
- Gather feedback and metrics
- Refine prompts based on results

### Phase 3: Gradual Rollout (Week 4)
- Enable for 25% of users (canary deployment)
- Monitor performance and quality metrics
- Increase to 50%, then 100% if successful
- Keep single-step as fallback

### Phase 4: Full Production (Week 5)
- Two-step becomes default
- Single-step remains as fallback option
- Document final approach
- Update user documentation

---

## Rollback Plan

If issues arise:
1. **Immediate**: Disable two-step via config (`use_two_step_approach: false`)
2. **Monitor**: All users revert to single-step automatically
3. **Investigate**: Review logs to identify root cause
4. **Fix**: Address issues in development environment
5. **Retest**: Validate fixes before re-enabling

---

## Success Metrics

### Quality Metrics
- ✅ Alt text accuracy improves by >15%
- ✅ WCAG compliance rate improves by >10%
- ✅ Hallucination rate decreases by >20%
- ✅ User satisfaction increases (survey)
- ✅ Manual correction rate decreases

### Performance Metrics
- ✅ Average processing time < 7 seconds
- ✅ Success rate > 95%
- ✅ Fallback usage < 5% of cases

### Adoption Metrics
- Configuration adoption rate
- User feedback sentiment
- Bug report frequency

---

## Related Issues

This feature relates to:
- Claude API usage and optimization
- Alt text quality and accuracy
- WCAG compliance verification
- Image classification (functional/informative/decorative)
- Error handling and fallback mechanisms

---

## Labels

- `enhancement`
- `accessibility`
- `bug-fix`
- `ai-optimization`
- `wcag-compliance`

---

## ADR Reference

Decisions requiring ADR documentation:
- Rationale for two-step vs single-step approach
- JSON structure for Step 1 analysis
- Fallback strategy when two-step fails
- Performance trade-offs (speed vs quality)
- Temperature settings for each step

Create ADR in `/development/05-decisions/adr-two-step-approach.md`

---

## Future Enhancements

### Potential Extensions
- **Three-Step Approach**: Add validation/review step before final output
- **Analysis Caching**: Cache and reuse analyses for similar images
- **User Feedback Loop**: Allow users to rate analysis quality
- **Multi-Model Comparison**: Run Step 2 with multiple models, choose best
- **Confidence Scoring**: Surface confidence scores to users
- **Interactive Analysis**: Allow users to edit Step 1 before Step 2
