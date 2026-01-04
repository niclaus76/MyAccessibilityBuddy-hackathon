# Webmaster UI - Model Selection and Filtering Specifications

## Overview
The webmaster UI must dynamically filter and display only the models from providers that are enabled in the `config.json` file. This ensures users only see available options based on their configuration.

## Configuration Structure Reference

### Provider Configuration Format
Each provider in `config.json` follows this structure:

```json
{
  "provider_name": {
    "enabled": true/false,
    "available_models": {
      "vision": ["model1", "model2", ...],
      "processing": ["model1", "model2", ...],
      "translation": ["model1", "model2", ...]
    }
  }
}
```

### Supported Providers
1. **OpenAI** - `openai.enabled`
2. **Claude** - `claude.enabled`
3. **ECB-LLM** - `ecb_llm.enabled`
4. **Ollama** - `ollama.enabled`

## Functional Requirements

### 1. Model Filtering Logic

#### Filter by Provider Status
- **IF** `provider.enabled === true` → Include provider's models in dropdowns
- **IF** `provider.enabled === false` → Exclude provider's models from dropdowns
- **IF** no providers are enabled → Display warning message to user

#### Filter by Step Type
For each step (vision, processing, translation), only show models from the corresponding `available_models` array:
- **Vision step** → Show models from `provider.available_models.vision`
- **Processing step** → Show models from `provider.available_models.processing`
- **Translation step** → Show models from `provider.available_models.translation`

### 2. UI Section: "Configure provider and model for each step"

This section corresponds to the `steps` configuration in config.json:

```json
"steps": {
  "vision": {
    "provider": "OpenAI",
    "model": "gpt-4o"
  },
  "processing": {
    "provider": "OpenAI",
    "model": "gpt-4o"
  },
  "translation": {
    "provider": "OpenAI",
    "model": "gpt-4o"
  }
}
```

#### UI Layout
Each step should have:
1. **Provider dropdown** - Shows only enabled providers
2. **Model dropdown** - Shows only models available for the selected provider and step type
3. **Dynamic update** - When provider changes, model dropdown updates automatically

### 3. Implementation Details

#### Backend API Endpoint
Create an endpoint to return filtered configuration:

```
GET /api/available-models
```

**Response Format:**
```json
{
  "providers": {
    "OpenAI": {
      "enabled": true,
      "models": {
        "vision": ["gpt-4o", "gpt-5.1", "gpt-5.2"],
        "processing": ["gpt-4o", "gpt-5.1", "gpt-5.2"],
        "translation": ["gpt-4o", "gpt-5.1", "gpt-5.2"]
      }
    },
    "Claude": {
      "enabled": true,
      "models": {
        "vision": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        "processing": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        "translation": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]
      }
    }
  },
  "enabled_providers": ["OpenAI", "Claude"]
}
```

#### Frontend JavaScript Logic

**Step 1: Fetch Available Models**
```javascript
async function fetchAvailableModels() {
    const response = await fetch('/api/available-models');
    const data = await response.json();
    return data;
}
```

**Step 2: Populate Provider Dropdowns**
```javascript
function populateProviderDropdown(stepType, availableModels) {
    const providerSelect = document.getElementById(`${stepType}-provider`);
    providerSelect.innerHTML = ''; // Clear existing options

    // Only add enabled providers
    availableModels.enabled_providers.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = provider;
        providerSelect.appendChild(option);
    });
}
```

**Step 3: Populate Model Dropdowns (Dynamic)**
```javascript
function populateModelDropdown(stepType, provider, availableModels) {
    const modelSelect = document.getElementById(`${stepType}-model`);
    modelSelect.innerHTML = ''; // Clear existing options

    // Get models for this provider and step type
    const providerData = availableModels.providers[provider];
    if (!providerData || !providerData.enabled) {
        return; // Provider not available
    }

    const models = providerData.models[stepType] || [];
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
}
```

**Step 4: Update on Provider Change**
```javascript
document.getElementById('vision-provider').addEventListener('change', function(e) {
    const selectedProvider = e.target.value;
    populateModelDropdown('vision', selectedProvider, availableModels);
});
```

### 4. HTML Structure Example

```html
<div class="step-config mb-4">
    <h5>Vision Step</h5>
    <div class="row">
        <div class="col-md-6">
            <label for="vision-provider" class="form-label">Provider</label>
            <select id="vision-provider" class="form-select" aria-label="Select vision provider">
                <!-- Dynamically populated with enabled providers only -->
            </select>
        </div>
        <div class="col-md-6">
            <label for="vision-model" class="form-label">Model</label>
            <select id="vision-model" class="form-select" aria-label="Select vision model">
                <!-- Dynamically populated based on selected provider -->
            </select>
        </div>
    </div>
</div>

<div class="step-config mb-4">
    <h5>Processing Step</h5>
    <div class="row">
        <div class="col-md-6">
            <label for="processing-provider" class="form-label">Provider</label>
            <select id="processing-provider" class="form-select" aria-label="Select processing provider">
                <!-- Dynamically populated with enabled providers only -->
            </select>
        </div>
        <div class="col-md-6">
            <label for="processing-model" class="form-label">Model</label>
            <select id="processing-model" class="form-select" aria-label="Select processing model">
                <!-- Dynamically populated based on selected provider -->
            </select>
        </div>
    </div>
</div>

<div class="step-config mb-4">
    <h5>Translation Step</h5>
    <div class="row">
        <div class="col-md-6">
            <label for="translation-provider" class="form-label">Provider</label>
            <select id="translation-provider" class="form-select" aria-label="Select translation provider">
                <!-- Dynamically populated with enabled providers only -->
            </select>
        </div>
        <div class="col-md-6">
            <label for="translation-model" class="form-label">Model</label>
            <select id="translation-model" class="form-select" aria-label="Select translation model">
                <!-- Dynamically populated based on selected provider -->
            </select>
        </div>
    </div>
</div>
```

### 5. Edge Cases and Error Handling

#### No Enabled Providers
**Scenario:** All providers have `enabled: false`

**Handling:**
```html
<div class="alert alert-warning" role="alert">
    <strong>No providers enabled!</strong>
    Please enable at least one provider in config.json to use this feature.
    <br>
    Enabled providers: OpenAI, Claude, ECB-LLM, or Ollama
</div>
```

#### Provider Disabled After Selection
**Scenario:** User has selected a provider, then it gets disabled in config

**Handling:**
- Reset to first available enabled provider
- Show notification: "Selected provider is no longer available. Switched to [new_provider]"

#### Model Not Available
**Scenario:** Selected model is not in the available_models list for the step

**Handling:**
- Reset to first available model from the selected provider
- Show notification: "Selected model is not available for this step. Switched to [new_model]"

### 6. Provider-Specific Notes

#### Ollama
- Requires `base_url` configuration
- May need to check server availability
- Consider adding status indicator (connected/disconnected)

#### ECB-LLM
- Internal provider, may require special authentication
- Show only if user has access

### 7. Validation Rules

**Before Submission:**
1. Ensure provider is enabled in config
2. Ensure selected model exists in provider's available_models for the step
3. Ensure all three steps (vision, processing, translation) have valid selections
4. If two_step_processing is false, only vision step is required

### 8. User Experience Enhancements

#### Visual Indicators
- Show provider logo/icon next to provider name
- Display model capabilities (e.g., "Vision capable", "Translation optimized")
- Highlight recommended models

#### Tooltips
- Add tooltip to provider dropdown: "Only enabled providers are shown"
- Add tooltip to model dropdown: "Models available for [step_type] in [provider]"

#### Loading States
- Show skeleton loader while fetching available models
- Disable dropdowns until data is loaded

### 9. Accessibility Requirements

- All dropdowns must have descriptive `aria-label` attributes
- Error messages must have `role="alert"` for screen reader announcement
- Keyboard navigation must work seamlessly (Tab, Arrow keys, Enter)
- Focus management when dropdowns update dynamically

## Acceptance Criteria

- [ ] Only enabled providers appear in provider dropdowns
- [ ] Model dropdowns show only models for selected provider and step type
- [ ] Model dropdown updates automatically when provider changes
- [ ] Warning displayed when no providers are enabled
- [ ] Frontend fetches configuration from backend API
- [ ] Current selections from config.json are pre-selected on page load
- [ ] Form validation prevents submission of invalid combinations
- [ ] All accessibility requirements are met
- [ ] Error handling covers all edge cases
- [ ] UI updates smoothly without page refresh

## API Endpoint Specification

### GET /api/available-models

**Response:**
```json
{
  "providers": {
    "<provider_name>": {
      "enabled": boolean,
      "models": {
        "vision": ["model1", "model2"],
        "processing": ["model1", "model2"],
        "translation": ["model1", "model2"]
      }
    }
  },
  "enabled_providers": ["provider1", "provider2"],
  "current_config": {
    "vision": {"provider": "OpenAI", "model": "gpt-4o"},
    "processing": {"provider": "OpenAI", "model": "gpt-4o"},
    "translation": {"provider": "OpenAI", "model": "gpt-4o"}
  }
}
```

**Error Responses:**
- `500` - Error reading config.json
- `503` - Configuration service unavailable
