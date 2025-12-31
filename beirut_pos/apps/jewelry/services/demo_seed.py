"""Seed demo data for Jewelry app."""

from __future__ import annotations

from .db import add_payment_method, save_product


def seed_demo_data() -> None:
    sample_products = [
        ("خاتم كريستال", "Crystal Ring", "CR-001", 250.0, 10, 2, "Rings", True, "Crystal", "Silver"),
        ("سوار يدوي", "Handmade Bracelet", "HB-002", 180.0, 15, 3, "Bracelets", True, "Pearl", "Gold"),
        ("قلادة حجر", "Stone Necklace", "SN-003", 320.0, 8, 2, "Necklaces", True, "Stone", "Rose"),
        ("أقراط لؤلؤ", "Pearl Earrings", "PE-004", 150.0, 6, 2, "Earrings", True, "Pearl", "White"),
    ]
    for data in sample_products:
        save_product(
            None,
            data[0],
            data[1],
            data[2],
            "",
            "",
            data[3],
            data[4],
            data[5],
            data[6],
            data[7],
            data[8],
            data[9],
        )

    add_payment_method("بطاقة", "Card")
