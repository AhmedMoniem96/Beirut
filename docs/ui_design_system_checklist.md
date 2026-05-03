# UI Design System Checklist (High-Traffic Screens)

Use this checklist for dense forms/tables in Jewelry and Playstation apps.

## Tokens first
- Use app theme tokens as source of truth for spacing, typography, control heights, and table metrics.
- Avoid hardcoded pixel values when equivalent token exists.

## Forms
- Keep label alignment consistent (left-aligned labels, vertically centered with fields).
- Use shared field widths/heights from control tokens.
- Use helper text styling for hints/validation (muted/default, danger on errors).
- Keep related optional fields in grouped panels with tokenized spacing.

## Tables
- Use themed table component where available (`DSTable` in Playstation).
- Standardize row/header height from table tokens.
- Use row selection style from theme; avoid per-screen custom colors.
- Provide consistent empty-state messaging in table area.
- Keep export actions in controls row and aligned consistently.

## Review before merge
- Check at least one high-traffic view in each app (invoice/reporting/main admin surface).
- Confirm no new one-off `setSpacing(...)`, `setMinimumWidth(...)`, or stylesheet sizing was introduced without token mapping.
