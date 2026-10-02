"""Application boundary joining the pure label renderer to Windows transport."""
from .models import LabelData
from .renderer import render_label
from .transport import print_image, Submission

def print_label(label_data: LabelData, printer_name: str, copies: int = 1) -> Submission:
    """Render *label_data* once and submit that exact image to *printer_name*.

    Rendering and transport exceptions intentionally propagate unchanged, preserving
    their useful type and message. A returned Submission means only Windows accepted
    the job; it does not confirm physical printing.
    """
    if not isinstance(label_data, LabelData):
        raise TypeError("label_data must be a LabelData instance")
    image = render_label(label_data)
    return print_image(image, printer_name, copies)
