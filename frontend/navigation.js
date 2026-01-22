/**
 * Navigation visibility control based on config.advanced.json pages_visibility settings.
 * This script fetches the configuration and hides/shows navigation links and home page cards
 * based on the pages_visibility configuration.
 */
(function() {
    'use strict';

    // Map of page keys to their corresponding href patterns
    const pageHrefMap = {
        'home': 'home.html',
        'webmaster': 'webmaster.html',
        'accessibility_compliance': 'accessibility-compliance.html',
        'prompt_optimization': 'prompt-optimization.html',
        'remediation': 'remediation.html',
        'admin': 'admin.html'
    };

    // Default visibility (all pages visible)
    const defaultVisibility = {
        home: true,
        webmaster: true,
        accessibility_compliance: true,
        prompt_optimization: true,
        remediation: true,
        admin: true
    };

    /**
     * Apply page visibility settings to the DOM
     * @param {Object} pagesVisibility - Object with page keys and boolean visibility values
     */
    function applyPageVisibility(pagesVisibility) {
        const visibility = { ...defaultVisibility, ...pagesVisibility };

        Object.keys(pageHrefMap).forEach(pageKey => {
            const href = pageHrefMap[pageKey];
            const isVisible = visibility[pageKey] !== false;

            // Hide/show navigation menu links (check multiple selectors)
            const navSelectors = [
                `nav a[href="${href}"]`,
                `.nav-menu a[href="${href}"]`,
                `#primaryNav a[href="${href}"]`
            ];

            navSelectors.forEach(selector => {
                const links = document.querySelectorAll(selector);
                links.forEach(link => {
                    link.style.display = isVisible ? '' : 'none';
                });
            });

            // Hide/show home page cards (links with card class)
            const cardSelectors = [
                `a.card[href="${href}"]`,
                `a.card-tool[href="${href}"]`
            ];

            cardSelectors.forEach(selector => {
                const cards = document.querySelectorAll(selector);
                cards.forEach(card => {
                    // Find the parent column (col) and hide it to maintain grid layout
                    const col = card.closest('.col');
                    if (col) {
                        col.style.display = isVisible ? '' : 'none';
                    } else {
                        card.style.display = isVisible ? '' : 'none';
                    }
                });
            });
        });

        console.log('[Navigation] Page visibility applied:', visibility);
    }

    /**
     * Fetch configuration and apply page visibility
     */
    async function initPageVisibility() {
        try {
            const response = await fetch('/api/available-providers');
            if (!response.ok) {
                console.warn('[Navigation] Failed to fetch config, status:', response.status);
                return;
            }

            const data = await response.json();
            console.log('[Navigation] Config received:', data.config_defaults?.pages_visibility);

            if (data.config_defaults && data.config_defaults.pages_visibility) {
                applyPageVisibility(data.config_defaults.pages_visibility);
            } else {
                console.warn('[Navigation] No pages_visibility in config');
            }
        } catch (error) {
            console.warn('[Navigation] Error fetching config:', error);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPageVisibility);
    } else {
        // DOM is already ready, run immediately
        initPageVisibility();
    }
})();
