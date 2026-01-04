# Frontend Assets Fixes

## 1. Bootstrap Italia SVG Sprites Fix

### Problem

The application was returning **403 Forbidden** errors when trying to load SVG sprite icons:

```
Request URL: https://d2nuwzlynr0xpz.cloudfront.net/bootstrap-italia/dist/svg/sprites.svg
Status: 403 Forbidden
x-cache: Error from cloudfront
```

## Root Cause

The HTML/JS files were referencing Bootstrap Italia SVG sprites from a **local path** that doesn't exist:

```html
<!-- ❌ WRONG - Local path that doesn't exist -->
<use href="/bootstrap-italia/dist/svg/sprites.svg#it-copy"></use>
```

However, the Bootstrap Italia CSS was being loaded from **CDN**:

```html
<!-- ✅ CORRECT - CDN -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap-italia@2.8.2/dist/css/bootstrap-italia.min.css" rel="stylesheet">
```

This mismatch caused the issue.

## Solution

Updated all SVG sprite references to use the **same CDN** as the CSS:

```html
<!-- ✅ FIXED - CDN -->
<use href="https://cdn.jsdelivr.net/npm/bootstrap-italia@2.8.2/dist/svg/sprites.svg#it-copy"></use>
```

## Files Changed

1. **[frontend/home.html](../frontend/home.html)** - 2 occurrences fixed
2. **[frontend/app.js](../frontend/app.js)** - 1 occurrence fixed

## Files Affected

- `frontend/home.html` (lines 285, 334)
- `frontend/app.js` (line 485)

All references to `/bootstrap-italia/dist/svg/sprites.svg` have been changed to:
`https://cdn.jsdelivr.net/npm/bootstrap-italia@2.8.2/dist/svg/sprites.svg`

## Icons Fixed

The following SVG icons are now working:
- ✅ **Delete icon** (`#it-delete`) - Used in history buttons
- ✅ **Copy icon** (`#it-copy`) - Used in copy alt text buttons

## Deployment

### Option 1: Quick Frontend Update (Recommended)

Use the quick update script to deploy only frontend changes:

```bash
./tools/quick_frontend_update.sh
```

This script will:
1. Sync frontend files to S3
2. Invalidate CloudFront cache
3. Take ~5-15 minutes for cache to clear

### Option 2: Full Deployment

Use the full deployment script:

```bash
# Normal mode (with testing)
./tools/deploy_vm_to_aws.sh

# Fast mode (skip testing)
./tools/deploy_vm_to_aws.sh --fast
```

## Testing

After deployment and cache invalidation:

1. **Visit your CloudFront URL**
2. **Check browser console** - No more 403 errors
3. **Verify icons appear** in:
   - History item delete buttons (trash icon)
   - Alt text copy buttons (copy icon)

## Alternative: Self-Hosted Bootstrap Italia

If you prefer to self-host Bootstrap Italia instead of using CDN:

1. **Download Bootstrap Italia**:
   ```bash
   cd frontend
   npm install bootstrap-italia
   # or download from: https://github.com/italia/bootstrap-italia/releases
   ```

2. **Copy to frontend**:
   ```bash
   mkdir -p bootstrap-italia/dist
   cp -r node_modules/bootstrap-italia/dist/* bootstrap-italia/dist/
   ```

3. **Update HTML** to use local paths:
   ```html
   <link href="/bootstrap-italia/dist/css/bootstrap-italia.min.css" rel="stylesheet">
   <use href="/bootstrap-italia/dist/svg/sprites.svg#it-copy"></use>
   ```

4. **Deploy** to S3 (includes bootstrap-italia folder)

## Benefits of CDN Approach (Current Solution)

✅ **No extra files** - Reduces S3 storage and transfer costs
✅ **Faster loading** - CDN is globally distributed
✅ **Automatic updates** - Version pinned but easily updatable
✅ **No maintenance** - Don't need to manage Bootstrap Italia files
✅ **Better caching** - Users may already have CDN files cached from other sites

## Verification

After deployment, you can verify the fix by:

1. **Check Network Tab**:
   ```
   https://cdn.jsdelivr.net/npm/bootstrap-italia@2.8.2/dist/svg/sprites.svg
   Status: 200 OK
   ```

2. **Verify SVG loads**:
   ```bash
   curl -I "https://cdn.jsdelivr.net/npm/bootstrap-italia@2.8.2/dist/svg/sprites.svg"
   # Should return: HTTP/2 200
   ```

3. **Test icons visually** - Icons should appear in the UI

## Related Files

- Deployment script: [tools/deploy_vm_to_aws.sh](../tools/deploy_vm_to_aws.sh)
- Quick update script: [tools/quick_frontend_update.sh](../tools/quick_frontend_update.sh)
- Frontend files: [frontend/](../frontend/)

## 2. Favicon Fix

### Problem

The application had no favicon configured, resulting in:
- Browser errors trying to load `/favicon.ico`
- No icon in browser tabs
- Poor brand recognition
- Missing PWA icons for mobile devices

### Solution

Generated a complete set of favicons from the existing logo (`Buddy-Logo_no_text.png`) and configured them properly in the HTML.

### Files Created

**Favicon Images:**
- `frontend/assets/favicon.ico` (935 bytes) - Multi-size ICO file (16x16, 32x32, 48x48)
- `frontend/assets/favicon-16x16.png` (913 bytes) - Standard small favicon
- `frontend/assets/favicon-32x32.png` (2.8KB) - Standard favicon
- `frontend/assets/apple-touch-icon.png` (38KB) - iOS home screen icon (180x180)
- `frontend/assets/android-chrome-192x192.png` (42KB) - Android icon
- `frontend/assets/android-chrome-512x512.png` (294KB) - Android high-res icon

**Configuration Files:**
- `frontend/site.webmanifest` - PWA manifest for Android/Chrome
- `frontend/browserconfig.xml` - Windows tile configuration

### HTML Changes

Added to `frontend/home.html`:

```html
<!-- Meta tags -->
<meta name="description" content="AI tool for creating WCAG 2.2-compliant alt text...">
<meta name="theme-color" content="#0066cc">
<meta name="msapplication-TileColor" content="#0066cc">

<!-- Favicons -->
<link rel="icon" type="image/x-icon" href="assets/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="assets/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="assets/apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
```

### Benefits

✅ **Professional appearance** - Branded icon in browser tabs
✅ **Better UX** - Easy to identify among multiple tabs
✅ **PWA support** - Can be added to home screen on mobile
✅ **Cross-platform** - Works on all browsers and devices
✅ **SEO improvement** - Meta description added
✅ **Accessibility** - Theme colors for better mobile experience

## Date Fixed

2026-01-03

## Status

✅ **RESOLVED** - All issues fixed:
- SVG sprite references updated to use CDN
- Complete favicon set generated and configured
- PWA manifest and browserconfig added
- Meta tags optimized
