# CSUF Scheduler Design System

## Principles
- Clarity first: scheduling data is readable at a glance.
- Fast actions: common flows use high-contrast primary actions.
- Consistency: spacing, typography, and states remain predictable.
- Accessibility: keyboard-friendly controls and visible focus states.

## Color Tokens
- Primary: `#1d4ed8`
- Primary Hover: `#1e40af`
- Surface: `#ffffff`
- Surface Alt: `#f8fafc`
- Border: `#dbe2ea`
- Text Primary: `#0f172a`
- Text Secondary: `#475569`
- Success: `#15803d`
- Danger: `#dc2626`
- Warning: `#d97706`
- Info: `#2563eb`

## Typography
- Font Stack: `Inter, Segoe UI, Arial, sans-serif`
- Page Title: `32px / 700`
- Section Title: `20px / 700`
- Card Title: `16px / 600`
- Body Text: `14px / 400`
- Meta Text: `12px / 500`

## Spacing & Radius
- `xs`: 4px
- `sm`: 8px
- `md`: 12px
- `lg`: 16px
- `xl`: 24px
- Radius small: 8px
- Radius medium: 12px
- Radius large: 16px

## Component Standards
- Buttons: primary, secondary, danger; disabled state uses reduced contrast.
- Forms: labels above inputs; inline helper/error text below control.
- Cards: optional header/body/footer with consistent padding.
- Tables: sticky headers, striped rows, mobile overflow support.
- Alerts/Toasts: success, info, warning, error variants.
- Navigation: top tab bar with active state and keyboard focus ring.

## States
- Loading: lightweight spinner with context label.
- Empty: short explanation + next action hint.
- Error: persistent message + retry action.
- Success: auto-dismissing toast (3s).

## Responsive Breakpoints
- Mobile: `< 768px`
- Tablet: `768px - 1023px`
- Desktop: `>= 1024px`

## Accessibility Baseline
- Minimum tap target: 44x44 px.
- Text contrast target: 4.5:1 or better.
- All interactive elements keyboard reachable.
- Visible focus indicator on inputs, links, and buttons.
