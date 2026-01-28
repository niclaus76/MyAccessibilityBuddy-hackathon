/**
 * Navigation visibility and position control based on config settings.
 * This script fetches the configuration and:
 * - hides/shows navigation links and home page cards based on pages_visibility
 * - applies menu position (fixed or static) based on menu_position
 */
(function() {
    'use strict';

    // Map of page keys to their corresponding href patterns
    const pageHrefMap = {
        'home': 'index.html',
        'content_creator': 'content-creator.html',
        'accessibility_compliance': 'accessibility-compliance.html',
        'prompt_optimization': 'prompt-optimization.html',
        'remediation': 'remediation.html',
        'admin': 'admin.html'
    };

    // Default visibility (all pages visible)
    const defaultVisibility = {
        home: true,
        content_creator: true,
        accessibility_compliance: true,
        prompt_optimization: true,
        remediation: true,
        admin: true
    };

    /**
     * Apply menu position setting
     * @param {string} position - 'fixed' or 'static'
     */
    function applyMenuPosition(position) {
        const menuToggle = document.getElementById('menuToggle');
        const navMenu = document.getElementById('primaryNav');
        const overlay = document.getElementById('navOverlay');

        if (!menuToggle) return;

        if (position === 'static') {
            // Static mode: menu button is part of normal flow, always visible at top
            // Use setProperty with 'important' to override CSS stylesheet rules
            menuToggle.style.setProperty('position', 'relative', 'important');
            menuToggle.style.setProperty('top', 'auto', 'important');
            menuToggle.style.setProperty('right', 'auto', 'important');
            menuToggle.style.setProperty('margin', '10px', 'important');
            menuToggle.style.setProperty('float', 'right', 'important');
            menuToggle.style.setProperty('z-index', '1050', 'important');

            // Add a container for the menu button if not already present
            let menuContainer = document.getElementById('menuContainer');
            if (!menuContainer) {
                menuContainer = document.createElement('div');
                menuContainer.id = 'menuContainer';
                menuContainer.style.cssText = 'position: sticky; top: 0; background: white; z-index: 1050; padding: 10px 15px; border-bottom: 1px solid #dee2e6; margin-bottom: 10px; overflow: hidden;';
                // Insert after the skip link or at the start of body
                const skipLink = document.querySelector('.skip-link');
                if (skipLink && skipLink.nextSibling) {
                    document.body.insertBefore(menuContainer, skipLink.nextSibling);
                } else {
                    document.body.insertBefore(menuContainer, document.body.firstChild);
                }
            }
            // Move the button into the container (overflow:hidden acts as clearfix)
            menuContainer.appendChild(menuToggle);
        } else {
            // Fixed mode (default): menu button is fixed in top-right corner
            menuToggle.style.setProperty('position', 'fixed', 'important');
            menuToggle.style.setProperty('top', '20px', 'important');
            menuToggle.style.setProperty('right', '20px', 'important');
            menuToggle.style.removeProperty('margin');
            menuToggle.style.removeProperty('float');

            // Remove container if it exists
            const menuContainer = document.getElementById('menuContainer');
            if (menuContainer) {
                // Move button back to body before removing container
                document.body.insertBefore(menuToggle, menuContainer);
                menuContainer.remove();
            }
        }

        console.log('[Navigation] Menu position applied:', position);
    }

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
     * Fetch configuration and apply settings
     */
    async function initNavigation() {
        try {
            const response = await fetch('/api/available-providers');
            if (!response.ok) {
                console.warn('[Navigation] Failed to fetch config, status:', response.status);
                return;
            }

            const data = await response.json();

            // Apply menu position
            if (data.config_defaults && data.config_defaults.menu_position) {
                applyMenuPosition(data.config_defaults.menu_position);
            }

            // Apply page visibility
            if (data.config_defaults && data.config_defaults.pages_visibility) {
                applyPageVisibility(data.config_defaults.pages_visibility);
            } else {
                console.warn('[Navigation] No pages_visibility in config');
            }
        } catch (error) {
            console.warn('[Navigation] Error fetching config:', error);
        }
    }

    // Expose applyMenuPosition globally for admin page to use
    window.applyMenuPosition = applyMenuPosition;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavigation);
    } else {
        // DOM is already ready, run immediately
        initNavigation();
    }
})();
