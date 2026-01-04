# Webmaster Extended Context Files Support

## Why

The webmaster tool currently analyzes images based on webpage context. However, websites often have supporting documentation in various formats (DOCX, PDF, ODG) that provide essential context for accurate alt text generation:
- Policy documents that explain the purpose of images
- Design specifications that clarify visual intent
- Documentation that describes functional workflows
- Supporting materials that provide domain-specific context

By allowing these file types as context sources, the alt text generation becomes more accurate and contextually relevant, especially for:
- Technical documentation sites
- Government portals
- Educational platforms
- Enterprise intranets

---

## Expected Behavior

When using the webmaster tool:

1. **File Upload Interface**
   - User can upload context files in addition to specifying webpage URL
   - Supported formats: `.docx`, `.pdf`, `.odg` (OpenDocument Graphics)
   - Multiple files can be uploaded simultaneously
   - Clear indication of supported file types and size limits

2. **Context Processing**
   - Uploaded documents are parsed and text content is extracted
   - Extracted content is combined with webpage context
   - Combined context is used for image analysis and alt text generation
   - Original files are stored temporarily for the session

3. **User Feedback**
   - Progress indicator during document processing
   - Confirmation of successful context extraction
   - Error messages if file cannot be processed
   - Summary showing context sources used (webpage + N documents)

4. **Integration with Analysis**
   - Context from documents is included in the prompt sent to the AI model
   - Report indicates which context sources were used
   - User can review extracted context before proceeding with analysis

---

## Acceptance Criteria

### Functional Requirements
- [ ] File upload interface accepts `.docx`, `.pdf`, and `.odg` files
- [ ] Multiple files can be uploaded in a single session
- [ ] Text content is successfully extracted from all supported formats
- [ ] Extracted context is combined with webpage context
- [ ] Combined context is used in alt text generation prompts
- [ ] User can preview extracted context before analysis
- [ ] Context files are properly cleaned up after session ends

### Technical Requirements
- [ ] Use appropriate libraries for document parsing:
  - DOCX: `python-docx` or similar
  - PDF: `PyPDF2`, `pdfplumber`, or `pypdf`
  - ODG: `odfpy` or similar for OpenDocument format
- [ ] Implement file size limits (e.g., max 10MB per file)
- [ ] Validate file types server-side (not just by extension)
- [ ] Handle malformed or corrupted documents gracefully
- [ ] Extract text while preserving structure (headings, lists, tables)
- [ ] Implement temporary file storage with automatic cleanup
- [ ] Add context length limits and truncation strategy if needed

### Security Requirements
- [ ] Validate file uploads to prevent malicious files
- [ ] Sanitize extracted text to prevent injection attacks
- [ ] Implement file size limits to prevent DoS
- [ ] Store uploaded files in secure temporary directory
- [ ] Ensure files are deleted after session expires
- [ ] Scan for macros in DOCX files (warn/reject if present)

### Accessibility Requirements
- [ ] File upload interface is keyboard accessible
- [ ] Screen readers announce upload status and errors
- [ ] ARIA labels for file input and upload progress
- [ ] Visual and programmatic indication of file processing status
- [ ] Error messages are clear and actionable

### Quality Requirements
- [ ] Unit tests for each document format parser
- [ ] Integration tests for combined context handling
- [ ] Performance tests for large document processing
- [ ] Error handling tests for corrupted files
- [ ] Documentation of supported features and limitations per format

---

## Implementation Notes

### Document Parsing Approach

#### DOCX Files
```python
# Use python-docx library
from docx import Document

def extract_docx_text(file_path):
    """Extract text from DOCX file preserving structure"""
    doc = Document(file_path)
    text_parts = []

    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)

    # Handle tables if needed
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text_parts.append(cell.text)

    return "\n\n".join(text_parts)
```

#### PDF Files
```python
# Use pdfplumber or PyPDF2
import pdfplumber

def extract_pdf_text(file_path):
    """Extract text from PDF file"""
    text_parts = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return "\n\n".join(text_parts)
```

#### ODG Files
```python
# Use odfpy library
from odf import text, teletype
from odf.opendocument import load

def extract_odg_text(file_path):
    """Extract text from ODG file"""
    doc = load(file_path)
    text_parts = []

    # Extract text from all text elements
    for para in doc.getElementsByType(text.P):
        text_content = teletype.extractText(para)
        if text_content.strip():
            text_parts.append(text_content)

    return "\n\n".join(text_parts)
```

### Context Combination Strategy

```python
def build_combined_context(webpage_context, document_contexts):
    """
    Combine webpage and document contexts for prompt

    Args:
        webpage_context: str - HTML/text from webpage
        document_contexts: list[dict] - List of {filename, content} dicts

    Returns:
        str - Combined context for AI prompt
    """
    parts = ["=== WEBPAGE CONTEXT ===", webpage_context, ""]

    for doc in document_contexts:
        parts.append(f"=== DOCUMENT: {doc['filename']} ===")
        parts.append(doc['content'])
        parts.append("")

    return "\n".join(parts)
```

### Frontend Interface

```javascript
// File upload handling
const contextFileUpload = {
  allowedTypes: ['.docx', '.pdf', '.odg'],
  maxSize: 10 * 1024 * 1024, // 10MB
  maxFiles: 5,

  validateFile(file) {
    // Check file size
    if (file.size > this.maxSize) {
      return { valid: false, error: 'File too large (max 10MB)' };
    }

    // Check file extension
    const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!this.allowedTypes.includes(ext)) {
      return { valid: false, error: 'Unsupported file type' };
    }

    return { valid: true };
  }
};
```

### Storage and Cleanup

- Store uploaded files in: `/tmp/webmaster-context/{session_id}/`
- Implement cleanup job that removes files older than 24 hours
- Clear session files immediately after analysis completes
- Add server startup routine to clean orphaned temp files

---

## User Interface Mockup

```
┌─────────────────────────────────────────────────┐
│ Webmaster Tool - Image Analysis                 │
├─────────────────────────────────────────────────┤
│                                                  │
│ Website URL: [___________________________]       │
│                                                  │
│ Additional Context Files (Optional):             │
│ ┌───────────────────────────────────────────┐   │
│ │ Drag & drop files here or click to upload │   │
│ │ Supported: DOCX, PDF, ODG (max 10MB each) │   │
│ └───────────────────────────────────────────┘   │
│                                                  │
│ Uploaded Files:                                  │
│ ✓ policy-document.docx (245 KB)        [Remove] │
│ ✓ design-specs.pdf (1.2 MB)           [Remove] │
│ ⚠ archive.odg - Processing...                   │
│                                                  │
│ [Preview Extracted Context]  [Analyze Images]   │
└─────────────────────────────────────────────────┘
```

---

## Data Flow

```
User Action → File Upload
              ↓
           Validation (type, size, malware check)
              ↓
           Store in /tmp/{session_id}/
              ↓
           Extract Text (format-specific parser)
              ↓
           Combine with Webpage Context
              ↓
           Generate Image Analysis Prompt
              ↓
           Process Images & Generate Alt Text
              ↓
           Cleanup Temporary Files
```

---

## Error Handling

| Error Scenario | User Message | System Action |
|----------------|--------------|---------------|
| Unsupported file type | "File type not supported. Please upload DOCX, PDF, or ODG files." | Reject upload |
| File too large | "File exceeds 10MB limit. Please upload a smaller file." | Reject upload |
| Corrupted document | "Unable to read document. File may be corrupted." | Continue with other sources |
| Extraction timeout | "Document processing timed out. Continuing with available context." | Use partial results |
| No text extracted | "No text found in document. Please verify file content." | Continue with other sources |

---

## Performance Considerations

- Document parsing should not block the UI
- Implement async processing with progress feedback
- Set timeout limits for large document parsing (e.g., 30 seconds per file)
- Consider text length limits to avoid token overruns
- Cache extracted context during the session to avoid re-parsing

---

## Related Issues

This feature relates to:
- Webmaster tool core functionality
- Context analysis and prompt engineering
- File upload and processing infrastructure
- Security and validation layer

---

## Labels

- `feature`
- `webmaster-tool`
- `enhancement`
- `context-analysis`

---

## Dependencies

### Required Libraries
```
# Add to requirements.txt
python-docx>=0.8.11
pdfplumber>=0.9.0  # or PyPDF2>=3.0.0
odfpy>=1.4.1
python-magic>=0.4.27  # For file type validation
```

---

## ADR Reference

Decisions requiring ADR documentation:
- Choice of PDF parsing library (pdfplumber vs PyPDF2 vs pypdf)
- Context length limit and truncation strategy
- File storage location and cleanup schedule
- Security scanning approach for uploaded files

Create ADRs in `/development/05-decisions/` addressing these choices.

---

## Testing Strategy

### Unit Tests
- Test each document format parser independently
- Test context combination logic
- Test file validation and sanitization

### Integration Tests
- Test complete flow: upload → parse → analyze → cleanup
- Test error recovery scenarios
- Test with various document formats and structures

### Security Tests
- Test with malicious file uploads
- Test with oversized files
- Test with corrupted/malformed documents
- Test file cleanup and no data leakage

### Performance Tests
- Test with large documents (near size limit)
- Test with multiple simultaneous uploads
- Test cleanup job performance
