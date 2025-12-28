    // State variables for each step
    let visionProvider = '';
    let visionModel = '';
    let processingProvider = '';
    let processingModel = '';
    let translationProvider = '';
    let translationModel = '';
    let currentLang = 'en';
    let selectedFile = null;
    let selectedContextFile = null;
    let contextText = '';
    let actualAltText = ''; // Store the actual alt text for copying
    let isAuthenticated = false;
    let loginUrl = null;

    // Model options for each provider (from config.json)
    const modelOptions = {
        openai: {
            vision: ['gpt-4o', 'gpt-4o-mini'],
            processing: ['gpt-4o', 'gpt-4o-mini'],
            translation: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo']
        },
        claude: {
            vision: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
            processing: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
            translation: ['claude-3-5-haiku-20241022', 'claude-3-haiku-20240307']
        },
        'ecb-llm': {
            vision: ['gpt-4o', 'gpt-5.1'],
            processing: ['gpt-4o', 'gpt-5.1'],
            translation: ['gpt-4o', 'gpt-5.1']
        },
        ollama: {
            vision: ['granite3.2-vision', 'llama3.2-vision', 'moondream', 'llava'],
            processing: ['phi3', 'llama3.2', 'granite3.2', 'qwen2.5', 'mistral'],
            translation: ['phi3', 'llama3.2', 'granite3.2', 'qwen2.5', 'mistral']
        }
    };

    // Initialize Bootstrap tooltips
    document.addEventListener('DOMContentLoaded', function() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Check authentication status on page load
        checkAuthenticationStatus();

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
    // const providerSelect = document.getElementById('providerSelect');
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
    const copyBtn = document.getElementById('copyBtn');
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

    // Language selection
    langSelect.addEventListener('change', (e) => {
        currentLang = e.target.value;
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
        if (!file.type.startsWith('image/')) return;

        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            uploadArea.classList.add('d-none');
            previewContainer.classList.remove('d-none');
            generateBtn.disabled = false;
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

    function handleContextFile(file) {
        selectedContextFile = file;
        const reader = new FileReader();

        reader.onload = (e) => {
            contextText = e.target.result;
            contextFileName.textContent = file.name;
            const preview = contextText.length > 100 ? contextText.substring(0, 100) + '...' : contextText;
            contextFilePreview.textContent = preview;
            contextPreviewContainer.classList.remove('d-none');
            contextDragdrop.classList.add('d-none');
        };

        reader.readAsText(file);
    }

    removeContext.addEventListener('click', () => {
        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
    });

    function resetForm() {
        selectedFile = null;
        fileInput.value = '';
        previewContainer.classList.add('d-none');
        previewImage.src = '';
        uploadArea.classList.remove('d-none');
        selectedContextFile = null;
        contextText = '';
        contextFileInput.value = '';
        contextPreviewContainer.classList.add('d-none');
        contextDragdrop.classList.remove('d-none');
        generateBtn.disabled = true;
        resultSection.classList.add('d-none');
    }

    // API Configuration
    const API_BASE_URL = 'http://localhost:8000/api';

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

        btnText.textContent = 'Generating...';
        btnSpinner.classList.remove('d-none');
        generateBtn.disabled = true;

        try {
            // Prepare FormData
            const formData = new FormData();
            formData.append('image', selectedFile);
            formData.append('language', currentLang);

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
                actualAltText = data.alt_text; // Store actual value
                const altTextDisplay = data.alt_text === "" ? '(Empty alt text for decorative image)' : data.alt_text;
                document.getElementById('resultText').value = altTextDisplay;
                resultSection.classList.remove('d-none');
                resultSection.scrollIntoView({ behavior: 'smooth' });

                // Enable Clear button after successful generation
                clearBtn.disabled = false;
            } else {
                throw new Error(data.error || 'Failed to generate alt-text');
            }

        } catch (error) {
            console.error('Error generating alt-text:', error);
            alert(`Generation error: ${error.message}\n\nMake sure the API server is running (python backend/api.py)`);
        } finally {
            btnText.textContent = 'Generate Alt Text';
            btnSpinner.classList.add('d-none');
            generateBtn.disabled = false;
        }
    }

    // Copy result
    copyBtn.addEventListener('click', () => {
        // Copy the current value from textarea (allowing user edits)
        const textToCopy = document.getElementById('resultText').value;
        navigator.clipboard.writeText(textToCopy).then(() => {
            document.getElementById('copyBtnText').textContent = 'Copied!';
            setTimeout(() => {
                document.getElementById('copyBtnText').textContent = 'Copy';
            }, 2000);
        });
    });

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

        langSelect.value = 'en';
        currentLang = 'en';

        // Hide result section
        resultSection.classList.add('d-none');
        document.getElementById('resultText').value = '';
        actualAltText = '';

        // Disable buttons
        generateBtn.disabled = true;
        clearBtn.disabled = true;

        // Scroll back to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
