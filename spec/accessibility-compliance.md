# Accessibility Compliance Page Specification
**File**: `accessibility-compliance.html`
**Related**: See [admin.md](admin.md), [remediation.md](remediation.md), [shared-components.md](shared-components.md)

## Overview
The Accessibility Compliance Page is an **Alternative Text Compliance Checker** that analyzes web pages to identify images missing alt text or with inadequate alt text. It generates comprehensive reports and provides AI-powered suggestions for WCAG 2.2-compliant alternative text.

**Key Features**:
- URL-based web page analysis (single page or site crawl)
- Detects all image types (img tags, CSS backgrounds, SVG, picture elements)
- WCAG 2.2 compliance assessment
- AI-powered alt-text suggestions
- Batch processing capabilities
- Multiple export formats (PDF, Excel, CSV, JSON, HTML)
- Integration with Administration settings for AI models
- Health status monitoring for AI providers

---

## Accessibility Compliance Page Specification

### 3.1 Purpose
Page for generating complete alternative text compliance reports of web pages. This tool analyzes web pages, identifies all images (with or without alt text), and generates comprehensive reports showing which images need alternative text or have inadequate alt text according to WCAG 2.2 standards.

### 3.2 Page Structure

#### Header
- Logo: `assets/Buddy-Logo_no_text.png` (96px × 96px)
- Title: "Alternative Text Compliance Checker" (h1)
- Subtitle: "Generate complete alternative text reports for your web pages"
- Burger menu (top right)

#### Main Content Section

##### 3.2.1 URL Input Section
**Layout**: Centered card with shadow (similar to webmaster.html design)

**Components**:
- **URL Input Field**:
  - Label: "Web Page URL" (h5)
  - Input type: text/url
  - Placeholder: "https://example.com/page-to-analyze"
  - Validation: Must be valid URL format
  - Required: Yes
  - Full-width input with Bootstrap Italia styling
  - Helper text: "Enter the full URL of the web page you want to analyze"

- **Analysis Options** (Collapsible section - "Advanced Options"):
  - **Crawl Depth** (radio buttons):
    - "Single page only" (default)
    - "Include linked pages (up to 5 pages)"
    - "Full site crawl (up to 50 pages)"
  - **Image Detection** (checkboxes):
    - ✓ `<img>` tags (checked by default)
    - ✓ CSS background images (checked by default)
    - ✓ SVG images (checked by default)
    - ✓ `<picture>` elements (checked by default)
  - **Report Options** (checkboxes):
    - ✓ Include images with existing alt text for review (checked by default)
    - ✓ Capture image screenshots (optional)
    - ✓ Include context information (surrounding text, headings, links)

- **Action Buttons**:
  - **Primary button**: "Analyze Page" (large, full-width, Bootstrap primary)
    - Disabled until valid URL entered
    - Shows spinner during analysis
  - **Secondary button**: "Clear" (outline-danger, full-width)
    - Resets form and clears results

##### 3.2.2 Progress Indicator (shown during analysis)
**Display**: Animated progress bar with status messages

**Status Messages** (sequential):
1. "Fetching web page..."
2. "Analyzing HTML structure..."
3. "Detecting images..."
4. "Checking existing alt text..."
5. "Generating AI-powered suggestions..."
6. "Compiling report..."

**Visual**: Bootstrap Italia progress bar with percentage and current step indicator

##### 3.2.3 Results Section (shown after analysis completes)
**Layout**: Full-width container with multiple sub-sections

###### Summary Dashboard (Top Section)
**Layout**: 3-4 metric cards in a responsive grid

**Metrics Cards**:
1. **Total Images Found**
   - Large number display
   - Icon: Image icon
   - Color: Blue (#0066cc)

2. **Missing Alt Text**
   - Large number display
   - Icon: Warning/Alert icon
   - Color: Red (#dc3545)
   - Percentage of total

3. **Has Alt Text**
   - Large number display
   - Icon: Checkmark icon
   - Color: Green (#28a745)
   - Percentage of total

4. **Needs Review**
   - Large number display
   - Icon: Question/Review icon
   - Color: Orange (#fd7e14)
   - Alt text exists but may be inadequate (empty, filename, generic)

###### Filter and Sort Controls
**Layout**: Horizontal toolbar above results table

**Filter Options** (dropdown/buttons):
- "All Images" (default)
- "Missing Alt Text Only"
- "Has Alt Text"
- "Needs Review"
- "Decorative Images"

**Sort Options** (dropdown):
- "Position in page" (default)
- "By priority (critical first)"
- "By image type"
- "Alphabetical by filename"

**Search Box**:
- Filter by image filename or existing alt text
- Real-time filtering

###### Detailed Results Table
**Layout**: Responsive table with expandable rows

**Table Columns**:
1. **Status Icon** (20px)
   - 🔴 Red dot: Missing alt text (critical)
   - 🟠 Orange dot: Needs review (warning)
   - 🟢 Green dot: Has adequate alt text
   - ⚪ Gray dot: Decorative (alt="" is appropriate)

2. **Image Preview** (100px thumbnail)
   - Clickable to view full size in modal
   - Fallback if image can't load

3. **Image Information**
   - **Filename/URL** (truncated with tooltip for full path)
   - **Type**: IMG tag / Background CSS / SVG / Picture
   - **Dimensions**: 800×600px
   - **Context**: Heading or paragraph containing the image

4. **Current Alt Text** (150px)
   - Display existing alt attribute
   - Show as "—" if missing
   - Highlight issues:
     - Empty string: `alt=""`
     - Filename-like: `alt="image001.jpg"`
     - Generic: `alt="image"`, `alt="photo"`
     - Too long: >150 characters (show warning)

5. **WCAG Assessment** (100px)
   - "✓ Compliant" (green)
   - "✗ Non-compliant" (red)
   - "⚠ Review needed" (orange)
   - Brief reason (tooltip)

6. **AI Suggestion** (200px)
   - AI-generated alt text suggestion
   - "Generate" button if not yet generated
   - Copy button to copy suggestion
   - Edit inline functionality

7. **Actions** (80px)
   - "Edit" button: Opens modal for detailed editing
   - "Mark as decorative" toggle
   - "Add to queue" for batch processing

###### Expandable Row Details (click on row to expand)
**Additional Information**:
- **Full Image URL**
- **HTML Context** (code snippet showing image in DOM)
- **Surrounding Text** (paragraph before/after, parent heading)
- **Link Context** (if image is inside `<a>` tag)
- **Page Structure** (breadcrumb: Header > Navigation > Logo)
- **Recommendations**:
  - WCAG 2.2 criterion reference (1.1.1 Non-text Content)
  - Specific guidance for this image
  - Why AI suggested this alt text

##### 3.2.4 Bulk Actions Panel
**Position**: Sticky toolbar at bottom of results (when items selected)

**Actions**:
- "Generate AI alt text for selected images" (batch processing)
- "Mark selected as decorative"
- "Export selected to CSV"
- "Send to Remediation Tool" (opens remediation.html with data)

**Selection**:
- Checkboxes in table rows
- "Select all" option
- "Select all missing alt text" quick action

##### 3.2.5 Report Export Section
**Layout**: Card at bottom of results

**Export Options**:
1. **Download Report** (dropdown button):
   - PDF Report (formatted, printable)
   - Excel/CSV (data table)
   - JSON (structured data for API)
   - HTML Report (standalone webpage)

2. **Report Content Options** (checkboxes):
   - ✓ Include summary dashboard
   - ✓ Include all images table
   - ✓ Include image thumbnails
   - ✓ Include AI suggestions
   - ✓ Include remediation recommendations
   - ✓ Include WCAG references

3. **Additional Actions**:
   - "Email Report" button (opens email modal)
   - "Schedule Regular Audits" (link to admin settings)
   - "Save as Template" (for recurring audits)

##### 3.2.6 AI Generation Modal (when "Generate" or batch generate is clicked)
**Modal Structure**:

**Header**: "Generate AI Alt Text Suggestions"

**Body**:
- **Image Display**: Large preview of current image
- **Context Input** (optional):
  - Textarea: "Provide additional context about this image"
  - Pre-filled with surrounding text from page
  - User can edit or add more context
- **Model Selection** (links to admin configuration):
  - Shows currently configured model
  - Link: "Change in Administration settings"
- **Progress indicator** (during generation)

**Generated Results**:
- **Suggested Alt Text** (editable textarea)
- **Character Count**: 125/150 (WCAG recommends <150 chars)
- **WCAG Compliance Indicator**: ✓ Compliant / ⚠ Review suggested
- **Alternative Suggestions** (if available):
  - Short version (concise)
  - Detailed version (descriptive)
  - Decorative option: `alt=""`

**Footer Actions**:
- "Accept & Apply" (saves to results table)
- "Regenerate" (generates new suggestion)
- "Edit Manually" (opens full editor)
- "Cancel"

##### 3.2.7 Image Detail Editor Modal
**Opened when**: User clicks "Edit" in actions column

**Modal Structure**:

**Header**: "Edit Alternative Text"

**Body Layout** (Two columns):

**Left Column** (Image & Context):
- Large image preview
- Image properties:
  - Dimensions
  - File size
  - Format (PNG, JPG, SVG, etc.)
  - URL/path
- HTML context (code viewer)
- Surrounding text display
- Link destination (if applicable)

**Right Column** (Alt Text Editor):
- **Current Alt Text** (display)
- **AI Suggestion** (if generated)
  - "Use this suggestion" button
- **Manual Alt Text Editor**:
  - Large textarea
  - Character counter (live update)
  - WCAG guidelines sidebar:
    - Be concise (<150 characters recommended)
    - Describe function, not appearance (for functional images)
    - Don't start with "Image of..." or "Picture of..."
    - Use alt="" for decorative images
- **Alt Text Type Selection**:
  - ○ Informative (default)
  - ○ Decorative (alt="")
  - ○ Functional (describe action/link)
  - ○ Complex (needs long description)
- **Long Description** (for complex images):
  - Checkbox: "This image needs a long description"
  - Textarea for long description
  - Options for longdesc attribute or aria-describedby

**Footer Actions**:
- "Save Changes" (updates results table)
- "Apply to Similar Images" (smart matching)
- "Cancel"

#### Footer
- Testing disclaimer (same as home.html)

### 3.3 User Workflow

**Step 1**: User enters web page URL
**Step 2**: User configures analysis options (optional)
**Step 3**: User clicks "Analyze Page"
**Step 4**: System fetches page and analyzes images (progress shown)
**Step 5**: Results displayed with summary dashboard
**Step 6**: User reviews each image:
   - For missing alt text: Generate AI suggestion or write manually
   - For existing alt text: Review WCAG compliance
**Step 7**: User exports report or sends to remediation tool
**Step 8**: Optional: Schedule recurring audits

### 3.4 Technical Implementation Notes

#### 3.4.1 Backend API Endpoints
- `POST /api/analyze-page` - Initiates page analysis
  - Input: URL, options
  - Returns: Job ID for polling
- `GET /api/analysis-status/{job_id}` - Polls analysis progress
- `GET /api/analysis-results/{job_id}` - Retrieves completed analysis
- `POST /api/generate-alt-text` - Generates AI alt text for single image
  - Input: Image URL/data, context, model preferences
  - Returns: Suggested alt text
- `POST /api/batch-generate-alt-text` - Batch generation
- `GET /api/export-report/{job_id}` - Exports report in requested format

#### 3.4.2 Data Structure for Results
```json
{
  "analysis_id": "uuid",
  "url": "https://example.com/page",
  "timestamp": "2026-01-03T10:30:00Z",
  "summary": {
    "total_images": 45,
    "missing_alt": 12,
    "has_alt": 28,
    "needs_review": 5,
    "decorative": 0
  },
  "images": [
    {
      "id": "img_001",
      "src": "https://example.com/images/logo.png",
      "type": "img_tag",
      "dimensions": {"width": 200, "height": 100},
      "current_alt": "",
      "status": "missing",
      "context": {
        "parent_tag": "header",
        "surrounding_text": "Welcome to our site",
        "is_linked": true,
        "link_href": "/"
      },
      "ai_suggestion": null,
      "wcag_compliant": false
    }
  ]
}
```

#### 3.4.3 Configuration (stored in admin settings)
- Default AI model for alt text generation
- AI provider (OpenAI, Claude, ECB-LLM, Ollama)
- Max images per analysis
- Crawl depth limits
- Report template preferences
- Email notification settings

### 3.5 Styling
- Consistent with home.html and webmaster.html
- Bootstrap Italia framework
- Custom styles from `styles.css`
- Color coding:
  - Red (#dc3545): Critical issues (missing alt)
  - Orange (#fd7e14): Warnings (needs review)
  - Green (#28a745): Compliant
  - Blue (#0066cc): Primary actions
  - Gray (#6c757d): Decorative/neutral

### 3.6 Accessibility Requirements
- All form controls properly labeled
- Progress announcements for screen readers
- Keyboard navigation for all interactive elements
- ARIA live regions for dynamic updates
- Focus management in modals
- High contrast mode support
- Results table accessible to screen readers (proper headers, row/col associations)

---

