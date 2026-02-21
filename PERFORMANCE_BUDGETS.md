# Performance Budgets (Premium but Fast)

Targets for logged-in web experiences (dashboard, forms, admin):

- LCP: <= 2.5s (p75, mobile)
- INP: <= 200ms (p75)
- CLS: <= 0.10 (p75)

## Page-Level Budgets

- Initial HTML document: <= 70KB compressed
- Critical CSS loaded at first paint: <= 45KB compressed
- JS needed for first interaction: <= 120KB compressed
- Total image bytes above the fold: <= 180KB compressed

## Interaction Budgets

- Form step change render: <= 100ms
- Autosave response target: <= 800ms
- Dashboard filter/search response: <= 500ms (server + render)

## Guardrails

- Avoid adding render-blocking third-party scripts in logged-in pages.
- Prefer server-rendered HTML for core workflow pages.
- Keep animations transform/opacity-only where possible.
- Use skeletons/empty states instead of blocking spinners.

## Tracking Plan

- Measure LCP/CLS/INP on:
  - `/intake/my-submissions/`
  - `/intake/`
  - `/intake/homemade-questionnaire/`
  - `/appointments/`
  - `/appointments/admin/dashboard/`
- Review monthly and before any major UI release.
