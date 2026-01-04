# Webmaster Report Feature

## Why

When using the "Save and generate report" functionality in the webmaster tool, users need a comprehensive report that documents all images processed, the prompts used for analysis, and the generated alt text. This enables:
- Traceability of accessibility improvements
- Quality assurance review
- Documentation for compliance audits
- Historical record of changes made to the website

The function for generating reports already exists in the codebase and needs to be integrated with the save all functionality.

---

## Expected Behavior

When a user clicks "Save and generate report" in the webmaster tool:

1. The image present in the input box is processed 
2. A comprehensive report is automatically generated containing:
   - The image name
   - The analysis prompts used for each image
   - The generated alt text for each image
   - Timestamp of the operation

3. The report in a standard HTML page and the user is prompted with the location where the file must be saved
4. User receives confirmation when the file is saved

---

## Acceptance Criteria

### Functional Requirements
- [ ] Report generation is triggered automatically when "Save and generate rteport" is executed
- [ ] Report includes the image and the context
- [ ] Report shows the generated alt text for each language
- [ ] Report includes operation timestamp and summary statistics
- [ ] Report is saved in an accessible, readable format
- [ ] User is notified of report location after generation

### Technical Requirements
- [ ] Reuse existing report generation function from the codebase
- [ ] Handle errors gracefully (e.g., report generation failure should not prevent rename)
- [ ] Report file naming follows a consistent pattern (e.g., `webmaster-report-YYYY-MM-DD-HHmmss.html`)

### Accessibility Requirements
- [ ] Report format is screen-reader accessible
- [ ] Images in the report include proper alt text
- [ ] Report structure uses semantic HTML (headings, lists, tables)
- [ ] Color contrast meets WCAG AA standards
- [ ] Report can be navigated using keyboard only

### Quality Requirements
- [ ] Report generation function is properly tested
- [ ] Error scenarios are documented and handled
- [ ] Performance impact is minimal (async generation if needed)
- [ ] Generated reports are stored in a designated output directory

---

## Technical Analysis

### Existing Function Location

**Function:** `generate_html_report()` in `backend/app.py:464-920`

**Current Usage:**
- CLI workflow: Triggered by `--report` flag at `app.py:4377` and `app.py:4424`
- Called after batch processing or workflow completion
- Reads all JSON files from `output/alt-text/` folder
- Generates comprehensive HTML report using template at `output/reports/report_template.html`

**Function Capabilities:**
- ✅ Processes single or multiple images (reads all `.json` files in folder)
- ✅ Supports multilingual alt text (handles both string and array formats)
- ✅ Embeds images as base64 data URIs (self-contained report)
- ✅ Includes statistics: image types, HTML tags/attributes, processing time
- ✅ Fully accessible: semantic HTML, ARIA labels, WCAG AA compliant
- ✅ Configurable display sections via `config.json` settings
- ✅ Smart filename generation based on page title

**Function Signature:**
```python
def generate_html_report(
    alt_text_folder=None,           # Folder with JSON files (default: from config)
    output_filename="alt-text-report.html",  # Output filename
    page_title=None                 # Optional page title for filename
) -> str | None                      # Returns path to generated file or None
```

---

## Web Application Integration

### Current State Analysis

#### Frontend (`frontend/home.html` & `frontend/app.js`)

**User Interface:**
- Button: "Save and generate report" at `home.html:408`
- Button handler: `saveAllReviewedAltTexts()` function at `app.js:538-649`

**Current Behavior:**
1. User uploads single image via drag-drop or browse
2. User selects language(s) and generates alt text
3. User reviews and edits generated alt text in textarea(s)
4. User clicks "Save and generate report"
5. Frontend calls `/api/save-reviewed-alt-text` for each language
6. **Gap:** No report generation is triggered
7. **Gap:** User receives only save confirmation, no report download

**Current Limitations:**
- No `/api/generate-report` endpoint exists
- Button only saves reviewed text, doesn't generate report
- No download/save prompt for report file
- No mobile-specific handling

#### Backend API (`backend/api.py`)

**Available Endpoints:**
- ✅ `POST /api/generate-alt-text` - Generates alt text for uploaded image (line 510)
  - Saves JSON to temporary folder, then copies to `output/alt-text/`
  - Returns JSON with alt text, image_id, json_file_path
- ✅ `POST /api/save-reviewed-alt-text` - Saves human-reviewed alt text (line 735)
  - Updates existing JSON file with `human_reviewed_alt_text` field
- ❌ **Missing:** Report generation endpoint

**Data Flow Issues:**
1. **HTML Tag/Attribute Missing:** Web uploads don't capture HTML context
   - `image_tag_attribute` field is not populated in `generate_alt_text_json()`
   - Report shows "unknown" for tag and attribute
   - **Fix needed:** Add default values `{"tag": "img", "attribute": "alt"}` for web uploads

2. **JSON File Location:** Files are correctly saved to `output/alt-text/` (line 689-698)
   - Permanent location matches what `generate_html_report()` expects ✅
   - Files are named: `{image_name_without_ext}_{language}.json`

---

## Implementation Notes

### Required Changes

#### 1. Backend: Add Report Generation Endpoint

**Location:** `backend/api.py` (add after line 839)

**Endpoint Specification:**
```python
@app.post("/api/generate-report")
async def generate_report_endpoint():
    """
    Generate HTML report for webmaster tool.

    Returns:
        FileResponse: HTML report file for download

    Raises:
        HTTPException: If report generation fails
    """
```

**Implementation Requirements:**
- Import `generate_html_report` from `app` module
- Generate timestamp-based filename: `webmaster-report-YYYY-MM-DD-HHmmss.html`
- Call `generate_html_report()` with `output/alt-text` folder
- Return report as `FileResponse` for browser download
- Handle errors gracefully (report failure should not crash API)

**Return Behavior:**
- Desktop browsers: Triggers download dialog with suggested filename
- Mobile browsers: Downloads to device's download folder or prompts save location
- Content-Type: `text/html`
- Headers: `Content-Disposition: attachment; filename="{filename}"`

#### 2. Frontend: Integrate Report Generation

**Location:** `frontend/app.js:538` (modify `saveAllReviewedAltTexts()` function)

**Integration Points:**
1. After successful save of all reviewed texts (line 632)
2. Before showing success message
3. Call new `/api/generate-report` endpoint
4. Handle response as file download

**Implementation Requirements:**
- Check if all saves succeeded (`errorCount === 0`)
- Call `POST /api/generate-report`
- Convert response to Blob
- Create temporary anchor element for download
- Trigger download with timestamp-based filename
- Clean up temporary DOM elements
- Update user feedback messages
- Handle errors without blocking save success message

**Mobile Considerations:**
- Use `window.URL.createObjectURL()` for Blob handling (works on mobile)
- Set `download` attribute on anchor element
- Programmatic click works on iOS Safari and Android Chrome
- Alternative: Open in new tab if download fails on older mobile browsers

#### 3. Backend: Fix Missing Tag/Attribute Data

**Location:** `backend/app.py` (in `generate_alt_text_json()` function)

**Issue:**
- Web uploads lack HTML context (no tag/attribute information)
- CLI workflow extracts tags from actual HTML pages
- Report displays "unknown" for web-uploaded images

**Solution:**
Add default values when generating JSON for web uploads:

```python
json_data = {
    "image_id": image_filename,
    "image_tag_attribute": {
        "tag": "img",
        "attribute": "alt"
    },
    # ... other fields
}
```

**Rationale:**
- Web tool is specifically for `<img>` tag alt text
- Assumption is safe and accurate for this use case
- Report will display meaningful information instead of "unknown"

---

## Mobile User Experience

### Expected Behavior on Mobile

When a mobile user clicks "Save and generate report":

1. **Save Phase:**
   - All reviewed alt texts are saved to JSON files
   - Success message appears

2. **Report Generation:**
   - API generates HTML report on backend
   - Report is sent as file download response

3. **Download Handling:**
   - **iOS Safari:** Downloads to Downloads folder, notification appears
   - **Android Chrome:** Downloads to Downloads folder, notification appears
   - **Mobile Firefox:** May prompt "Open with..." or "Save to..."
   - **Progressive Web Apps:** Can use File System API for better control

4. **User Confirmation:**
   - Browser notification: "Download complete"
   - Success message in UI: "Report generated and download started"
   - Screen reader announcement for accessibility

### Technical Implementation for Mobile

**FileResponse Approach (Recommended):**
```python
from fastapi.responses import FileResponse

return FileResponse(
    path=report_path,
    media_type='text/html',
    filename=os.path.basename(report_path),
    headers={
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    }
)
```

**Frontend Download Handling:**
```javascript
const blob = await response.blob();
const url = window.URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `webmaster-report-${timestamp}.html`;
a.style.display = 'none';
document.body.appendChild(a);
a.click();
window.URL.revokeObjectURL(url);
document.body.removeChild(a);
```

**Mobile-Specific Considerations:**
- ✅ Works on all modern mobile browsers
- ✅ Respects user's default download location
- ✅ Provides native download notification
- ✅ File can be shared via native share sheet
- ⚠️ Some browsers may block automatic downloads (show user action button as fallback)
- ⚠️ Downloaded files go to browser's download folder (not always obvious to users)

**Fallback Strategy:**
If download fails on mobile:
1. Open report in new tab/window
2. User can manually save via browser menu
3. Provide "Download Report" button in the opened report

---

## Data Flow Diagram

### Web Application Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER UPLOADS IMAGE                                           │
│    frontend/home.html → frontend/app.js                         │
│    - Upload via drag-drop or file picker                        │
│    - Optional: Add context text                                 │
│    - Select language(s)                                          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. GENERATE ALT TEXT                                            │
│    POST /api/generate-alt-text (api.py:510)                     │
│    - Saves image to temp folder                                 │
│    - Calls generate_alt_text_json() (app.py)                    │
│    - Creates JSON file in output/alt-text/{image}_{lang}.json   │
│    - Returns: alt_text, image_id, json_file_path                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. USER REVIEWS AND EDITS                                       │
│    frontend/app.js → createLanguageResultCard()                 │
│    - Display generated alt text in textarea                     │
│    - User edits text (if needed)                                │
│    - Character count validation (⚠️ >125 chars)                 │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SAVE REVIEWED ALT TEXT                                       │
│    Click "Save and generate report"                             │
│    → saveAllReviewedAltTexts() (app.js:538)                     │
│    → POST /api/save-reviewed-alt-text (api.py:735)              │
│    - Updates JSON with human_reviewed_alt_text field            │
│    - Called once per language                                   │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GENERATE REPORT (TO BE IMPLEMENTED)                          │
│    → POST /api/generate-report (NEW ENDPOINT)                   │
│    → generate_html_report() (app.py:464)                        │
│    - Reads all JSON files from output/alt-text/                 │
│    - Generates HTML using report_template.html                  │
│    - Saves to output/reports/webmaster-report-{timestamp}.html  │
│    - Returns file as FileResponse                               │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. DOWNLOAD REPORT                                              │
│    frontend/app.js → Blob download                              │
│    - Desktop: Save dialog with filename suggestion              │
│    - Mobile: Download to device folder with notification        │
│    - Accessible confirmation message for screen readers         │
└─────────────────────────────────────────────────────────────────┘
```

### CLI Workflow (Existing, for comparison)

```
python3 app.py --workflow https://example.com --report
    ↓
1. Download images from URL
2. Extract HTML context (tags, attributes)
3. Generate alt text JSON files
4. Call generate_html_report() if --report flag set
5. Save report to output/reports/
```

**Key Difference:** CLI has HTML context, web app doesn't.

---

## Gap Analysis Summary

| Component | Current State | Required | Priority |
|-----------|--------------|----------|----------|
| **Backend: Report API** | ❌ Missing | ✅ Add `/api/generate-report` endpoint | **HIGH** |
| **Frontend: Report Integration** | ❌ Not implemented | ✅ Call API and trigger download | **HIGH** |
| **Backend: Tag/Attribute Data** | ❌ Missing for web uploads | ✅ Add default values | **MEDIUM** |
| **Mobile: Download UX** | ❌ Not implemented | ✅ FileResponse + Blob download | **HIGH** |
| **Error Handling** | ⚠️ Partial | ✅ Graceful degradation | **MEDIUM** |
| **User Feedback** | ⚠️ Save only | ✅ Report download confirmation | **LOW** |

---

## Report Structure

### Generated Report Contents

The `generate_html_report()` function creates a comprehensive report with:

#### 1. Header Section
- **Logo:** My Accessibility Buddy branding (base64 embedded)
- **Title:** "MyAccessibilityBuddy Alt-Text Report"
- **Source Information:**
  - Page title (if available from JSON)
  - Source URL (if available from JSON)
- **AI Model Details:**
  - Vision provider and model (e.g., "OpenAI gpt-4o")
  - Processing provider and model
  - Translation provider and model (if multilingual)
- **Translation Method:** Fast vs Accurate (if multilingual)
- **Summary Statistics:**
  - Total images processed
  - Total processing time (seconds)
  - Generation timestamp (CET timezone)

#### 2. Image Analysis Overview (Configurable)
Controlled by `config.json` → `html_report_display.display_image_analysis_overview`

- **Image Type Distribution:**
  - Informative, decorative, functional, etc.
  - Count per type
- **HTML Tags Used:**
  - List of HTML tags encountered (`<img>`, `<picture>`, etc.)
  - Count per tag
- **HTML Attributes Used:**
  - List of attributes encountered (`alt`, `aria-label`, etc.)
  - Count per attribute

#### 3. Detailed Results (Per Image)
Each image card includes (configurable via `config.json`):

- **Image Preview:** Base64-embedded image (configurable)
- **Image Type:** Badge showing informative/decorative/etc. (configurable)
- **Current Alt Text:** Original alt text from HTML (configurable)
- **Proposed Alt Text:**
  - Single language: Plain text
  - Multilingual: Grouped by language code (EN, IT, ES, etc.)
  - Configurable display
- **HTML Tag/Attribute:** Shows `<tag>` and attribute name (configurable)
- **Vision Model Output:** Step 1 analysis from vision model (always shown if available)
- **Reasoning:**
  - Explanation of why alt text was chosen
  - Single language or multilingual format
  - Configurable display
- **Context:**
  - Surrounding HTML context (truncated to 500 chars if too long)
  - Configurable display

#### 4. Accessibility Features
The report itself is WCAG 2.2 AA compliant:
- ✅ Semantic HTML structure (`<article>`, `<section>`, `<h1>-<h6>`)
- ✅ ARIA labels and landmarks (`role="article"`, `aria-labelledby`)
- ✅ Proper heading hierarchy
- ✅ Keyboard navigable (all interactive elements)
- ✅ Color contrast meets WCAG AA standards
- ✅ Screen reader friendly announcements
- ✅ Images include descriptive alt text
- ✅ Self-contained (no external dependencies)

#### 5. Styling
- **Framework:** Bootstrap Italia (embedded styles)
- **Colors:** Professional blue/gray palette
- **Typography:** Clear, readable fonts
- **Responsive:** Works on desktop, tablet, mobile
- **Print-friendly:** Clean layout for printing/PDF export

### Report Configuration

Report display options in `config.json`:

```json
{
  "html_report_display": {
    "display_proposed_alt_text": true,
    "display_image_type": true,
    "display_current_alt_text": true,
    "display_image_tag_attribute": true,
    "display_reasoning": true,
    "display_context": true,
    "display_image_preview": true,
    "display_html_attributes_used": true,
    "display_html_tags_used": true,
    "display_image_type_distribution": true,
    "display_image_analysis_overview": true
  }
}
```

**Use Cases for Configuration:**
- **Minimal report:** Show only proposed alt text and image preview
- **Detailed report:** Show all fields including reasoning and context
- **Compliance report:** Show all fields for audit trail
- **Quick review:** Hide statistics, show only individual results

### Single Image vs Multiple Images

The `generate_html_report()` function works identically for both:

**Single Image (Web Application):**
- Reads single JSON file from `output/alt-text/`
- Report shows one image card
- Statistics show "Total images: 1"
- All features work the same

**Multiple Images (CLI Workflow):**
- Reads all JSON files from `output/alt-text/`
- Report shows multiple image cards (sorted alphabetically)
- Statistics aggregate all images
- Summary section shows distribution across all images

**No code changes needed** - function adapts automatically based on number of JSON files found.

---

## Implementation Checklist

### Backend Changes

- [ ] **api.py:** Add `/api/generate-report` endpoint
  - [ ] Import `generate_html_report` from `app` module
  - [ ] Generate timestamp-based filename
  - [ ] Call `generate_html_report()` with correct folder path
  - [ ] Return `FileResponse` with proper headers
  - [ ] Add error handling and logging
  - [ ] Test endpoint with Postman/curl

- [ ] **app.py:** Fix missing tag/attribute data (optional but recommended)
  - [ ] Locate `generate_alt_text_json()` function
  - [ ] Add default `image_tag_attribute` for web uploads
  - [ ] Ensure field is always populated in JSON output
  - [ ] Test with web upload flow

### Frontend Changes

- [ ] **app.js:** Modify `saveAllReviewedAltTexts()` function
  - [ ] After successful save, call `/api/generate-report`
  - [ ] Handle response as Blob
  - [ ] Create download link with timestamp filename
  - [ ] Trigger automatic download
  - [ ] Clean up temporary DOM elements
  - [ ] Update success message to mention report download
  - [ ] Add screen reader announcement
  - [ ] Test on desktop browsers (Chrome, Firefox, Safari, Edge)
  - [ ] Test on mobile browsers (iOS Safari, Android Chrome)

### Testing Scenarios

- [ ] **Desktop Web:**
  - [ ] Upload single image, generate alt text, save and download report
  - [ ] Upload image with context, verify context appears in report
  - [ ] Generate multilingual alt text, verify all languages in report
  - [ ] Edit reviewed alt text, verify human-reviewed version in report
  - [ ] Verify report downloads with correct filename
  - [ ] Verify report opens in browser and is readable

- [ ] **Mobile Web:**
  - [ ] Test on iOS Safari (iPhone)
  - [ ] Test on Android Chrome
  - [ ] Verify download notification appears
  - [ ] Verify file is accessible in Downloads folder
  - [ ] Verify report is readable on mobile screen
  - [ ] Test portrait and landscape orientations

- [ ] **Accessibility:**
  - [ ] Navigate report with keyboard only
  - [ ] Test with screen reader (NVDA, JAWS, VoiceOver)
  - [ ] Verify all images have alt text
  - [ ] Check color contrast ratios
  - [ ] Verify heading structure is logical
  - [ ] Test zoom to 200% (readability)

- [ ] **Error Scenarios:**
  - [ ] No JSON files in folder (should fail gracefully)
  - [ ] Report generation fails (should not block save operation)
  - [ ] Network error during report download (should show error message)
  - [ ] Browser blocks download (should provide fallback)

### Documentation

- [ ] Update API documentation with new endpoint
- [ ] Add example request/response for `/api/generate-report`
- [ ] Document report configuration options
- [ ] Add troubleshooting section for download issues
- [ ] Update user guide with report generation workflow

---

## Code Examples

### Backend: Report Generation Endpoint

**File:** `backend/api.py` (add after line 839)

```python
@app.post("/api/generate-report")
async def generate_report_endpoint():
    """
    Generate HTML report for webmaster tool.

    Reads all JSON files from the output/alt-text folder and generates
    a comprehensive accessibility report.

    Returns:
        FileResponse: HTML report file for download

    Raises:
        HTTPException: If report generation fails or no images to report
    """
    from app import generate_html_report
    from datetime import datetime
    from fastapi.responses import FileResponse
    import os

    try:
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        output_filename = f"webmaster-report-{timestamp}.html"

        # Get alt-text folder path
        alt_text_folder = get_absolute_folder_path('output/alt-text')

        # Generate report
        report_path = generate_html_report(
            alt_text_folder=alt_text_folder,
            output_filename=output_filename
        )

        if not report_path:
            raise HTTPException(
                status_code=500,
                detail="Report generation failed - no images found or internal error"
            )

        # Check if file exists
        if not os.path.exists(report_path):
            raise HTTPException(
                status_code=500,
                detail="Report file was not created"
            )

        # Return file for download
        return FileResponse(
            path=report_path,
            media_type='text/html',
            filename=os.path.basename(report_path),
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(report_path)}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )
```

### Frontend: Report Download Integration

**File:** `frontend/app.js` (modify `saveAllReviewedAltTexts()` function around line 632)

```javascript
// Show results
if (errorCount === 0) {
    saveAllSuccessMsg.textContent = `✓ Successfully saved all ${savedCount} language(s)!`;
    saveAllMessage.classList.remove('d-none');

    // Generate and download report
    try {
        saveAllBtnText.textContent = 'Generating report...';

        const reportResponse = await fetch(`${API_BASE_URL}/generate-report`, {
            method: 'POST'
        });

        if (reportResponse.ok) {
            // Convert response to blob
            const blob = await reportResponse.blob();

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const timestamp = new Date().toISOString().slice(0,19).replace(/:/g,'-');
            const filename = `webmaster-report-${timestamp}.html`;

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();

            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Update success message
            saveAllSuccessMsg.textContent = `✓ Successfully saved all ${savedCount} language(s) and generated report!`;
            announceToScreenReader(`Report generated and download started. Check your downloads folder for ${filename}`);
        } else {
            // Report generation failed but saves succeeded
            console.error('Report generation failed:', await reportResponse.text());
            saveAllSuccessMsg.textContent = `✓ Saved ${savedCount} language(s) (report generation failed)`;
        }
    } catch (error) {
        // Report generation error - don't block success message for saves
        console.error('Error generating report:', error);
        saveAllSuccessMsg.textContent = `✓ Saved ${savedCount} language(s) (report generation unavailable)`;
    }

    setTimeout(() => {
        saveAllMessage.classList.add('d-none');
    }, 5000); // Longer timeout to show report message
}
```

---

---

## Recommendation

### Best Function to Use

**Function:** `generate_html_report()` in `backend/app.py:464-920`

**Recommendation:** ✅ **Use as-is without modifications**

**Rationale:**
1. **Already complete:** The function is production-ready and handles all requirements
2. **Works for single images:** Despite being designed for batch processing, it works perfectly with one image
3. **No code changes needed:** The function automatically adapts to the number of JSON files found
4. **Fully accessible:** Already meets all WCAG 2.2 AA requirements
5. **Configurable:** Display options can be controlled via `config.json`

### Integration Strategy

**Minimal Changes Approach (Recommended):**

1. **Backend:** Add one new API endpoint (`/api/generate-report`) - ~30 lines of code
2. **Frontend:** Modify one function (`saveAllReviewedAltTexts()`) - ~25 lines of code
3. **Optional:** Add default tag/attribute values - ~5 lines of code

**Total implementation:** ~60 lines of code, no function rewrites needed

### Why Not Create a New Function?

Creating a webmaster-specific report function would be **redundant** because:
- ❌ Duplicates existing, tested code
- ❌ Increases maintenance burden
- ❌ No additional features needed for single-image reports
- ❌ Same output format desired for both CLI and web workflows
- ✅ Current function already handles all edge cases (multilingual, missing data, etc.)

### Mobile Compatibility

The recommended approach (**FileResponse + Blob download**) is the industry standard for file downloads in web applications:

**Proven to work on:**
- ✅ iOS Safari (iPhone/iPad) - Downloads to Files app
- ✅ Android Chrome - Downloads to Download folder
- ✅ Mobile Firefox - Download notification
- ✅ Samsung Internet Browser
- ✅ Mobile Edge

**Why this approach:**
- Standard web API (no special libraries needed)
- Handles large files efficiently
- Works offline (blob is in memory)
- Respects user's download preferences
- Accessible to assistive technologies

**Fallback options if needed:**
- Open in new tab (user can manually save)
- Add "Download" button to generated report
- Use Service Worker for offline caching

---

## Related Issues

This feature relates to:
- Webmaster tool functionality
- Accessibility compliance documentation
- Quality assurance workflow

---

## Labels

- `feature`
- `accessibility`
- `webmaster-tool`
- `enhancement`

---

## ADR Reference

**Decisions Made:**

1. **Report Format:** HTML (already decided, existing function uses HTML)
   - Self-contained with embedded images
   - Accessible and screen-reader friendly
   - Can be easily converted to PDF if needed

2. **Storage Location:** `output/reports/` folder (already decided, existing function uses this)
   - Consistent with CLI workflow
   - Separate from source data (`output/alt-text/`)
   - Easy to manage and clean up

3. **Performance:** Synchronous generation (acceptable for single images)
   - Single image reports generate in <1 second
   - Async not needed unless processing many images
   - User expects immediate download after clicking button

**No ADR needed** - All decisions align with existing architecture and patterns.

---

## Summary

### Current State
- ✅ Report generation function exists and is fully functional
- ✅ Works for single or multiple images without modification
- ❌ Not integrated with web application
- ❌ No API endpoint for web access
- ❌ No download mechanism in frontend

### Required Work
1. Add `/api/generate-report` endpoint (backend)
2. Integrate report generation in `saveAllReviewedAltTexts()` (frontend)
3. Test on desktop and mobile browsers

### Timeline Estimate
- Backend implementation: 1-2 hours
- Frontend implementation: 1-2 hours
- Testing (desktop + mobile): 2-3 hours
- **Total:** ~6 hours for complete implementation and testing

### Risk Assessment
- **Low risk:** Using existing, tested function
- **High compatibility:** FileResponse works on all modern browsers
- **Graceful degradation:** Report failure doesn't block save operation
- **No breaking changes:** Purely additive feature

---

## Next Steps

1. **Review this specification** with stakeholders
2. **Approve implementation approach**
3. **Implement backend endpoint** (`/api/generate-report`)
4. **Implement frontend integration** (modify `saveAllReviewedAltTexts()`)
5. **Test on target devices** (desktop, iOS, Android)
6. **Deploy to staging** for user acceptance testing
7. **Deploy to production** after approval
