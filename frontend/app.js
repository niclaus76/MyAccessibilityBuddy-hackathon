    // State variables for each step
    let visionProvider = '';
    let visionModel = '';
    let processingProvider = '';
    let processingModel = '';
    let translationProvider = '';
    let translationModel = '';
    let selectedLanguages = ['en']; // Array of selected language codes
    let translationMode = 'fast'; // 'fast' or 'accurate'
    let geoBoost = false; // GEO (Generative Engine Optimization) boost
    let selectedFile = null;
    let selectedContextFile = null;
    let contextText = '';
    let languageResults = {}; // Store alt text results for each language {lang: {text, imageId, jsonPath}}
    let isAuthenticated = false;
    let loginUrl = null;
    let currentAbortController = null; // For aborting ongoing requests
    let currentReportPath = null; // Store the current report path for view/download

    // Model options for each provider (will be loaded from API)
    let modelOptions = {};
    let availableProviders = [];
    let processingMode = 'basic'; // 'basic' or 'advanced'
    let configDefaults = {}; // Store default config values
    let timeEstimation = {}; // Progress estimate heuristics
    let baseAltTextMaxChars = 125; // Default alt-text limit (configurable via backend)
    let geoBoostIncreasePercent = 20; // Default GEO boost increase (configurable via backend)

    // Language names mapping
    const languageNames = {
        'bg': 'Български (Bulgarian)',
        'cs': 'Čeština (Czech)',
        'da': 'Dansk (Danish)',
        'de': 'Deutsch (German)',
        'el': 'Ελληνικά (Greek)',
        'en': 'English',
        'es': 'Español (Spanish)',
        'et': 'Eesti keel (Estonian)',
        'fi': 'Suomi (Finnish)',
        'fr': 'Français (French)',
        'ga': 'Gaeilge (Irish)',
        'hr': 'Hrvatski (Croatian)',
        'hu': 'Magyar (Hungarian)',
        'it': 'Italiano (Italian)',
        'lt': 'Lietuvių (Lithuanian)',
        'lv': 'Latviešu (Latvian)',
        'mt': 'Malti (Maltese)',
        'nl': 'Nederlands (Dutch)',
        'pl': 'Polski (Polish)',
        'pt': 'Português (Portuguese)',
        'ro': 'Română (Romanian)',
        'sk': 'Slovenčina (Slovak)',
        'sl': 'Slovenščina (Slovenian)',
        'sv': 'Svenska (Swedish)'
    };

    // Fetch config defaults and available providers from API
    async function loadAvailableProviders() {
        try {
            // Fetch both available providers and their connection status
            const [providersResponse, statusResponse] = await Promise.all([
                fetch(`${API_BASE_URL}/available-providers`, { credentials: 'include' }),
                fetch(`${API_BASE_URL}/provider-status`, { credentials: 'include' })
            ]);
            const data = await providersResponse.json();
            let statusData = {};

            try {
                statusData = await statusResponse.json();
                console.log('[PROVIDERS] Provider status:', statusData);
            } catch (e) {
                console.warn('[PROVIDERS] Could not parse provider status, showing all enabled providers');
            }

            // Filter to only include providers with 'connected' status
            // If status check failed or returned empty, fall back to all enabled providers
            // Note: provider-status API returns { providers: {...}, checked_at: "..." }
            const providerStatuses = statusData.providers || statusData;
            const hasStatusData = Object.keys(providerStatuses).length > 0;
            const connectedProviders = {};

            for (const [provider, models] of Object.entries(data.providers || {})) {
                // Include if: no status data available, OR status is 'connected'
                if (!hasStatusData || providerStatuses[provider]?.status === 'connected') {
                    connectedProviders[provider] = models;
                }
            }

            modelOptions = connectedProviders;

            // Build list of available providers (only connected ones)
            availableProviders = Object.keys(connectedProviders);

            console.log('[PROVIDERS] Filtered providers:', availableProviders);

            // Store config defaults if provided
            if (data.config_defaults) {
                configDefaults = data.config_defaults;
                if (typeof data.config_defaults.alt_text_max_chars === 'number') {
                    baseAltTextMaxChars = data.config_defaults.alt_text_max_chars;
                }
                if (typeof data.config_defaults.geo_boost_increase_percent === 'number') {
                    geoBoostIncreasePercent = data.config_defaults.geo_boost_increase_percent;
                }
                if (data.config_defaults.time_estimation) {
                    timeEstimation = data.config_defaults.time_estimation;
                }
                updateAltTextLimitDisplays();
            }

            // Show/hide ECB-LLM info in the "Read more" section based on availability
            const ecbLlmInfo = document.getElementById('ecbLlmInfo');
            if (ecbLlmInfo) {
                if (data.ecb_llm_available) {
                    ecbLlmInfo.classList.remove('d-none');
                } else {
                    ecbLlmInfo.classList.add('d-none');
                }
            }

            // Check if no providers are enabled
            if (availableProviders.length === 0) {
                showNoProvidersWarning();
            } else {
                hideNoProvidersWarning();
                // Populate provider dropdowns
                populateProviderDropdowns();
                // Set default values from config
                setDefaultProviders();
                updateProgressEstimate();
            }

            console.log('[PROVIDERS] Loaded available providers:', availableProviders);
            console.log('[PROVIDERS] ECB-LLM available:', data.ecb_llm_available);
        } catch (error) {
            console.error('[PROVIDERS] Error loading available providers:', error);
            // Fallback to default providers
            availableProviders = ['openai', 'claude'];
            modelOptions = {
                openai: {
                    vision: ['gpt-4o', 'gpt-5.1', 'gpt-5.2'],
                    processing: ['gpt-4o', 'gpt-5.1', 'gpt-5.2'],
                    translation: ['gpt-4o', 'gpt-5.1', 'gpt-5.2']
                },
                claude: {
                    vision: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514'],
                    processing: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514'],
                    translation: ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022']
                }
            };
            populateProviderDropdowns();
            setDefaultProviders();
            updateProgressEstimate();
        }
    }

    // Set default provider and model values from config
    function setDefaultProviders() {
        // Use config defaults if available, otherwise fall back to first available provider
        const visionDefaults = configDefaults.vision || {};
        const processingDefaults = configDefaults.processing || {};
        const translationDefaults = configDefaults.translation || {};

        // Helper function to normalize provider name to lowercase
        const normalizeProviderName = (provider) => {
            if (!provider) return '';
            const providerMap = {
                'OpenAI': 'openai',
                'Claude': 'claude',
                'ECB-LLM': 'ecb-llm',
                'Ollama': 'ollama',
                'Gemini': 'gemini'
            };
            return providerMap[provider] || provider.toLowerCase();
        };

        // Set vision provider and model
        const visionProviderDefault = normalizeProviderName(visionDefaults.provider);
        if (availableProviders.includes(visionProviderDefault)) {
            visionProviderSelect.value = visionProviderDefault;
            populateModelDropdown(visionProviderDefault, 'vision', visionModelSelect);
            if (visionDefaults.model) {
                visionModelSelect.value = visionDefaults.model;
            }
            visionProvider = visionProviderDefault;
            visionModel = visionModelSelect.value;
        } else if (availableProviders.length > 0) {
            // Fall back to first available provider
            const firstProvider = availableProviders[0];
            visionProviderSelect.value = firstProvider;
            populateModelDropdown(firstProvider, 'vision', visionModelSelect);
            visionProvider = firstProvider;
            visionModel = visionModelSelect.value;
        }

        // Set processing provider and model
        const processingProviderDefault = normalizeProviderName(processingDefaults.provider);
        if (availableProviders.includes(processingProviderDefault)) {
            processingProviderSelect.value = processingProviderDefault;
            populateModelDropdown(processingProviderDefault, 'processing', processingModelSelect);
            if (processingDefaults.model) {
                processingModelSelect.value = processingDefaults.model;
            }
            processingProvider = processingProviderDefault;
            processingModel = processingModelSelect.value;
        } else if (availableProviders.length > 0) {
            const firstProvider = availableProviders[0];
            processingProviderSelect.value = firstProvider;
            populateModelDropdown(firstProvider, 'processing', processingModelSelect);
            processingProvider = firstProvider;
            processingModel = processingModelSelect.value;
        }

        // Set translation provider and model
        const translationProviderDefault = normalizeProviderName(translationDefaults.provider);
        if (availableProviders.includes(translationProviderDefault)) {
            translationProviderSelect.value = translationProviderDefault;
            populateModelDropdown(translationProviderDefault, 'translation', translationModelSelect);
            if (translationDefaults.model) {
                translationModelSelect.value = translationDefaults.model;
            }
            translationProvider = translationProviderDefault;
            translationModel = translationModelSelect.value;
        } else if (availableProviders.length > 0) {
            const firstProvider = availableProviders[0];
            translationProviderSelect.value = firstProvider;
            populateModelDropdown(firstProvider, 'translation', translationModelSelect);
            translationProvider = firstProvider;
            translationModel = translationModelSelect.value;
        }
    }

    // Show warning when no providers are enabled
    function showNoProvidersWarning() {
        const advancedSettings = document.getElementById('advancedSettings');

        // Create warning element if it doesn't exist
        let warningDiv = document.getElementById('noProvidersWarning');
        if (!warningDiv) {
            warningDiv = document.createElement('div');
            warningDiv.id = 'noProvidersWarning';
            warningDiv.className = 'row justify-content-center mb-4';
            warningDiv.innerHTML = `
                <div class="col-12 col-md-8">
                    <div class="alert alert-warning" role="alert">
                        <h6 class="alert-heading"><strong>No providers enabled!</strong></h6>
                        <p class="mb-0">Please enable at least one provider in config.json to use this feature.</p>
                        <p class="mb-0"><small>Available providers: OpenAI, Claude, ECB-LLM, Gemini, or Ollama</small></p>
                    </div>
                </div>
            `;
            // Insert before the language selection section
            const languageSection = document.querySelector('.row.justify-content-center.mb-4');
            if (languageSection && advancedSettings) {
                advancedSettings.insertAdjacentElement('afterend', warningDiv);
            }
        }
        warningDiv.classList.remove('d-none');

        // Disable the generate button
        if (generateBtn) {
            generateBtn.disabled = true;
        }
    }

    // Hide warning when providers are available
    function hideNoProvidersWarning() {
        const warningDiv = document.getElementById('noProvidersWarning');
        if (warningDiv) {
            warningDiv.classList.add('d-none');
        }
    }

    // Populate provider dropdown options based on available providers
    function populateProviderDropdowns() {
        const providerSelects = [visionProviderSelect, processingProviderSelect, translationProviderSelect];

        providerSelects.forEach(select => {
            // Clear existing options except the first "Please select"
            while (select.options.length > 1) {
                select.remove(1);
            }

            // Add available providers
            availableProviders.forEach(provider => {
                const option = document.createElement('option');
                option.value = provider;

                // Display names
                const displayNames = {
                    'openai': 'OpenAI',
                    'claude': 'Claude',
                    'ecb-llm': 'ECB-LLM',
                    'ollama': 'Ollama',
                    'gemini': 'Gemini'
                };

                option.textContent = displayNames[provider] || provider;
                select.appendChild(option);
            });
        });
    }

    // Processing mode toggle
    function handleProcessingModeChange() {
        const processingModeToggle = document.getElementById('processingModeToggle');
        const advancedSettings = document.getElementById('advancedSettings');

        const isAdvanced = Boolean(processingModeToggle && processingModeToggle.checked);

        processingMode = isAdvanced ? 'advanced' : 'basic';

        if (processingModeToggle) {
            processingModeToggle.setAttribute('aria-checked', isAdvanced ? 'true' : 'false');
        }

        if (advancedSettings) {
            advancedSettings.classList.toggle('d-none', !isAdvanced);
        }

        updateProgressEstimate();
        console.log(`[MODE] Switched to ${isAdvanced ? 'Advanced mode (two_step_processing: true)' : 'Basic mode (two_step_processing: false)'}`);
    }

    // Translation mode toggle
    function handleTranslationModeChange() {
        const isAdvancedTranslation = Boolean(translationModeToggle && translationModeToggle.checked);

        translationMode = isAdvancedTranslation ? 'accurate' : 'fast';

        if (translationModeToggle) {
            translationModeToggle.setAttribute('aria-checked', isAdvancedTranslation ? 'true' : 'false');
        }

        updateProgressEstimate();
        console.log(`[TRANSLATION] Mode set to: ${translationMode}`);
    }

    // GEO Boost toggle
    function handleGeoBoostChange() {
        const geoBoostToggle = document.getElementById('geoBoostToggle');
        const isGeoBoostEnabled = Boolean(geoBoostToggle && geoBoostToggle.checked);

        geoBoost = isGeoBoostEnabled;

        if (geoBoostToggle) {
            geoBoostToggle.setAttribute('aria-checked', isGeoBoostEnabled ? 'true' : 'false');
        }

        updateAltTextLimitDisplays();
        updateProgressEstimate();
        console.log(`[GEO] Boost set to: ${geoBoost}`);
    }

    // Initialize Bootstrap tooltips
    document.addEventListener('DOMContentLoaded', function() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Load available providers first
        loadAvailableProviders();

        // Check authentication status on page load
        checkAuthenticationStatus();

        // Set up processing mode listener
        const processingModeToggle = document.getElementById('processingModeToggle');

        if (processingModeToggle) {
            processingModeToggle.addEventListener('change', handleProcessingModeChange);
            processingModeToggle.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    processingModeToggle.checked = !processingModeToggle.checked;
                    handleProcessingModeChange();
                }
            });

            // Initialize state to ensure ARIA attributes and visibility are in sync
            handleProcessingModeChange();
        }

        // Set up translation mode listener
        if (translationModeToggle) {
            translationModeToggle.addEventListener('change', handleTranslationModeChange);
            translationModeToggle.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    translationModeToggle.checked = !translationModeToggle.checked;
                    handleTranslationModeChange();
                }
            });

            // Initialize state to ensure ARIA attributes are in sync
            handleTranslationModeChange();
        }

        // Set up GEO Boost listener
        const geoBoostToggle = document.getElementById('geoBoostToggle');
        if (geoBoostToggle) {
            geoBoostToggle.addEventListener('change', handleGeoBoostChange);
            geoBoostToggle.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    geoBoostToggle.checked = !geoBoostToggle.checked;
                    handleGeoBoostChange();
                }
            });

            // Initialize state to ensure ARIA attributes are in sync
            handleGeoBoostChange();
        }

        // Toggle detailed instructions visibility
        const showInstructionsBtn = document.getElementById('showInstructionsBtn');
        const detailedInstructions = document.getElementById('detailedInstructions');

        if (showInstructionsBtn && detailedInstructions) {
            showInstructionsBtn.addEventListener('click', function() {
                const isHidden = detailedInstructions.classList.contains('d-none');

                if (isHidden) {
                    detailedInstructions.classList.remove('d-none');
                    showInstructionsBtn.setAttribute('aria-expanded', 'true');
                    showInstructionsBtn.setAttribute('title', 'Hide detailed instructions');
                } else {
                    detailedInstructions.classList.add('d-none');
                    showInstructionsBtn.setAttribute('aria-expanded', 'false');
                    showInstructionsBtn.setAttribute('title', 'Click for detailed instructions');
                }
            });
        }

        // Toggle processing info visibility
        const toggleInfoBtn = document.getElementById('toggleInfoBtn');
        const processingInfo = document.getElementById('processingInfo');

        if (toggleInfoBtn && processingInfo) {
            toggleInfoBtn.addEventListener('click', function() {
                const isHidden = processingInfo.classList.contains('d-none');

                if (isHidden) {
                    processingInfo.classList.remove('d-none');
                    toggleInfoBtn.setAttribute('aria-expanded', 'true');
                    toggleInfoBtn.innerHTML = `
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" class="me-1" style="vertical-align: text-bottom;" aria-hidden="true">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
                        </svg>
                        Hide processing steps & models
                    `;
                } else {
                    processingInfo.classList.add('d-none');
                    toggleInfoBtn.setAttribute('aria-expanded', 'false');
                    toggleInfoBtn.innerHTML = `
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" class="me-1" style="vertical-align: text-bottom;" aria-hidden="true">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
                        </svg>
                        Read more about processing steps & models
                    `;
                }
            });
        }
    });

    // DOM Elements
    const visionProviderSelect = document.getElementById("visionProviderSelect");
    const processingProviderSelect = document.getElementById("processingProviderSelect");
    const translationProviderSelect = document.getElementById("translationProviderSelect");
    const visionModelSelect = document.getElementById('visionModelSelect');
    const processingModelSelect = document.getElementById('processingModelSelect');
    const translationModelSelect = document.getElementById('translationModelSelect');
    const translationModeToggle = document.getElementById('translationModeToggle');
    const langSelect = document.getElementById('languageSelect');
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadDragdrop');
    const browseBtn = document.getElementById('browseBtn');
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');
    const generateBtn = document.getElementById('generateBtn');
    const stopGenerationBtn = document.getElementById('stopGenerationBtn');
    const clearBtn = document.getElementById('clearBtn');
    const resultSection = document.getElementById('resultSection');
    const resultsContainer = document.getElementById('resultsContainer');
    const removeImage = document.getElementById('removeImage');

    // Context file elements
    const contextFileInput = document.getElementById('contextFileInput');
    const contextDragdrop = document.getElementById('contextDragdrop');
    const contextBrowseBtn = document.getElementById('contextBrowseBtn');
    const contextPreviewContainer = document.getElementById('contextPreviewContainer');
    const contextFileName = document.getElementById('contextFileName');
    const contextFilePreview = document.getElementById('contextFilePreview');
    const removeContext = document.getElementById('removeContext');

    // Progress bar elements
    const progressContainer = document.getElementById('progressContainer');
    const progressStatus = document.getElementById('progressStatus');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressEstimate = document.getElementById('progressEstimate');
    const estimatePreview = document.getElementById('estimatePreview');

    // Update Progress bar
    function updateProgress(percent, message) {
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
            progressBar.setAttribute('aria-valuenow', percent);
        }
        if (progressPercent) {
            progressPercent.textContent = `${percent}%`;
        }
        if (progressStatus) {
            progressStatus.textContent = message;
        }
    }

    // Show/Hide Progress bar
    function showProgress(show) {
        if (progressContainer) {
            if (show) {
                progressContainer.style.display = '';
                updateProgress(0, 'Initializing...');
            } else {
                progressContainer.style.display = 'none';
            }
        }
    }

    function formatDuration(seconds) {
        if (!Number.isFinite(seconds) || seconds <= 0) return '--:--';
        const rounded = Math.round(seconds);
        const mins = Math.floor(rounded / 60);
        const secs = rounded % 60;
        const mm = String(mins).padStart(2, '0');
        const ss = String(secs).padStart(2, '0');
        return `${mm}:${ss}`;
    }

    function getProviderCategory(provider) {
        const map = timeEstimation.provider_category || {};
        return map[provider] || 'web';
    }

    function getBaseSeconds(provider) {
        const base = timeEstimation.base_seconds_per_image || {};
        const category = getProviderCategory(provider);
        return base[category] || 10;
    }

    function getStepMultiplier(step) {
        const steps = timeEstimation.step_multipliers || {};
        return steps[step] || 1;
    }

    function getModelMultiplier(model) {
        const models = timeEstimation.model_multipliers || {};
        return models[model] || 1;
    }

    function getTranslationModeMultiplier(mode) {
        const modes = timeEstimation.translation_mode_multiplier || {};
        return modes[mode] || 1;
    }

    function estimateGenerationSeconds() {
        const languages = Math.max(selectedLanguages.length, 1);
        const visionProviderValue = visionProviderSelect.value || visionProvider;
        const processingProviderValue = processingProviderSelect.value || processingProvider;
        const translationProviderValue = translationProviderSelect.value || translationProvider;
        const visionModelValue = visionModelSelect.value || visionModel;
        const processingModelValue = processingModelSelect.value || processingModel;
        const translationModelValue = translationModelSelect.value || translationModel;

        const visionStep = getBaseSeconds(visionProviderValue) * getStepMultiplier('vision') * getModelMultiplier(visionModelValue);
        const processingStep = getBaseSeconds(processingProviderValue) * getStepMultiplier('processing') * getModelMultiplier(processingModelValue);
        const translationStep = getBaseSeconds(translationProviderValue) * getStepMultiplier('translation') * getModelMultiplier(translationModelValue);
        const translationMultiplier = getTranslationModeMultiplier(translationMode);

        let total = 0;
        if (translationMode === 'accurate') {
            total = (visionStep + processingStep + translationStep) * languages * translationMultiplier;
        } else {
            total = visionStep + processingStep + translationStep;
            if (languages > 1) {
                total += translationStep * (languages - 1) * translationMultiplier;
            }
        }

        if (geoBoost) {
            total *= timeEstimation.geo_boost_multiplier || 1.1;
        }

        total += timeEstimation.overhead_seconds || 5;
        return total;
    }

    function updateProgressEstimate() {
        const seconds = estimateGenerationSeconds();
        const duration = formatDuration(seconds);
        if (progressEstimate) {
            progressEstimate.textContent = `Estimated time: ~${duration}`;
        }
        if (estimatePreview) {
            estimatePreview.textContent = `(duration: ${duration})`;
        }
    }

    // Function to populate model dropdown for a specific step
    function populateModelDropdown(provider, stepType, modelSelect) {
        if (!provider || provider === '') {
            // No provider selected - disable model dropdown
            modelSelect.disabled = true;
            modelSelect.innerHTML = '<option value="">Please select provider first</option>';
            return;
        }

        // Enable model dropdown
        modelSelect.disabled = false;

        const models = modelOptions[provider];

        // Populate model dropdown with options for this provider and step type
        modelSelect.innerHTML = '';
        if (models && models[stepType]) {
            models[stepType].forEach(model => {
                modelSelect.innerHTML += `<option value="${model}">${model}</option>`;
            });

            // Auto-select the first model
            if (models[stepType].length > 0) {
                modelSelect.value = models[stepType][0];
            }
        }
    }

    // Vision provider selection
    visionProviderSelect.addEventListener('change', (e) => {
        visionProvider = e.target.value;
        populateModelDropdown(visionProvider, 'vision', visionModelSelect);
        // Auto-update the model variable with the first selected model
        visionModel = visionModelSelect.value;
        updateProgressEstimate();
    });

    // Vision model selection
    visionModelSelect.addEventListener('change', (e) => {
        visionModel = e.target.value;
        updateProgressEstimate();
    });

    // Processing provider selection
    processingProviderSelect.addEventListener('change', (e) => {
        processingProvider = e.target.value;
        populateModelDropdown(processingProvider, 'processing', processingModelSelect);
        // Auto-update the model variable with the first selected model
        processingModel = processingModelSelect.value;
        updateProgressEstimate();
    });

    // Processing model selection
    processingModelSelect.addEventListener('change', (e) => {
        processingModel = e.target.value;
        updateProgressEstimate();
    });

    // Translation provider selection
    translationProviderSelect.addEventListener('change', (e) => {
        translationProvider = e.target.value;
        populateModelDropdown(translationProvider, 'translation', translationModelSelect);
        // Auto-update the model variable with the first selected model
        translationModel = translationModelSelect.value;
        updateProgressEstimate();
    });

    // Translation model selection
    translationModelSelect.addEventListener('change', (e) => {
        translationModel = e.target.value;
        updateProgressEstimate();
    });

    // Language selection (multiple)
    langSelect.addEventListener('change', (e) => {
        selectedLanguages = Array.from(e.target.selectedOptions).map(opt => opt.value);
        console.log('[LANGUAGE] Selected languages:', selectedLanguages);

        // Announce selection changes to screen readers
        const count = selectedLanguages.length;
        const langNames = selectedLanguages.map(code => languageNames[code] || code).join(', ');
        announceToScreenReader(`${count} language${count !== 1 ? 's' : ''} selected: ${langNames}`);
        updateProgressEstimate();
    });

    // Enhanced keyboard navigation for language selection
    let lastSelectedIndex = -1;

    langSelect.addEventListener('keydown', (e) => {
        const options = Array.from(langSelect.options);
        const focusedIndex = langSelect.selectedIndex;

        // Handle Space key for selection
        if (e.key === ' ') {
            e.preventDefault();

            const currentOption = options[focusedIndex] || options[0];

            if (e.ctrlKey || e.metaKey) {
                // Ctrl/Cmd + Space: Toggle selection
                currentOption.selected = !currentOption.selected;
            } else if (e.shiftKey && lastSelectedIndex !== -1) {
                // Shift + Space: Range selection
                const start = Math.min(lastSelectedIndex, focusedIndex);
                const end = Math.max(lastSelectedIndex, focusedIndex);
                for (let i = start; i <= end; i++) {
                    options[i].selected = true;
                }
            } else {
                // Plain Space: Toggle current option
                currentOption.selected = !currentOption.selected;
            }

            // Update last selected index
            lastSelectedIndex = focusedIndex;

            // Trigger change event
            langSelect.dispatchEvent(new Event('change'));
        }

        // Handle Shift + Arrow keys for range selection
        if (e.shiftKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
            if (lastSelectedIndex === -1) {
                lastSelectedIndex = focusedIndex;
            }

            // Let the default behavior handle navigation, then select the range
            setTimeout(() => {
                const newIndex = Array.from(options).findIndex(opt => opt === document.activeElement) || focusedIndex;
                const start = Math.min(lastSelectedIndex, newIndex);
                const end = Math.max(lastSelectedIndex, newIndex);

                for (let i = start; i <= end; i++) {
                    options[i].selected = true;
                }

                langSelect.dispatchEvent(new Event('change'));
            }, 0);
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            // Update last selected index on regular arrow navigation
            setTimeout(() => {
                lastSelectedIndex = Array.from(options).findIndex(opt => opt === document.activeElement) || focusedIndex;
            }, 0);
        }

        // Handle Ctrl/Cmd + A for select all
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
            e.preventDefault();
            options.forEach(opt => opt.selected = true);
            langSelect.dispatchEvent(new Event('change'));
            announceToScreenReader('All languages selected');
        }
    });

    // Character count and visual feedback for a specific textarea
    function getAltTextLimit() {
        if (geoBoost) {
            return Math.floor(baseAltTextMaxChars * (1 + geoBoostIncreasePercent / 100));
        }
        return baseAltTextMaxChars;
    }

    function updateAltTextLimitDisplays() {
        const maxChars = getAltTextLimit();
        document.querySelectorAll('[data-char-warning]').forEach((warning) => {
            warning.textContent = ` (⚠ Over ${maxChars} characters)`;
        });
        document.querySelectorAll('[data-recommended-limit]').forEach((limitLabel) => {
            limitLabel.textContent = `Recommended: ≤ ${maxChars} characters`;
        });
        document.querySelectorAll('[data-alt-text-input]').forEach((textarea) => {
            const lang = textarea.getAttribute('data-lang');
            const charCountNum = document.getElementById(`charCountNum_${lang}`);
            const charWarning = document.getElementById(`charWarning_${lang}`);
            if (charCountNum && charWarning) {
                updateCharacterCount(textarea, charCountNum, charWarning);
            }
        });
    }

    function updateCharacterCount(textarea, charCountNum, charWarning) {
        const text = textarea.value;
        const count = text.length;
        const previousCount = parseInt(charCountNum.textContent) || 0;
        const maxChars = getAltTextLimit();

        charCountNum.textContent = count;

        // Check if we crossed the configured character threshold
        const wasOverLimit = previousCount > maxChars;
        const isOverLimit = count > maxChars;

        if (isOverLimit) {
            charWarning.classList.remove('d-none');
            textarea.style.color = 'red';
            // Announce when crossing threshold
            if (!wasOverLimit) {
                announceToScreenReader(`Warning: Alt text exceeds recommended ${maxChars} characters. Current count: ${count} characters.`);
            }
        } else {
            charWarning.classList.add('d-none');
            textarea.style.color = '';
            // Announce when going back under threshold
            if (wasOverLimit) {
                announceToScreenReader(`Alt text is now within recommended limit (${maxChars} characters). Current count: ${count} characters.`);
            }
        }
    }

    // Create a result card for a specific language
    function createLanguageResultCard(lang, altText, imageId, jsonPath) {
        const langName = languageNames[lang] || lang;
        const altTextDisplay = altText === "" ? '(Empty alt text for decorative image)' : altText;
        const maxChars = getAltTextLimit();

        // Build descriptive label with image name and all languages
        // Format: "Generated alternative text for image.png in English" or "Generated alternative text for image.png in English, Spanish"
        const allLanguageNames = selectedLanguages.map(code => languageNames[code] || code).join(', ');
        const labelText = selectedLanguages.length > 1
            ? `Generated alternative text for ${imageId} in ${allLanguageNames}`
            : `Generated alternative text for ${imageId} in ${langName}`;

        const card = document.createElement('div');
        card.className = 'card shadow-sm mb-3';
        card.setAttribute('data-language', lang);

        card.innerHTML = `
            <div class="card-body">
                <div class="callout success">
                    <label for="resultText_${lang}" class="form-label">${labelText}</label>
                    <textarea id="resultText_${lang}" class="form-control mb-2" rows="4" data-alt-text-input data-lang="${lang}"
                        placeholder="Generated alt text will appear here..."
                        aria-describedby="charCount_${lang}">${altTextDisplay}</textarea>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <small id="charCount_${lang}" class="text-muted" aria-live="polite" aria-atomic="true">
                            <span id="charCountNum_${lang}">${altText.length}</span> characters
                            <span id="charWarning_${lang}" class="text-warning ${altText.length > maxChars ? '' : 'd-none'}" role="status" data-char-warning> (⚠ Over ${maxChars} characters)</span>
                        </small>
                        <small class="text-muted" aria-hidden="true" data-recommended-limit>Recommended: ≤ ${maxChars} characters</small>
                    </div>
                    <div class="text-center">
                        <button type="button" class="btn btn-primary btn-sm copy-btn" data-lang="${lang}" aria-label="Copy alt text for ${langName}">
                            <svg class="icon icon-sm me-1" aria-hidden="true"><use href="assets/bootstrap-italia-sprites.svg#it-copy"></use></svg>
                            <span class="copy-btn-text">Copy</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners
        const textarea = card.querySelector(`#resultText_${lang}`);
        const charCountNum = card.querySelector(`#charCountNum_${lang}`);
        const charWarning = card.querySelector(`#charWarning_${lang}`);

        textarea.addEventListener('input', () => updateCharacterCount(textarea, charCountNum, charWarning));
        textarea.addEventListener('change', () => updateCharacterCount(textarea, charCountNum, charWarning));

        // Copy button
        const copyBtn = card.querySelector('.copy-btn');
        copyBtn.addEventListener('click', () => {
            const textToCopy = textarea.value;
            navigator.clipboard.writeText(textToCopy).then(() => {
                const btnText = copyBtn.querySelector('.copy-btn-text');
                btnText.textContent = 'Copied!';
                setTimeout(() => {
                    btnText.textContent = 'Copy';
                }, 2000);
            });
        });

        return card;
    }

    // Save and generate report, then perform action
    async function saveAndGenerateReport(action) {
        const viewReportBtn = document.getElementById('viewReportBtn');
        const downloadReportBtn = document.getElementById('downloadReportBtn');
        const viewReportBtnText = document.getElementById('viewReportBtnText');
        const downloadReportBtnText = document.getElementById('downloadReportBtnText');
        const saveAllMessage = document.getElementById('saveAllMessage');
        const saveAllSuccessMsg = document.getElementById('saveAllSuccessMsg');
        const saveAllErrorMsg = document.getElementById('saveAllErrorMsg');

        // Disable buttons during processing
        if (viewReportBtn) viewReportBtn.disabled = true;
        if (downloadReportBtn) downloadReportBtn.disabled = true;

        const originalViewText = viewReportBtnText ? viewReportBtnText.textContent : 'View HTML Report';
        const originalDownloadText = downloadReportBtnText ? downloadReportBtnText.textContent : 'Download Report';

        if (saveAllMessage) {
            saveAllMessage.classList.add('d-none');
            saveAllSuccessMsg.textContent = '';
            saveAllErrorMsg.textContent = '';
        }

        try {
            // Update button text to show progress
            if (action === 'view' && viewReportBtnText) {
                viewReportBtnText.textContent = 'Saving...';
            } else if (action === 'download' && downloadReportBtnText) {
                downloadReportBtnText.textContent = 'Saving...';
            }

            const maxChars = getAltTextLimit();
            // Check for over-length warnings
            const warnings = [];
            for (const lang of Object.keys(languageResults)) {
                const textarea = document.getElementById(`resultText_${lang}`);
                if (textarea) {
                    const reviewedText = textarea.value;
                    const textToSave = reviewedText === '(Empty alt text for decorative image)' ? '' : reviewedText;
                    if (textToSave.length > maxChars) {
                        const langName = languageNames[lang] || lang;
                        warnings.push(`${langName}: ${textToSave.length} characters`);
                    }
                }
            }

            if (warnings.length > 0) {
                const confirmSave = confirm(
                    `⚠️ Warning: Some alt texts exceed ${maxChars} characters:\n\n${warnings.join('\n')}\n\n` +
                    `Longer alt text may not be ideal for screen reader users.\n\n` +
                    `Do you want to save them anyway?`
                );
                if (!confirmSave) {
                    return;
                }
            }

            // Save all reviewed alt-texts
            let savedCount = 0;
            let errorCount = 0;
            const errors = [];

            for (const lang of Object.keys(languageResults)) {
                const result = languageResults[lang];
                if (!result || !result.imageId) {
                    errorCount++;
                    errors.push(`${lang}: No image ID available`);
                    continue;
                }

                const textarea = document.getElementById(`resultText_${lang}`);
                if (!textarea) {
                    errorCount++;
                    errors.push(`${lang}: Textarea not found`);
                    continue;
                }

                const reviewedText = textarea.value;
                const textToSave = reviewedText === '(Empty alt text for decorative image)' ? '' : reviewedText;

                try {
                    const response = await fetch(`${API_BASE_URL}/save-reviewed-alt-text`, {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            image_id: result.imageId,
                            reviewed_alt_text: textToSave,
                            language: lang,
                            reviewed_alt_text_length: textToSave.length
                        })
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        errorCount++;
                        const langName = languageNames[lang] || lang;
                        const errorMsg = data.detail || data.error || `HTTP ${response.status}`;
                        errors.push(`${langName}: ${errorMsg}`);
                    } else if (data.success) {
                        savedCount++;
                    } else {
                        errorCount++;
                        const langName = languageNames[lang] || lang;
                        errors.push(`${langName}: ${data.error || 'Unknown error'}`);
                    }
                } catch (error) {
                    errorCount++;
                    const langName = languageNames[lang] || lang;
                    errors.push(`${langName}: ${error.message}`);
                }
            }

            if (savedCount === 0 && errorCount === 0) {
                announceToScreenReader('No alt-text to save. Please generate alt-text first.');
                if (saveAllMessage) {
                    saveAllErrorMsg.textContent = 'No alt-text to save. Please generate alt-text first.';
                    saveAllMessage.classList.remove('d-none');
                    setTimeout(() => saveAllMessage.classList.add('d-none'), 3000);
                }
                return;
            }

            if (errorCount > 0 && savedCount === 0) {
                announceToScreenReader(`Failed to save all languages`);
                if (saveAllMessage) {
                    saveAllErrorMsg.textContent = `✗ Failed to save: ${errors.join(', ')}`;
                    saveAllMessage.classList.remove('d-none');
                }
                return;
            }

            // Update button text
            if (action === 'view' && viewReportBtnText) {
                viewReportBtnText.textContent = 'Generating report...';
            } else if (action === 'download' && downloadReportBtnText) {
                downloadReportBtnText.textContent = 'Generating report...';
            }

            // Generate report
            const clearAfterCheckbox = document.getElementById('clearAfterReportCheckbox');
            const clearAfter = clearAfterCheckbox ? clearAfterCheckbox.checked : true;

            const reportResponse = await fetch(`${API_BASE_URL}/generate-report?clear_after=${clearAfter}&return_path=true`, {
                method: 'POST',
                credentials: 'include'
            });

            if (!reportResponse.ok) {
                throw new Error('Report generation failed');
            }

            const reportData = await reportResponse.json();
            currentReportPath = reportData.report_path;

            // Show success message
            if (saveAllMessage) {
                if (errorCount > 0) {
                    saveAllSuccessMsg.textContent = `✓ Saved ${savedCount} language(s)`;
                    saveAllErrorMsg.textContent = `✗ Failed: ${errors.join(', ')}`;
                } else {
                    saveAllSuccessMsg.textContent = `✓ Saved ${savedCount} language(s) and generated report!`;
                }
                saveAllMessage.classList.remove('d-none');
                setTimeout(() => saveAllMessage.classList.add('d-none'), 5000);
            }

            announceToScreenReader(`Saved ${savedCount} language(s) and generated report.`);

            // Perform the action
            if (action === 'view') {
                const url = `${API_BASE_URL}/view-report?path=${encodeURIComponent(currentReportPath)}`;
                window.open(url, '_blank');
                announceToScreenReader('Report opened in new tab');
            } else if (action === 'download') {
                const link = document.createElement('a');
                link.href = `${API_BASE_URL}/download-report?path=${encodeURIComponent(currentReportPath)}`;
                link.download = currentReportPath.split('/').pop();
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                announceToScreenReader('Report download started');
            }

        } catch (error) {
            console.error('Error:', error);
            announceToScreenReader('Error generating report');
            if (saveAllMessage) {
                saveAllErrorMsg.textContent = 'Error generating report. Please try again.';
                saveAllMessage.classList.remove('d-none');
                setTimeout(() => saveAllMessage.classList.add('d-none'), 3000);
            }
        } finally {
            // Re-enable buttons and restore text
            if (viewReportBtn) viewReportBtn.disabled = false;
            if (downloadReportBtn) downloadReportBtn.disabled = false;
            if (viewReportBtnText) viewReportBtnText.textContent = originalViewText;
            if (downloadReportBtnText) downloadReportBtnText.textContent = originalDownloadText;
        }
    }

    // View Report in New Tab
    function viewReportInNewTab() {
        saveAndGenerateReport('view');
    }

    // Download Report
    function downloadReport() {
        saveAndGenerateReport('download');
    }

    // Set up report button handlers after DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        const viewReportBtn = document.getElementById('viewReportBtn');
        const downloadReportBtn = document.getElementById('downloadReportBtn');

        if (viewReportBtn) {
            viewReportBtn.addEventListener('click', viewReportInNewTab);
        }
        if (downloadReportBtn) {
            downloadReportBtn.addEventListener('click', downloadReport);
        }
    });

    // Browse button click
    browseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    });

    // Upload area click
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== browseBtn && !browseBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Drag and drop functionality
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.style.borderColor = '#0052cc';
        uploadArea.style.backgroundColor = '#e6f0ff';
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.style.borderColor = '#0066cc';
        uploadArea.style.backgroundColor = '#f0f6fc';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.style.borderColor = '#0066cc';
        uploadArea.style.backgroundColor = '#f0f6fc';

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            announceToScreenReader('Invalid file type. Please select an image file.', true);
            showErrorMessage('Invalid file type. Please select an image file (JPG, PNG, GIF, WEBP, BMP, SVG, or TIFF).');
            return;
        }

        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            uploadArea.classList.add('d-none');
            previewContainer.classList.remove('d-none');
            generateBtn.disabled = false;
            contextDragdrop.focus();

            // Update Remove button with file name for accessibility
            removeImage.setAttribute('aria-label', `Remove ${file.name}`);

            // Clear any previous errors
            clearErrorMessages();

            // Announce successful upload
            announceToScreenReader(`Image ${file.name} uploaded successfully. Ready to generate alt text.`);
        };
        reader.readAsDataURL(file);
    }

    // Remove image
    removeImage.addEventListener('click', resetForm);

    // Context file upload handlers
    contextBrowseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        contextFileInput.click();
    });

    contextDragdrop.addEventListener('click', () => {
        contextFileInput.click();
    });

    contextDragdrop.addEventListener('dragover', (e) => {
        e.preventDefault();
        contextDragdrop.style.borderColor = '#0066cc';
        contextDragdrop.style.backgroundColor = '#e6f2ff';
    });

    contextDragdrop.addEventListener('dragleave', () => {
        contextDragdrop.style.borderColor = '#17324d';
        contextDragdrop.style.backgroundColor = '#f5f5f5';
    });

    contextDragdrop.addEventListener('drop', (e) => {
        e.preventDefault();
        contextDragdrop.style.borderColor = '#17324d';
        contextDragdrop.style.backgroundColor = '#f5f5f5';

        const file = e.dataTransfer.files[0];
        if (file && file.type === 'text/plain') {
            handleContextFile(file);
        }
    });

    contextFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleContextFile(file);
        }
    });

    // Context textbox element
    const contextTextbox = document.getElementById('contextTextbox');
    const clearContextBtn = document.getElementById('clearContextBtn');

    function handleContextFile(file) {
        if (file.type !== 'text/plain') {
            announceToScreenReader('Invalid file type. Please select a text file.', true);
            showErrorMessage('Invalid file type. Please select a text file (.txt).');
            return;
        }

        selectedContextFile = file;
        const reader = new FileReader();

        reader.onload = (e) => {
            contextText = e.target.result;

            // Load content into textarea
            if (contextTextbox) {
                contextTextbox.value = contextText;
                // Show clear button
                clearContextBtn.classList.remove('d-none');
            }

            // Update Remove button with file name for accessibility
            removeContext.setAttribute('aria-label', `Remove ${file.name}`);

            // Announce successful upload
            announceToScreenReader(`Context file ${file.name} uploaded successfully. Content loaded into text editor.`);
        };

        reader.readAsText(file);
    }

    removeContext.addEventListener('click', () => {
        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        if (contextTextbox) {
            contextTextbox.value = '';
        }
        clearContextBtn.classList.add('d-none');

        // Clear aria-label from Remove context button
        removeContext.removeAttribute('aria-label');

        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
        contextDragdrop.focus();
    });

    // Clear context button handler
    if (clearContextBtn) {
        clearContextBtn.addEventListener('click', () => {
            if (contextTextbox) {
                contextTextbox.value = '';
                contextText = '';
                selectedContextFile = null;
                contextFileInput.value = '';
                clearContextBtn.classList.add('d-none');
                announceToScreenReader('Context cleared.');
            }
        });
    }

    // Handle textarea input - show/hide clear button and update contextText
    if (contextTextbox) {
        contextTextbox.addEventListener('input', () => {
            contextText = contextTextbox.value;
            // Show clear button if there's text
            if (contextText.trim().length > 0) {
                clearContextBtn.classList.remove('d-none');
            } else {
                clearContextBtn.classList.add('d-none');
            }
        });

        // Update contextText on blur to ensure it's always synced
        contextTextbox.addEventListener('blur', () => {
            contextText = contextTextbox.value;
        });
    }

    function resetForm() {
        selectedFile = null;
        fileInput.value = '';
        previewContainer.classList.add('d-none');
        previewImage.src = '';
        uploadArea.classList.remove('d-none');

        // Clear aria-label from Remove button
        removeImage.removeAttribute('aria-label');

        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        if (contextTextbox) {
            contextTextbox.value = '';
        }
        if (clearContextBtn) {
            clearContextBtn.classList.add('d-none');
        }

        // Clear aria-label from Remove context button
        removeContext.removeAttribute('aria-label');

        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
        generateBtn.disabled = true;
        resultSection.classList.add('d-none');

        // Reset duration timer
        if (estimatePreview) {
            estimatePreview.textContent = '(duration: --:--)';
        }
        if (progressEstimate) {
            progressEstimate.textContent = 'Estimated time: --:--';
        }

        uploadArea.focus();
    }

    // API Configuration - use relative path (frontend and API served from same origin)
    const API_BASE_URL = '/api';

    // Screen reader announcement utility
    function announceToScreenReader(message, assertive = false) {
        const announcement = document.getElementById('screenReaderAnnouncements');
        if (announcement) {
            announcement.textContent = message;
            if (assertive) {
                announcement.setAttribute('aria-live', 'assertive');
            } else {
                announcement.setAttribute('aria-live', 'polite');
            }
            // Clear after announced to allow same message to be announced again
            setTimeout(() => {
                announcement.textContent = '';
                announcement.setAttribute('aria-live', 'polite');
            }, 1000);
        }
    }

    // Show report options (clear checkbox)
    function showReportOptions() {
        const reportOptionsContainer = document.getElementById('reportOptionsContainer');
        if (reportOptionsContainer) {
            reportOptionsContainer.style.display = 'block';
        }
    }

    // Hide report options (clear checkbox)
    function hideReportOptions() {
        const reportOptionsContainer = document.getElementById('reportOptionsContainer');
        if (reportOptionsContainer) {
            reportOptionsContainer.style.display = 'none';
        }
    }

    // Show accessible error message
    function showErrorMessage(message) {
        const errorDiv = document.getElementById('errorMessages');
        if (errorDiv) {
            errorDiv.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <strong>Error:</strong> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close error message"></button>
                </div>
            `;
            // Move focus to error message
            const alertElement = errorDiv.querySelector('.alert');
            if (alertElement) {
                alertElement.setAttribute('tabindex', '-1');
                alertElement.focus();
            }
        }
    }

    // Show accessible info message
    function showInfoMessage(message) {
        const errorDiv = document.getElementById('errorMessages');
        if (errorDiv) {
            errorDiv.innerHTML = `
                <div class="alert alert-info alert-dismissible fade show" role="alert">
                    <strong>Info:</strong> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close info message"></button>
                </div>
            `;
            // Move focus to info message
            const alertElement = errorDiv.querySelector('.alert');
            if (alertElement) {
                alertElement.setAttribute('tabindex', '-1');
                alertElement.focus();
            }
        }
    }

    // Clear error messages
    function clearErrorMessages() {
        const errorDiv = document.getElementById('errorMessages');
        if (errorDiv) {
            errorDiv.innerHTML = '';
        }
    }

    // Check authentication status
    async function checkAuthenticationStatus() {
        console.log('[AUTH] Checking authentication status...');
        try {
            const response = await fetch(`${API_BASE_URL}/auth/status`, {
                credentials: 'include'
            });
            const data = await response.json();
            console.log('[AUTH] Status response:', data);

            if (data.authenticated && data.requires_u2a) {
                // U2A mode: check if we have valid session
                isAuthenticated = data.has_credentials;
                loginUrl = data.login_url;
                console.log('[AUTH] U2A mode - isAuthenticated:', isAuthenticated, 'loginUrl:', loginUrl);
            } else if (!data.requires_u2a) {
                // OpenAI: no user auth required
                isAuthenticated = true;
                console.log('[AUTH] OpenAI mode - no auth required');
            }
        } catch (error) {
            console.error('[AUTH] Error checking auth status:', error);
            isAuthenticated = false;
        }
    }

    // Show authentication via OAuth2 redirect
    async function showAuthentication() {
        console.log('[AUTH] showAuthentication called');
        console.log('[AUTH] loginUrl:', loginUrl);
        console.log('[AUTH] isAuthenticated:', isAuthenticated);

        // If loginUrl is not set, try to fetch auth status again
        if (!loginUrl) {
            console.log('[AUTH] Login URL not set, fetching auth status...');
            await checkAuthenticationStatus();
        }

        if (loginUrl) {
            // Redirect to OAuth2 authorization endpoint
            // This will redirect to ECB login and then back to our callback
            console.log('[AUTH] Redirecting to:', `${API_BASE_URL}${loginUrl}`);
            window.location.href = `${API_BASE_URL}${loginUrl}`;
        } else {
            console.error('[AUTH] No login URL available even after re-checking');
            alert('Authentication is required but no login URL is configured. Please check your setup and ensure the API server is running.');
        }
    }

    // Generate with real API call
    generateBtn.addEventListener('click', async () => {
        console.log('[GENERATE] Button clicked');

        // Backend handles authentication automatically via CredentialManager
        // No frontend authentication check needed
        performGeneration();
    });

    async function performGeneration() {
        const btnText = document.getElementById('btnText');
        const btnSpinner = document.getElementById('btnSpinner');
        const generationStatus = document.getElementById('generationStatus');

        // Show progress bar
        showProgress(true);
        updateProgressEstimate();
        updateProgress(5, 'Clearing previous session data...');

        // Clear previous session data before starting new generation
        try {
            await clearSessionData();
            console.log('[WEBMASTER] Cleared previous session data before new generation');
        } catch (error) {
            console.error('[WEBMASTER] Failed to clear previous session data:', error);
            // Continue anyway - don't block new generation
        }

        updateProgress(10, 'Preparing generation...');

        // Show "Generate..." with spinner during processing, hide duration estimate
        btnText.textContent = 'Generate...';
        btnSpinner.classList.remove('d-none');
        const estimatePreview = document.getElementById('estimatePreview');
        if (estimatePreview) {
            estimatePreview.classList.add('d-none');
        }
        generateBtn.disabled = true;
        if (stopGenerationBtn) {
            stopGenerationBtn.disabled = false;
        }

        // Create new AbortController for this generation
        currentAbortController = new AbortController();

        // Clear previous results and errors
        resultsContainer.innerHTML = '';
        languageResults = {};
        clearErrorMessages();

        // Announce start of generation
        announceToScreenReader(`Starting alt text generation for ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''}.`);

        try {
            // Generate for each selected language
            const totalLanguages = selectedLanguages.length;
            for (let i = 0; i < totalLanguages; i++) {
                const lang = selectedLanguages[i];
                const langName = languageNames[lang] || lang;

                // Calculate progress (10-90% for generation, reserve 90-100% for completion)
                const progressPercent = Math.round(10 + (i / totalLanguages) * 80);
                updateProgress(progressPercent, `Generating alt text for ${langName} (${i + 1} of ${totalLanguages})...`);

                // Update status for screen readers
                if (generationStatus) {
                    generationStatus.textContent = `Generating alt text for ${langName}, language ${i + 1} of ${totalLanguages}`;
                }

                // Prepare FormData
                const formData = new FormData();
                formData.append('image', selectedFile);
                formData.append('language', lang);
                formData.append('translation_mode', translationMode);
                formData.append('use_geo_boost', geoBoost);

                // Handle processing mode
                if (processingMode === 'basic') {
                    // Basic mode: Use default OpenAI GPT-4o with two_step_processing: false
                    // Don't send provider/model parameters, let backend use defaults
                    console.log('[GENERATE] Basic mode - using backend defaults (two_step_processing: false)');
                } else {
                    // Advanced mode: Send selected provider and model values
                    // Add per-step provider and model overrides
                    if (visionProvider) {
                        formData.append('vision_provider', visionProvider);
                    }
                    if (visionModel) {
                        formData.append('vision_model', visionModel);
                    }
                    if (processingProvider) {
                        formData.append('processing_provider', processingProvider);
                    }
                    if (processingModel) {
                        formData.append('processing_model', processingModel);
                    }
                    if (translationProvider) {
                        formData.append('translation_provider', translationProvider);
                    }
                    if (translationModel) {
                        formData.append('translation_model', translationModel);
                    }
                    console.log('[GENERATE] Advanced mode - using custom providers:', {
                        vision: visionProvider + '/' + visionModel,
                        processing: processingProvider + '/' + processingModel,
                        translation: translationProvider + '/' + translationModel
                    });
                }

                if (contextText && contextText.trim()) {
                    formData.append('context', contextText.trim());
                }

                // Update progress before API call
                const sendingPercent = Math.round(10 + ((i + 0.3) / totalLanguages) * 80);
                updateProgress(sendingPercent, `Processing ${selectedFile.name} for ${langName}...`);

                // API Call
                const response = await fetch(`${API_BASE_URL}/generate-alt-text`, {
                    method: 'POST',
                    credentials: 'include',
                    body: formData,
                    signal: currentAbortController.signal
                });

                // Update progress while processing response
                const processingPercent = Math.round(10 + ((i + 0.7) / totalLanguages) * 80);
                updateProgress(processingPercent, `Processing response for ${selectedFile.name} in ${langName}...`);

                const data = await response.json();

                // Check for API quota or rate limit errors
                if (!response.ok) {
                    // Check if error message contains quota/rate limit information
                    let errorMsg = `HTTP error! status: ${response.status}`;

                    if (data.error) {
                        errorMsg = data.error;

                        // Detect quota exceeded errors
                        if (errorMsg.toLowerCase().includes('quota') ||
                            errorMsg.toLowerCase().includes('insufficient_quota') ||
                            errorMsg.toLowerCase().includes('rate limit')) {
                            throw new Error(`API Quota Exceeded: Your API provider has run out of credits or reached rate limits. Please check your billing settings or try using a different provider (enable Advanced Processing Mode to switch providers).`);
                        }

                        // Detect authentication errors
                        if (errorMsg.toLowerCase().includes('authentication') ||
                            errorMsg.toLowerCase().includes('api key') ||
                            errorMsg.toLowerCase().includes('unauthorized')) {
                            throw new Error(`API Authentication Error: ${errorMsg}. Please verify your API keys are configured correctly.`);
                        }
                    }

                    throw new Error(errorMsg);
                }

                if (data.success && data.alt_text !== undefined && data.alt_text !== null) {
                    // Store result for this language
                    languageResults[lang] = {
                        text: data.alt_text,
                        imageId: data.image_id,
                        jsonPath: data.json_file_path
                    };

                    // Create and add result card for this language
                    const card = createLanguageResultCard(lang, data.alt_text, data.image_id, data.json_file_path);
                    resultsContainer.appendChild(card);

                    console.log(`[GENERATE] Successfully generated for ${lang}`);
                } else {
                    // Check if the backend returned a generation error with details
                    if (data.error) {
                        // Check for quota issues in the error message
                        if (data.error.toLowerCase().includes('quota') ||
                            data.error.toLowerCase().includes('insufficient_quota')) {
                            throw new Error(`API Quota Exceeded: Your API provider has run out of credits. Please add credits to your account or switch to a different provider (enable Advanced Processing Mode to change providers).`);
                        }
                        throw new Error(data.error);
                    }
                    throw new Error(`Failed to generate alt-text for ${lang}`);
                }
            }

            // Update progress to complete
            updateProgress(100, 'Generation complete!');

            // Show result section and scroll to it
            resultSection.classList.remove('d-none');
            resultSection.scrollIntoView({ behavior: 'smooth' });

            // Show report options checkbox
            showReportOptions();

            // Enable Clear button after successful generation
            clearBtn.disabled = false;

            // Announce completion
            announceToScreenReader(`Alt text generated successfully for ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''}. Review and edit the results below.`);
            if (generationStatus) {
                generationStatus.textContent = `Generation complete. ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''} processed.`;
            }

            // Hide progress bar after a short delay
            setTimeout(() => showProgress(false), 500);

            // Move focus to first result textarea
            setTimeout(() => {
                const firstTextarea = document.getElementById(`resultText_${selectedLanguages[0]}`);
                if (firstTextarea) {
                    firstTextarea.focus();
                }
            }, 600);

        } catch (error) {
            console.error('[GENERATE] Error generating alt-text:', error);

            // Check if error was due to abort
            if (error.name === 'AbortError') {
                console.log('[GENERATE] Generation aborted by user');
                showProgress(false);
                return; // Stop function already handled the cleanup
            }

            // Determine if this is a known error type
            let errorMessage;
            if (error.message.includes('API Quota Exceeded')) {
                errorMessage = error.message;
            } else if (error.message.includes('API Authentication Error')) {
                errorMessage = error.message;
            } else if (error.message.includes('HTTP error! status: 500')) {
                errorMessage = `Server Error (500): The backend encountered an error processing your request. This may be due to API quota limits or configuration issues. Check the browser console and server logs for details.`;
            } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                errorMessage = `Network Error: Cannot connect to the API server. Make sure the backend is running (python backend/api.py) and accessible.`;
            } else {
                errorMessage = `Generation Error: ${error.message}`;
            }

            showErrorMessage(errorMessage);
            announceToScreenReader(errorMessage, true);
            if (generationStatus) {
                generationStatus.textContent = 'Generation failed. Please see error message above.';
            }
            showProgress(false);
        } finally {
            btnText.textContent = 'Generate';
            btnSpinner.classList.add('d-none');
            const estimatePreview = document.getElementById('estimatePreview');
            if (estimatePreview) {
                estimatePreview.classList.remove('d-none');
            }
            generateBtn.disabled = false;
            if (stopGenerationBtn) {
                stopGenerationBtn.disabled = true;
            }
            currentAbortController = null;
        }
    }

    // Copy and Save buttons are now handled dynamically in createLanguageResultCard()

    // Stop generation function
    async function stopGeneration() {
        // Show spinner on stop button
        const stopIcon = document.getElementById('stopIcon');
        const stopSpinner = document.getElementById('stopSpinner');
        const stopBtnText = document.getElementById('stopBtnText');
        if (stopIcon) stopIcon.classList.add('d-none');
        if (stopSpinner) stopSpinner.classList.remove('d-none');
        if (stopBtnText) stopBtnText.textContent = 'Stopping...';
        if (stopGenerationBtn) stopGenerationBtn.disabled = true;

        // Update progress to show stopping
        updateProgress(10, 'Stopping generation...');
        announceToScreenReader('Stopping generation and clearing session data');

        if (currentAbortController) {
            currentAbortController.abort();
            updateProgress(30, 'Aborting current request...');
        }

        // Small delay for visual feedback
        await new Promise(resolve => setTimeout(resolve, 200));
        updateProgress(50, 'Clearing session data...');

        // Clear session data to start from a clean state
        try {
            await clearSessionData();
            updateProgress(80, 'Session data cleared');
        } catch (error) {
            console.error('[WEBMASTER] Failed to clear session data:', error);
            updateProgress(80, 'Session cleanup attempted');
        }

        currentAbortController = null;
        languageResults = {};
        resultsContainer.innerHTML = '';
        resultSection.classList.add('d-none');

        updateProgress(100, 'Generation stopped');

        // Small delay before hiding progress
        await new Promise(resolve => setTimeout(resolve, 500));
        showProgress(false);

        showInfoMessage('Generation stopped and session data cleared');
        announceToScreenReader('Generation stopped and session data cleared');

        // Reset button states
        const btnText = document.getElementById('btnText');
        const btnSpinner = document.getElementById('btnSpinner');
        const estimatePreview = document.getElementById('estimatePreview');
        if (btnText) btnText.textContent = 'Generate';
        if (btnSpinner) btnSpinner.classList.add('d-none');
        if (estimatePreview) estimatePreview.classList.remove('d-none');
        generateBtn.disabled = false;

        // Reset stop button
        if (stopIcon) stopIcon.classList.remove('d-none');
        if (stopSpinner) stopSpinner.classList.add('d-none');
        if (stopBtnText) stopBtnText.textContent = 'Stop';
        if (stopGenerationBtn) stopGenerationBtn.disabled = true;
    }

    // Clear session data helper function
    async function clearSessionData() {
        try {
            await fetch(`${API_BASE_URL}/clear-session`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
        } catch (error) {
            console.error('[WEBMASTER] Failed to clear session data:', error);
        }
    }

    // Stop button event listener
    if (stopGenerationBtn) {
        stopGenerationBtn.addEventListener('click', stopGeneration);
    }

    // Clear all - reset form to initial state and clear session data
    clearBtn.addEventListener('click', async () => {
        try {
            // Call API to clear session data on server
            const response = await fetch(`${API_BASE_URL}/clear-session`, {
                method: 'POST',
                credentials: 'include'
            });

            const data = await response.json();

            if (data.success) {
                console.log(`[CLEAR] Session cleared: ${data.files_deleted} files, ${data.folders_deleted} folders deleted`);
            } else {
                console.warn(`[CLEAR] Session clear warning: ${data.message}`);
            }
        } catch (error) {
            console.error('[CLEAR] Error clearing session:', error);
            // Continue with frontend reset even if API call fails
        }

        // Reset image upload
        selectedFile = null;
        fileInput.value = '';
        previewContainer.classList.add('d-none');
        uploadArea.classList.remove('d-none');

        // Reset context
        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
        if (contextTextbox) {
            contextTextbox.value = '';
        }

        // Reset advanced processing mode toggle (must be done before setDefaultProviders)
        const processingModeToggle = document.getElementById('processingModeToggle');
        if (processingModeToggle) {
            processingModeToggle.checked = false;
        }
        handleProcessingModeChange();

        // Reset all provider and model selections to default values from config
        setDefaultProviders();

        // Reset language selection
        langSelect.selectedIndex = -1; // Deselect all
        Array.from(langSelect.options).forEach(option => {
            if (option.value === 'en') {
                option.selected = true; // Re-select English by default
            }
        });
        selectedLanguages = ['en'];

        // Reset translation mode
        if (translationModeToggle) {
            translationModeToggle.checked = false;
        }
        handleTranslationModeChange();

        // Reset GEO Boost
        const geoBoostToggle = document.getElementById('geoBoostToggle');
        if (geoBoostToggle) {
            geoBoostToggle.checked = false;
        }
        handleGeoBoostChange();

        // Hide result section and clear results
        resultSection.classList.add('d-none');
        resultsContainer.innerHTML = '';
        languageResults = {};

        // Hide report options checkbox
        hideReportOptions();

        // Disable buttons
        generateBtn.disabled = true;
        clearBtn.disabled = true;

        // Scroll back to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
        uploadArea.focus();

        // Announce to screen reader
        announceToScreenReader('All data cleared. Session reset.');
    });
