    // State variables for each step
    let visionProvider = '';
    let visionModel = '';
    let processingProvider = '';
    let processingModel = '';
    let translationProvider = '';
    let translationModel = '';
    let selectedLanguages = ['en']; // Array of selected language codes
    let translationMode = 'fast'; // 'fast' or 'accurate'
    let selectedFile = null;
    let selectedContextFile = null;
    let contextText = '';
    let languageResults = {}; // Store alt text results for each language {lang: {text, imageId, jsonPath}}
    let isAuthenticated = false;
    let loginUrl = null;

    // Model options for each provider (will be loaded from API)
    let modelOptions = {};
    let availableProviders = [];
    let processingMode = 'basic'; // 'basic' or 'advanced'
    let configDefaults = {}; // Store default config values

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
            const response = await fetch(`${API_BASE_URL}/available-providers`);
            const data = await response.json();

            modelOptions = data.providers;

            // Build list of available providers (only enabled ones)
            availableProviders = Object.keys(data.providers);

            // Store config defaults if provided
            if (data.config_defaults) {
                configDefaults = data.config_defaults;
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
                'Ollama': 'ollama'
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
                        <p class="mb-0"><small>Available providers: OpenAI, Claude, ECB-LLM, or Ollama</small></p>
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
                    'ollama': 'Ollama'
                };

                option.textContent = displayNames[provider] || provider;
                select.appendChild(option);
            });
        });
    }

    // Processing mode toggle
    function handleProcessingModeChange() {
        const basicMode = document.getElementById('processingModeBasic');
        const advancedSettings = document.getElementById('advancedSettings');

        if (basicMode.checked) {
            processingMode = 'basic';
            advancedSettings.classList.add('d-none');
            console.log('[MODE] Switched to Basic mode (two_step_processing: false)');
        } else {
            processingMode = 'advanced';
            advancedSettings.classList.remove('d-none');
            console.log('[MODE] Switched to Advanced mode (two_step_processing: true)');
        }
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

        // Set up processing mode listeners
        const processingModeBasic = document.getElementById('processingModeBasic');
        const processingModeAdvanced = document.getElementById('processingModeAdvanced');

        if (processingModeBasic && processingModeAdvanced) {
            processingModeBasic.addEventListener('change', handleProcessingModeChange);
            processingModeAdvanced.addEventListener('change', handleProcessingModeChange);
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
    const langSelect = document.getElementById('languageSelect');
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadDragdrop');
    const browseBtn = document.getElementById('browseBtn');
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');
    const generateBtn = document.getElementById('generateBtn');
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
        modelSelect.innerHTML = '<option value="">Please select</option>';
        if (models && models[stepType]) {
            models[stepType].forEach(model => {
                modelSelect.innerHTML += `<option value="${model}">${model}</option>`;
            });
        }
    }

    // Vision provider selection
    visionProviderSelect.addEventListener('change', (e) => {
        visionProvider = e.target.value;
        populateModelDropdown(visionProvider, 'vision', visionModelSelect);
    });

    // Vision model selection
    visionModelSelect.addEventListener('change', (e) => {
        visionModel = e.target.value;
    });

    // Processing provider selection
    processingProviderSelect.addEventListener('change', (e) => {
        processingProvider = e.target.value;
        populateModelDropdown(processingProvider, 'processing', processingModelSelect);
    });

    // Processing model selection
    processingModelSelect.addEventListener('change', (e) => {
        processingModel = e.target.value;
    });

    // Translation provider selection
    translationProviderSelect.addEventListener('change', (e) => {
        translationProvider = e.target.value;
        populateModelDropdown(translationProvider, 'translation', translationModelSelect);
    });

    // Translation model selection
    translationModelSelect.addEventListener('change', (e) => {
        translationModel = e.target.value;
    });

    // Language selection (multiple)
    langSelect.addEventListener('change', (e) => {
        selectedLanguages = Array.from(e.target.selectedOptions).map(opt => opt.value);
        console.log('[LANGUAGE] Selected languages:', selectedLanguages);
    });

    // Translation mode selection
    document.getElementById('translationModeFast').addEventListener('change', (e) => {
        if (e.target.checked) {
            translationMode = 'fast';
            console.log('[TRANSLATION] Mode set to: fast');
        }
    });

    document.getElementById('translationModeAccurate').addEventListener('change', (e) => {
        if (e.target.checked) {
            translationMode = 'accurate';
            console.log('[TRANSLATION] Mode set to: accurate');
        }
    });

    // Character count and visual feedback for a specific textarea
    function updateCharacterCount(textarea, charCountNum, charWarning) {
        const text = textarea.value;
        const count = text.length;
        const previousCount = parseInt(charCountNum.textContent) || 0;

        charCountNum.textContent = count;

        // Check if we crossed the 125 character threshold
        const wasOverLimit = previousCount > 125;
        const isOverLimit = count > 125;

        if (isOverLimit) {
            charWarning.classList.remove('d-none');
            textarea.style.color = 'red';
            // Announce when crossing threshold
            if (!wasOverLimit) {
                announceToScreenReader(`Warning: Alt text exceeds recommended 125 characters. Current count: ${count} characters.`);
            }
        } else {
            charWarning.classList.add('d-none');
            textarea.style.color = '';
            // Announce when going back under threshold
            if (wasOverLimit) {
                announceToScreenReader(`Alt text is now within recommended limit. Current count: ${count} characters.`);
            }
        }
    }

    // Create a result card for a specific language
    function createLanguageResultCard(lang, altText, imageId, jsonPath) {
        const langName = languageNames[lang] || lang;
        const altTextDisplay = altText === "" ? '(Empty alt text for decorative image)' : altText;

        const card = document.createElement('div');
        card.className = 'card shadow-sm mb-3';
        card.setAttribute('data-language', lang);

        card.innerHTML = `
            <div class="card-body">
                <h6 class="card-title mb-3">${langName}</h6>
                <div class="callout success">
                    <label for="resultText_${lang}" class="form-label">Generated alternative text for ${langName}</label>
                    <textarea id="resultText_${lang}" class="form-control mb-2" rows="4"
                        placeholder="Generated alt text will appear here..."
                        aria-describedby="charCount_${lang}">${altTextDisplay}</textarea>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <small id="charCount_${lang}" class="text-muted" aria-live="polite" aria-atomic="true">
                            <span id="charCountNum_${lang}">${altText.length}</span> characters
                            <span id="charWarning_${lang}" class="text-warning ${altText.length > 125 ? '' : 'd-none'}" role="status"> (⚠ Over 125 characters)</span>
                        </small>
                        <small class="text-muted" aria-hidden="true">Recommended: ≤ 125 characters</small>
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

    // Save all reviewed alt texts
    async function saveAllReviewedAltTexts() {
        const saveAllBtn = document.getElementById('saveAllBtn');
        const saveAllBtnText = document.getElementById('saveAllBtnText');
        const saveAllMessage = document.getElementById('saveAllMessage');
        const saveAllSuccessMsg = document.getElementById('saveAllSuccessMsg');
        const saveAllErrorMsg = document.getElementById('saveAllErrorMsg');

        saveAllBtnText.textContent = 'Saving...';
        saveAllBtn.disabled = true;
        saveAllMessage.classList.add('d-none');
        saveAllSuccessMsg.textContent = '';
        saveAllErrorMsg.textContent = '';

        let savedCount = 0;
        let errorCount = 0;
        const errors = [];

        // Check for over-length warnings
        const warnings = [];
        for (const lang of Object.keys(languageResults)) {
            const textarea = document.getElementById(`resultText_${lang}`);
            if (textarea) {
                const reviewedText = textarea.value;
                const textToSave = reviewedText === '(Empty alt text for decorative image)' ? '' : reviewedText;
                if (textToSave.length > 125) {
                    const langName = languageNames[lang] || lang;
                    warnings.push(`${langName}: ${textToSave.length} characters`);
                }
            }
        }

        if (warnings.length > 0) {
            const confirmSave = confirm(
                `⚠️ Warning: Some alt texts exceed 125 characters:\n\n${warnings.join('\n')}\n\n` +
                `Longer alt text may not be ideal for screen reader users.\n\n` +
                `Do you want to save them anyway?`
            );
            if (!confirmSave) {
                saveAllBtnText.textContent = 'Save All Reviews';
                saveAllBtn.disabled = false;
                return;
            }
        }

        // Save each language
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

                if (data.success) {
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

        // Show results
        if (errorCount === 0) {
            saveAllSuccessMsg.textContent = `✓ Successfully saved all ${savedCount} language(s)!`;
            saveAllMessage.classList.remove('d-none');
            setTimeout(() => {
                saveAllMessage.classList.add('d-none');
            }, 3000);
        } else if (savedCount > 0) {
            saveAllSuccessMsg.textContent = `✓ Saved ${savedCount} language(s)`;
            saveAllErrorMsg.textContent = `✗ Failed to save ${errorCount} language(s): ${errors.join(', ')}`;
            saveAllMessage.classList.remove('d-none');
        } else {
            saveAllErrorMsg.textContent = `✗ Failed to save all languages: ${errors.join(', ')}`;
            saveAllMessage.classList.remove('d-none');
        }

        saveAllBtnText.textContent = 'Save All Reviews';
        saveAllBtn.disabled = false;
    }

    // Set up Save All button handler after DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        const saveAllBtn = document.getElementById('saveAllBtn');
        if (saveAllBtn) {
            saveAllBtn.addEventListener('click', saveAllReviewedAltTexts);
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

    // Upload area keyboard accessibility
    uploadArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
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

    // Context drag-drop keyboard accessibility
    contextDragdrop.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            contextFileInput.click();
        }
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
        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
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
        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        if (contextTextbox) {
            contextTextbox.value = '';
        }
        if (clearContextBtn) {
            clearContextBtn.classList.add('d-none');
        }
        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
        generateBtn.disabled = true;
        resultSection.classList.add('d-none');
    }

    // API Configuration - dynamically determine backend URL
    // In Docker/AWS: frontend on :8080, backend on :8000
    // Use current hostname but with port 8000 for API calls
    const currentHost = window.location.hostname;
    const currentPort = window.location.port;
    const currentProtocol = window.location.protocol;

    let API_BASE_URL;
    if (currentPort === '8080') {
        // Frontend is on 8080, backend is on 8000
        API_BASE_URL = `${currentProtocol}//${currentHost}:8000/api`;
    } else if (currentPort === '8000') {
        // Accessing backend directly
        API_BASE_URL = '/api';
    } else {
        // Production with reverse proxy - use relative path
        API_BASE_URL = '/api';
    }

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
            const response = await fetch(`${API_BASE_URL}/auth/status`);
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

        btnText.textContent = 'Generating...';
        btnSpinner.classList.remove('d-none');
        generateBtn.disabled = true;

        // Clear previous results and errors
        resultsContainer.innerHTML = '';
        languageResults = {};
        clearErrorMessages();

        // Announce start of generation
        announceToScreenReader(`Starting alt text generation for ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''}.`);

        try {
            // Generate for each selected language
            for (let i = 0; i < selectedLanguages.length; i++) {
                const lang = selectedLanguages[i];
                const langName = languageNames[lang] || lang;
                btnText.textContent = `Generating (${i + 1}/${selectedLanguages.length})...`;

                // Update status for screen readers
                if (generationStatus) {
                    generationStatus.textContent = `Generating alt text for ${langName}, language ${i + 1} of ${selectedLanguages.length}`;
                }

                // Prepare FormData
                const formData = new FormData();
                formData.append('image', selectedFile);
                formData.append('language', lang);
                formData.append('translation_mode', translationMode);

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

                // API Call
                const response = await fetch(`${API_BASE_URL}/generate-alt-text`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

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
                    throw new Error(data.error || `Failed to generate alt-text for ${lang}`);
                }
            }

            // Show result section and scroll to it
            resultSection.classList.remove('d-none');
            resultSection.scrollIntoView({ behavior: 'smooth' });

            // Enable Clear button after successful generation
            clearBtn.disabled = false;

            // Announce completion
            announceToScreenReader(`Alt text generated successfully for ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''}. Review and edit the results below.`);
            if (generationStatus) {
                generationStatus.textContent = `Generation complete. ${selectedLanguages.length} language${selectedLanguages.length > 1 ? 's' : ''} processed.`;
            }

            // Move focus to first result textarea
            setTimeout(() => {
                const firstTextarea = document.getElementById(`resultText_${selectedLanguages[0]}`);
                if (firstTextarea) {
                    firstTextarea.focus();
                }
            }, 500);

        } catch (error) {
            console.error('Error generating alt-text:', error);
            const errorMessage = `Generation error: ${error.message}. Make sure the API server is running (python backend/api.py).`;
            showErrorMessage(errorMessage);
            announceToScreenReader(errorMessage, true);
            if (generationStatus) {
                generationStatus.textContent = 'Generation failed. Please see error message.';
            }
        } finally {
            btnText.textContent = 'Generate Alt Text';
            btnSpinner.classList.add('d-none');
            generateBtn.disabled = false;
        }
    }

    // Copy and Save buttons are now handled dynamically in createLanguageResultCard()

    // Clear all - reset form to initial state
    clearBtn.addEventListener('click', () => {
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

        // Reset all provider and model selections to default
        visionProviderSelect.value = '';
        visionModelSelect.value = '';
        visionModelSelect.disabled = true;
        visionProvider = '';
        visionModel = '';

        processingProviderSelect.value = '';
        processingModelSelect.value = '';
        processingModelSelect.disabled = true;
        processingProvider = '';
        processingModel = '';

        translationProviderSelect.value = '';
        translationModelSelect.value = '';
        translationModelSelect.disabled = true;
        translationProvider = '';
        translationModel = '';

        // Reset language selection
        langSelect.selectedIndex = -1; // Deselect all
        Array.from(langSelect.options).forEach(option => {
            if (option.value === 'en') {
                option.selected = true; // Re-select English by default
            }
        });
        selectedLanguages = ['en'];

        // Reset translation mode
        document.getElementById('translationModeFast').checked = true;
        translationMode = 'fast';

        // Hide result section and clear results
        resultSection.classList.add('d-none');
        resultsContainer.innerHTML = '';
        languageResults = {};

        // Disable buttons
        generateBtn.disabled = true;
        clearBtn.disabled = true;

        // Scroll back to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
