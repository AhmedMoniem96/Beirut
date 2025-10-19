# # beirut_pos/ui/zreport_dialog.py
# from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit, QTextEdit, QMessageBox
# from PyQt6.QtCore import QDate, Qt
# from .common.big_dialog import BigDialog
# from ..services.reports import z_report, format_z_text
# from ..core.db import setting_get
# from ..services.printer import printer
# from datetime import datetime
# from pathlib import Path
#
# class ZReportDialog(BigDialog):
#     def __init__(self, parent=None):
#         super().__init__("تقرير يومي (Z-Report)", remember_key="zreport", parent=parent)
#
#         v = QVBoxLayout(self)
#
#         row = QHBoxLayout()
#         row.addWidget(QLabel("اختر التاريخ:"))
#         self.date = QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True)
#         row.addWidget(self.date, 1)
#         self.btn_run = QPushButton("تجهيز"); self.btn_run.setDefault(True)
#         self.btn_run.clicked.connect(self._run)
#         row.addWidget(self.btn_run)
#         v.addLayout(row)
#
#         self.text = QTextEdit(); self.text.setReadOnly(True)
#         v.addWidget(self.text, 1)
#
#         row2 = QHBoxLayout()
#         btn_print = QPushButton("طباعة")
#         btn_save  = QPushButton("حفظ ملف TXT")
#         btn_print.clicked.connect(self._print)
#         btn_save.clicked.connect(self._save)
#         row2.addWidget(btn_print); row2.addWidget(btn_save)
#         v.addLayout(row2)
#
#         # auto-run for today
#         self._run()
#
#     def _run(self):
#         iso = self.date.date().toString("yyyy-MM-dd")
#         data = z_report(iso)
#         company = setting_get("company_name","Beirut Coffee")
#         currency = setting_get("currency","EGP")
#         txt = format_z_text(data, company=company, currency=currency)
#         self.text.setPlainText(txt)
#
#     def _print(self):
#         txt = self.text.toPlainText().strip()
#         if not txt:
#             QMessageBox.information(self,"طباعة","لا يوجد تقرير للطباعة."); return
#         try:
#             # Use printer fallback to save readable Z-report file
#             printer._file_fallback_write("receipts", f"Z-{datetime.now():%Y%m%d}.txt", txt)
#             QMessageBox.information(self,"طباعة","تم إرسال التقرير/حفظه.")
#         except Exception:
#             Path("receipts").mkdir(exist_ok=True)
#             Path("receipts")/f"Z-{datetime.now():%Y%m%d}.txt".write_text(txt, encoding="utf-8")
#             QMessageBox.information(self,"طباعة","تم حفظ التقرير كملف.")
#
#     def _save(self):
#         txt = self.text.toPlainText().strip()
#         if not txt:
#             QMessageBox.information(self,"حفظ","لا يوجد تقرير للحفظ."); return
#         Path("receipts").mkdir(exist_ok=True)
#         p = Path("receipts")/f"Z-{datetime.now():%Y%m%d-%H%M%S}.txt"
#         p.write_text(txt, encoding="utf-8")
#         QMessageBox.information(self,"حفظ",f"تم الحفظ: {p}")
