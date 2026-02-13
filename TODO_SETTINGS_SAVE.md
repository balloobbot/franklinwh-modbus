# TODO: Fix Settings Menu Persistence

## Issue
Settings menu does not save user preferences properly.

## Context
- Likely broken when app settings for logging were added
- Settings changes are not persisting after closing the settings modal
- May be related to localStorage/backend sync issue

## Investigation Needed
- [ ] Check if settings modal save handler is calling the correct API endpoint
- [ ] Verify backend `/api/settings` endpoint is working
- [ ] Test localStorage persistence
- [ ] Check for JavaScript errors in console when saving
- [ ] Review settings modal code in `templates/base.html` or `templates/settings_modal.html`

## Expected Behavior
- User changes settings in modal
- Clicks "Save" button
- Settings persist across page reloads
- Settings sync to backend for multi-device support

## Related Files
- `templates/settings_modal.html` - Settings UI
- `src/web_server.py` - Settings API endpoints
- Frontend JavaScript - Save handler

## Priority
Medium - User can still use the app, but loses preferences on reload
