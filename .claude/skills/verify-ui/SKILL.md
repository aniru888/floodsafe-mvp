---
name: verify-ui
description: Visual verification of frontend UI using Claude-in-Chrome browser automation. Takes screenshots of all screens at desktop and mobile viewports.
disable-model-invocation: true
user-invocable: true
---

# Visual UI Verification

Use Claude-in-Chrome browser automation to visually verify the FloodSafe frontend.

## Prerequisites
- Frontend dev server running on `http://localhost:5175`
- Chrome browser open

## Steps

### 1. Setup
- Load Claude-in-Chrome tools via ToolSearch if not already loaded
- Call `tabs_context_mcp` to see current browser state
- Create a new tab with `tabs_create_mcp`

### 2. Desktop Screenshots (1400x900)
Navigate to `http://localhost:5175` and screenshot each screen:

1. **Login Screen** — `http://localhost:5175` (when logged out)
2. **Home Screen** — main dashboard after login
3. **Flood Atlas** — map view
4. **Alerts** — alerts tab
5. **Profile** — profile/settings
6. **Report** — report submission flow (first step)

Use `read_page` to check for accessibility issues on each screen.

### 3. Mobile Screenshots (375x812)
- Use `resize_window` to set viewport to 375x812
- Re-screenshot Home, Atlas, and Alerts screens
- Check for overflow, hidden elements, navigation usability

### 4. Console Check
- Use `read_console_messages` to check for errors/warnings
- Report any console errors found

### 5. Report
Provide a summary:
- ✅/❌ Each screen renders correctly
- ✅/❌ Mobile responsive
- ✅/❌ Console clean (no errors)
- List any visual issues found with descriptions
