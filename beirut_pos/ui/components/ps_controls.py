from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer, Qt
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any


class PSControls(QWidget):
    """
    UI widget for PlayStation session control.

    Use .update_session(session) to show an existing running session.
    session is either None (no session), or a dict with keys:
      - "mode": "P2" or "P4"
      - "started_at": ISO string or datetime (UTC or naive assumed UTC)
      - "total_seconds": int (accumulated persisted seconds)
    """

    def __init__(self, on_start_p2: Callable, on_start_p4: Callable, on_switch_p2: Callable, on_switch_p4: Callable, on_stop: Callable):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        self.status = QLabel("لا توجد جلسة بلايستيشن")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.status)

        r1 = QHBoxLayout()
        b1 = QPushButton("بدء ٢ لاعبين")
        b2 = QPushButton("بدء ٤ لاعبين")
        r1.addWidget(b1)
        r1.addWidget(b2)
        v.addLayout(r1)

        r2 = QHBoxLayout()
        s1 = QPushButton("تحويل إلى ٢")
        s2 = QPushButton("تحويل إلى ٤")
        r2.addWidget(s1)
        r2.addWidget(s2)
        v.addLayout(r2)

        stop = QPushButton("إيقاف الجلسة")
        v.addWidget(stop)

        # wiring (guard callbacks)
        b1.clicked.connect(lambda: self._safe(on_start_p2))
        b2.clicked.connect(lambda: self._safe(on_start_p4))
        s1.clicked.connect(lambda: self._safe(on_switch_p2))
        s2.clicked.connect(lambda: self._safe(on_switch_p4))
        stop.clicked.connect(lambda: self._safe(on_stop))

        # timer & state
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

        # session data used for authoritative elapsed calculation:
        self._mode: Optional[str] = None
        self._started_at: Optional[datetime] = None   # tz-aware UTC
        self._base_total_seconds: int = 0             # persisted/accumulated seconds before started_at

    def _safe(self, fn):
        try:
            fn()
        except Exception:
            # bubble up to the global excepthook so the app can handle/log it
            raise

    # ----- helpers for parsing started_at safely -----
    @staticmethod
    def _ensure_dt(value) -> Optional[datetime]:
        """Accept datetime or ISO string. Return tz-aware UTC datetime or None."""
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                raw_value = str(value)
                if raw_value.endswith("Z"):
                    raw_value = raw_value[:-1] + "+00:00"
                dt = datetime.fromisoformat(raw_value)
            except Exception:
                # last resort: try naive parse fallback (very permissive)
                try:
                    dt = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _format_hms(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ----- public API -----
    from datetime import datetime, timezone

    class PSControls(QWidget):
        # ... existing __init__ and methods ...

        def update_session(self, sess: dict | None) -> None:
            """
            sess: None => stop and clear
            sess: dict with keys 'mode', 'started_at' (ISO string or datetime), 'total_seconds' (int)
            """
            if not sess:
                # stop timer + show stopped message
                self.show_stopped("لا توجد جلسة بلايستيشن")
                return

            mode = sess.get("mode", "P2")
            started = sess.get("started_at")
            total_seconds = int(sess.get("total_seconds", 0) or 0)

            # normalize started to datetime (tz-aware if possible)
            if isinstance(started, str):
                try:
                    raw_value = started
                    if raw_value.endswith("Z"):
                        raw_value = raw_value[:-1] + "+00:00"
                    started_dt = datetime.fromisoformat(raw_value)
                except Exception:
                    started_dt = datetime.now(timezone.utc)
            elif isinstance(started, datetime):
                started_dt = started
            else:
                started_dt = datetime.now(timezone.utc)

            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            elapsed_since_started = max(0, int((now - started_dt).total_seconds()))
            self._seconds = total_seconds + elapsed_since_started

            # Show running UI and ensure timer is active
            title = "٢ لاعبين" if mode == "P2" else "٤ لاعبين"
            if not self.timer.isActive():
                self.timer.start(1000)
            self.status.setText(f"جلسة بلايستيشن ({title}) — {self._fmt_seconds(self._seconds)}")

        def _fmt_seconds(self, seconds: int) -> str:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        def _tick(self):
            self._seconds += 1
            parts = self.status.text().split("—")
            prefix = parts[0].strip() if parts else "جلسة بلايستيشن"
            self.status.setText(f"{prefix} — {self._fmt_seconds(self._seconds)}")

    def _stop_and_clear(self, msg: str = "لا توجد جلسة بلايستيشن") -> None:
        if self.timer.isActive():
            self.timer.stop()
        self._mode = None
        self._started_at = None
        self._base_total_seconds = 0
        self.status.setText(msg)

    # ----- internal tick -----
    def _compute_elapsed_seconds(self) -> int:
        """Compute base_total_seconds + elapsed since started_at (if any)."""
        base = int(self._base_total_seconds or 0)
        if not self._started_at:
            return base
        now = datetime.now(timezone.utc)
        elapsed = int((now - self._started_at).total_seconds())
        if elapsed < 0:
            elapsed = 0
        return base + elapsed

    def _tick(self) -> None:
        if not self._mode:
            # nothing to do: stop timer to save CPU
            if self.timer.isActive():
                self.timer.stop()
            return
        seconds = self._compute_elapsed_seconds()
        title = "٢ لاعبين" if self._mode == "P2" else "٤ لاعبين"
        self.status.setText(f"جلسة بلايستيشن ({title}) — {self._format_hms(seconds)}")

    def show_running(self, mode: str):
        """Legacy: start local timer from zero (keeps backward compatibility)."""
        self._mode = mode
        self._started_at = datetime.now(timezone.utc)
        self._base_total_seconds = 0
        if not self.timer.isActive():
            self.timer.start()
        title = "٢ لاعبين" if mode == "P2" else "٤ لاعبين"
        self.status.setText(f"جلسة بلايستيشن ({title}) — 00:00:00")

    def show_stopped(self, msg: str = "لا توجد جلسة بلايستيشن"):
        self._stop_and_clear(msg)

    def closeEvent(self, e):
        # make sure timer is stopped on dispose
        if self.timer.isActive():
            self.timer.stop()
        super().closeEvent(e)
