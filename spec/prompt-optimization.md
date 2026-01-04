# Batch Prompt Comparison Tool Specification
**File**: `prompt-optimization.html`
**Related**: See [admin.md](admin.md), [webmaster.md](webmaster.md), [shared-components.md](shared-components.md)

## Overview
The Batch Prompt Comparison Tool is a specialized tool for **AI engineers and prompt developers** to systematically test and optimize prompts for generating WCAG 2.2-compliant alternative text.

**Primary Purpose**: Scientific prompt engineering through systematic comparison and analysis

**Key Features**:
- Test multiple prompt variants (up to 10) simultaneously
- Run prompts against test image datasets (up to 50 images)
- Side-by-side comparison of outputs
- Automatic quality metrics (length, WCAG compliance, readability, specificity)
- Statistical analysis with charts and visualizations
- AI-generated insights and recommendations
- Export comprehensive results (PDF, Excel, CSV, JSON)
- Prompt template library with version control
- Integration with Webmaster Tool for deployment

**Target Users**: Prompt engineers, AI researchers, accessibility specialists optimizing alt-text generation

---

## Batch Prompt Comparison Tool Specification

### 4.1 Purpose
**Batch Prompt Comparison Tool for AI Engineers**

This tool enables AI engineers and prompt developers to systematically compare different prompt variations across multiple test images. It helps optimize prompts for generating high-quality, WCAG 2.2-compliant alternative text by:
- Testing multiple prompt variants simultaneously
- Running prompts against a dataset of test images
- Comparing outputs side-by-side
- Analyzing quality metrics and performance
- Exporting results for further analysis

**Primary Use Cases**:
- Prompt engineering and optimization for alt text generation
- A/B testing of prompt variations
- Evaluating prompt performance across different image types
- Fine-tuning prompts for specific accessibility requirements
- Benchmarking different AI models with the same prompts

### 4.2 Page Structure

#### Header
- Logo: `assets/Buddy-Logo_no_text.png` (96px × 96px)
- Title: "Batch Prompt Comparison Tool" (h1)
- Subtitle: "Compare and optimize AI prompts for accessibility-focused results"
- Burger menu (top right)

#### Main Content Section

##### 4.2.1 Quick Start / Mode Selection
**Layout**: Card with two prominent options

**Mode Selection** (large radio buttons with descriptions):

1. **Quick Test Mode**
   - Icon: Lightning bolt
   - Description: "Test 2-3 prompt variants on a few images for rapid iteration"
   - Best for: Initial prompt development
   - Button: "Start Quick Test"

2. **Batch Comparison Mode** (default)
   - Icon: Grid/Table
   - Description: "Comprehensive comparison of multiple prompts across a test dataset"
   - Best for: Systematic evaluation and optimization
   - Button: "Start Batch Comparison"

---

##### 4.2.2 Setup Section (Step 1: Configure Test)

###### Test Configuration Panel
**Layout**: Centered card with tabs or sections

**Section A: Prompts to Compare**

**Prompt Input Method** (radio buttons):
- ○ Manual Entry (default)
- ○ Upload from File (.txt, one prompt per file)
- ○ Load from Template Library

**Prompt Variants** (repeatable fields):
- **Prompt 1** (required):
  - Label/Name: Text input (e.g., "Baseline", "Concise", "Detailed v2")
    - Placeholder: "Enter a descriptive name"
  - Prompt Text: Large textarea (10+ rows)
    - Placeholder: "Enter your system prompt or instructions..."
    - Character count displayed
  - Variables: Shows detected placeholders like `{context}`, `{image_type}`
  - "Test this prompt" button (quick single-image test)

- **Add Prompt Variant** button (+ icon)
  - Maximum: 10 prompt variants per batch
  - Each additional prompt gets same interface as Prompt 1

**Prompt Template Library** (if "Load from Template" selected):
- Dropdown with pre-defined templates:
  - "WCAG 2.2 Standard Template"
  - "Concise Alt Text Template"
  - "Detailed Descriptive Template"
  - "Functional Image Template"
  - "Complex Image Template"
  - Custom saved templates (user's own)
- "Preview" button shows template content
- "Use Template" button loads into prompt field

**Section B: Test Dataset**

**Image Selection Method** (radio buttons):
- ○ Upload Test Images
- ○ Use Predefined Test Set
- ○ Select from Previous Analyses

**Upload Test Images** (if selected):
- Drag-and-drop zone (supports multiple files)
- File browser button
- Supported formats: JPG, PNG, WEBP, GIF
- Maximum: 50 images per batch
- Shows thumbnail grid of uploaded images
- Each thumbnail has:
  - Remove button (X)
  - Context input (optional): Brief text about image
  - Image type tag (auto-detected or manual): Photo, Icon, Chart, Diagram, UI Element, etc.

**Predefined Test Sets** (if selected):
- Dropdown with curated test sets:
  - "Standard Web Images (20 images)"
  - "UI Components (15 images)"
  - "Data Visualizations (12 images)"
  - "Product Photos (10 images)"
  - "Mixed Content (25 images)"
- Description of each test set
- "Preview Set" button shows all images

**Image Grid Display**:
- Responsive grid (3-4 columns on desktop)
- Each image card shows:
  - Thumbnail (150x150px)
  - Filename
  - Context field (editable)
  - Image type dropdown
  - Remove button

**Section C: Model & Provider Configuration**

**Use Configuration From** (radio buttons):
- ○ Administration Settings (default)
  - Shows current configured provider/model
  - Link: "Change in Admin settings"
- ○ Override for this test
  - Shows provider/model dropdowns (same as webmaster.html)

**Provider Selection** (if override enabled):
- Provider dropdown: OpenAI, Claude, ECB-LLM, Ollama
- Model dropdown (changes based on provider)

**Processing Options**:
- **Temperature** (slider): 0.0 to 1.0 (default: 0.7)
  - Helper text: "Lower = more deterministic, Higher = more creative"
- **Max Tokens** (number input): Default 150
- **Number of Generations per Image** (dropdown):
  - 1 (default)
  - 3 (for variance testing)
  - 5 (for statistical analysis)
  - Helper text: "Multiple generations help assess prompt consistency"

**Section D: Evaluation Criteria**

**Automatic Quality Metrics** (checkboxes - selected by default):
- ✓ Length (character count)
- ✓ WCAG Compliance (basic checks)
- ✓ Keyword density (common words, filler words)
- ✓ Readability score
- ✓ Specificity score (generic vs. specific language)

**Manual Review** (toggle):
- ☐ Enable manual rating after generation
  - If enabled, user will rate each output on 1-5 scale

**Custom Evaluation Prompt** (optional):
- Checkbox: "Use AI to evaluate output quality"
- Textarea: "Enter evaluation criteria for AI judge"
  - Example: "Rate this alt text on accuracy, conciseness, and WCAG compliance"
  - Uses separate AI call to score each generated alt text

**Action Buttons**:
- **Run Comparison** (large primary button)
  - Disabled until at least 2 prompts and 1 image configured
  - Shows estimated time: "~2 minutes for 3 prompts × 10 images"
  - Shows estimated cost (if using paid API): "~$0.25"
- **Save Configuration** (secondary button)
  - Saves test setup for later reuse
- **Clear All** (outline-danger button)

---

##### 4.2.3 Progress Section (shown during batch processing)

**Progress Display**:
- Overall progress bar: "Processing 15/30 image-prompt combinations"
- Current status: "Generating alt text with Prompt 2 for image_5.jpg..."
- Time elapsed / Estimated time remaining
- "Pause" and "Cancel" buttons

**Live Results Preview** (optional):
- Shows completed results as they arrive
- Expandable section showing latest 3-5 results

**Error Handling**:
- If any generation fails, shows warning
- Option to retry failed items
- Continue with successful results

---

##### 4.2.4 Results Section (shown after completion)

###### Overview Dashboard
**Layout**: Summary cards at top

**Summary Metrics**:
1. **Total Outputs Generated**
   - Number: 30 (3 prompts × 10 images)
   - Processing time: 2m 34s
   - Success rate: 100%

2. **Average Metrics per Prompt**
   - Table showing averages for each prompt variant:
     | Prompt | Avg Length | Avg Quality Score | WCAG Pass Rate |
     |--------|-----------|-------------------|----------------|
     | Baseline | 87 chars | 4.2/5 | 90% |
     | Concise | 52 chars | 3.8/5 | 80% |
     | Detailed v2 | 134 chars | 4.6/5 | 100% |

3. **Winning Prompt** (if clear leader):
   - Highlighted card showing top-performing prompt
   - Based on weighted scoring of metrics

###### Detailed Results Table
**Layout**: Interactive data table with advanced features

**View Options** (tabs):
- **By Image**: Group results by image, compare all prompts for each image
- **By Prompt**: Group results by prompt, show all images for each prompt
- **Side-by-Side**: Matrix view of all combinations

**Table Controls**:
- **Filter** (dropdown):
  - Show all
  - Show only WCAG compliant
  - Show only high-quality (score > 4)
  - Show outliers
- **Sort** (dropdown):
  - By image name
  - By prompt name
  - By quality score
  - By length
- **Search**: Filter by image name or generated text
- **Export Table** button: CSV, Excel, JSON

**Table Structure** (By Image view):

For each image, expandable row showing:

**Image Row Header**:
- Thumbnail (100px)
- Image filename
- Context (if provided)
- Image type
- Expand/collapse icon

**Expanded Content** (comparison of all prompts for this image):

| Prompt | Generated Alt Text | Length | Quality Score | WCAG | Actions |
|--------|-------------------|--------|---------------|------|---------|
| Baseline | "A red apple on white background" | 32 | 4.0 | ✓ | Copy, Edit, Star |
| Concise | "Red apple" | 9 | 3.2 | ✓ | Copy, Edit, Star |
| Detailed v2 | "Vibrant red apple with green stem on clean white background, showing natural texture" | 92 | 4.8 | ✓ | Copy, Edit, Star |

**Quality Score** (hover for breakdown):
- Tooltip shows:
  - Specificity: 4.5/5
  - Readability: 5.0/5
  - WCAG Compliance: 5.0/5
  - Overall: 4.8/5

**Actions**:
- **Copy**: Copies alt text to clipboard
- **Edit**: Opens inline editor to modify
- **Star**: Mark as favorite/example
- **View Details**: Opens modal with full analysis

**Highlight Best** (toggle button):
- When enabled, highlights the best-performing alt text for each image (green background)

###### Side-by-Side Comparison View
**Layout**: Matrix/grid layout

**Headers**:
- Rows: Images (with thumbnails)
- Columns: Prompts

**Cells**: Generated alt text for each combination
- Color-coded by quality score (green = high, yellow = medium, red = low)
- Click to expand and see full details
- Hover to see quick metrics

###### Statistical Analysis Panel
**Layout**: Charts and graphs section

**Charts Available**:
1. **Length Distribution** (box plot):
   - Shows distribution of character counts for each prompt
   - Identifies outliers
   - Shows min, max, median, quartiles

2. **Quality Score Distribution** (histogram):
   - Frequency distribution of quality scores per prompt
   - Shows consistency of each prompt

3. **WCAG Compliance Rate** (bar chart):
   - Percentage of compliant outputs per prompt
   - Breakdown by compliance criteria

4. **Keyword Frequency** (word cloud or bar chart):
   - Most common words used by each prompt
   - Identifies patterns or overused terms

5. **Performance Comparison** (radar chart):
   - Multi-dimensional comparison of prompts
   - Axes: Length, Quality, WCAG, Specificity, Readability, Consistency

**Export Charts**: Button to download as PNG or PDF

###### Detailed Result Modal (opened on "View Details")
**Modal Structure**:

**Header**: Image filename + Prompt name

**Body** (two columns):

**Left Column**:
- Large image preview
- Image metadata:
  - Dimensions
  - File size
  - Type
  - Context (if provided)

**Right Column**:
- **Generated Alt Text** (large, readable)
- **Quality Metrics**:
  - Length: 87 characters
  - Quality Score: 4.2/5 (breakdown shown)
  - WCAG Compliant: ✓ Yes
  - Readability: Grade 8
  - Specificity: High
- **Detailed Analysis**:
  - Keyword breakdown
  - Sentence structure
  - Common patterns detected
- **Comparison to Other Prompts**:
  - Quick comparison table showing how this result ranks
  - Highlighting strengths/weaknesses
- **AI Evaluation** (if enabled):
  - AI judge's assessment
  - Score and reasoning

**Footer Actions**:
- "Copy Alt Text"
- "Use as Example"
- "Flag for Review"
- "Close"

---

##### 4.2.5 Analysis & Insights Section

**AI-Generated Insights** (if enabled in admin settings):
- **Summary**: AI-generated analysis of the batch test
  - "Prompt 'Detailed v2' consistently outperformed others in specificity and WCAG compliance"
  - "Prompt 'Concise' produced alt text averaging 60% shorter but with 15% lower quality scores"
  - "Images of type 'Chart' showed highest variance across prompts"

**Recommendations**:
- Suggested improvements for underperforming prompts
- Best practices identified from top performers
- Areas where prompts showed inconsistency

**Pattern Detection**:
- Common phrases across prompts
- Problematic patterns (e.g., always starting with "Image of...")
- Successful patterns to replicate

---

##### 4.2.6 Export & Actions Section

**Export Options**:

1. **Export Results Report** (dropdown button):
   - **PDF Report**: Full formatted report with:
     - Executive summary
     - All metrics and charts
     - Sample outputs
     - Recommendations
   - **Excel Workbook**: Multiple sheets:
     - Summary sheet
     - Detailed results table
     - Statistical analysis
     - Raw data
   - **CSV**: Flat data table for custom analysis
   - **JSON**: Structured data for API integration

2. **Export Configuration Options** (checkboxes):
   - ✓ Include all generated alt text
   - ✓ Include quality metrics
   - ✓ Include charts and visualizations
   - ✓ Include AI insights
   - ✓ Include test images (as thumbnails or full-size)
   - ✓ Include prompts used

**Prompt Actions**:
- **Save Winning Prompt to Library**:
  - Button saves best-performing prompt as reusable template
  - Prompts user for name and description
- **Apply Winning Prompt to Webmaster Tool**:
  - Sets the best prompt as default in webmaster.html
- **Create New Test with Modified Prompts**:
  - Starts new comparison using insights from this test

**Dataset Actions**:
- **Save Image Set as Test Collection**:
  - Saves current images as reusable test set
- **Add More Images and Rerun**:
  - Extends current test with additional images

---

##### 4.2.7 Saved Tests Library

**Access**: Button in header or sidebar "Load Previous Test"

**Library View**:
- Table/grid of previously run batch tests
- Each entry shows:
  - Test name/ID
  - Date run
  - Number of prompts tested
  - Number of images
  - Quick metrics (winning prompt, avg score)
  - Actions: View, Rerun, Export, Delete

**Search & Filter**:
- Search by test name
- Filter by date range
- Filter by prompts used

**Load Previous Test**:
- Restores complete configuration
- Option to modify before rerunning
- Option to just view results

---

#### Footer
- Testing disclaimer (same as home.html)

### 4.3 User Workflow

**Typical Workflow for Prompt Engineers**:

1. **Setup Phase**:
   - Navigate to Prompt Optimization Tool
   - Choose "Batch Comparison Mode"
   - Enter 3-5 prompt variants to test
   - Upload or select test dataset (10-20 images)
   - Configure evaluation criteria
   - Review estimated time/cost
   - Click "Run Comparison"

2. **Processing Phase**:
   - Monitor progress
   - View live preview of results
   - Wait for completion (~2-5 minutes depending on size)

3. **Analysis Phase**:
   - Review overview dashboard
   - Examine detailed results table
   - Switch between views (by image, by prompt, side-by-side)
   - Study statistical analysis charts
   - Read AI-generated insights

4. **Decision Phase**:
   - Identify winning prompt
   - Understand why it performed better
   - Note areas for improvement

5. **Action Phase**:
   - Export results report
   - Save winning prompt to library
   - Apply winning prompt as default
   - Create follow-up test with refined prompts

**Quick Test Workflow** (for rapid iteration):
1. Enter 2 prompt variants
2. Upload 3-5 test images
3. Run quick comparison
4. Review side-by-side results
5. Iterate on prompts
6. Repeat until satisfied

### 4.4 Technical Implementation Notes

#### 4.4.1 Backend API Endpoints

- `POST /api/batch-test/create` - Create new batch test
  - Input: Prompts array, images array, config
  - Returns: Test ID, estimated time/cost

- `POST /api/batch-test/start/{test_id}` - Start processing
  - Initiates async batch job
  - Returns: Job ID

- `GET /api/batch-test/status/{job_id}` - Poll processing status
  - Returns: Progress percentage, current step, results so far

- `GET /api/batch-test/results/{test_id}` - Get completed results
  - Returns: Full results object with all metrics

- `POST /api/batch-test/evaluate` - Run AI evaluation on results
  - Input: Results, evaluation criteria
  - Returns: AI-generated insights and scores

- `GET /api/batch-test/export/{test_id}` - Export results
  - Query params: format (pdf, excel, csv, json)
  - Returns: File download

- `GET /api/batch-test/history` - List saved tests
  - Returns: Array of previous tests with metadata

- `DELETE /api/batch-test/{test_id}` - Delete saved test

- `POST /api/prompt-templates/save` - Save prompt to library
  - Input: Prompt text, name, description
  - Returns: Template ID

- `GET /api/prompt-templates` - List saved templates
  - Returns: Array of user's templates

#### 4.4.2 Data Structure for Batch Test

```json
{
  "test_id": "bt_uuid_12345",
  "name": "Baseline vs. Optimized Prompts",
  "created_at": "2026-01-03T14:30:00Z",
  "status": "completed",
  "config": {
    "prompts": [
      {
        "id": "p1",
        "name": "Baseline",
        "text": "Describe this image in detail for alternative text...",
        "variables": ["context", "image_type"]
      },
      {
        "id": "p2",
        "name": "Optimized",
        "text": "Generate WCAG-compliant alt text..."
      }
    ],
    "images": [
      {
        "id": "img1",
        "filename": "test_image_1.jpg",
        "url": "/uploads/test_image_1.jpg",
        "context": "Homepage hero image",
        "type": "photo"
      }
    ],
    "model": {
      "provider": "openai",
      "model": "gpt-4o",
      "temperature": 0.7,
      "max_tokens": 150,
      "generations_per_image": 1
    },
    "evaluation": {
      "auto_metrics": ["length", "wcag", "readability"],
      "manual_review": false,
      "ai_judge": {
        "enabled": true,
        "criteria": "Rate on accuracy and WCAG compliance"
      }
    }
  },
  "results": {
    "total_combinations": 20,
    "completed": 20,
    "failed": 0,
    "processing_time_seconds": 154,
    "outputs": [
      {
        "image_id": "img1",
        "prompt_id": "p1",
        "generated_alt_text": "A red apple on white background",
        "metrics": {
          "length": 32,
          "quality_score": 4.0,
          "wcag_compliant": true,
          "readability_grade": 5,
          "specificity_score": 0.75
        },
        "ai_evaluation": {
          "score": 4.0,
          "feedback": "Clear and concise, meets WCAG standards"
        }
      }
    ],
    "summary": {
      "by_prompt": {
        "p1": {
          "avg_length": 87,
          "avg_quality": 4.2,
          "wcag_pass_rate": 0.9
        },
        "p2": {
          "avg_length": 52,
          "avg_quality": 3.8,
          "wcag_pass_rate": 0.8
        }
      },
      "winning_prompt": "p1",
      "insights": [
        "Prompt 'Baseline' produced more specific descriptions",
        "Prompt 'Optimized' was more concise but less detailed"
      ]
    }
  }
}
```

#### 4.4.3 Performance Considerations

- **Parallel Processing**: Process multiple image-prompt combinations concurrently
  - Respect API rate limits
  - Use queue system for large batches
  - Default: 5 concurrent requests (configurable in admin)

- **Caching**:
  - Cache identical prompt+image combinations to avoid duplicate API calls
  - Store results for historical comparison

- **Cost Estimation**:
  - Calculate token usage based on prompt length and expected output
  - Show estimated cost before running (if using paid APIs)
  - Track actual costs after completion

- **Progress Updates**:
  - WebSocket or Server-Sent Events for real-time progress
  - Fallback to polling every 2-3 seconds

#### 4.4.4 Configuration (linked to admin settings)

- Default model/provider for batch tests
- Concurrent request limit
- Maximum batch size (prompts × images)
- Default evaluation criteria
- Cost tracking and budget limits
- Prompt template library storage

### 4.5 Styling

- Consistent with home.html and other tool pages
- Bootstrap Italia framework
- Custom styles from `styles.css`
- Data visualization:
  - Chart.js or similar for graphs
  - Color-coded quality indicators:
    - Green (#28a745): High quality (4.0-5.0)
    - Yellow (#ffc107): Medium quality (3.0-3.9)
    - Red (#dc3545): Low quality (<3.0)
- Responsive tables with horizontal scroll on mobile
- Expandable/collapsible sections for large datasets

### 4.6 Accessibility Requirements

- All form controls properly labeled
- Data tables with proper headers and ARIA attributes
- Charts include text alternatives (data tables)
- Progress updates announced to screen readers
- Keyboard navigation for all interactive elements
- Focus management in modals
- Color is not the only indicator (use icons/text with color coding)
- Export functionality accessible via keyboard

### 4.7 Advanced Features (Future Enhancements)

1. **A/B Testing Mode**:
   - Statistical significance testing
   - Confidence intervals
   - Sample size recommendations

2. **Prompt Version Control**:
   - Track changes to prompts over time
   - Compare current version to historical versions
   - Branching and merging of prompt variants

3. **Collaborative Features**:
   - Share test results with team
   - Comments and annotations on results
   - Team prompt library

4. **Integration with Webmaster Tool**:
   - One-click deployment of winning prompts
   - Real-time A/B testing on live traffic

5. **Custom Evaluation Models**:
   - Train custom scoring models
   - Import external evaluation criteria
   - Human-in-the-loop rating system

6. **Automated Prompt Optimization**:
   - AI-suggested prompt improvements
   - Genetic algorithm for prompt evolution
   - Automatic hyperparameter tuning

---

