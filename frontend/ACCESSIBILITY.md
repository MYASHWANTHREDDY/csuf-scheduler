# CSUF Scheduler Accessibility Checklist (Phase 2)

## Semantics & Labels
- [x] Primary app regions separated by semantic sections.
- [x] Inputs in login/create forms include descriptive placeholders.
- [x] Buttons and actionable links use meaningful text labels.
- [x] Modal dialogs use `role="dialog"` and `aria-modal="true"`.

## Keyboard & Focus
- [x] Navigation tabs are focusable buttons.
- [x] Default browser tab order is preserved.
- [x] Focus-visible ring styles added for buttons, links, and form fields.
- [ ] Add automated keyboard trap checks for all modal workflows.

## Color & Contrast
- [x] Primary text color uses dark-on-light contrast.
- [x] Status colors mapped to high-contrast tones.
- [x] Avoid color-only meaning by pairing labels/messages.

## Forms & Validation
- [x] Required fields are explicit in form structure.
- [x] Error/success messages are announced via `aria-live` regions.
- [x] Loading/error/empty states use text plus visual treatment.

## Responsive & Readability
- [x] Mobile-first layout avoids horizontal overflow in core views.
- [x] Controls maintain touch-friendly sizes on small screens.
- [x] Body text keeps readable size at 14px+.

## Follow-ups
- [ ] Run axe/Lighthouse scan in CI for regression checks.
- [ ] Add skip-link for rapid keyboard navigation to main content.
- [ ] Add explicit `for` + `id` wiring for every dynamic form label/input pair.
