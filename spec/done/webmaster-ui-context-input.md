# Webmaster UI Specifications

## Context Upload Area Requirements

### Overview
The context upload area should support both file upload (drag-and-drop or browse) and direct text input via an editable textbox.

### HTML Structure Reference
```html
<div class="upload-area border-2 border-dashed rounded p-3 text-center mb-3"
     id="contextDragdrop"
     role="button"
     tabindex="0"
     aria-label="Upload context file - drag and drop text file or press Enter to browse"
     style="border-color: #17324d; background-color: #f5f5f5; cursor: pointer; transition: all 0.3s;"
     data-focus-mouse="false">
    <!-- SVG icon and upload UI -->
</div>
```

### Functional Requirements

#### 1. Editable Textbox Integration
- **Location**: The textbox should be integrated within or immediately adjacent to the upload area
- **Visibility**: The textbox should be visible at all times, allowing users to either:
  - Upload a file (via drag-and-drop or browse button)
  - Type/paste text directly into the textbox

#### 2. File Upload Behavior
When a user uploads a file:
- The textbox must display the file's content
- The content must be **editable** - users can modify the uploaded text
- The drag-and-drop area should remain functional for uploading a different file
- Clear visual feedback should indicate that a file has been loaded

#### 3. Direct Text Input Behavior
When no file is uploaded:
- The textbox must be **active and editable** from the start
- Users can type or paste context directly into the textbox
- Placeholder text should guide users (e.g., "Enter context here or upload a file")

#### 4. Interaction Flow

**Scenario A: File Upload First**
1. User drags/drops or browses for a `.txt` file
2. File content is loaded into the textbox
3. User can edit the text in the textbox
4. User can upload a different file to replace the content

**Scenario B: Direct Text Entry**
1. User clicks into the textbox
2. User types or pastes context text
3. User can optionally upload a file later (which replaces the typed content)

#### 5. UI/UX Requirements

**Visual Design:**
- Textbox should have a minimum height (e.g., 150-200px) to accommodate multiple lines
- Clear border and background to distinguish from the upload area
- Maintain the existing color scheme (#17324d border, #f5f5f5 background)

**Accessibility:**
- Textbox must have proper `aria-label` (e.g., "Context text editor")
- Support keyboard navigation (Tab to focus, Esc to blur)
- Screen reader should announce when file content is loaded
- Visual focus indicator when textbox is active

**State Management:**
- Track whether content originated from file upload or direct input
- Provide option to clear content
- Consider adding character/line count display

#### 6. Technical Implementation Notes

**HTML Structure:**
```html
<div class="upload-area ...">
    <!-- Existing drag-drop UI -->
    <div class="upload-icon mb-2">...</div>
    <div class="upload-text">...</div>
    <input type="file" id="contextFileInput" ...>

    <!-- NEW: Editable textbox -->
    <textarea
        id="contextTextbox"
        class="form-control mt-3"
        rows="8"
        placeholder="Enter context here or upload a file above"
        aria-label="Context text editor"
        style="resize: vertical; min-height: 150px;">
    </textarea>
</div>
```

**JavaScript Behavior:**
- On file upload: Read file content and set `textarea.value = fileContent`
- Allow continuous editing of textarea
- Optionally add a "Clear" button to reset the textbox
- Consider adding unsaved changes warning if user navigates away

#### 7. Optional Enhancements
- **Clear button**: Add a button to clear the textbox content
- **File name display**: Show uploaded filename above the textbox
- **Auto-save**: Save draft content to localStorage
- **Format validation**: Warn if uploaded file is not plain text
- **Character limit**: Set maximum context length if applicable

### Acceptance Criteria
- [ ] Textbox is visible and active on page load
- [ ] User can type/paste text directly into textbox
- [ ] Uploaded file content appears in textbox
- [ ] Text remains editable after file upload
- [ ] User can upload a new file to replace existing content
- [ ] All accessibility requirements are met (keyboard nav, ARIA labels, screen reader support)
- [ ] Visual design is consistent with existing UI (#17324d color scheme)
- [ ] Drag-and-drop functionality continues to work with textbox present
