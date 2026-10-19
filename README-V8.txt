IBP Pipeline Explorer V8 — local editor + GitHub Pages read-only viewer

1. BACK UP YOUR LAYOUT using Export JSON in the local editor.
2. Install V8 in your existing ibp-visualizer folder (keep Vite and localStorage).
3. Copy your exported JSON into src/published-layout.json.
4. Choose the GitHub repo name ibp-pipeline (otherwise update base in vite.config.js).
5. npm.cmd install; npm.cmd run build:public
6. Push the visualizer source to a GitHub repository; enable Settings > Pages > GitHub Actions.

The public site reads src/published-layout.json, never browser localStorage, and hides editing controls.
Local npm.cmd run dev retains the full editable application and previous saved layout.
