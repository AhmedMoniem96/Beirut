from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _find_method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} not found")


def _calls_name(fn: ast.FunctionDef, name: str) -> bool:
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id == name:
                return True
            if isinstance(n.func, ast.Attribute) and n.func.attr == name:
                return True
    return False


def test_label_mode_gate_is_explicit_and_manual():
    src = _read("beirut_pos/apps/jewelry/ui/tabs/inventory_tab.py")
    tree = ast.parse(src)
    fn = _find_method(tree, "InventoryTab", "_ensure_printer_mode_for_labels")

    assert "Switch to Label Mode to print labels" in src
    assert _calls_name(fn, "set_printer_mode"), "Mode switch must be explicit via set_printer_mode"
    assert "QMessageBox.question" in src, "Must request confirmation before switching to label mode"


def test_receipt_mode_gate_is_explicit_and_manual():
    src = _read("beirut_pos/apps/jewelry/ui/tabs/invoice_tab.py")
    tree = ast.parse(src)
    fn = _find_method(tree, "InvoiceTab", "_ensure_printer_mode_for_receipt")

    assert "Switch to Receipt Mode to print receipts" in src
    assert _calls_name(fn, "set_printer_mode"), "Mode switch must be explicit via set_printer_mode"
    assert "QMessageBox.question" in src, "Must request confirmation before switching to receipt mode"


def test_receipt_and_label_renderers_are_separate():
    barcode_src = _read("beirut_pos/apps/jewelry/services/barcode_printer.py")
    receipt_src = _read("beirut_pos/apps/jewelry/services/receipt.py")

    assert "def render_barcode_label_image" in barcode_src
    assert "build_receipt_text" in receipt_src
    assert "reportlab.graphics.barcode" in barcode_src
    assert "RECEIPT_WIDTH_CHARS" in receipt_src


def test_label_dimensions_are_calibrated_for_sticker_media():
    barcode_src = _read("beirut_pos/apps/jewelry/services/barcode_printer.py")

    assert "_QR_LABEL_WIDTH_MM = 38.0" in barcode_src
    assert "_QR_LABEL_HEIGHT_MM = 25.0" in barcode_src
    assert "barcode_label_width_mm" in barcode_src
    assert "barcode_label_height_mm" in barcode_src


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
