"""Generate offline activation vouchers for Beirut POS."""

from __future__ import annotations

import argparse
import inspect
from datetime import datetime
from pathlib import Path

# uses only functions your build exports
from beirut_pos.core.simple_voucher import generate_many, format_voucher


def fmt(raw: str, default_prefix: str = "BEIRUT") -> str:
    """
    Wrap format_voucher() regardless of signature:
    - Some builds: format_voucher(raw, prefix)
    - Others:      format_voucher(raw)  # prefix internal/default
    """
    sig = inspect.signature(format_voucher)
    if len(sig.parameters) == 2:
        return format_voucher(raw, default_prefix)  # (raw, prefix)
    return format_voucher(raw)  # (raw)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate voucher codes for Beirut POS.")
    p.add_argument("count", type=int, help="عدد القسائم المطلوب إنشاؤها.")
    p.add_argument("--output-dir", type=Path, default=Path.cwd(),
                   help="المجلد الذي سيتم حفظ الملف فيه (الافتراضي: المجلد الحالي).")
    p.add_argument("--prefix", default="BEIRUT",
                   help="بادئة القسيمة (الافتراضي: BEIRUT).")
    return p


def main() -> None:
    args = build_parser().parse_args()
    n = max(0, args.count)

    raws = list(generate_many(n))
    codes = [fmt(r, args.prefix) for r in raws]

    ts = datetime.now().strftime("%Y%m%d-%H%M")
    outdir: Path = args.output_dir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"vouchers-{ts}.txt"

    with path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(codes) + ("\n" if codes else ""))

    print(f"Generated {len(codes)} vouchers → {path}")
    if codes:
        print("First code:", codes[0])


if __name__ == "__main__":
    main()
