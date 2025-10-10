from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer, Qt

class PSControls(QWidget):
    def __init__(self, on_start_p2, on_start_p4, on_switch_p2, on_switch_p4, on_stop):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0,0,0,0); v.setSpacing(6)

        self.status = QLabel("لا توجد جلسة بلايستيشن"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.status)

        r1 = QHBoxLayout()
        b1 = QPushButton("بدء ٢ لاعبين"); b2 = QPushButton("بدء ٤ لاعبين")
        r1.addWidget(b1); r1.addWidget(b2); v.addLayout(r1)

        r2 = QHBoxLayout()
        s1 = QPushButton("تحويل إلى ٢"); s2 = QPushButton("تحويل إلى ٤")
        r2.addWidget(s1); r2.addWidget(s2); v.addLayout(r2)

        stop = QPushButton("إيقاف الجلسة"); v.addWidget(stop)

        # wiring (guard callbacks)
        b1.clicked.connect(lambda: self._safe(on_start_p2))
        b2.clicked.connect(lambda: self._safe(on_start_p4))
        s1.clicked.connect(lambda: self._safe(on_switch_p2))
        s2.clicked.connect(lambda: self._safe(on_switch_p4))
        stop.clicked.connect(lambda: self._safe(on_stop))

        self._seconds = 0
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)

    def _safe(self, fn):
        try:
            fn()
        except Exception as e:
            # Bubble up to global excepthook
            raise

    def show_running(self, mode: str):
        self._seconds = 0
        if not self.timer.isActive():
            self.timer.start(1000)
        title = "٢ لاعبين" if mode == "P2" else "٤ لاعبين"
        self.status.setText(f"جلسة بلايستيشن ({title}) — 00:00:00")

    def show_stopped(self, msg="لا توجد جلسة بلايستيشن"):
        if self.timer.isActive():
            self.timer.stop()
        self._seconds = 0
        self.status.setText(msg)

    def _tick(self):
        self._seconds += 1
        h = self._seconds // 3600
        m = (self._seconds % 3600) // 60
        s = self._seconds % 60
        parts = self.status.text().split("—")
        prefix = parts[0].strip() if parts else "جلسة بلايستيشن"
        self.status.setText(f"{prefix} — {h:02d}:{m:02d}:{s:02d}")

    def closeEvent(self, e):
        # make sure timer is stopped on dispose
        if self.timer.isActive():
            self.timer.stop()
        super().closeEvent(e)
