from beirut_pos.services import printer as printer_module


def test_render_lines_to_bitmap_returns_image():
    img = printer_module._render_lines_to_bitmap(["hello", "world"])
    assert img.size[0] == printer_module.PAPER_PX
    assert img.size[1] > 0


def test_stack_bitmaps_concatenates_height():
    img1 = printer_module._render_lines_to_bitmap(["one"])
    img2 = printer_module._render_lines_to_bitmap(["two"])
    stacked = printer_module._stack_bitmaps([img1, img2])
    assert stacked.size[1] >= img1.size[1] + img2.size[1]
