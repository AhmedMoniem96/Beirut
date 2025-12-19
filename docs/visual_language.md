# Visual language & identity system

This page documents the extended brand layer that sits on top of the design tokens and components.
It captures how to apply the Beirut POS logo lockup, iconography, imagery, and micro-interactions
so every screen feels coherent.

## Logo lockup
- **Structure:** Icon + stacked wordmark/tagline contained in a rounded card with an 8px clear-space buffer.
- **Sizing:** Preferred height `40px` (resizes smoothly down to `28px` in tight toolbars).
- **Color:** Accent color on the icon silhouette, on-surface text for the wordmark, and muted text for the tagline.
- **Usage:** Call `LogoLockup` (from `beirut_pos.ui.theme`) and feed it `get_logo_pixmap()`; it auto-hides the icon if
  a custom logo is not configured.

## Icon set
- **Source:** Consolidated under `beirut_pos.ui.theme.brand.ICON_SET` with `resolve_icon(style, key)` helpers.
- **Style:** Qt standard glyphs that share the same stroke weight to avoid mixed icon families.
- **Mapping:** Tables (`SP_FileDialogDetailedView`), Reservations (`SP_DialogYesButton`), Inventory (`SP_DriveHDIcon`),
  Reports (`SP_FileDialogInfoView`), Purchases (`SP_FileDialogListView`), Tables Admin (`SP_DesktopIcon`),
  Settings (`SP_FileDialogDetailedView`), Recovery (`SP_DialogResetButton`).
- **Sizing:** Default to `20px` square with `md` padding on the nav rail for breathing room.

## Illustration & imagery
- **Treatment:** Muted grain overlays on dark walnut surfaces with subtle brass glows to echo the accent color.
- **Subjects:** Coffee craft, table service, ticket-like cards with rounded corners.
- **Placement:** Prefer full-bleed hero backgrounds (login) and small spot illustrations on empty states; avoid dense collages.
- **Contrast:** Keep copy readable by pairing illustrations with the surface color tokens and an inset shadow.

## Micro-interactions
- **Buttons:** Animated elevation on hover/press via `DSButton` (shadow grows on hover, compresses on press).
- **Toasts:** `DSAlert(animated=True)` fades and expands in/out; `InlineToast` adds a soft shadow to lift messages off forms.
- **Tooltips:** App-wide wake delay set to ~350ms with a gentle fall-asleep delay for readability.
- **Dividers & whitespace:** Use `DSDivider` and the updated `SectionCard` padding to create breathing room between blocks.
