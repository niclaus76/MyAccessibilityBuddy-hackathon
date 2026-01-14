# Button Debugging Guide - Accessibility Compliance Tool

## Issue
The Stop and Clear buttons in accessibility-compliance.html are not working as expected.

## Changes Made

### 1. Added Comprehensive Console Logging

**File: [frontend/accessibility-compliance.js](frontend/accessibility-compliance.js)**

#### Initialization Logging (Lines 73-81)
```javascript
function init() {
    console.log('[COMPLIANCE] Initializing...');
    console.log('[COMPLIANCE] clearBtn:', clearBtn);
    console.log('[COMPLIANCE] stopAnalysisBtn:', stopAnalysisBtn);
    console.log('[COMPLIANCE] generateBtn:', generateBtn);
    setupEventListeners();
    initializeBootstrapTooltips();
    loadAvailableProviders();
}
```

#### Event Listener Logging (Lines 250-270)
- Added console logs for ALL button clicks:
  - Generate button
  - Stop button
  - Clear button
  - Download button

#### Function Execution Logging
- **clearForm()** - Lines 390-428: Logs when called, session ID, and completion
- **stopAnalysis()** - Lines 655-682: Logs when called, abort controller state, and completion
- **downloadReport()** - Lines 717-753: Already had comprehensive logging

### 2. Improved Error Handling

- Added try-catch blocks in stopAnalysis() for session clearing
- Better error messages with screen reader announcements

## How to Debug

### Step 1: Check Console Logs on Page Load

1. Open accessibility-compliance.html in browser
2. Open Developer Tools (F12)
3. Go to Console tab
4. Look for these messages:
   ```
   [COMPLIANCE] Initializing...
   [COMPLIANCE] clearBtn: <button>...</button>
   [COMPLIANCE] stopAnalysisBtn: <button>...</button>
   [COMPLIANCE] generateBtn: <button>...</button>
   ```

**If buttons are `null`:**
- DOM elements are not being found
- Check that IDs match in HTML: `stopAnalysisBtn`, `clearBtn`, `generateBtn`
- Check that script is loaded AFTER the HTML body

### Step 2: Test Button Clicks

1. Click the **Clear** button
2. Look for console message: `[COMPLIANCE] Clear button clicked`
3. Then look for: `[COMPLIANCE] clearForm() called`

4. Start an analysis, then click the **Stop** button
5. Look for: `[COMPLIANCE] Stop button clicked`
6. Then: `[COMPLIANCE] stopAnalysis() called`

**If you see "clicked" but not the function call:**
- Event listener is attached but function has an error
- Check browser console for JavaScript errors

**If you don't see "clicked":**
- Event listener is not attached
- Check if `setupEventListeners()` is being called
- Check if buttons are disabled (check CSS or button state)

### Step 3: Check Button States

The buttons have different enabled/disabled states:

- **Clear button**: Should always be enabled
- **Stop button**: Only enabled during analysis (`setFormState(false)`)
- **Generate button**: Enabled when URL is valid

Check in browser console:
```javascript
// Check button states
document.getElementById('clearBtn').disabled  // Should be false
document.getElementById('stopAnalysisBtn').disabled  // Should be true when not analyzing
document.getElementById('generateBtn').disabled  // Depends on URL validation
```

### Step 4: Use Test Page

Open [test-buttons.html](test-buttons.html) to verify basic button functionality works in isolation.

## Common Issues and Solutions

### Issue 1: Buttons Not Responding to Clicks

**Symptoms:**
- No console log when clicking
- No visual feedback

**Possible Causes:**
1. **JavaScript Error Earlier**: Check console for errors before button setup
2. **Event Listener Not Attached**: `setupEventListeners()` not called or failed
3. **CSS Issue**: Button covered by another element (check z-index)
4. **Button Disabled**: Check `button.disabled` property

**Solution:**
```javascript
// In browser console, manually test:
const clearBtn = document.getElementById('clearBtn');
console.log('Button found:', clearBtn);
console.log('Button disabled:', clearBtn.disabled);
clearBtn.addEventListener('click', () => console.log('Manual listener works!'));
```

### Issue 2: Clear Button Does Nothing

**Symptoms:**
- See "Clear button clicked" log
- See "clearForm() called" log
- But form doesn't reset

**Possible Cause:**
- Function is running but encountering an error partway through

**Solution:**
Check console for errors in clearForm() execution. The function should log:
```
[COMPLIANCE] Clear button clicked
[COMPLIANCE] clearForm() called
[COMPLIANCE] currentSessionId: cli-xxx or null
[COMPLIANCE] Backend session data cleared (if session exists)
[COMPLIANCE] Form cleared successfully
```

### Issue 3: Stop Button Doesn't Work

**Symptoms:**
- Button appears disabled even during analysis
- Clicking does nothing

**Possible Cause:**
- `setFormState()` logic issue
- Button state not being updated correctly

**Solution:**
Check the `setFormState()` function at line 638. When analysis starts:
- `setFormState(false)` is called
- This should set `stopAnalysisBtn.disabled = false` (enabled)

Verify in console during analysis:
```javascript
document.getElementById('stopAnalysisBtn').disabled  // Should be false
```

## Testing Checklist

- [ ] Open Developer Tools Console
- [ ] Check initialization logs show all buttons found (not null)
- [ ] Click Clear button - verify console logs
- [ ] Enter a URL and click Generate
- [ ] During analysis, click Stop - verify console logs
- [ ] After analysis completes, click Download - verify console logs
- [ ] Check for any JavaScript errors in console

## Expected Console Output

### On Page Load:
```
[COMPLIANCE] Initializing...
[COMPLIANCE] clearBtn: button#clearBtn.btn.btn-danger.btn-lg.w-100
[COMPLIANCE] stopAnalysisBtn: button#stopAnalysisBtn.btn.btn-outline-warning.btn-lg.w-100.mb-2
[COMPLIANCE] generateBtn: button#generateBtn.btn.btn-primary.btn-lg.w-100.mb-2
[COMPLIANCE] Default providers set from config
```

### On Clear Button Click:
```
[COMPLIANCE] Clear button clicked
[COMPLIANCE] clearForm() called
[COMPLIANCE] currentSessionId: null (or cli-xxx if session exists)
[COMPLIANCE] Form cleared successfully
```

### During Analysis > Stop Button Click:
```
[COMPLIANCE] Stop button clicked
[COMPLIANCE] stopAnalysis() called
[COMPLIANCE] currentAbortController: AbortController {signal: AbortSignal, ...}
[COMPLIANCE] Aborted current request
[COMPLIANCE] Session data cleared after stop
[COMPLIANCE] Analysis stopped successfully
```

## Additional Debugging Commands

Run these in browser console:

```javascript
// Check if functions are defined
typeof clearForm  // Should be "function"
typeof stopAnalysis  // Should be "function"
typeof startAnalysis  // Should be "function"

// Check button references
document.getElementById('clearBtn')  // Should return button element
document.getElementById('stopAnalysisBtn')  // Should return button element

// Manually trigger functions
clearForm()  // Should clear the form
```

## Files Modified

1. **frontend/accessibility-compliance.js** - Added extensive logging
2. **frontend/accessibility-compliance.html** - Removed "View Report in New Tab" button
3. **backend/api.py** - Enhanced clear-session endpoint
4. **test-buttons.html** - Created test page for button debugging

## Next Steps

If buttons still don't work after following this guide:
1. Share the complete console output from page load to button click
2. Check Network tab for any failed API requests
3. Verify backend is running and accessible
4. Test with test-buttons.html to isolate the issue
