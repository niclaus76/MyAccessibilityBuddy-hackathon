/**
 * Accessibility Compliance Tool - Simplified Implementation
 * Matches specification from development/2-testing/accessibility-compliance.md
 *
 * This tool analyzes web pages for WCAG 2.2 alternative text compliance
 * by calling the backend API which executes: app.py -w --url <URL> --num-images <N> --language <langs> --report
 */

(function() {
    'use strict';

    // API Configuration - use relative path (frontend and API served from same origin)
    const API_BASE_URL = '/api';

    // DOM Elements
    const pageUrlInput = document.getElementById('pageUrl');
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const advancedOptionsDiv = document.getElementById('advancedOptions');
    const languageSelect = document.getElementById('languageSelect');
    const processAllImagesToggle = document.getElementById('processAllImagesToggle');
    const numImagesContainer = document.getElementById('numImagesContainer');
    const numImagesInput = document.getElementById('numImagesInput');

    // Advanced Options Elements
    const visionProviderSelect = document.getElementById('visionProviderSelect');
    const visionModelSelect = document.getElementById('visionModelSelect');
    const processingProviderSelect = document.getElementById('processingProviderSelect');
    const processingModelSelect = document.getElementById('processingModelSelect');
    const translationProviderSelect = document.getElementById('translationProviderSelect');
    const translationModelSelect = document.getElementById('translationModelSelect');
    const translationModeToggle = document.getElementById('translationModeToggle');
    const geoBoostToggle = document.getElementById('geoBoostToggle');
    const generateBtn = document.getElementById('generateBtn');
    const stopAnalysisBtn = document.getElementById('stopAnalysisBtn');
    const clearBtn = document.getElementById('clearBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const progressContainer = document.getElementById('progressContainer');
    const progressStatus = document.getElementById('progressStatus');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressEstimate = document.getElementById('progressEstimate');
    const estimatePreview = document.getElementById('estimatePreview');
    const resultsSection = document.getElementById('resultsSection');
    const reportSummary = document.getElementById('reportSummary');
    const downloadReportBtn = document.getElementById('downloadReportBtn');
    const viewReportBtn = document.getElementById('viewReportBtn');
    const screenReaderAnnouncements = document.getElementById('screenReaderAnnouncements');
    const analysisStatus = document.getElementById('analysisStatus');
    const errorMessages = document.getElementById('errorMessages');

    // State
    let currentReportPath = null;
    let currentReportData = null;
    let modelOptions = {};
    let availableProviders = [];
    let configDefaults = {};
    let timeEstimation = {};
    let currentAbortController = null;
    let currentSessionId = null;

    // Initialize
    function init() {
        console.log('[COMPLIANCE] Initializing...');
        console.log('[COMPLIANCE] clearBtn:', clearBtn);
        console.log('[COMPLIANCE] stopAnalysisBtn:', stopAnalysisBtn);
        console.log('[COMPLIANCE] generateBtn:', generateBtn);
        setupEventListeners();
        initializeBootstrapTooltips();
        loadAvailableProviders();
    }

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
                console.log('[COMPLIANCE] Provider status:', statusData);
            } catch (e) {
                console.warn('[COMPLIANCE] Could not parse provider status, showing all enabled providers');
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
            availableProviders = Object.keys(connectedProviders);

            console.log('[COMPLIANCE] Filtered providers:', availableProviders);

            // Store config defaults if provided
            if (data.config_defaults) {
                configDefaults = data.config_defaults;
                if (data.config_defaults.time_estimation) {
                    timeEstimation = data.config_defaults.time_estimation;
                }
            }

            // Populate provider dropdowns
            populateProviderDropdowns();
            // Set default values from config
            setDefaultProviders();

            console.log('[COMPLIANCE] Loaded available providers:', availableProviders);
            console.log('[COMPLIANCE] Config defaults:', configDefaults);
        } catch (error) {
            console.error('[COMPLIANCE] Error loading available providers:', error);
        }
    }

    // Populate provider dropdowns
    function populateProviderDropdowns() {
        // Populate vision provider
        visionProviderSelect.innerHTML = '<option value="">Please select</option>';
        availableProviders.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider;
            option.textContent = provider.charAt(0).toUpperCase() + provider.slice(1);
            visionProviderSelect.appendChild(option);
        });

        // Populate processing provider
        processingProviderSelect.innerHTML = '<option value="">Please select</option>';
        availableProviders.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider;
            option.textContent = provider.charAt(0).toUpperCase() + provider.slice(1);
            processingProviderSelect.appendChild(option);
        });

        // Populate translation provider
        translationProviderSelect.innerHTML = '<option value="">Please select</option>';
        availableProviders.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider;
            option.textContent = provider.charAt(0).toUpperCase() + provider.slice(1);
            translationProviderSelect.appendChild(option);
        });

        // Add event listeners for provider changes
        visionProviderSelect.addEventListener('change', () => {
            updateModelOptions('vision');
            updateProgressEstimate();
        });
        processingProviderSelect.addEventListener('change', () => {
            updateModelOptions('processing');
            updateProgressEstimate();
        });
        translationProviderSelect.addEventListener('change', () => {
            updateModelOptions('translation');
            updateProgressEstimate();
        });
    }

    // Update model dropdown based on selected provider
    function updateModelOptions(step) {
        let providerSelect, modelSelect;

        if (step === 'vision') {
            providerSelect = visionProviderSelect;
            modelSelect = visionModelSelect;
        } else if (step === 'processing') {
            providerSelect = processingProviderSelect;
            modelSelect = processingModelSelect;
        } else if (step === 'translation') {
            providerSelect = translationProviderSelect;
            modelSelect = translationModelSelect;
        }

        const selectedProvider = providerSelect.value;

        if (!selectedProvider) {
            modelSelect.disabled = true;
            modelSelect.innerHTML = '<option value="">Please select provider first</option>';
            return;
        }

        const models = modelOptions[selectedProvider]?.[step] || [];
        modelSelect.innerHTML = '';
        modelSelect.disabled = false;

        if (models.length === 0) {
            modelSelect.innerHTML = '<option value="">No models available</option>';
            modelSelect.disabled = true;
        } else {
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
        }
    }

    // Set default provider and model values from config
    function setDefaultProviders() {
        const visionDefaults = configDefaults.vision || {};
        const processingDefaults = configDefaults.processing || {};
        const translationDefaults = configDefaults.translation || {};

        // Normalize provider name helper
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

        // Set vision defaults
        if (visionDefaults.provider) {
            const normalizedProvider = normalizeProviderName(visionDefaults.provider);
            visionProviderSelect.value = normalizedProvider;
            updateModelOptions('vision');
            if (visionDefaults.model) {
                visionModelSelect.value = visionDefaults.model;
            }
        }

        // Set processing defaults
        if (processingDefaults.provider) {
            const normalizedProvider = normalizeProviderName(processingDefaults.provider);
            processingProviderSelect.value = normalizedProvider;
            updateModelOptions('processing');
            if (processingDefaults.model) {
                processingModelSelect.value = processingDefaults.model;
            }
        }

        // Set translation defaults
        if (translationDefaults.provider) {
            const normalizedProvider = normalizeProviderName(translationDefaults.provider);
            translationProviderSelect.value = normalizedProvider;
            updateModelOptions('translation');
            if (translationDefaults.model) {
                translationModelSelect.value = translationDefaults.model;
            }
        }

        console.log('[COMPLIANCE] Default providers set from config');
        updateProgressEstimate();
    }

    // Setup event listeners
    function setupEventListeners() {
        // URL input validation - mark that user has started typing
        pageUrlInput.addEventListener('input', () => {
            userHasTyped = true;
            validateUrl();
        });
        pageUrlInput.addEventListener('blur', validateUrl);

        // Advanced Options toggle
        advancedOptionsToggle.addEventListener('change', () => {
            toggleAdvancedOptions();
            updateProgressEstimate();
        });

        // Process All Images toggle
        processAllImagesToggle.addEventListener('change', () => {
            toggleNumImagesInput();
            updateProgressEstimate();
        });
        numImagesInput.addEventListener('input', updateProgressEstimate);
        languageSelect.addEventListener('change', updateProgressEstimate);

        if (visionModelSelect) {
            visionModelSelect.addEventListener('change', updateProgressEstimate);
        }
        if (processingModelSelect) {
            processingModelSelect.addEventListener('change', updateProgressEstimate);
        }
        if (translationModelSelect) {
            translationModelSelect.addEventListener('change', updateProgressEstimate);
        }
        if (translationModeToggle) {
            translationModeToggle.addEventListener('change', updateProgressEstimate);
        }
        if (geoBoostToggle) {
            geoBoostToggle.addEventListener('change', updateProgressEstimate);
        }

        // Buttons
        generateBtn.addEventListener('click', () => {
            console.log('[COMPLIANCE] Generate button clicked');
            startAnalysis();
        });

        if (stopAnalysisBtn) {
            stopAnalysisBtn.addEventListener('click', () => {
                console.log('[COMPLIANCE] Stop button clicked');
                stopAnalysis();
            });
        }

        clearBtn.addEventListener('click', () => {
            console.log('[COMPLIANCE] Clear button clicked');
            clearFormWithProgress();
        });

        downloadReportBtn.addEventListener('click', () => {
            console.log('[COMPLIANCE] Download button clicked');
            downloadReport();
        });

        viewReportBtn.addEventListener('click', () => {
            console.log('[COMPLIANCE] View report button clicked');
            viewReportInNewTab();
        });
    }

    // Initialize Bootstrap tooltips
    function initializeBootstrapTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Track if user has started typing
    let userHasTyped = false;

    // URL Validation (format only)
    function validateUrl() {
        const url = pageUrlInput.value.trim();
        const urlError = document.getElementById('urlError');

        // If user hasn't typed yet and we're on initial state (https://), don't validate
        if (!userHasTyped && url === 'https://') {
            pageUrlInput.classList.remove('is-valid', 'is-invalid');
            generateBtn.disabled = true;
            return false;
        }

        if (!url) {
            pageUrlInput.classList.remove('is-valid', 'is-invalid');
            generateBtn.disabled = true;
            return false;
        }

        try {
            const urlObj = new URL(url);
            if (urlObj.protocol === 'http:' || urlObj.protocol === 'https:') {
                // Only remove invalid class, don't add valid yet (wait for reachability check)
                pageUrlInput.classList.remove('is-invalid');
                urlError.textContent = '';
                generateBtn.disabled = false;
                return true;
            } else {
                throw new Error('URL must use HTTP or HTTPS protocol');
            }
        } catch (error) {
            // Only show validation errors if user has started typing
            if (userHasTyped) {
                pageUrlInput.classList.remove('is-valid');
                pageUrlInput.classList.add('is-invalid');
                urlError.textContent = 'Please enter a valid URL (e.g., https://example.com)';
            }
            generateBtn.disabled = true;
            return false;
        }
    }

    // Check if URL is reachable
    async function checkUrlReachability(url, signal) {
        try {
            const response = await fetch(`${API_BASE_URL}/check-url`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url }),
                signal
            });

            const data = await response.json();

            if (data.reachable) {
                pageUrlInput.classList.remove('is-invalid');
                pageUrlInput.classList.add('is-valid');
                return true;
            } else {
                pageUrlInput.classList.remove('is-valid');
                pageUrlInput.classList.add('is-invalid');
                return false;
            }
        } catch (error) {
            // If the endpoint doesn't exist, fall back to optimistic validation
            pageUrlInput.classList.add('is-valid');
            return true;
        }
    }

    // Toggle Advanced Options
    function toggleAdvancedOptions() {
        const isChecked = advancedOptionsToggle.checked;
        advancedOptionsToggle.setAttribute('aria-checked', isChecked);

        if (isChecked) {
            advancedOptionsDiv.classList.remove('d-none');
        } else {
            advancedOptionsDiv.classList.add('d-none');
        }

        announceToScreenReader(`Advanced options ${isChecked ? 'expanded' : 'collapsed'}`);
    }

    // Toggle Number of Images Input
    function toggleNumImagesInput() {
        const processAll = processAllImagesToggle.checked;
        processAllImagesToggle.setAttribute('aria-checked', processAll);

        if (processAll) {
            numImagesContainer.style.display = 'none';
            numImagesInput.required = false;
        } else {
            numImagesContainer.style.display = '';
            numImagesInput.required = true;
        }

        announceToScreenReader(`${processAll ? 'Processing all images' : 'Limited number of images'}`);
    }

    // Clear Form
    async function clearForm() {
        console.log('[COMPLIANCE] clearForm() called');
        console.log('[COMPLIANCE] currentSessionId:', currentSessionId);

        // Show progress bar
        showProgress(true);
        updateProgress(0, 'Preparing to clear...');
        announceToScreenReader('Clearing form and session data');

        // Disable buttons during clearing
        clearBtn.disabled = true;
        generateBtn.disabled = true;

        try {
            updateProgress(20, 'Clearing session data...');

            // Clear backend session data first
            if (currentSessionId) {
                try {
                    await clearSessionData();
                    console.log('[COMPLIANCE] Backend session data cleared');
                    updateProgress(60, 'Session data cleared');
                } catch (error) {
                    console.error('[COMPLIANCE] Failed to clear backend session data:', error);
                    updateProgress(60, 'Session data clear failed (continuing)');
                }
            } else {
                updateProgress(60, 'No session to clear');
            }

            // Small delay for visual feedback
            await new Promise(resolve => setTimeout(resolve, 300));
            updateProgress(80, 'Resetting form fields...');

            // Reset form fields
            pageUrlInput.value = 'https://';
            pageUrlInput.classList.remove('is-valid', 'is-invalid');
            userHasTyped = false; // Reset typing flag
            advancedOptionsToggle.checked = false;
            advancedOptionsDiv.classList.add('d-none');
            processAllImagesToggle.checked = false;
            numImagesContainer.style.display = '';
            numImagesInput.value = '1';

            // Reset language selection to English
            Array.from(languageSelect.options).forEach(option => {
                option.selected = (option.value === 'en');
            });

            resultsSection.style.display = 'none';
            errorMessages.innerHTML = '';
            currentReportPath = null;
            currentReportData = null;
            currentSessionId = null;

            updateProgress(100, 'Clear complete!');

            // Small delay before hiding progress
            await new Promise(resolve => setTimeout(resolve, 500));

            announceToScreenReader('Form cleared successfully');
            console.log('[COMPLIANCE] Form cleared successfully');

        } finally {
            // Hide progress and re-enable clear button
            showProgress(false);
            clearBtn.disabled = false;
            generateBtn.disabled = true; // Keep generate disabled until valid URL
        }
    }

    // Start Analysis
    async function startAnalysis() {
        if (!validateUrl()) {
            return;
        }

        const url = pageUrlInput.value.trim();
        const languages = getSelectedLanguages();
        const numImagesValue = numImagesInput.value;
        const processAllChecked = processAllImagesToggle.checked;
        const numImages = processAllChecked ? null : parseInt(numImagesValue, 10);

        console.log('[COMPLIANCE] ===== NUM IMAGES DEBUG =====');
        console.log('[COMPLIANCE] numImagesInput element:', numImagesInput);
        console.log('[COMPLIANCE] numImagesInput.value (raw):', numImagesValue);
        console.log('[COMPLIANCE] numImagesInput.value type:', typeof numImagesValue);
        console.log('[COMPLIANCE] processAllImagesToggle.checked:', processAllChecked);
        console.log('[COMPLIANCE] parseInt result:', parseInt(numImagesValue, 10));
        console.log('[COMPLIANCE] Final numImages value:', numImages);
        console.log('[COMPLIANCE] ===========================');

        // Clear previous session data before starting new analysis
        if (currentSessionId) {
            try {
                await clearSessionData();
                console.log('[COMPLIANCE] Cleared previous session data before new analysis');
            } catch (error) {
                console.error('[COMPLIANCE] Failed to clear previous session data:', error);
                // Continue anyway - don't block new analysis
            }
        }

        // Disable form during analysis
        setFormState(false);
        showProgress(true);
        updateProgressEstimate();
        hideError();
        resultsSection.style.display = 'none';

        currentAbortController = new AbortController();
        const now = new Date();
        const timestamp = now.getFullYear().toString() + '-' +
            String(now.getMonth() + 1).padStart(2, '0') + '-' +
            String(now.getDate()).padStart(2, '0') + 'T' +
            String(now.getHours()).padStart(2, '0') + '-' +
            String(now.getMinutes()).padStart(2, '0') + '-' +
            String(now.getSeconds()).padStart(2, '0');
        currentSessionId = `${timestamp}-${crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 10)}`;

        try {
            announceToScreenReader('Checking if URL is reachable');
            updateProgress(5, 'Checking URL reachability...');

            // Check if URL is reachable
            const isReachable = await checkUrlReachability(url, currentAbortController.signal);
            if (!isReachable) {
                throw new Error('The URL is not reachable. Please check the URL and try again.');
            }

            announceToScreenReader('Starting web page analysis');
            updateProgress(10, 'Starting analysis...');

            // Build request data
            const requestData = {
                url: url,
                languages: languages,
                session: currentSessionId
            };

            if (numImages !== null) {
                requestData.num_images = numImages;
            }

            // Add advanced options if enabled
            if (advancedOptionsToggle.checked) {
                // Step 1: Vision provider and model
                if (visionProviderSelect.value) {
                    requestData.vision_provider = visionProviderSelect.value;
                }
                if (visionModelSelect.value) {
                    requestData.vision_model = visionModelSelect.value;
                }

                // Step 2: Processing provider and model
                if (processingProviderSelect.value) {
                    requestData.processing_provider = processingProviderSelect.value;
                }
                if (processingModelSelect.value) {
                    requestData.processing_model = processingModelSelect.value;
                }

                // Step 3: Translation provider and model
                if (translationProviderSelect.value) {
                    requestData.translation_provider = translationProviderSelect.value;
                }
                if (translationModelSelect.value) {
                    requestData.translation_model = translationModelSelect.value;
                }

                // Advanced translation mode
                if (translationModeToggle.checked) {
                    requestData.advanced_translation = true;
                }

                // GEO boost
                if (geoBoostToggle.checked) {
                    requestData.geo_boost = true;
                }
            }

            console.log('[COMPLIANCE] Sending async analysis request:', requestData);

            // Start async analysis job
            const startResponse = await fetch(`${API_BASE_URL}/analyze-page-async`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                signal: currentAbortController.signal
            });

            if (!startResponse.ok) {
                const errorData = await startResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.error || `Server error: ${startResponse.status}`);
            }

            const startData = await startResponse.json();
            const jobId = startData.job_id;
            console.log('[COMPLIANCE] Started job:', jobId);

            // Poll for progress
            let pollCount = 0;
            const maxPolls = 300; // 10 minutes max (2 second intervals)
            let lastMessage = '';

            while (pollCount < maxPolls) {
                // Check if aborted
                if (currentAbortController.signal.aborted) {
                    throw new DOMException('Aborted', 'AbortError');
                }

                // Wait before polling (2 seconds)
                await new Promise(resolve => setTimeout(resolve, 2000));
                pollCount++;

                // Poll job status
                const statusResponse = await fetch(`${API_BASE_URL}/job-status/${jobId}`, {
                    signal: currentAbortController.signal
                });

                if (!statusResponse.ok) {
                    console.warn('[COMPLIANCE] Status poll failed:', statusResponse.status);
                    continue;
                }

                const status = await statusResponse.json();
                console.log('[COMPLIANCE] Job status:', status);

                // Update progress bar with real data from backend
                if (status.percent !== undefined && status.message) {
                    updateProgress(status.percent, status.message);

                    // Announce significant progress changes to screen readers
                    if (status.message !== lastMessage) {
                        lastMessage = status.message;
                        // Only announce phase changes, not every update
                        if (status.phase && (status.phase === 'downloading' || status.phase === 'processing')) {
                            if (status.current_image && status.total_images) {
                                announceToScreenReader(`${status.phase === 'downloading' ? 'Downloading' : 'Processing'} image ${status.current_image} of ${status.total_images}`);
                            }
                        }
                    }
                }

                // Check if job completed
                if (status.status === 'complete') {
                    console.log('[COMPLIANCE] Job completed:', status.result);
                    updateProgress(100, 'Analysis complete!');

                    // Store report data
                    const data = status.result;
                    currentReportPath = (data.report_path && !data.report_path.includes('report_template.html'))
                        ? data.report_path
                        : null;
                    currentReportData = data;
                    console.log('[COMPLIANCE] Stored report path:', currentReportPath);

                    // Show results
                    await new Promise(resolve => setTimeout(resolve, 500));
                    showResults(data);

                    announceToScreenReader('Analysis completed successfully. Report is ready.');
                    return; // Exit the function successfully
                }

                // Check if job failed
                if (status.status === 'error') {
                    throw new Error(status.error || 'Analysis failed');
                }
            }

            // Timeout
            throw new Error('Analysis timed out. Please try again with fewer images.');

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[COMPLIANCE] Analysis aborted by user');
                // Don't show error - stopAnalysis() already shows an info message
                return;
            }
            console.error('[COMPLIANCE] Analysis error:', error);

            // Create user-friendly error message
            let userMessage = 'Analysis failed. ';
            const errorMsg = error.message.toLowerCase();

            if (errorMsg.includes('not reachable') || errorMsg.includes('connection')) {
                userMessage += 'The webpage could not be reached. Please verify the URL is correct and accessible.';
            } else if (errorMsg.includes('timeout')) {
                userMessage += 'The request timed out. Please try again or check your internet connection.';
            } else if (errorMsg.includes('quota') || errorMsg.includes('rate limit')) {
                userMessage += 'The service quota has been exceeded. Please try again later.';
            } else if (errorMsg.includes('unauthorized') || errorMsg.includes('authentication')) {
                userMessage += 'Authentication error. Please contact the administrator.';
            } else {
                userMessage += 'An unexpected error occurred. Please try again or contact support.';
            }

            showError(userMessage);
            announceToScreenReader(userMessage);
        } finally {
            currentAbortController = null;
            setFormState(true);
            showProgress(false);
        }
    }

    // Get Selected Languages
    function getSelectedLanguages() {
        const selected = Array.from(languageSelect.selectedOptions).map(option => option.value);
        return selected.length > 0 ? selected : ['en'];
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

    function estimateAnalysisSeconds() {
        const languages = Math.max(getSelectedLanguages().length, 1);
        const processAllChecked = processAllImagesToggle.checked;
        const numImagesValue = parseInt(numImagesInput.value, 10);
        const defaultAll = timeEstimation.default_num_images_when_all || 10;
        const images = processAllChecked ? defaultAll : (Number.isFinite(numImagesValue) ? numImagesValue : 1);

        const visionProviderValue = visionProviderSelect.value;
        const processingProviderValue = processingProviderSelect.value;
        const translationProviderValue = translationProviderSelect.value;
        const visionModelValue = visionModelSelect.value;
        const processingModelValue = processingModelSelect.value;
        const translationModelValue = translationModelSelect.value;

        const translationMode = translationModeToggle.checked ? 'accurate' : 'fast';
        const visionStep = getBaseSeconds(visionProviderValue) * getStepMultiplier('vision') * getModelMultiplier(visionModelValue);
        const processingStep = getBaseSeconds(processingProviderValue) * getStepMultiplier('processing') * getModelMultiplier(processingModelValue);
        const translationStep = getBaseSeconds(translationProviderValue) * getStepMultiplier('translation') * getModelMultiplier(translationModelValue);
        const translationMultiplier = getTranslationModeMultiplier(translationMode);

        let perImage = 0;
        if (translationMode === 'accurate') {
            perImage = (visionStep + processingStep + translationStep) * languages * translationMultiplier;
        } else {
            perImage = visionStep + processingStep + translationStep;
            if (languages > 1) {
                perImage += translationStep * (languages - 1) * translationMultiplier;
            }
        }

        let total = perImage * images;

        if (geoBoostToggle.checked) {
            total *= timeEstimation.geo_boost_multiplier || 1.1;
        }

        total += timeEstimation.overhead_seconds || 5;
        return total;
    }

    function updateProgressEstimate() {
        const seconds = estimateAnalysisSeconds();
        const duration = formatDuration(seconds);
        if (progressEstimate) {
            progressEstimate.textContent = `Estimated time: ~${duration}`;
        }
        if (estimatePreview) {
            estimatePreview.textContent = `(duration: ${duration})`;
        }
    }

    // Update Progress
    function updateProgress(percent, message) {
        progressBar.style.width = `${percent}%`;
        progressBar.setAttribute('aria-valuenow', percent);
        progressPercent.textContent = `${percent}%`;
        progressStatus.textContent = message;
    }

    // Show/Hide Progress
    function showProgress(show) {
        if (show) {
            progressContainer.style.display = '';
            updateProgress(0, 'Initializing...');
        } else {
            progressContainer.style.display = 'none';
        }
    }

    // Set Form State (enable/disable)
    function setFormState(enabled) {
        pageUrlInput.disabled = !enabled;
        advancedOptionsToggle.disabled = !enabled;
        processAllImagesToggle.disabled = !enabled;
        languageSelect.disabled = !enabled;
        numImagesInput.disabled = !enabled;
        clearBtn.disabled = !enabled;
        generateBtn.disabled = !enabled;
        if (stopAnalysisBtn) {
            stopAnalysisBtn.disabled = enabled;
        }

        if (!enabled) {
            // Show "Generate..." with spinner during processing
            btnText.textContent = 'Generate...';
            btnSpinner.classList.remove('d-none');
        } else {
            btnText.textContent = 'Generate';
            btnSpinner.classList.add('d-none');
        }
    }

    // Clear Form with progress feedback
    async function clearFormWithProgress() {
        setFormState(false);
        showProgress(true);
        updateProgress(10, 'Clearing session data...');
        await clearSessionData();
        updateProgress(60, 'Resetting form...');
        resetForm();
        updateProgress(100, 'Ready');
        setTimeout(() => showProgress(false), 300);
        setFormState(true);
        announceToScreenReader('Form cleared and session data removed');
    }

    // Original clear/reset logic
    function resetForm() {
        pageUrlInput.value = 'https://';
        pageUrlInput.classList.remove('is-valid', 'is-invalid');
        userHasTyped = false; // Reset typing flag
        advancedOptionsToggle.checked = false;
        advancedOptionsDiv.classList.add('d-none');
        processAllImagesToggle.checked = false;
        numImagesContainer.style.display = '';
        numImagesInput.value = '1';

        // Reset language selection to English
        Array.from(languageSelect.options).forEach(option => {
            option.selected = (option.value === 'en');
        });

        generateBtn.disabled = true;
        progressContainer.style.display = 'none';
        resultsSection.style.display = 'none';
        errorMessages.innerHTML = '';
        currentReportPath = null;
        currentReportData = null;
        currentSessionId = null;

        // Reset duration timer
        if (estimatePreview) {
            estimatePreview.textContent = '(duration: --:--)';
        }
        if (progressEstimate) {
            progressEstimate.textContent = 'Estimated time: --:--';
        }

        announceToScreenReader('Form cleared');
    }

    async function stopAnalysis() {
        console.log('[COMPLIANCE] stopAnalysis() called');
        console.log('[COMPLIANCE] currentAbortController:', currentAbortController);

        // Show spinner on stop button
        const stopIcon = document.getElementById('stopIcon');
        const stopSpinner = document.getElementById('stopSpinner');
        const stopBtnText = document.getElementById('stopBtnText');
        if (stopIcon) stopIcon.classList.add('d-none');
        if (stopSpinner) stopSpinner.classList.remove('d-none');
        if (stopBtnText) stopBtnText.textContent = 'Stopping...';
        if (stopAnalysisBtn) stopAnalysisBtn.disabled = true;

        // Update progress to show stopping
        updateProgress(10, 'Stopping analysis...');
        announceToScreenReader('Stopping analysis and clearing session data');

        if (currentAbortController) {
            currentAbortController.abort();
            console.log('[COMPLIANCE] Aborted current request');
            updateProgress(30, 'Aborting current request...');
        }

        // Small delay for visual feedback
        await new Promise(resolve => setTimeout(resolve, 200));
        updateProgress(50, 'Clearing session data...');

        // Clear session data to start from a clean state
        try {
            await clearSessionData();
            console.log('[COMPLIANCE] Session data cleared after stop');
            updateProgress(80, 'Session data cleared');
        } catch (error) {
            console.error('[COMPLIANCE] Failed to clear session data:', error);
            updateProgress(80, 'Session cleanup attempted');
        }

        currentAbortController = null;
        currentSessionId = null;
        currentReportPath = null;
        currentReportData = null;

        updateProgress(100, 'Analysis stopped');

        // Small delay before hiding progress
        await new Promise(resolve => setTimeout(resolve, 500));

        showProgress(false);
        resultsSection.style.display = 'none';
        showInfo('Analysis stopped. Session data has been cleared.');
        setFormState(true);
        announceToScreenReader('Analysis stopped. Session data has been cleared.');

        // Reset stop button
        if (stopIcon) stopIcon.classList.remove('d-none');
        if (stopSpinner) stopSpinner.classList.add('d-none');
        if (stopBtnText) stopBtnText.textContent = 'Stop';
        if (stopAnalysisBtn) stopAnalysisBtn.disabled = true;

        console.log('[COMPLIANCE] Analysis stopped successfully');
    }

    // Show Results
    function showResults(data) {
        resultsSection.style.display = '';

        // Create summary
        let summaryHTML = '<div class="border-top pt-3">';

        if (data.summary) {
            summaryHTML += `
                <h3 class="h6">Analysis Summary</h3>
                <ul class="list-unstyled">
                    <li><strong>URL Analyzed:</strong> ${escapeHtml(data.url || 'N/A')}</li>
                    <li><strong>Total Images Found:</strong> ${data.summary.total_images || 0}</li>
                    <li><strong>Images Missing Alt Text:</strong> ${data.summary.missing_alt || 0}</li>
                    <li><strong>Images with Alt Text:</strong> ${data.summary.has_alt || 0}</li>
                </ul>
            `;
        }

        // Only show report path if it's an actual generated report (not the template)
        if (data.report_path && !data.report_path.includes('report_template.html')) {
            const reportFileName = data.report_path.split('/').pop();
            summaryHTML += `
                <p class="text-muted small mt-3">
                    <strong>Report Location:</strong> <code>${escapeHtml(reportFileName)}</code>
                </p>
            `;
        }

        summaryHTML += '</div>';
        reportSummary.innerHTML = summaryHTML;

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Download Report
    async function downloadReport() {
        if (!currentReportPath) {
            showError('No report available to download. Please run an analysis first.');
            announceToScreenReader('Error: No report available to download', true);
            return;
        }

        console.log('[COMPLIANCE] Downloading report:', currentReportPath);
        console.log('[COMPLIANCE] API Base URL:', API_BASE_URL);

        try {
            // Build download URL
            const downloadUrl = `${API_BASE_URL}/download-report?path=${encodeURIComponent(currentReportPath)}`;
            console.log('[COMPLIANCE] Download URL:', downloadUrl);

            // Create a temporary link and trigger download
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = currentReportPath.split('/').pop();
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();

            // Clean up after a short delay
            setTimeout(() => {
                document.body.removeChild(link);
            }, 100);

            announceToScreenReader('Report download started');
            console.log('[COMPLIANCE] Download initiated successfully');
        } catch (error) {
            console.error('[COMPLIANCE] Download error:', error);
            showError('Failed to download report. Please try again or check the console for details.');
            announceToScreenReader('Error: Failed to download report', true);
        }
    }

    // View Report in New Tab
    function viewReportInNewTab() {
        if (!currentReportPath) {
            showError('No report available to view. Please run an analysis first.');
            announceToScreenReader('Error: No report available to view', true);
            return;
        }

        console.log('[COMPLIANCE] Viewing report:', currentReportPath);

        const url = `${API_BASE_URL}/view-report?path=${encodeURIComponent(currentReportPath)}`;
        window.open(url, '_blank');

        announceToScreenReader('Report opened in new tab');
        console.log('[COMPLIANCE] Report opened in new tab');
    }

    // Show Error
    function showError(message) {
        errorMessages.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>Error:</strong> ${escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        errorMessages.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Show Info Message
    function showInfo(message) {
        errorMessages.innerHTML = `
            <div class="alert alert-info alert-dismissible fade show" role="alert">
                <strong>Info:</strong> ${escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        errorMessages.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Hide Error
    function hideError() {
        errorMessages.innerHTML = '';
    }

    // Screen Reader Announcements
    function announceToScreenReader(message) {
        screenReaderAnnouncements.textContent = message;
        // Clear after announcement
        setTimeout(() => {
            screenReaderAnnouncements.textContent = '';
        }, 1000);
    }

    async function clearSessionData() {
        try {
            const payload = currentSessionId ? { session_id: currentSessionId } : {};
            console.log('[COMPLIANCE] Clearing session data with payload:', payload);

            const response = await fetch(`${API_BASE_URL}/clear-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                credentials: 'include'
            });

            const data = await response.json();
            console.log('[COMPLIANCE] Clear session response:', data);

            if (data.success) {
                console.log(`[COMPLIANCE] Successfully cleared: ${data.files_deleted} files, ${data.folders_deleted} folders`);
                if (data.cleared) {
                    console.log('[COMPLIANCE] Cleared folders:', data.cleared);
                }
            } else {
                console.warn('[COMPLIANCE] Clear session warning:', data.message);
            }

            return data;
        } catch (error) {
            console.error('[COMPLIANCE] Failed to clear session data:', error);
            throw error;
        }
    }

    // Utility: Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
