# GEO Boost Feature

## Why

Generative Engine Optimization (GEO) is an emerging field focused on optimizing content for AI-powered search engines and large language models. As AI-driven search becomes more prevalent, alt text serves a dual purpose:

1. **Accessibility**: Making images understandable for users with screen readers
2. **AI Discoverability**: Enabling AI search engines to understand and index image content

By adding a GEO boost option, users can optimize their alt text to be:
- More discoverable in AI-powered search results
- Better indexed by generative AI systems
- Search-relevant while maintaining natural language
- Optimized for both assistive technologies and AI crawlers

This feature benefits:
- Content creators seeking better AI search visibility
- SEO professionals adapting to generative AI search
- Organizations wanting dual accessibility + discoverability
- Websites targeting both human users and AI agents

---

## Expected Behavior

### Configuration

1. **Backend Configuration (`config.json`)**
   - Parameter name: `GEO_boost`
   - Type: Boolean
   - Default: `false`
   - Location: Configuration file read by backend

2. **Frontend Control (`webmaster.html`)**
   - UI element: Radio button or toggle switch
   - Label: "Enable GEO Boost" or "Optimize for AI Search"
   - Location: Webmaster tool options panel
   - State: Synced with backend configuration

### Prompt Enhancement

When `GEO_boost` is set to `true`, the following sections are added to the AI prompt:

#### WHO YOU ARE Section
```
* You are an accessibility and Generative Engine Optimization (GEO) optimization expert.
```

#### Alt Text Requirements Section
```
Alt text must be:
* Use search-relevant but natural terms
* Optimize for assistive technologies and AI indexing
```

### User Workflow

1. User opens webmaster tool
2. User sees "Enable GEO Boost" option (radio button/toggle)
3. User enables GEO boost
4. Setting is saved to `config.json` (`GEO_boost: true`)
5. When analyzing images, enhanced prompt includes GEO instructions
6. Generated alt text is optimized for both accessibility and AI search
7. User can toggle off to return to accessibility-only mode

---

## Acceptance Criteria

### Functional Requirements
- [ ] `GEO_boost` parameter exists in `config.json`
- [ ] Radio button/toggle control exists in `webmaster.html`
- [ ] UI control correctly reads current `GEO_boost` state
- [ ] Changing UI control updates `config.json`
- [ ] When enabled, prompt includes GEO-specific instructions
- [ ] When disabled, prompt uses standard accessibility-only instructions
- [ ] Setting persists across sessions
- [ ] Clear visual indication of current GEO boost state

### Technical Requirements
- [ ] Config parameter is properly validated (boolean type)
- [ ] Frontend-backend synchronization works correctly
- [ ] Prompt building logic includes conditional GEO sections
- [ ] No performance impact when GEO boost is disabled
- [ ] Configuration change takes effect immediately (no restart needed)
- [ ] Error handling for invalid config values

### Prompt Integration Requirements
- [ ] "WHO YOU ARE" section added when GEO_boost is true
- [ ] "Alt text must be" section added when GEO_boost is true
- [ ] Prompt sections are inserted at correct positions
- [ ] GEO instructions don't conflict with base accessibility requirements
- [ ] Both accessibility and GEO guidelines are followed simultaneously

### User Experience Requirements
- [ ] Radio button/toggle is clearly labeled
- [ ] Tooltip or help text explains GEO boost feature
- [ ] Visual feedback when toggling setting
- [ ] Setting is easily discoverable in UI
- [ ] Documentation explains when to use GEO boost

### Accessibility Requirements
- [ ] Radio button/toggle is keyboard accessible
- [ ] Screen reader announces control state (on/off)
- [ ] ARIA labels properly describe the control
- [ ] Visual state clearly indicates enabled/disabled
- [ ] Help text is accessible to assistive technologies

### Quality Requirements
- [ ] Unit tests for config reading/writing
- [ ] Integration tests for prompt building with GEO boost
- [ ] UI tests for toggle functionality
- [ ] Validation that GEO-optimized alt text remains accessible
- [ ] Comparison tests (GEO on vs off) for quality assurance

---

## Implementation Notes

### Backend: Config Structure

```json
{
  "GEO_boost": false,
  "other_settings": "..."
}
```

### Backend: Prompt Building Logic

```python
def build_prompt(image_data, config):
    """
    Build prompt with optional GEO boost sections
    """
    prompt_parts = []

    # Base prompt
    prompt_parts.append("You are analyzing an image to generate alt text.")

    # WHO YOU ARE section (conditional)
    if config.get('GEO_boost', False):
        prompt_parts.append("""
WHO YOU ARE:
* You are an accessibility and Generative Engine Optimization (GEO) optimization expert.
""")
    else:
        prompt_parts.append("""
WHO YOU ARE:
* You are an accessibility expert specializing in WCAG compliance.
""")

    # Image context
    prompt_parts.append(f"Image path: {image_data['path']}")
    prompt_parts.append(f"Context: {image_data['context']}")

    # Alt text requirements (conditional)
    if config.get('GEO_boost', False):
        prompt_parts.append("""
Alt text must be:
* Use search-relevant but natural terms
* Optimize for assistive technologies and AI indexing
* Follow WCAG 2.1 Level AA guidelines
* Be concise yet descriptive (80-125 characters recommended)
""")
    else:
        prompt_parts.append("""
Alt text must be:
* Follow WCAG 2.1 Level AA guidelines
* Be concise yet descriptive (80-125 characters recommended)
* Accurately describe image content and purpose
""")

    return "\n".join(prompt_parts)
```

### Frontend: Radio Button HTML

```html
<div class="form-group">
    <label class="font-weight-bold">Alt Text Optimization</label>
    <div class="form-check">
        <input
            class="form-check-input"
            type="radio"
            name="geoBoost"
            id="geoBoostOff"
            value="false"
            checked>
        <label class="form-check-label" for="geoBoostOff">
            Accessibility Only
            <small class="form-text text-muted">
                Focus on WCAG compliance and screen reader optimization
            </small>
        </label>
    </div>
    <div class="form-check">
        <input
            class="form-check-input"
            type="radio"
            name="geoBoost"
            id="geoBoostOn"
            value="true">
        <label class="form-check-label" for="geoBoostOn">
            Accessibility + GEO Boost
            <small class="form-text text-muted">
                Optimize for both assistive technologies and AI search indexing
            </small>
        </label>
    </div>
</div>
```

### Frontend: JavaScript Logic

```javascript
// Load current setting from config
async function loadGeoBoostSetting() {
    const response = await fetch('/api/config');
    const config = await response.json();
    const geoBoost = config.GEO_boost || false;

    // Set radio button state
    if (geoBoost) {
        document.getElementById('geoBoostOn').checked = true;
    } else {
        document.getElementById('geoBoostOff').checked = true;
    }
}

// Save setting when changed
document.querySelectorAll('input[name="geoBoost"]').forEach(radio => {
    radio.addEventListener('change', async (e) => {
        const geoBoost = e.target.value === 'true';

        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ GEO_boost: geoBoost })
        });

        // Show confirmation
        showNotification('GEO Boost setting updated');
    });
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', loadGeoBoostSetting);
```

---

## Example Comparison

### Same Image, Different Settings

**Image:** Screenshot of a dashboard with analytics graphs

**GEO Boost OFF (Accessibility Only):**
```
Prompt: You are an accessibility expert specializing in WCAG compliance.
        Alt text must follow WCAG 2.1 Level AA guidelines...

Generated Alt Text:
"Dashboard showing website analytics with visitor count, page views,
and engagement metrics displayed in bar graphs"
```

**GEO Boost ON (Accessibility + GEO):**
```
Prompt: You are an accessibility and Generative Engine Optimization (GEO)
        optimization expert.
        Alt text must use search-relevant but natural terms and optimize
        for assistive technologies and AI indexing...

Generated Alt Text:
"Web analytics dashboard displaying real-time traffic statistics,
visitor metrics, page view trends, and user engagement data visualizations"
```

**Key Differences:**
- GEO version includes search-relevant terms: "web analytics", "real-time traffic", "user engagement data"
- Maintains natural language and accessibility
- More discoverable by AI search engines
- Still follows WCAG guidelines

---

## UI Mockup

```
┌─────────────────────────────────────────────────┐
│ Webmaster Tool - Settings                       │
├─────────────────────────────────────────────────┤
│                                                  │
│ Alt Text Optimization:                          │
│                                                  │
│ ○ Accessibility Only                            │
│   Focus on WCAG compliance and screen reader    │
│   optimization                                  │
│                                                  │
│ ● Accessibility + GEO Boost                     │
│   Optimize for both assistive technologies      │
│   and AI search indexing                        │
│                                                  │
│ ℹ️ GEO Boost enhances alt text for AI-powered   │
│   search engines while maintaining accessibility│
│   standards.                                    │
│                                                  │
│ [Learn More About GEO]                          │
└─────────────────────────────────────────────────┘
```

---

## Data Flow

```
User Toggles Radio Button
    ↓
JavaScript Event Listener
    ↓
POST /api/config
    ↓
Update config.json (GEO_boost: true/false)
    ↓
Return Success
    ↓
User Analyzes Images
    ↓
Backend Reads Config
    ↓
Build Prompt with Conditional GEO Sections
    ↓
Send to AI Model
    ↓
AI Generates GEO-Optimized (or Standard) Alt Text
    ↓
Return to User
```

---

## Configuration API Endpoints

### GET /api/config
Returns current configuration including GEO_boost setting

**Response:**
```json
{
  "GEO_boost": false,
  "other_settings": "..."
}
```

### POST /api/config
Updates configuration settings

**Request:**
```json
{
  "GEO_boost": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration updated",
  "GEO_boost": true
}
```

---

## Testing Strategy

### Unit Tests
```python
def test_prompt_without_geo_boost():
    config = {"GEO_boost": False}
    prompt = build_prompt(image_data, config)
    assert "GEO optimization expert" not in prompt
    assert "search-relevant" not in prompt

def test_prompt_with_geo_boost():
    config = {"GEO_boost": True}
    prompt = build_prompt(image_data, config)
    assert "GEO optimization expert" in prompt
    assert "search-relevant but natural terms" in prompt
    assert "AI indexing" in prompt

def test_config_update():
    update_config({"GEO_boost": True})
    config = read_config()
    assert config["GEO_boost"] == True
```

### Integration Tests
- Test complete flow: UI toggle → config update → prompt generation
- Verify alt text quality with GEO boost enabled
- Compare GEO-optimized vs standard alt text
- Test persistence across sessions

### Accessibility Validation
- Verify radio button keyboard navigation
- Test screen reader announcements
- Validate ARIA labels
- Confirm visual state indicators

---

## Documentation Updates

### User Documentation
- Explain what GEO boost does
- When to enable GEO boost (content sites, SEO focus)
- When to keep it disabled (pure accessibility focus)
- Examples of GEO-optimized alt text

### Technical Documentation
- Configuration parameter reference
- API endpoint specifications
- Prompt template changes
- Integration guide for developers

---

## Related Issues

This feature relates to:
- Prompt engineering and optimization
- Configuration management
- Webmaster tool UI/UX
- SEO and AI search optimization

---

## Labels

- `feature`
- `enhancement`
- `seo`
- `geo-optimization`
- `configuration`

---

## ADR Reference

Decisions requiring ADR documentation:
- Radio button vs toggle switch for UI control
- Prompt structure with GEO sections
- Default value for GEO_boost (true or false)
- Whether to allow per-image GEO boost or only global setting

Create ADRs in `/development/05-decisions/` addressing these choices.

---

## Future Enhancements

### Potential Extensions
- **GEO Strength Slider**: Low/Medium/High GEO optimization levels
- **Per-Image Override**: Enable GEO boost for specific images only
- **GEO Analytics**: Track AI search performance of GEO-optimized images
- **Custom GEO Keywords**: Allow users to specify target search terms
- **A/B Testing**: Compare performance of GEO vs non-GEO alt text

---

## Success Metrics

- User adoption rate of GEO boost feature
- Improved AI search visibility (if trackable)
- Maintained WCAG compliance with GEO boost enabled
- User satisfaction with GEO-optimized alt text
- Performance comparison: discoverability vs accessibility scores
