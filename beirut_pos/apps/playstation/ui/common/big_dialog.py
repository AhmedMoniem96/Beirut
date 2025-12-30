# beirut_pos/ui/common/big_dialog.py
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt

# absolute import to avoid relative-depth issues
from beirut_pos.core.db import setting_get, setting_set  # reuse settings table to persist geometry

class BigDialog(QDialog):
    """
    Standard large dialog: RTL, big size, resizable with size grip.
    Remembers its geometry under a settings key (optional).
    """
    def __init__(self, title: str, remember_key: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumSize(900, 600)  # nice big default
        self.setSizeGripEnabled(True)
        self._remember_key = remember_key

        # Restore geometry if available
        if remember_key:
            g = setting_get(f"geom_{remember_key}", "")
            if g:
                parts = g.split(",")
                if len(parts) == 4:
                    try:
                        x, y, w, h = [int(v) for v in parts]
                        self.setGeometry(x, y, w, h)
                    except Exception:
                        pass

    def accept(self):
        self._save_geometry()
        return super().accept()

    def reject(self):
        self._save_geometry()
        return super().reject()

    def _save_geometry(self):
        if not self._remember_key:
            return
        g = self.geometry()
        setting_set(f"geom_{self._remember_key}", f"{g.x()},{g.y()},{g.width()},{g.height()}")
