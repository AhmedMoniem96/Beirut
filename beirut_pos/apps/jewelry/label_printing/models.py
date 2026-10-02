from dataclasses import dataclass
@dataclass(frozen=True)
class LabelData:
    product_name: str
    barcode: str
    price: str
