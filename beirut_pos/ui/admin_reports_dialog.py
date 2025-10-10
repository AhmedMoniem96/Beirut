from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton
from PyQt6.QtCore import Qt
from ..core.db import get_conn

class AdminReportsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تقارير تغييرات الأسعار")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        v = QVBoxLayout(self)
        lbl = QLabel("سجل تغييرات الأسعار (غير قابل للحذف):")
        v.addWidget(lbl)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["الوقت", "المستخدم", "العنصر", "السعر القديم", "السعر الجديد", "تفاصيل"])
        v.addWidget(self.table)

        refresh = QPushButton("تحديث"); refresh.clicked.connect(self._load)
        v.addWidget(refresh)

        self._load()

    def _load(self):
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""SELECT ts, username, entity_name, old_value, new_value, extra
                       FROM audit_log
                       WHERE action='price_change'
                       ORDER BY id DESC""")
        rows = cur.fetchall(); conn.close()

        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount(); self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r["ts"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["username"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["entity_name"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(r["old_value"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(r["new_value"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(r["extra"] or ""))
