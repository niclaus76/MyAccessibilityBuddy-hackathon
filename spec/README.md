# My Accessibility Buddy - Specifications

This directory contains detailed specifications for all pages of the My Accessibility Buddy web application.

## Specification Files

### Core Application Pages
1. **[home.md](home.md)** - Landing page with tool navigation
2. **[webmaster.md](webmaster.md)** - AI-powered alt-text generation tool
3. **[accessibility-compliance.md](accessibility-compliance.md)** - Web page alt-text compliance checker
4. **[prompt-optimization.md](prompt-optimization.md)** - Batch prompt comparison tool for AI engineers
5. **[remediation.md](remediation.md)** - Accessibility issue remediation tool
6. **[admin.md](admin.md)** - Administration and configuration page

### Shared Resources
7. **[shared-components.md](shared-components.md)** - Reusable components, technical requirements, and implementation guidelines

## File Structure Overview

```
My Accessibility Buddy/
├── home.html (NEW)                    → Main landing page
├── webmaster.html (RENAMED)      → Alt-text generation tool
├── accessibility-compliance.html (NEW) → Compliance checking tool
├── prompt-optimization.html (NEW)      → Batch prompt testing tool
├── remediation.html (NEW)         → Issue remediation tool
└── admin.html (NEW)                    → Administration panel
```

## Configuration Files Referenced

The specifications reference the following configuration files:
- `backend/config/config.json` - Main configuration (AI models, providers, basic settings)
- `backend/config/config.advanced.json` - Advanced configuration (folders, testing, training)

## Key Features by Page

### 1. Home Page (home.md)
- 2×2 grid of tool cards with images
- Responsive design (mobile/tablet/desktop)
- Burger menu navigation
- Footer with disclaimer

### 2. Webmaster Tool (webmaster.md)
- Current `home.html` functionality
- Image upload with context
- AI alt-text generation
- Multilingual support (24 EU languages)
- Basic/Advanced processing modes

### 3. Accessibility Compliance (accessibility-compliance.md)
- URL-based web page analysis
- Image detection (img tags, CSS backgrounds, SVG, picture elements)
- Alt-text quality assessment
- WCAG 2.2 compliance checking
- Batch AI suggestion generation
- Detailed reports (PDF, Excel, CSV, JSON, HTML)
- Integration with remediation tool

### 4. Prompt Optimization (prompt-optimization.md)
- Batch prompt comparison testing
- Multiple prompt variants (up to 10)
- Test dataset management (upload or predefined sets)
- Statistical analysis and visualizations
- AI-generated insights and recommendations
- Export results in multiple formats
- Prompt template library

### 5. Remediation Tool (remediation.md)
- Placeholder for future implementation
- AI-assisted accessibility issue fixing
- Before/after previews
- Batch remediation capabilities

### 6. Administration (admin.md)
- AI model and provider configuration
- API key management with health checks
- Default preferences and settings
- Report template customization
- Advanced settings (performance, caching, logging)
- System information and diagnostics
- Configuration import/export
- **All settings load from config.json as factory defaults**
- **Real-time health checks for all APIs (🟢 green = OK, 🔴 red = error)**

## Shared Components (shared-components.md)

- Burger menu (navigation)
- Footer (testing disclaimer)
- Browser support matrix
- Technical requirements
- Implementation phases
- Assets inventory
- Content guidelines
- Acceptance criteria

## Design Principles

### Consistency
- All pages use Bootstrap Italia 2.8.2 framework
- Consistent color scheme (#0066cc primary, #17324d secondary)
- Uniform header/footer across all pages
- Shared navigation pattern (burger menu)

### Accessibility
- WCAG 2.2 Level AA compliance required
- Keyboard navigation support
- Screen reader compatibility
- Proper ARIA labels and semantic HTML
- Color contrast requirements met

### Responsive Design
- Mobile-first approach
- Breakpoints: Mobile (<768px), Tablet (768-1024px), Desktop (>1024px)
- Touch targets minimum 44×44px
- Flexible layouts with Bootstrap grid system

### Factory Defaults & Configuration
- All default values loaded from `config.json` and `config.advanced.json`
- User changes saved to separate `config.user.json` (preserves factory defaults)
- Configuration can be reset to factory defaults
- Export/import functionality for configuration backup

### Health Monitoring
- Real-time provider health checks in Administration page
- Visual indicators: 🟢 Green (OK), 🔴 Red (Error), 🟠 Orange (Warning), ⚪ Gray (Disabled)
- Latency measurements for each provider
- Model availability verification
- OAuth2 token expiration tracking (ECB-LLM)

## Implementation Notes

1. **Phase 1**: Core structure (home page, rename webmaster tool, add navigation)
2. **Phase 2**: Placeholder pages (compliance, optimization, remediation)
3. **Phase 3**: Full implementations of placeholder pages
4. **Phase 4**: Styling, polish, and accessibility testing

## Version History

- **v1.0** (2026-01-04): Initial specification split into modular files
  - Added comprehensive health checks for all APIs
  - Integrated config.json as factory defaults
  - Detailed Administration tool specification
  - Complete Batch Prompt Comparison Tool specification
  - Complete Accessibility Compliance Tool specification

## Related Documentation

- Main specification (legacy): `new-page-structure.md`
- Backend API documentation: (TBD)
- Frontend component library: Bootstrap Italia 2.8.2
- Configuration schema: See admin.md section 6.4.4

---

**Last Updated**: 2026-01-04
**Status**: Ready for Implementation
