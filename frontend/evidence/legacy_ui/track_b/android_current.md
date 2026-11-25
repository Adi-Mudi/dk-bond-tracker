# Android Current State & Architectural Capture

**Document**: `evidence/current/android_current.md`  
**Platform**: Android Native Shell (`com.dkbondtracker.app`)  
**Source Location**: `android/app/src/main/`  
**Date**: 2026-11-23

---

## 1. Android Native Architecture & Integration Points

The DK Bond Tracker Android application is an embedded hybrid client combining a native Java host activity with an embedded Python Flask runtime via Chaquopy, rendered through an Android `WebView`.

### 1.1 Core Components (`MainActivity.java`)
1. **Chaquopy Python Lifecycle**:
   - Spun up in a background thread `dkbt-py-start` during `onCreate()`.
   - Starts Python runtime (`Python.start(...)`), loads `main.py`, and invokes `start(filesDir)`.
   - Local Flask server listens on `127.0.0.1:5000`.
   - Initial placeholder rendered in WebView:
     ```html
     <html><body style='font-family:sans-serif'>DK Bond Tracker starting...</body></html>
     ```

2. **Hardware & Gesture Back Navigation**:
   - `onBackPressed()` intercepts user navigation:
     ```java
     webView.evaluateJavascript(
       "(function(){return window.closeTopOverlay ? window.closeTopOverlay() : false;})()",
       new ValueCallback<String>() { ... }
     );
     ```
   - If a modal, dialog, or tooltip overlay is open in the DOM, `window.closeTopOverlay()` returns `true` and suppresses default activity exit. If `false`, Android navigates back in browser history or exits.

3. **Export & Sharing Subsystem**:
   - WebView downloads are intercepted by `setDownloadListener`:
     ```java
     startExport(url, contentDisposition, mimeType);
     ```
   - Files are streamed to `getFilesDir() + "/exports/"`.
   - Dispatches native Android sharing via `Intent.ACTION_SEND` and `Intent.createChooser(...)` with content URI:
     `content://com.dkbondtracker.app.export/exports/<filename>`
   - Handled by `ExportProvider` extending Android's `FileProvider`.

4. **External vs Local URL Routing**:
   - `DKBTWebViewClient.shouldOverrideUrlLoading` restricts WebView rendering to `127.0.0.1` or `localhost`.
   - External links (e.g. GitHub update URLs, Google OAuth, NSE/BSE portals) are routed to external browsers via `Intent.ACTION_VIEW` (`FLAG_ACTIVITY_NEW_TASK`).

---

## 2. Current Android UI State & Ergonomic Assessment

1. **Viewport Constraints**:
   - Standard phone width is **360dp** (typical Android device: Samsung Galaxy, Google Pixel, Redmi).
   - Horizontal table widths (`min-width: 40rem` = 640px) break viewport bounds, forcing awkward horizontal scrolling.

2. **Touch Targets**:
   - Native bottom tabs (`.bottom-tabs`) have adequate height (`48px`), but inline table controls and action chips lack standard 48x48dp hit bounds.

3. **Visual Shell**:
   - Lacks an edge-to-edge Material 3 status bar and navigation bar inset management.
   - Initial cold boot displays unstyled black text on white background without theme awareness.
