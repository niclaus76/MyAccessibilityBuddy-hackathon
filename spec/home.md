# Home Page Specification - My Accessibility Buddy

## Overview
This specification defines the requirements for creating a new landing page (home.html) that serves as the main entry point to the My Accessibility Buddy application suite, along with new specialized tool pages.

## File Structure Changes

### Pages to Create
1. **home.html** - New landing page with tool navigation (NEW)
2. **webmaster.html** - Renamed from current home.html
3. **accessibility-compliance.html** - New compliance checking tool page
4. **prompt-optimization.html** - New prompt optimization tool page
5. **remediation.html** - New remediation tool page
6. **admin.html** - New administrative tool page

### File Renaming
- Current `home.html` → `webmaster.html`

## 1. New Home Page (home.html)

### 1.1 Page Header
- **Title**: "My Accessibility Buddy"
- **Logo**: Use existing `assets/Buddy-Logo_no_text.png` (96px × 96px)
- **Favicon**: Use existing favicon assets
- **Meta Tags**:
  - Description: "My Accessibility Buddy - Suite of AI-powered accessibility tools for WCAG 2.2 compliance"
  - Theme color: #0066cc
  - Viewport configuration for responsive design
  - Cache control headers

### 1.2 Page Structure

#### Header Section
- Centered layout with logo
- Title: "My Accessibility Buddy" (h1, font-size: 2rem)
- Subtitle/description: Brief introduction to the tool suite (e.g., "AI-Powered Accessibility Tools Suite")
- Skip to main content link for accessibility

#### Main Content Section
The main section contains a grid of four clickable tool cards, each with:
- Tool image (clickable)
- Tool title
- Brief description
- Clear visual affordance (hover effects)

##### Tool Cards Grid Layout
**Layout**: 2×2 responsive grid
- Desktop: 2 columns
- Tablet: 2 columns
- Mobile: 1 column (stacked)

##### Tool Card 1: Webmaster Tool
- **Image**: `assets/webmaster-tool-button.png`
- **Title**: "Webmaster Tool"
- **Description**: "AI tool for creating WCAG 2.2-compliant alt text. Upload an image, provide context, and get accessible alt text."
- **Link**: `webmaster.html`
- **Alt Text**: "Webmaster tool - AI-powered alt text generator"

##### Tool Card 2: Accessibility Compliance
- **Image**: `assets/accessibility-compliance.png`
- **Title**: "Accessibility Compliance"
- **Description**: "Check your web page for WCAG 2.2 alternative text compliance and get detailed accessibility reports."
- **Link**: `accessibility-compliance.html`
- **Alt Text**: "Alternative text compliance checker"

##### Tool Card 3: Prompt Optimization
- **Image**: `assets/prompt-optimization-tool.png`
- **Title**: "Prompt Optimization"
- **Description**: "Optimize your AI prompts for better accessibility-focused results and improved performance."
- **Link**: `prompt-optimization.html`
- **Alt Text**: "Prompt optimization tool"

##### Tool Card 4: Remediation Tool
- **Image**: `assets/remediation-tool.png`
- **Title**: "Remediation Tool"
- **Description**: "Identify and fix accessibility issues with AI-powered suggestions and automated corrections."
- **Link**: `remediation.html`
- **Alt Text**: "Accessibility remediation tool"

##### Tool Card 5: Admin Tool
- **Image**: `assets/admin-tool.png`
- **Title**: "Administration Tool"
- **Description**: "Configuration parameters and administrative tools for My Accessibility Buddy."
- **Link**: `admin-tool.html`
- **Alt Text**: "Administration tool"

#### Navigation (Burger Menu)
- **Position**: Top right corner
- **Type**: Hamburger menu icon (☰)
- **Behavior**:
  - Toggles navigation menu overlay/sidebar
  - Accessible via keyboard (Tab, Enter)
  - ARIA labels for screen readers
- **Menu Items**:
  - Home
  - Webmaster Tool
  - Accessibility Compliance
  - Prompt Optimization
  - Remediation Tool
  - Administration Tool
  - About (optional)
  - Help (optional)

### 1.3 Footer Section
**Content**: Testing disclaimer (centered)
```
For testing purposes only (bold)
Use with non-confidential images. Avoid uploading personal or sensitive data. AI suggestions require human review before use.
```

**Styling**:
- Background: Light gray (#f8f9fa)
- Border-top: 1px solid #dee2e6
- Padding: Vertical 1rem, horizontal responsive
- Text: Muted color (#6c757d)
- Font size: Small (0.875rem)

### 1.4 Styling & Framework
- **CSS Framework**: Bootstrap Italia 2.8.2 (via CDN)
- **Custom CSS**: `styles.css` (existing file)
- **Color Scheme**:
  - Primary: #0066cc (existing brand color)
  - Secondary: #17324d
  - Background: #ffffff
  - Card backgrounds: #f0f6fc or light variants
- **Card Styling**:
  - Shadow: subtle box-shadow
  - Border-radius: 8px
  - Hover effect: scale(1.05) and enhanced shadow
  - Transition: all 0.3s ease
  - Padding: 1.5rem

### 1.5 Accessibility Requirements
- **WCAG 2.2 Level AA Compliance**
- Skip to main content link
- Semantic HTML5 structure (header, nav, main, footer)
- Proper heading hierarchy (h1 → h2 → h3)
- Keyboard navigation support for all interactive elements
- Focus indicators visible and clear
- ARIA labels for all interactive elements
- Alt text for all images
- Color contrast ratios meet WCAG AA standards (4.5:1 for normal text)
- Touch targets minimum 44×44 px for mobile
- Screen reader announcements for dynamic content

### 1.6 Responsive Behavior
- **Mobile (< 768px)**:
  - Single column layout
  - Tool cards stacked vertically
  - Full-width cards
  - Burger menu icon visible

- **Tablet (768px - 1024px)**:
  - 2-column grid
  - Adjusted padding and spacing

- **Desktop (> 1024px)**:
  - 2-column grid with max-width container (960px)
  - Optimal spacing and card sizes

### 1.7 JavaScript Requirements
- Burger menu toggle functionality
- Smooth scrolling (optional)
- Keyboard event handlers for menu navigation
- Focus management for menu open/close
- No dependencies on external JS beyond Bootstrap Italia

---

