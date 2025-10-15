"""Generate offline activation vouchers for Beirut POS."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from beirut_pos.core.simple_voucher import generate_many, validate_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate voucher codes for Beirut POS.")
    parser.add_argument(
        "count",
        type=int,
        help="عدد القسائم المطلوب إنشاؤها.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="المجلد الذي سيتم حفظ الملف فيه (الافتراضي: المجلد الحالي).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    count = max(0, args.count)
    codes = generate_many(count)
    if not validate_batch(codes):
        raise SystemExit("فشل التحقق من القسائم المولدة.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    output_dir: Path = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"vouchers-{timestamp}.txt"

    with file_path.open("w", encoding="utf-8") as handle:
        for code in codes:
            handle.write(f"{code}\n")

    print(f"Generated {len(codes)} vouchers → {file_path}")


if __name__ == "__main__":
    main()
