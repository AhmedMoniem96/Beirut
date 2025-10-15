# Catalog & Order Screen Updates

This release refreshes the ordering workflow and adds an in-app catalog manager.

## Order screen

- The right-hand order panel is taller and more compact so at least six line items remain
  visible on a 1366×768 display without scrolling.
- The application now opens maximised by default to make better use of available space.
- PlayStation controls continue to appear on the left, while totals and payment actions
  stay anchored at the bottom of the screen.
- Cashiers can double-click an order line (or use **تعديل المحدد**) to adjust the
  quantity or note without removing and re-adding the item. Stock checks still run during
  edits, and the list refreshes immediately after the change.

## Managing the catalog

- Admins can open **إدارة الأصناف (مدير)** to launch the new catalog manager dialog.
- The left list shows all categories. Use **إضافة…**, **تعديل…**, or **حذف** to manage
  sections. The **⬆ أعلى** and **⬇ أسفل** buttons persist the display order.
- Selecting a category loads its products on the right. Products can be added, edited,
  deleted, or reordered without leaving the dialog. Each product includes toggles for
  **تتبع المخزون** and **يدعم خيارات مخصصة** plus editable stock and alert thresholds.
- When a product is marked as customizable an options panel becomes available to manage
  add-on choices (labels, price deltas, and order). Options can be added, edited,
  reordered, or removed with confirmation prompts.
- Changes are applied immediately and broadcast through the app, so open order screens
  refresh automatically.

When a customizable product with options is added to an order, the cashier is prompted
to pick an option before the item is queued. Any option notes (and coffee customizations)
are printed on the bar ticket and remain editable from the order window.

New installations start with an empty catalog. Administrators can populate sections and
products directly from the dialog without editing the database manually.
