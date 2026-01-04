"""Guided workflow to inspect backups and rerun integrity checks."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from beirut_pos.core import db as db_module
from ..services.backup import BackupMetadata, list_backup_metadata, restore_backup
from .common.big_dialog import BigDialog


class RecoveryCenterDialog(BigDialog):
    """Provides a single place to react to integrity warnings."""

    def __init__(self, issue_details: str = "", parent=None):
        super().__init__("مركز الاستعادة", remember_key="recovery_center", parent=parent)
        self._issue_text = issue_details.strip() or "تم اكتشاف مشكلة في قاعدة البيانات."
        self._restored_path: Path | None = None
        self._status_label = QLabel(self._issue_text)
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName("RecoveryIssue")

        hint = QLabel(
            "يمكنك إعادة فحص قاعدة البيانات أو استرجاع نسخة احتياطية حديثة."
        )
        hint.setObjectName("RecoveryHint")

        self.backups = QTreeWidget()
        self.backups.setColumnCount(3)
        self.backups.setHeaderLabels(["تاريخ النسخة", "الحجم", "المسار"])
        self.backups.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups.setRootIsDecorated(False)
        self.backups.setAlternatingRowColors(True)
        self.backups.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.backups.itemSelectionChanged.connect(self._sync_actions)

        self.btn_restore = QPushButton("استرجاع النسخة المحددة")
        self.btn_restore.setEnabled(False)
        self.btn_restore.clicked.connect(self._restore_selected)

        self.btn_check = QPushButton("إعادة فحص السلامة")
        self.btn_check.clicked.connect(self._rerun_integrity_check)

        self.btn_refresh = QPushButton("تحديث القائمة")
        self.btn_refresh.clicked.connect(self._load_backups)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        # Provide an explicit continue/accept button even though dialog is mostly informational.
        continue_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if continue_btn:
            continue_btn.setText("متابعة")

        actions_row = QHBoxLayout()
        actions_row.addWidget(self.btn_restore)
        actions_row.addWidget(self.btn_check)
        actions_row.addWidget(self.btn_refresh)
        actions_row.addStretch(1)
        actions_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status_label)
        layout.addWidget(hint)
        layout.addWidget(self.backups, 1)
        layout.addLayout(actions_row)

        self._load_backups()

    # ------------------------------------------------------------------ properties
    @property
    def restored_path(self) -> Path | None:
        return self._restored_path

    # ------------------------------------------------------------------ helpers
    def _sync_actions(self) -> None:
        has_selection = bool(self.backups.selectedItems())
        self.btn_restore.setEnabled(has_selection)

    def _load_backups(self) -> None:
        self.backups.setUpdatesEnabled(False)
        self.backups.clear()
        rows: Iterable[BackupMetadata] = list_backup_metadata(limit=12)
        for meta in rows:
            item = QTreeWidgetItem()
            item.setText(0, meta.created_at.strftime("%Y-%m-%d %I:%M %p"))
            item.setText(1, meta.human_size)
            item.setText(2, str(meta.path))
            item.setData(0, Qt.ItemDataRole.UserRole, str(meta.path))
            self.backups.addTopLevelItem(item)
        for col in range(3):
            self.backups.resizeColumnToContents(col)
        self.backups.setUpdatesEnabled(True)
        self._sync_actions()

    def _current_selection(self) -> Path | None:
        items = self.backups.selectedItems()
        if not items:
            return None
        raw = items[0].data(0, Qt.ItemDataRole.UserRole)
        return Path(str(raw)) if raw else None

    def _rerun_integrity_check(self) -> None:
        ok, details = db_module.maybe_run_integrity_check(force=True)
        if ok:
            QMessageBox.information(self, "فحص السلامة", "النتيجة: قاعدة البيانات سليمة.")
            self._status_label.setText("تم التحقق من سلامة قاعدة البيانات.")
        else:
            QMessageBox.warning(self, "فحص السلامة", details or "تم العثور على أخطاء.")
            if details:
                self._status_label.setText(details)

    def _restore_selected(self) -> None:
        path = self._current_selection()
        if path is None:
            return
        confirm = QMessageBox.question(
            self,
            "تأكيد الاسترجاع",
            "سيتم استبدال قاعدة البيانات الحالية بهذه النسخة. هل أنت متأكد؟",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            restore_backup(path)
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "فشل الاسترجاع", f"تعذر استرجاع النسخة:\n{exc}")
            return
        self._restored_path = path
        QMessageBox.information(
            self,
            "تم الاسترجاع",
            "تمت عملية الاسترجاع بنجاح. سيتم إغلاق التطبيق لإعادة التشغيل.",
        )
        self.accept()
