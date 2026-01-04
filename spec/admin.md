# Administration Tool Page Specification
**File**: `admin.html`
**Related**: See all other page specs, [shared-components.md](shared-components.md)

## Overview
The Administration page is the **centralized configuration and settings hub** for My Accessibility Buddy. It allows users to configure AI models, manage API keys, set defaults, and monitor system health.

**Key Features**:
- **Factory Defaults**: All settings load from `config/config.json` and `config/config.advanced.json`
- **Health Monitoring**: Real-time health checks for all AI providers (🟢 green = OK, 🔴 red = error, 🟠 orange = warning, ⚪ gray = disabled)
- **7 Configuration Tabs**: AI Models, Compliance Settings, API Keys, Preferences, Report Templates, Advanced Settings, System Info
- **Security**: API keys encrypted at rest, separate save for sensitive data
- **Import/Export**: Configuration backup and restore
- **Reset Options**: Reset to factory defaults or complete factory reset

**Configuration Files**:
- **Input**: `backend/config/config.json` (main settings)
- **Input**: `backend/config/config.advanced.json` (advanced settings)
- **Output**: `backend/config/config.user.json` (user changes, preserves factory defaults)

**Health Check System**:
- Tests all enabled AI providers (OpenAI, Claude, ECB-LLM, Ollama)
- Shows connection status, latency, available models
- OAuth2 token expiration tracking
- Automatic refresh and manual test options

---

## Administration Tool Page Specification

### 6.1 Purpose
Centralized configuration and administration page for all My Accessibility Buddy tools. This page allows users to configure AI models, API keys, default settings, and preferences that are used across all tools (Webmaster Tool, Accessibility Compliance, Prompt Optimization, and Remediation Tool).

**Factory Defaults**: All settings load initial values from `config/config.json` and `config/config.advanced.json`. Users can modify these settings through the UI, and changes are saved to a separate user configuration file (e.g., `config/config.user.json`), preserving the original factory defaults.

**Health Monitoring**: Real-time health checks for all configured AI providers with visual indicators (green = OK, red = error, orange = warning).

### 6.2 Page Structure

#### Header
- Logo: `assets/Buddy-Logo_no_text.png` (96px × 96px)
- Title: "Administration" (h1)
- Subtitle: "Configure settings and preferences for My Accessibility Buddy"
- Burger menu (top right)

#### Main Content Section

##### 6.2.1 Settings Navigation Tabs
**Layout**: Horizontal tabs or vertical sidebar navigation

**Tab Categories**:
1. AI Models & Providers
2. Accessibility Compliance Settings
3. API Keys & Authentication
4. Default Preferences
5. Report Templates
6. Advanced Settings
7. System Information

---

##### 6.2.2 Tab 1: AI Models & Providers

**Section Title**: "AI Model Configuration"
**Description**: "Configure which AI models and providers to use for different tasks"

**Health Status Banner** (always visible at top):
- Real-time connectivity status for all enabled providers
- Visual indicators:
  - 🟢 Green dot + "Connected" (provider is accessible and working)
  - 🔴 Red dot + "Error" (provider is not accessible or authentication failed)
  - 🟠 Orange dot + "Warning" (provider is configured but not tested)
  - ⚪ Gray dot + "Disabled" (provider is disabled in config)
- Layout: Horizontal row of provider status badges
- Example: `OpenAI 🟢 | Claude 🔴 | ECB-LLM ⚪ | Ollama 🟠`
- Click on badge to expand details (error message, latency, last checked time)
- "Refresh All" button to rerun health checks

###### Vision Step Configuration (Image Analysis)
**Purpose**: Used in Webmaster Tool and Accessibility Compliance for image analysis

**Factory Default Source**: `config.json → steps.vision.provider` and `steps.vision.model`

**Components**:
- **Default Provider** (dropdown):
  - OpenAI
  - Claude (Anthropic)
  - ECB-LLM (if enabled in config)
  - Ollama (if enabled in config)
  - Label: "Vision Provider"
  - Helper text: "Provider used for analyzing images"
  - Factory Default: Loaded from `config.json → steps.vision.provider` (default: "OpenAI")
  - Health indicator next to dropdown: Shows provider status (🟢 🔴 🟠)

- **Default Model** (dropdown - changes based on provider):
  - Options loaded dynamically from `config.json → [provider].available_models.vision`
  - OpenAI: gpt-4o, gpt-5.1, gpt-5.2 (from config.json)
  - Claude: claude-sonnet-4-20250514, claude-opus-4-20250514 (from config.json)
  - ECB-LLM: gpt-4o, gpt-5.1 (from config.json)
  - Ollama: granite3.2-vision, llama3.2-vision, moondream, llava (from config.json)
  - Label: "Vision Model"
  - Helper text: "Specific model for image analysis"
  - Factory Default: Loaded from `config.json → steps.vision.model` (default: "gpt-4o")

- **Test Connection** button:
  - Tests if the selected provider/model is accessible
  - Shows inline status:
    - 🟢 Success: "Connected successfully (latency: 245ms)"
    - 🔴 Error: "Connection failed: Invalid API key"
    - 🟠 Warning: "Connected but model not available"
  - Updates health status banner after test

###### Processing Step Configuration (Alt Text Generation)
**Purpose**: Used for generating alt text from image descriptions

**Factory Default Source**: `config.json → steps.processing.provider` and `steps.processing.model`

**Components**:
- **Default Provider** (dropdown)
  - Same options as Vision
  - Factory Default: Loaded from `config.json → steps.processing.provider` (default: "OpenAI")
  - Health indicator next to dropdown: Shows provider status (🟢 🔴 🟠)

- **Default Model** (dropdown)
  - Options loaded dynamically from `config.json → [provider].available_models.processing`
  - OpenAI: gpt-4o, gpt-5.1, gpt-5.2 (from config.json)
  - Claude: claude-sonnet-4-20250514, claude-opus-4-20250514 (from config.json)
  - ECB-LLM: gpt-4o, gpt-5.1 (from config.json)
  - Ollama: phi3, llama3.2, granite3.2, qwen2.5, mistral (from config.json)
  - Factory Default: Loaded from `config.json → steps.processing.model` (default: "gpt-4o")

- **Test Connection** button
  - Same behavior as Vision step
  - Updates health status banner

###### Translation Step Configuration
**Purpose**: Used for translating alt text to multiple languages

**Factory Default Source**: `config.json → steps.translation.provider`, `steps.translation.model`, and `translation_mode`

**Components**:
- **Default Provider** (dropdown)
  - Same options as Vision/Processing
  - Factory Default: Loaded from `config.json → steps.translation.provider` (default: "OpenAI")
  - Health indicator next to dropdown: Shows provider status (🟢 🔴 🟠)

- **Default Model** (dropdown)
  - Options loaded dynamically from `config.json → [provider].available_models.translation`
  - OpenAI: gpt-4o, gpt-5.1, gpt-5.2 (from config.json)
  - Claude: claude-sonnet-4-20250514, claude-3-5-haiku-20241022 (from config.json)
  - ECB-LLM: gpt-4o, gpt-5.1 (from config.json)
  - Ollama: phi3, llama3.2, granite3.2, qwen2.5, mistral (from config.json)
  - Factory Default: Loaded from `config.json → steps.translation.model` (default: "gpt-4o")

- **Translation Mode** (radio buttons):
  - ○ Fast (translate from first language)
  - ○ Accurate (generate in each language)
  - Factory Default: Loaded from `config.json → translation_mode` (default: "fast")

- **Test Connection** button
  - Same behavior as Vision/Processing steps
  - Updates health status banner

###### Model Selection Strategy
**Components**:
- **Allow Override in Tools** (checkbox):
  - ✓ Allow users to select different models in Advanced mode (checked by default)
  - If unchecked, users must use admin-configured defaults

- **Fallback Behavior** (dropdown):
  - "Use default model if selected model fails"
  - "Show error and stop processing"
  - "Prompt user to select alternative"

**Save Button**: "Save AI Configuration" (primary button)

---

##### 6.2.3 Tab 2: Accessibility Compliance Settings

**Section Title**: "Accessibility Compliance Tool Configuration"
**Description**: "Settings specific to the Alternative Text Compliance Checker"

###### Analysis Settings

**Crawl Limits**:
- **Maximum Pages per Analysis** (number input):
  - Default: 50
  - Range: 1-500
  - Helper text: "Limit for 'Full site crawl' option"

- **Maximum Images per Page** (number input):
  - Default: 100
  - Range: 1-1000
  - Helper text: "Stop analysis after detecting this many images on a single page"

- **Analysis Timeout** (number input):
  - Default: 300 (5 minutes)
  - Range: 60-3600 seconds
  - Helper text: "Maximum time to wait for page analysis"

**Image Detection Settings** (checkboxes - defaults for Analysis Options):
- ✓ Detect `<img>` tags (checked, disabled - always on)
- ✓ Detect CSS background images (checked by default)
- ✓ Detect SVG images (checked by default)
- ✓ Detect `<picture>` elements (checked by default)
- ☐ Detect inline data URIs
- ☐ Detect images in iframes

**Alt Text Quality Assessment**:
- **Minimum Alt Text Length** (number input):
  - Default: 3 characters
  - Helper text: "Alt text shorter than this triggers 'needs review'"

- **Maximum Recommended Length** (number input):
  - Default: 150 characters
  - Helper text: "WCAG recommendation for alt text length"

- **Generic Alt Text Detection** (textarea):
  - Pre-filled keywords that indicate poor alt text:
    - "image", "photo", "picture", "img", "graphic"
    - Filenames like ".jpg", ".png", "IMG_", "DSC_"
  - Users can add/remove keywords

**AI Generation Settings for Compliance Tool**:
- **Auto-generate AI Suggestions** (radio buttons):
  - ○ Generate immediately for all missing alt text
  - ○ Generate only when user clicks "Generate" button (default)
  - ○ Never auto-generate (manual only)

- **Batch Generation Limit** (number input):
  - Default: 20 images
  - Range: 1-100
  - Helper text: "Maximum images to process in one batch generation request"

###### Report Settings

**Default Export Format** (dropdown):
- PDF Report (formatted, printable)
- Excel/CSV (data table)
- JSON (structured data)
- HTML Report (standalone)

**Default Report Contents** (checkboxes):
- ✓ Include summary dashboard
- ✓ Include all images table
- ✓ Include image thumbnails
- ☐ Include AI suggestions
- ✓ Include remediation recommendations
- ✓ Include WCAG references
- ☐ Include page screenshots

**Report Branding**:
- **Organization Name** (text input):
  - Optional, appears in header of PDF reports
- **Logo Upload** (file input):
  - Upload organization logo for reports
  - Supported: PNG, JPG (max 500KB)

###### Audit Scheduling

**Enable Scheduled Audits** (toggle switch):
- When enabled, shows additional options:

**Scheduled URLs** (repeatable field):
- URL input + Frequency dropdown (Daily/Weekly/Monthly)
- "Add another URL" button

**Email Notifications**:
- **Send Reports To** (email input, comma-separated):
  - Example: admin@example.com, team@example.com
- **Email Format** (dropdown):
  - Attach PDF report
  - Attach CSV data
  - Link to online report

**Save Button**: "Save Compliance Settings" (primary button)

---

##### 6.2.4 Tab 3: API Keys & Authentication

**Section Title**: "API Keys & Authentication"
**Description**: "Configure authentication for AI providers"
**Security Note**: "⚠️ API keys are encrypted and stored securely. Never share your keys."

**Overall Health Status Banner** (at top):
- Summary bar showing authentication status for all providers
- Example: `🟢 OpenAI: Authenticated | 🔴 Claude: Not configured | 🟠 ECB-LLM: Not tested | 🟢 Ollama: Connected`
- "Test All Connections" button to run health checks on all providers

---

###### OpenAI Configuration
**Factory Default Source**: `config.json → openai.enabled`

**Section Health Status** (top-right of section header):
- 🟢 "API key valid and working (tested 2 min ago)"
- 🔴 "Authentication failed: Invalid API key"
- 🟠 "API key set but not tested"
- ⚪ "Disabled"

**Components**:
- **Enable OpenAI** (toggle switch):
  - Factory Default: `config.json → openai.enabled` (default: true)
  - When disabled, grays out all OpenAI settings

- **OpenAI API Key** (password input):
  - Masked input field (shows as ••••••••)
  - "Show/Hide" toggle button (eye icon)
  - Placeholder: "sk-proj-..." (if empty)
  - "Test Key" button:
    - Validates key by making test API call
    - Updates health status:
      - 🟢 "Valid - Models: gpt-4o, gpt-5.1 (latency: 312ms)"
      - 🔴 "Invalid: Unauthorized (401)"
      - 🔴 "Network error: Connection timeout"
  - Helper text: "Required for OpenAI API access. Get key from platform.openai.com"

- **Organization ID** (text input, optional):
  - Placeholder: "org-..."
  - Helper text: "Optional - only needed for organization accounts"

- **Base URL** (text input):
  - Default: https://api.openai.com/v1
  - Factory Default: Standard OpenAI endpoint
  - Helper text: "Custom endpoint for proxies or OpenAI-compatible APIs"

---

###### Anthropic (Claude) Configuration
**Factory Default Source**: `config.json → claude.enabled`

**Section Health Status** (top-right of section header):
- Same format as OpenAI with provider-specific messages

**Components**:
- **Enable Claude** (toggle switch):
  - Factory Default: `config.json → claude.enabled` (default: true)

- **Anthropic API Key** (password input):
  - Masked, with show/hide toggle
  - Placeholder: "sk-ant-..."
  - "Test Key" button:
    - Validates with Anthropic API
    - Updates health status:
      - 🟢 "Valid - Models: claude-sonnet-4, claude-opus-4 (latency: 245ms)"
      - 🔴 "Invalid: Authentication error"
  - Helper text: "Required for Claude API. Get key from console.anthropic.com"

- **Base URL** (text input):
  - Default: https://api.anthropic.com
  - Factory Default: Standard Anthropic endpoint
  - Helper text: "Custom endpoint if using proxy"

---

###### ECB-LLM Configuration
**Factory Default Sources**:
- `config.json → ecb_llm.enabled`
- `config.advanced.json → ecb_llm.token_url`, `ecb_llm.authorize_url`, `ecb_llm.scope`

**Section Health Status** (top-right of section header):
- 🟢 "OAuth2 authenticated as john.doe@ecb.europa.eu"
- 🟢 "Token valid (expires in 4h 23m)"
- 🔴 "Authentication failed: Token expired"
- 🟠 "Configured but not tested"
- ⚪ "Disabled (ecb_llm_client not installed)"

**Components**:
- **Enable ECB-LLM** (toggle switch):
  - Factory Default: `config.json → ecb_llm.enabled` (default: false)
  - Helper text: "⚠️ Requires ecb_llm_client Python package"
  - Shows installation instruction if package missing

- **Authentication Method** (radio buttons):
  - ○ OAuth2 U2A (User-to-Application) - recommended
  - ○ API Token (for service accounts)

- **OAuth2 Settings** (if OAuth2 selected):
  - **Token URL** (display field, read-only):
    - Value: Loaded from `config.advanced.json → ecb_llm.token_url`
    - Default: "https://igam.escb.eu/igam-oauth/oauth2/rest/token"
  - **Authorize URL** (display field, read-only):
    - Value: Loaded from `config.advanced.json → ecb_llm.authorize_url`
    - Default: "https://igam.escb.eu/igam-oauth/oauth2/rest/authorize"
  - **Scope** (display field, read-only):
    - Value: Loaded from `config.advanced.json → ecb_llm.scope`
    - Default: "openid profile LLM.api.read"
  - **"Connect to ECB-LLM"** button (primary):
    - Initiates OAuth2 authorization flow
    - Opens new window/tab for ECB authentication
    - Updates status after successful authentication
  - **Connection Status Card**:
    - 🟢 **Connected**:
      - Shows: "Authenticated as [username]"
      - Token expiration: "Expires: 2026-01-03 18:30 (in 4h 23m)"
      - Last refreshed: "Token refreshed 15 min ago"
    - 🔴 **Not Connected**: "Click 'Connect' to authenticate"
  - **"Disconnect"** button (danger, shown only if connected):
    - Revokes OAuth token
    - Updates health status to "Not connected"

- **API Token Settings** (if API Token selected):
  - **API Token** (password input):
    - Masked input field
    - "Show/Hide" toggle
    - Placeholder: "Token for service account access"
  - **"Test Token"** button:
    - Validates token with ECB-LLM API
    - Updates health status:
      - 🟢 "Valid service token (latency: 156ms)"
      - 🔴 "Invalid or expired token"

- **ECB-LLM Endpoint** (text input, read-only by default):
  - Loaded from environment variable or backend configuration
  - Helper text: "Internal ECB LLM service endpoint"
  - Shows health check result after connection test

---

###### Ollama Configuration
**Factory Default Sources**:
- `config.json → ollama.enabled`
- `config.json → ollama.base_url`
- `config.json → ollama.available_models.*`

**Section Health Status** (top-right of section header):
- 🟢 "Connected - 8 models available (vision: 2, text: 6)"
- 🔴 "Cannot connect to Ollama server at localhost:11434"
- 🟠 "Connected but no models installed"
- ⚪ "Disabled"

**Components**:
- **Enable Ollama** (toggle switch):
  - Factory Default: `config.json → ollama.enabled` (default: false)
  - Helper text: "⚠️ Requires Ollama installed and running locally"
  - Link: "Install Ollama" → https://ollama.com

- **Ollama Base URL** (text input):
  - Factory Default: `config.json → ollama.base_url`
  - Default value (shown in placeholder):
    - Docker: "http://host.docker.internal:11434"
    - Local: "http://localhost:11434"
  - Helper text: "URL of your Ollama instance"

- **"Test Connection"** button:
  - Checks if Ollama server is reachable
  - Fetches list of installed models
  - Updates health status with results:
    - 🟢 Success: Shows model count and categories
    - 🔴 "Connection refused - Is Ollama running?"
    - 🔴 "Timeout - Check firewall/network settings"
    - 🟠 "Connected but no models found"

- **Available Models Panel** (shown after successful test):
  - **Vision Models** (expandable section):
    - Lists models from Ollama with metadata:
      - Model name: `granite3.2-vision:latest`
      - Size: "4.9 GB"
      - Last modified: "2 days ago"
    - Shows which models are in `config.json → ollama.available_models.vision`
    - 🟢 Listed models: "Available for use"
    - 🟠 Unlisted models: "Installed but not in config"

  - **Processing Models** (expandable section):
    - Same format as vision models
    - Lists text-only models for processing/translation

  - **Actions**:
    - "Pull Model" button: Shows modal with model name input
    - "Refresh List" button: Re-scans Ollama for models
    - Link: "Browse Ollama Models" → https://ollama.com/library

###### Custom Provider Configuration
- **Add Custom Provider** button:
  - Opens modal to add custom OpenAI-compatible API
  - Fields: Provider name, Base URL, API key, Available models

**Save Button**: "Save API Keys" (primary button, separate from other sections for security)

---

##### 6.2.5 Tab 4: Default Preferences

**Section Title**: "Default User Preferences"
**Description**: "Set default options that appear when tools are loaded"

###### Webmaster Tool Defaults

**Processing Mode** (radio buttons):
- ○ Basic (use default settings)
- ○ Advanced (show model selection)

**Default Languages** (multi-select):
- Pre-select languages that appear by default
- Example: English, French, German
- Users can still change in the tool

**Translation Mode** (radio buttons):
- ○ Fast (translate from first language)
- ○ Accurate (generate in each language)

###### Accessibility Compliance Defaults

**Default Crawl Depth** (radio buttons):
- ○ Single page only
- ○ Include linked pages (up to 5)
- ○ Full site crawl (up to limit set in Tab 2)

**Default View** (dropdown):
- "Show all images"
- "Show missing alt text only"
- "Show needs review only"

###### General UI Preferences

**Theme** (dropdown):
- Light (default)
- Dark
- Auto (based on system preference)
- Note: If dark theme not implemented, show "Coming soon"

**Language/Locale** (dropdown):
- English (default)
- Other languages (if i18n implemented)

**Tooltips & Help** (checkboxes):
- ✓ Show helpful tooltips
- ✓ Show inline help text
- ✓ Show keyboard shortcuts hints

**Save Button**: "Save Preferences" (primary button)

---

##### 6.2.6 Tab 5: Report Templates

**Section Title**: "Report Templates"
**Description**: "Customize templates for exported reports"

###### PDF Report Template

**Header Configuration**:
- **Include Logo** (toggle): On/Off
- **Header Text** (text input):
  - Default: "Accessibility Compliance Report"
- **Include Date** (toggle): On
- **Include Page Count** (toggle): On

**Content Sections** (sortable list with drag handles):
- Executive Summary (checkbox: include/exclude)
- Summary Statistics Dashboard
- Detailed Findings Table
- Image Previews
- Recommendations
- WCAG References
- Appendix

**Footer Configuration**:
- **Footer Text** (text input):
  - Default: "Generated by My Accessibility Buddy"
- **Include Page Numbers** (toggle): On

**Styling**:
- **Color Scheme** (dropdown):
  - Professional (blues and grays)
  - High Contrast (black and white)
  - Custom (color pickers for primary/secondary)

###### CSV/Excel Template

**Column Selection** (checkboxes):
- ✓ Image URL
- ✓ Current Alt Text
- ✓ AI Suggestion
- ✓ WCAG Compliance Status
- ✓ Image Dimensions
- ☐ File Size
- ☐ Context HTML
- ☐ Surrounding Text

**Column Order** (drag-and-drop list)

###### HTML Report Template

**Template Style** (dropdown):
- Bootstrap Italia (matches app)
- Plain HTML (minimal styling)
- Custom CSS (upload stylesheet)

**Interactive Features** (checkboxes):
- ✓ Sortable tables
- ✓ Filterable results
- ☐ Inline image previews
- ☐ Expandable details

**Preview Button**: "Preview Template" (opens modal with sample report)

**Save Button**: "Save Report Templates" (primary button)

---

##### 6.2.7 Tab 6: Advanced Settings

**Section Title**: "Advanced Settings"
**Description**: "Advanced configuration options for power users"

###### Performance Settings

**Concurrent Requests** (number input):
- Default: 5
- Range: 1-20
- Helper text: "Number of parallel AI API requests (higher = faster but more expensive)"

**Request Timeout** (number input):
- Default: 30 seconds
- Range: 10-300
- Helper text: "Maximum time to wait for AI response"

**Retry Logic**:
- **Max Retries** (number input): Default 3, Range 0-10
- **Retry Delay** (number input): Default 2 seconds, Range 1-30

###### Caching Settings

**Enable Response Caching** (toggle):
- On by default
- Helper text: "Cache AI responses to reduce costs and improve speed"

**Cache Duration** (number input):
- Default: 24 hours
- Range: 1-720 hours (30 days)

**Cache Size Limit** (number input):
- Default: 1000 entries
- Range: 100-10000

**Clear Cache Button**: "Clear All Cached Responses"

###### Logging & Debugging

**Enable Debug Logging** (toggle):
- Off by default
- Helper text: "Log detailed information for troubleshooting"

**Log Level** (dropdown):
- Error
- Warning
- Info
- Debug

**Log Storage**:
- **Maximum Log Size** (number input): Default 100MB
- **Download Logs** button: Downloads current log file

###### Data Privacy

**Data Retention** (number input):
- Default: 30 days
- Range: 1-365 days
- Helper text: "Automatically delete analysis results after this many days"

**External API Data Sharing** (checkboxes):
- ☐ Send usage analytics to improve the tool
- ☐ Allow crash reports
- Note: "Image data is never shared. Only metadata and error logs."

**Clear All Data Button**: "Delete All Stored Data" (danger button)
- Confirmation modal: "Are you sure? This will delete all analysis results, cached responses, and logs."

**Save Button**: "Save Advanced Settings" (primary button)

---

##### 6.2.8 Tab 7: System Information

**Section Title**: "System Information"
**Description**: "View system status and diagnostic information"

###### Application Information (Read-only)

**Display Fields**:
- **Version**: 1.0.0 (or from package.json)
- **Build Date**: 2026-01-03
- **Environment**: Production / Development / Testing
- **Database**: Connected / Not Connected
- **Backend API Status**: Online / Offline

###### Installed Dependencies

**AI Provider SDKs**:
- ✓ OpenAI Python SDK: v1.12.0 (Installed)
- ✓ Anthropic SDK: v0.18.0 (Installed)
- ⚠ ECB-LLM Client: Not configured
- ✓ Ollama: Running on localhost:11434

**System Libraries**:
- Python version: 3.11.x
- Flask version: 3.0.x
- Other key dependencies...

###### Health Check

**Provider Connectivity** (table):
| Provider | Status | Latency | Last Checked |
|----------|--------|---------|--------------|
| OpenAI   | ✓ Connected | 245ms | 2 min ago |
| Claude   | ✗ No API key | — | — |
| ECB-LLM  | ⚠ Not configured | — | — |
| Ollama   | ✓ Connected | 12ms | 1 min ago |

**Refresh Status Button**: "Run Health Check"

###### Storage & Usage Statistics

**Display Fields**:
- **Total Analyses Run**: 1,247
- **Total Images Processed**: 45,892
- **Total AI Requests**: 67,334
- **Cache Hit Rate**: 67%
- **Disk Usage**: 245 MB / 10 GB available
- **Database Records**: 12,450 images, 456 analysis jobs

###### Export/Import Configuration

**Export Settings**:
- **Export Configuration** button:
  - Downloads JSON file with all settings (excluding API keys)
  - Filename: `mab-config-2026-01-03.json`

**Import Settings**:
- **Import Configuration** button:
  - Upload JSON file to restore settings
  - Confirmation prompt before overwriting
  - Validation of JSON structure

###### Reset Options

**Reset to Defaults**:
- **Reset All Settings** button (danger button):
  - Confirmation modal
  - Resets all settings to factory defaults
  - Does NOT delete API keys or analysis results

- **Factory Reset** button (danger button):
  - Confirmation modal with password
  - Resets everything including API keys
  - Deletes all data

---

#### Footer
- Testing disclaimer (same as home.html)

### 6.3 User Workflow

**Typical Setup Flow**:
1. User navigates to Administration page
2. User enters API keys in Tab 3
3. User configures default AI models in Tab 1
4. User sets Accessibility Compliance limits in Tab 2
5. User saves settings
6. Settings are now used across all tools

**Ongoing Management**:
- User periodically checks System Information (Tab 7) for health
- User adjusts settings as needed based on usage patterns
- User exports configuration for backup

### 6.4 Technical Implementation Notes

#### 6.4.1 Configuration Storage
- Settings stored in database (user-specific or global)
- API keys encrypted at rest
- Settings accessible via `/api/config` endpoints
- Real-time validation of settings

#### 6.4.2 API Endpoints
- `GET /api/admin/config` - Retrieve all configuration
- `PUT /api/admin/config/{section}` - Update specific section
- `POST /api/admin/test-provider` - Test provider connectivity
- `GET /api/admin/health` - Health check all providers
- `GET /api/admin/stats` - Usage statistics
- `POST /api/admin/export-config` - Export configuration
- `POST /api/admin/import-config` - Import configuration
- `DELETE /api/admin/cache` - Clear cache
- `DELETE /api/admin/data` - Delete all data

#### 6.4.3 Security Considerations
- API keys never exposed in API responses (masked)
- Separate save button for API keys section
- Audit log of configuration changes
- Admin access control (if multi-user)
- CSRF protection on all forms

#### 6.4.4 Configuration Schema
```json
{
  "ai_models": {
    "vision": {
      "provider": "openai",
      "model": "gpt-4o"
    },
    "processing": {
      "provider": "claude",
      "model": "claude-sonnet-4"
    },
    "translation": {
      "provider": "openai",
      "model": "gpt-4o",
      "mode": "fast"
    }
  },
  "compliance": {
    "max_pages": 50,
    "max_images_per_page": 100,
    "timeout": 300,
    "image_detection": {
      "img_tags": true,
      "css_backgrounds": true,
      "svg": true,
      "picture_elements": true
    },
    "alt_text_quality": {
      "min_length": 3,
      "max_length": 150,
      "generic_keywords": ["image", "photo", "picture"]
    },
    "auto_generate": "on_demand",
    "batch_limit": 20
  },
  "api_keys": {
    "openai": "encrypted_key_here",
    "anthropic": "encrypted_key_here",
    "ecb_llm_token": "encrypted_token_here"
  },
  "defaults": {
    "webmaster_mode": "basic",
    "languages": ["en", "fr", "de"],
    "translation_mode": "fast",
    "compliance_crawl_depth": "single",
    "ui_theme": "light"
  },
  "performance": {
    "concurrent_requests": 5,
    "request_timeout": 30,
    "max_retries": 3,
    "retry_delay": 2
  },
  "caching": {
    "enabled": true,
    "duration_hours": 24,
    "max_entries": 1000
  },
  "privacy": {
    "data_retention_days": 30
  }
}
```

### 6.5 Styling
- Consistent with home.html and other tool pages
- Bootstrap Italia framework
- Tab navigation with active state indicators
- Form validation styling (invalid inputs highlighted)
- Success/error messages for save operations
- Loading states for test connection buttons

### 6.6 Accessibility Requirements
- All form inputs properly labeled
- Tab navigation keyboard accessible (Arrow keys, Tab)
- Focus indicators on all interactive elements
- Form validation errors announced to screen readers
- ARIA labels for complex controls
- Help text associated with inputs via aria-describedby
- Save confirmation announcements

---

