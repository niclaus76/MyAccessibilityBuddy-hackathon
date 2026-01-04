# Remove 125 Character Alt Text Limit

## Why

The current prompt instructs the AI to truncate alt text to a maximum of 125 characters. This artificial limitation creates several problems:

1. **WCAG Doesn't Mandate Length Limits**: WCAG 2.1 guidelines recommend conciseness but do not specify a hard character limit. The 125-character rule is arbitrary and not based on accessibility standards.

2. **Context May Require Longer Descriptions**: Some images convey complex information (charts, diagrams, infographics) that cannot be adequately described in 125 characters while maintaining accuracy and usefulness.

3. **Screen Readers Handle Long Alt Text**: Modern screen readers can handle alt text of various lengths. While conciseness is valued, truncating meaningful descriptions reduces accessibility rather than improving it.

4. **Loss of Critical Information**: Forcing truncation may cause the AI to omit important details, making the alt text less useful for users who rely on it.

5. **Conflicts with "Informative" Image Requirements**: Informative images require descriptions that convey the content and meaning. A strict character limit may prevent adequate descriptions.

### Current vs Desired Behavior

**Current (with 125-limit):**
```
Image: Complex chart showing quarterly revenue trends
Alt text: "Bar chart showing quarterly revenue with upward trend in Q3 and Q4"
(Exactly 125 chars, may omit specific data points)
```

**Desired (no hard limit):**
```
Image: Complex chart showing quarterly revenue trends
Alt text: "Bar chart displaying quarterly revenue for 2024: Q1 $2.5M, Q2 $2.8M,
Q3 $3.4M, Q4 $4.1M, showing a consistent upward trend with 64% growth year-over-year"
(~160 chars, includes specific data and context)
```

---

## Expected Behavior

### Prompt Changes

1. **Remove Hard Limit Instruction**
   - Remove or modify: "Be concise yet descriptive (80-125 characters recommended)"
   - Replace with guidance on appropriate length based on image type

2. **Add Contextual Length Guidance**
   - Functional images: Brief (20-60 characters typical)
   - Simple informative images: Concise (40-100 characters typical)
   - Complex informative images: As needed (100-250+ characters acceptable)
   - Decorative images: Empty alt text

3. **Emphasize Quality Over Length**
   - Focus on conveying the image's purpose and content
   - Be concise while being complete
   - Don't sacrifice accuracy for brevity
   - Include all essential information

### User Experience

1. **No Arbitrary Truncation**
   - AI generates alt text of appropriate length for the image
   - Complex images receive detailed descriptions
   - Simple images receive brief descriptions
   - Length varies based on content, not arbitrary limits

2. **Optional User Preferences**
   - Users can optionally specify preferred length ranges
   - Default behavior: no hard limit, AI decides based on context
   - Advanced option: user-defined max length (if needed for CMS constraints)

---

## Acceptance Criteria

### Functional Requirements
- [ ] Prompt does not include "80-125 characters recommended" instruction
- [ ] Prompt includes context-appropriate length guidance
- [ ] AI generates alt text of varying lengths based on image complexity
- [ ] Simple images receive concise alt text (naturally brief)
- [ ] Complex images receive detailed alt text (as needed)
- [ ] No truncation of meaningful information

### Technical Requirements
- [ ] Update prompt templates to remove 125-character limit
- [ ] Update all prompt variations (standard, GEO boost, etc.)
- [ ] Ensure prompt emphasizes quality and completeness
- [ ] Add guidance for different image types (functional/informative/decorative)
- [ ] Backend does not enforce character limits on generated alt text
- [ ] Frontend displays alt text of any length appropriately

### Quality Requirements
- [ ] Test with simple images (expect <100 characters)
- [ ] Test with complex images (expect >125 characters when needed)
- [ ] Validate that long alt text remains focused and useful
- [ ] Verify WCAG compliance of generated alt text
- [ ] Compare quality before/after removing limit
- [ ] Ensure alt text remains concise when appropriate

### Documentation Requirements
- [ ] Update user documentation explaining length approach
- [ ] Provide examples of appropriate lengths for different image types
- [ ] Document optional length preferences (if implemented)
- [ ] Update prompt engineering documentation

---

## Implementation Notes

### Current Prompt Structure (Before)

```python
prompt = f"""
You are an accessibility expert.

Image: {image_path}
Context: {context}

Generate appropriate alt text following these guidelines:
- Follow WCAG 2.1 Level AA guidelines
- Be concise yet descriptive (80-125 characters recommended)  # ← REMOVE THIS
- Accurately describe image content and purpose
"""
```

### Updated Prompt Structure (After)

```python
prompt = f"""
You are an accessibility expert.

Image: {image_path}
Context: {context}

Generate appropriate alt text following these guidelines:
- Follow WCAG 2.1 Level AA guidelines
- Be as concise as possible while fully conveying the image's purpose
- Length should match the image type:
  * Functional images (buttons, links): Brief and action-oriented
  * Simple informative images: Concise description of visible content
  * Complex informative images: Detailed enough to convey all essential information
  * Decorative images: Empty alt text (alt="")
- Focus on quality and completeness, not character count
- Include all essential information; don't sacrifice accuracy for brevity
"""
```

### Alternative: Flexible Length Ranges

If some guidance is still desired:

```python
length_guidance = {
    'functional': 'Keep brief (typically 20-60 characters)',
    'simple_informative': 'Keep concise (typically 40-100 characters)',
    'complex_informative': 'Provide complete description (100-250+ characters as needed)',
    'decorative': 'Use empty alt text (alt="")'
}

prompt = f"""
...
Image type: {image_type}
Alt text guidance: {length_guidance[image_type]}
...
"""
```

### Updating All Prompt Variations

Ensure the change is applied to:

1. **Standard Accessibility Prompt**
2. **GEO Boost Prompt**
3. **Webmaster Tool Prompt**
4. **Single Image Analysis Prompt**
5. **Batch Processing Prompt**

Example for GEO Boost:

```python
# Before
"""
Alt text must be:
* Use search-relevant but natural terms
* Optimize for assistive technologies and AI indexing
* Follow WCAG 2.1 Level AA guidelines
* Be concise yet descriptive (80-125 characters recommended)  # ← REMOVE
"""

# After
"""
Alt text must be:
* Use search-relevant but natural terms
* Optimize for assistive technologies and AI indexing
* Follow WCAG 2.1 Level AA guidelines
* Be as concise as possible while conveying complete information
* Length should be appropriate for the image's complexity and purpose
* Don't sacrifice essential details for arbitrary brevity
"""
```

---

## Code Changes Required

### 1. Update Prompt Template Files

```bash
# Files to update:
- prompt/processing/processing_prompt_v2.txt
- Any other prompt template files used in the system
```

### 2. Update Backend Prompt Building

```python
# In backend/api.py or wherever prompts are built

def build_alt_text_prompt(image_data, context, config):
    """Build prompt without character limit restrictions"""

    base_guidelines = """
Generate appropriate alt text following these guidelines:
- Follow WCAG 2.1 Level AA guidelines
- Be concise while fully conveying the image's purpose and content
- Length should naturally match the complexity of the image
- Functional images: Brief and action-oriented
- Simple images: Concise description of visible content
- Complex images: Detailed enough to convey all essential information
- Focus on accuracy and completeness over character count
"""

    # Add GEO boost if enabled
    if config.get('GEO_boost', False):
        base_guidelines += """
- Use search-relevant but natural terms
- Optimize for assistive technologies and AI indexing
"""

    return base_guidelines
```

### 3. Remove Any Backend Length Validation

```python
# BEFORE: Remove code like this
def validate_alt_text(alt_text):
    if len(alt_text) > 125:
        return alt_text[:125]  # Truncation
    return alt_text

# AFTER: No truncation
def validate_alt_text(alt_text):
    # Validate quality, not length
    if not alt_text.strip():
        raise ValueError("Alt text cannot be empty")
    return alt_text.strip()
```

---

## Examples

### Example 1: Simple Logo (Functional)

**Image:** Company logo used as home link

**Current (with limit):** "MyAccessibilityBuddy logo linking to home page" (48 chars)

**After (no limit):** "MyAccessibilityBuddy logo linking to home page" (48 chars)

*Result: Same, naturally concise*

### Example 2: Data Visualization (Complex Informative)

**Image:** Multi-series bar chart with trend lines

**Current (with 125 limit):**
"Bar chart showing quarterly sales data for four product categories with upward trends in electronics and home goods" (118 chars)
*Missing: Specific values, percentages, time period*

**After (no limit):**
"Bar chart displaying quarterly sales performance for 2024 across four product categories: Electronics ($4.2M, +45% YoY), Home Goods ($3.1M, +32% YoY), Apparel ($2.8M, +12% YoY), and Accessories ($1.9M, -5% YoY), showing strong growth in Electronics and Home Goods while Accessories declined" (287 chars)
*Includes: Specific data, context, trends, complete picture*

### Example 3: Icon Button (Functional)

**Image:** Gear icon in settings button

**Current (with limit):** "Settings" (8 chars)

**After (no limit):** "Settings" (8 chars)

*Result: Same, naturally brief*

### Example 4: Infographic (Complex Informative)

**Image:** Accessibility compliance process infographic

**Current (with 125 limit):**
"Infographic showing five-step accessibility compliance process from audit to implementation and monitoring" (107 chars)
*Missing: The actual steps, connections, outcomes*

**After (no limit):**
"Infographic illustrating the five-step accessibility compliance process: 1) Conduct comprehensive WCAG audit, 2) Prioritize issues by severity and impact, 3) Develop remediation plan with timeline, 4) Implement fixes and alt text updates, 5) Continuous monitoring and testing. Arrows show cyclical nature with feedback loops between testing and remediation." (358 chars)
*Includes: All steps, process flow, key insights*

---

## Testing Strategy

### A/B Comparison Testing

```python
def test_alt_text_quality():
    """Compare alt text quality with and without 125-char limit"""

    test_images = [
        ('simple_logo.png', 'functional'),
        ('product_photo.jpg', 'simple_informative'),
        ('complex_chart.png', 'complex_informative'),
        ('infographic.svg', 'complex_informative'),
    ]

    for image, image_type in test_images:
        # Generate with old prompt (125 limit)
        alt_text_old = generate_alt_text_old(image)

        # Generate with new prompt (no limit)
        alt_text_new = generate_alt_text_new(image)

        # Compare
        print(f"\nImage: {image} ({image_type})")
        print(f"Old ({len(alt_text_old)} chars): {alt_text_old}")
        print(f"New ({len(alt_text_new)} chars): {alt_text_new}")

        # Assess completeness and quality
        assert assess_completeness(alt_text_new, image) >= \
               assess_completeness(alt_text_old, image)
```

### Quality Metrics

- **Completeness**: Does alt text convey all essential information?
- **Accuracy**: Is the description factually correct?
- **Conciseness**: Is it as brief as possible while being complete?
- **WCAG Compliance**: Does it follow accessibility guidelines?
- **User Feedback**: Do screen reader users find it helpful?

### Test Cases

| Image Type | Expected Length Range | Quality Check |
|------------|----------------------|---------------|
| Icon/Button | 5-50 chars | Action is clear |
| Simple photo | 40-100 chars | Subject is described |
| Complex chart | 100-300+ chars | Data is conveyed |
| Infographic | 150-400+ chars | Process/story is clear |
| Decorative | 0 chars (empty) | Correctly identified |

---

## User Communication

### Documentation Update

Add to user guide:

```markdown
## Alt Text Length

MyAccessibilityBuddy generates alt text of appropriate length based on
the image's complexity and purpose:

- **Functional images** (buttons, links): Brief descriptions focusing on
  the action or destination

- **Simple informative images**: Concise descriptions of visible content

- **Complex informative images** (charts, diagrams, infographics): Detailed
  descriptions that convey all essential information, which may be longer

The system prioritizes quality and completeness over arbitrary character
limits. While alt text is kept as concise as possible, complex images may
require longer descriptions to be truly accessible.

### Why No Character Limit?

WCAG guidelines recommend conciseness but don't specify character limits.
Modern screen readers handle alt text of various lengths effectively. Our
approach ensures that users receive complete, accurate information rather
than truncated descriptions.
```

---

## Migration and Rollout

### Phase 1: Update Prompts (Week 1)
- Remove 125-character limit from all prompts
- Add contextual length guidance
- Deploy to development environment

### Phase 2: Testing and Validation (Week 2)
- Run A/B comparison tests
- Gather sample outputs for various image types
- Validate WCAG compliance
- Collect feedback from accessibility experts

### Phase 3: Production Deployment (Week 3)
- Deploy updated prompts to production
- Monitor alt text lengths and quality
- Gather user feedback
- Document any issues

### Phase 4: Documentation and Training (Week 4)
- Update all user documentation
- Create examples showing appropriate lengths
- Publish blog post explaining the change
- Update training materials

---

## Rollback Plan

If issues arise:

1. **Immediate**: Revert to previous prompt with 125 limit
2. **Analyze**: Determine what went wrong (AI generating excessive length, unhelpful verbosity)
3. **Adjust**: Refine guidance in prompt (add "avoid unnecessary verbosity")
4. **Retest**: Validate fixes in development
5. **Redeploy**: Roll out corrected version

---

## Success Metrics

### Quantitative Metrics
- Average alt text length by image type
- Distribution of alt text lengths
- User satisfaction scores (survey)
- Screen reader user feedback ratings
- WCAG compliance test results

### Qualitative Metrics
- Expert review of sample alt text quality
- User testimonials on alt text usefulness
- Comparison of information completeness before/after
- Reduction in manual alt text corrections needed

### Target Outcomes
- ✅ Simple images remain concise (<100 chars typical)
- ✅ Complex images receive adequate descriptions (>125 chars when needed)
- ✅ No loss of WCAG compliance
- ✅ Positive user feedback on alt text quality
- ✅ Reduced need for manual corrections

---

## Related Issues

This feature relates to:
- WCAG compliance and accessibility standards
- Prompt engineering and optimization
- Alt text quality and usefulness
- User experience for screen reader users

---

## Labels

- `enhancement`
- `accessibility`
- `prompt-engineering`
- `wcag-compliance`

---

## ADR Reference

Decisions requiring ADR documentation:
- Rationale for removing 125-character limit
- Contextual length guidance approach
- Testing and validation methodology
- Rollback criteria if quality degrades

Create ADR in `/development/05-decisions/adr-remove-125-char-limit.md`

---

## WCAG Reference

### WCAG 2.1 Guidelines on Alt Text

**Success Criterion 1.1.1 Non-text Content (Level A):**
> All non-text content that is presented to the user has a text alternative
> that serves the equivalent purpose...

**WCAG does NOT specify character limits.** Key guidance:
- Alt text should convey the same information as the image
- Be as concise as possible while being complete
- Complex images may require long descriptions
- Length depends on content, not arbitrary rules

### Resources
- [WCAG 2.1 - Text Alternatives](https://www.w3.org/WAI/WCAG21/Understanding/non-text-content.html)
- [W3C Alt Text Decision Tree](https://www.w3.org/WAI/tutorials/images/decision-tree/)
- [WebAIM: Alternative Text](https://webaim.org/techniques/alttext/)
