from dataclasses import dataclass
WIDTH, HEIGHT = 304, 200
@dataclass(frozen=True)
class Rect:
    x:int; y:int; width:int; height:int
    @property
    def right(self): return self.x+self.width
    @property
    def bottom(self): return self.y+self.height
PRODUCT_REGION=Rect(10,8,284,48)
BARCODE_REGION=Rect(10,62,284,86)
HUMAN_REGION=Rect(10,151,284,22)
PRICE_REGION=Rect(10,176,284,18)
QUIET_ZONE_MODULES=10
