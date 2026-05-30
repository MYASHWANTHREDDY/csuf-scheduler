# Frontend (Phase 2 Scaffold)

This folder now contains a lightweight Vue + Vite component scaffold aligned to Phase 2 deliverables.

Flask integration status:

- `/` serves the main scheduler UI (`backend/app/templates/index.html`)
- `/frontend/...` serves frontend assets directly from this folder
- `/app-vue` serves the Vue host page (`backend/app/templates/vue_app.html`) for component-library preview

## Includes

- Reusable components in `src/components/`
  - `Button.vue`
  - `Alert.vue`
  - `Navbar.vue`
  - `FormField.vue`
  - `DataTable.vue`
  - `Modal.vue`
- Responsive base styles in `src/styles/main.css`
- Local preview entrypoint in `src/main.js`

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

This scaffold is intentionally decoupled from the existing Flask template UI so it can be iterated safely and migrated incrementally.
