/**
 * Prompt Optimization Tool - Simplified Implementation
 * Matches specification from development/0-backlog/prompt-optimization.md
 *
 * This tool compares multiple processing prompts for generating WCAG 2.2-compliant alternative text
 * by calling the backend API which executes: batch_compare_prompts.py --images-folder <folder> --prompts <list> --report
 */

(function() {
    'use strict';

    // API Configuration
    const currentProtocol = window.location.protocol;
    const currentHost = window.location.hostname;
    const currentPort = window.location.port;

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

    // DOM Elements
    const promptSelect = document.getElementById('promptSelect');
    const imageHelp = document.getElementById('imageHelp');
    const contextHelp = document.getElementById('contextHelp');
    const folderInput = document.getElementById('folderInput');
    const contextFolderInput = document.getElementById('contextFolderInput');
    const languageSelect = document.getElementById('languageSelect');
    const generateBtn = document.getElementById('generateBtn');
    const stopComparisonBtn = document.getElementById('stopComparisonBtn');
    const clearBtn = document.getElementById('clearBtn');
    const promptCount = document.getElementById('promptCount');
    const imageCount = document.getElementById('imageCount');
    
    // Progress and Results
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const progressContainer = document.getElementById('progressContainer');
    const progressStatus = document.getElementById('progressStatus');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const resultsSection = document.getElementById('resultsSection');
    const resultsSummary = document.getElementById('resultsSummary');
    const downloadReportBtn = document.getElementById('downloadReportBtn');
    const viewReportBtn = document.getElementById('viewReportBtn');
    const errorMessages = document.getElementById('errorMessages');
    const screenReaderAnnouncements = document.getElementById('screenReaderAnnouncements');
    const imageSelect = document.getElementById('imageSelect'); // legacy element, used for validation fallback
    const contextStatus = document.getElementById('contextStatus');
    const folderSelect = null; // removed from HTML; keep null to simplify logic

    // State
    let selectedImageFiles = [];
    let selectedContextFiles = [];
    let currentReportPath = null;
    let currentCsvPath = null;
    let availableTestFolders = [];
    let currentAbortController = null;

    // Initialize
    function init() {
        setupEventListeners();
        loadAvailablePrompts();
        loadAvailableTestFolders();
        validateSelections();
    }

    // Setup event listeners
    function setupEventListeners() {
        // Prompt selection
        promptSelect.addEventListener('change', () => {
            updatePromptCount();
            validateSelections();
        });

        // Folder selection
        folderInput.addEventListener('change', handleImageFolderSelection);
        contextFolderInput.addEventListener('change', handleContextFolderSelection);
        if (stopComparisonBtn) {
            stopComparisonBtn.addEventListener('click', stopComparison);
        }

        // Buttons
        generateBtn.addEventListener('click', startComparison);
        clearBtn.addEventListener('click', clearFormWithProgress);
        downloadReportBtn.addEventListener('click', downloadReport);
        viewReportBtn.addEventListener('click', viewReportInNewTab);
    }
    
    // Load Available Prompts
    async function loadAvailablePrompts() {
        try {
            const response = await fetch(`${API_BASE_URL}/available-prompts`);

            if (!response.ok) {
                throw new Error(`Failed to load prompts: ${response.status}`);
            }

            const data = await response.json();
            console.log('[PROMPT-OPT] Available prompts:', data);

            // Clear and populate select
            promptSelect.innerHTML = '';

            if (data.prompts && data.prompts.length > 0) {
                data.prompts.forEach(prompt => {
                    const option = document.createElement('option');
                    option.value = prompt;
                    option.textContent = prompt;

                    // Pre-select default prompts if specified
                    if (data.default && data.default.includes(prompt)) {
                        option.selected = true;
                    }

                    promptSelect.appendChild(option);
                });

                updatePromptCount();
                validateSelections();
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No prompts available';
                option.disabled = true;
                promptSelect.appendChild(option);
            }

        } catch (error) {
            console.error('[PROMPT-OPT] Error loading prompts:', error);
            showError(`Failed to load available prompts: ${error.message}`);

            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Error loading prompts';
            option.disabled = true;
            promptSelect.appendChild(option);
        }
    }

    // Load Available Test Folders (for guidance)
    async function loadAvailableTestFolders() {
        if (!imageHelp) return;
        try {
            const response = await fetch(`${API_BASE_URL}/available-test-folders`, { credentials: 'include' });
            if (!response.ok) {
                throw new Error(`Failed to load test folders: ${response.status}`);
            }
            const data = await response.json();
            availableTestFolders = data.folders || [];

            if (availableTestFolders.length === 0) {
                if (imageHelp) {
                    imageHelp.textContent = 'No test folders found. Please pick a folder manually.';
                }
                return;
            }

            // Update helper text with first folder hint
            const firstFolder = availableTestFolders[0];
            if (firstFolder && imageHelp) {
                imageHelp.textContent = `Choose a folder (e.g., ${firstFolder.path}) to load test images. Subfolders are supported.`;
            }
            if (firstFolder && contextHelp) {
                contextHelp.textContent = `Context files usually live in ${firstFolder.context_folder || 'test/input/context'}. They are matched by filename automatically.`;
            }
        } catch (error) {
            console.error('[PROMPT-OPT] Error loading test folders:', error);
            showError(`Failed to load available test folders: ${error.message}`);
        }
    }

    // Handle Image Folder Selection
    function handleImageFolderSelection(event) {
        const files = event.target.files;

        if (!files || files.length === 0) {
            selectedImageFiles = [];
            imageCount.style.display = 'none';
            validateSelections();
            return;
        }

        // Filter for image files
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
        selectedImageFiles = Array.from(files).filter(file => {
            const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
            return imageExtensions.includes(ext);
        });

        // Show image count
        if (selectedImageFiles.length > 0) {
            imageCount.textContent = `${selectedImageFiles.length} images selected`;
            imageCount.style.display = 'inline-block';
            announceToScreenReader(`${selectedImageFiles.length} images selected`);
        } else {
            imageCount.textContent = 'No image files found in folder';
            imageCount.style.display = 'inline-block';
            imageCount.classList.add('bg-warning');
            imageCount.classList.remove('bg-info');
        }

        validateSelections();
    }

    // Handle Context Folder Selection
    function handleContextFolderSelection(event) {
        const files = event.target.files;

        if (!files || files.length === 0) {
            selectedContextFiles = [];
            return;
        }

        // Filter for text files
        selectedContextFiles = Array.from(files).filter(file => {
            return file.name.toLowerCase().endsWith('.txt');
        });

        if (selectedContextFiles.length > 0) {
            announceToScreenReader(`${selectedContextFiles.length} context files selected`);
        }
    }

    // Update Prompt Count
    function updatePromptCount() {
        const selected = Array.from(promptSelect.selectedOptions).length;
        promptCount.textContent = `${selected} of 10 prompts selected`;

        if (selected < 2) {
            promptCount.classList.remove('bg-primary', 'bg-success');
            promptCount.classList.add('bg-secondary');
        } else if (selected > 10) {
            promptCount.classList.remove('bg-primary', 'bg-secondary');
            promptCount.classList.add('bg-warning');
        } else {
            promptCount.classList.remove('bg-secondary', 'bg-warning');
            promptCount.classList.add('bg-primary');
        }

        announceToScreenReader(`${selected} prompts selected`);
    }

    // Validate Form
    function validateSelections() {
        const selectedPrompts = Array.from(promptSelect.selectedOptions).length;
        const hasImages = selectedImageFiles.length > 0;

        // Enable button only if 2+ prompts and images selected
        const isValid = selectedPrompts >= 2 && selectedPrompts <= 10 && hasImages;
        generateBtn.disabled = !isValid;

        return isValid;
    }
    
    // Clear Form with progress feedback
    async function clearFormWithProgress() {
        setFormState(false);
        showProgress(true);
        updateProgress(10, 'Clearing session data...');
        await clearSessionData();
        updateProgress(60, 'Resetting form...');
        clearForm();
        updateProgress(100, 'Ready');
        setTimeout(() => showProgress(false), 300);
        setFormState(true);
        announceToScreenReader('Form cleared and session data removed');
    }

    // Clear Form
    function clearForm() {
        // Clear selections
        Array.from(promptSelect.options).forEach(option => {
            option.selected = false;
        });
        folderInput.value = '';
        contextFolderInput.value = '';
        selectedImageFiles = [];
        selectedContextFiles = [];

        // Reset language to English only
        Array.from(languageSelect.options).forEach(option => {
            option.selected = (option.value === 'en');
        });

        imageCount.style.display = 'none';
        imageCount.classList.remove('bg-warning');
        imageCount.classList.add('bg-info');
        updatePromptCount();

        // Hide results
        progressContainer.style.display = 'none';
        resultsSection.style.display = 'none';
        errorMessages.innerHTML = '';

        currentReportPath = null;
        currentCsvPath = null;

        generateBtn.disabled = true;

        announceToScreenReader('Form cleared');
    }

    // Start Comparison
    async function startComparison() {
        if (!validateSelections()) {
            showError('Please select at least 2 prompts and image files');
            return;
        }

        // Clear previous session data before starting new comparison
        try {
            await clearSessionData();
            console.log('[PROMPT-OPT] Cleared previous session data before new comparison');
        } catch (error) {
            console.error('[PROMPT-OPT] Failed to clear previous session data:', error);
            // Continue anyway - don't block new comparison
        }

        const selectedPrompts = Array.from(promptSelect.selectedOptions).map(option => option.value);
        const languages = getSelectedLanguages();
        currentAbortController = new AbortController();

        // Disable form during processing
        setFormState(false);
        showProgress(true);
        hideError();
        resultsSection.style.display = 'none';

        try {
            announceToScreenReader('Starting prompt comparison');
            updateProgress(5, 'Uploading images to server...');

            // Step 1: Upload images to a temporary folder on the server
            const formData = new FormData();
            selectedImageFiles.forEach(file => {
                formData.append('images', file);
            });

            // Upload context files if any
            if (selectedContextFiles.length > 0) {
                selectedContextFiles.forEach(file => {
                    formData.append('context', file);
                });
            }

            const uploadResponse = await fetch(`${API_BASE_URL}/upload-test-files`, {
                method: 'POST',
                body: formData,
                signal: currentAbortController.signal
            });

            if (!uploadResponse.ok) {
                const errorData = await uploadResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.error || `Upload failed: ${uploadResponse.status}`);
            }

            const uploadData = await uploadResponse.json();
            console.log('[PROMPT-OPT] Upload response:', uploadData);

            updateProgress(15, 'Initializing batch comparison...');

            // Step 2: Call batch compare API with uploaded folder paths
            const requestData = {
                prompts: selectedPrompts,
                images_folder: uploadData.images_folder,
                context_folder: uploadData.context_folder || '',
                languages: languages
            };

            console.log('[PROMPT-OPT] Sending comparison request:', requestData);

            const response = await fetch(`${API_BASE_URL}/batch-compare-prompts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                signal: currentAbortController.signal
            });

            updateProgress(30, 'Processing images with each prompt...');

            if (!response.ok) {
                // Clone the response so we can read it multiple times if needed
                const responseClone = response.clone();
                let errorData;
                try {
                    errorData = await response.json();
                } catch (jsonError) {
                    // Response is not JSON, try to get text from the clone
                    const errorText = await responseClone.text();
                    throw new Error(errorText || `Server error: ${response.status}`);
                }
                throw new Error(errorData.detail || errorData.error || `Server error: ${response.status}`);
            }

            updateProgress(60, 'Generating comparison metrics...');

            const data = await response.json();
            console.log('[PROMPT-OPT] Comparison response:', data);

            updateProgress(80, 'Compiling HTML report...');

            // Simulate progress for user feedback
            await new Promise(resolve => setTimeout(resolve, 500));
            updateProgress(100, 'Comparison complete!');

            // Store report data
            currentReportPath = data.report_path || null;
            currentCsvPath = data.csv_path || null;

            // Show results
            await new Promise(resolve => setTimeout(resolve, 500));
            showResults(data);

            announceToScreenReader('Comparison completed successfully. Report is ready.');

        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('[PROMPT-OPT] Comparison aborted by user');
                showError('Comparison stopped by user');
                await clearSessionData();
            } else {
                console.error('[PROMPT-OPT] Comparison error:', error);
                showError(`Comparison failed: ${error.message}`);
                announceToScreenReader(`Comparison failed: ${error.message}`);
            }
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

    // Show Results
    function showResults(data) {
        resultsSection.style.display = '';

        // Create summary
        let summaryHTML = '<div class="border-top pt-3">';

        if (data.summary) {
            summaryHTML += `
                <h4 class="h6">Comparison Summary</h4>
                <ul class="list-unstyled">
                    <li><strong>Total Images Processed:</strong> ${data.summary.total_images || 0}</li>
                    <li><strong>Prompts Compared:</strong> ${data.summary.prompts_compared || 0}</li>
                    <li><strong>Languages:</strong> ${data.summary.languages || 0}</li>
                    <li><strong>Success Rate:</strong> ${data.summary.success_rate || 0}%</li>
                </ul>
            `;
        }

        if (currentReportPath) {
            summaryHTML += `
                <p class="text-muted small mt-3">
                    <strong>Report Location:</strong> <code>${escapeHtml(currentReportPath)}</code>
                </p>
            `;
        }

        if (currentCsvPath) {
            summaryHTML += `
                <p class="text-muted small">
                    <strong>CSV Data:</strong> <code>${escapeHtml(currentCsvPath)}</code>
                </p>
            `;
        }

        summaryHTML += '</div>';
        resultsSummary.innerHTML = summaryHTML;

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        promptSelect.disabled = !enabled;
        folderInput.disabled = !enabled;
        contextFolderInput.disabled = !enabled;
        languageSelect.disabled = !enabled;
        clearBtn.disabled = !enabled;
        generateBtn.disabled = !enabled;
        if (stopComparisonBtn) {
            stopComparisonBtn.disabled = enabled;
        }

        if (!enabled) {
            // Show "Generate..." with spinner during processing
            btnText.textContent = 'Generate...';
            btnSpinner.classList.remove('d-none');
        } else {
            btnText.textContent = 'Generate';
            btnSpinner.classList.add('d-none');
            validateSelections(); // Re-validate after re-enabling
        }
    }

    // Stop comparison and clear session data for a clean state
    async function stopComparison() {
        if (currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }
        // Clear session data to start from a clean state
        await clearSessionData();
        currentReportPath = null;
        showProgress(false);
        resultsSection.style.display = 'none';
        showError('Comparison stopped and session data cleared');
        setFormState(true);
        announceToScreenReader('Comparison stopped and session data cleared');
    }

    // View Report in New Tab
    function viewReportInNewTab() {
        if (!currentReportPath) {
            showError('No report available to view');
            return;
        }

        const url = `${API_BASE_URL}/view-report?path=${encodeURIComponent(currentReportPath)}`;
        window.open(url, '_blank');

        announceToScreenReader('Report opened in new tab');
    }

    // Download Report
    function downloadReport() {
        if (!currentReportPath) {
            showError('No report available to download');
            return;
        }

        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = `${API_BASE_URL}/download-report?path=${encodeURIComponent(currentReportPath)}`;
        link.download = currentReportPath.split('/').pop();
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        announceToScreenReader('Report download started');
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
            await fetch(`${API_BASE_URL}/clear-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
        } catch (error) {
            console.error('[PROMPT-OPT] Failed to clear session data:', error);
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
