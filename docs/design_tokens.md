# Design tokens & component library

The UI now centralizes styling through design tokens under `beirut_pos/ui/theme/tokens.py` and a reusable component set in `beirut_pos/ui/theme/components.py`. Use these when building dialogs or widgets to keep spacing, colors, and typography consistent.

## Tokens
- **Colors** (`COLORS`): primary, primary_dark, on_primary, surface/surface_alt/surface_muted, text/text_muted, border, success, warning, danger, info.
- **Typography** (`TYPOGRAPHY`):
  - `display`: 28px / 800 weight for page titles.
  - `title`: 16px / 700 weight for section headers.
  - `body`: 13px / 600 weight for body text.
  - `caption`: 11px / 600 weight for hints.
- **Spacing** (`SPACING`): xxs=4, xs=8, sm=12, md=16, lg=24, xl=32, xxl=48. Use `md` for form spacing, `lg` for sections, and `xl` for page gutters.
- **Radii** (`RADII`): sm=8, md=12, lg=16, xl=22, pill=999.
- **Shadows** (`SHADOWS`): soft, raised, inset (usable with `QGraphicsDropShadowEffect`).

`typography_rule(role)` returns a ready-to-use QSS snippet for typography roles.

## Components
Import from `beirut_pos.ui.theme`:
- `DSButton`, `DSLinkButton` — variants: `primary` (default), `secondary`, `link`; sizes: `sm`, `md`, `lg`.
- `DSTextField` — padded text input that honors focus outlines and minimum width.
- `DSSelect` — styled `QComboBox` that pairs with the same tokens as inputs.
- `DSTable` — table with token-driven headers and row selection.
- `DSAlert` — inline banner with severities `info`, `success`, `warning`, `danger`.
- `DSTabWidget` — styled tabs aligned to the color palette.
- `DSModal` — base dialog shell with default palette and RTL support.
- `TokenDocBlock` — helper card for documentation/notes.
- `apply_typography(widget, role)` — apply a typography role to any label or text widget.
- `design_system_stylesheet(accent=None)` — inject the QSS for all components (accent overrides optional).

## Usage tips
- Prefer `DSButton`/`DSTextField` instead of raw Qt widgets. They inherit focus, hover, and disabled states from the tokens without inline styles.
- Set spacing and margins with `SPACING` constants instead of magic numbers.
- For section containers, set `frame.setObjectName("SectionCard")` to get the token card styling.
- Use `apply_typography(label, "title")` for headings and `apply_typography(label, "body")` for descriptions.
- When you need alerts or validation messages, show a `DSAlert` and adjust its severity via `set_severity()`.

See `StyleGuideDialog` from the toolbar to preview component states and tokens in context.
