from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QDialogButtonBox,
    QMessageBox,
    QSizePolicy,
    QHBoxLayout,
    QRadioButton,
    QButtonGroup,
)
from PyQt6.QtCore import Qt
from beirut_pos.core.auth import authenticate
from ..texts import texts

class DiscountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.get("orders.discount_dialog_title"))
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self.value = 0.0
        self.reason = ""
        self.discount_type = "amount"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(12)
        layout.addLayout(form)

        def _configure_line(widget):
            widget.setMinimumWidth(260)
            widget.setMinimumHeight(34)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet("padding: 6px 10px;")

        # Discount type radios
        type_row = QHBoxLayout()
        type_row.setSpacing(12)
        self.type_group = QButtonGroup(self)
        self.amount_radio = QRadioButton(texts.get("orders.discount_label_amount"))
        self.percent_radio = QRadioButton(texts.get("orders.discount_label_percent"))
        self.amount_radio.setChecked(True)
        self.type_group.addButton(self.amount_radio)
        self.type_group.addButton(self.percent_radio)
        type_row.addWidget(self.amount_radio)
        type_row.addWidget(self.percent_radio)
        layout.addLayout(type_row)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setDecimals(0)
        self.value_spin.setRange(0, 10_000_000)
        self.value_spin.setSingleStep(1.0)
        self.value_spin.setSuffix(f" {texts.get('orders.discount_amount_suffix')}")
        _configure_line(self.value_spin)
        form.addRow(texts.get("orders.discount_value_label"), self.value_spin)

        self.rea = QLineEdit()
        self.rea.setPlaceholderText(texts.get("orders.discount_reason_placeholder"))
        _configure_line(self.rea)
        form.addRow(texts.get("orders.discount_reason_label"), self.rea)

        self.u = QLineEdit()
        self.u.setPlaceholderText(texts.get("orders.discount_username_placeholder"))
        _configure_line(self.u)
        form.addRow(texts.get("orders.discount_username_label"), self.u)

        self.p = QLineEdit()
        self.p.setEchoMode(QLineEdit.EchoMode.Password)
        _configure_line(self.p)
        form.addRow(texts.get("orders.discount_password_label"), self.p)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok.setText(texts.get("orders.discount_apply_button"))
        cancel.setText(texts.get("orders.cancel_button"))
        layout.addWidget(buttons)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        self.amount_radio.toggled.connect(self._on_type_change)
        self.percent_radio.toggled.connect(self._on_type_change)
        self._on_type_change()

    def _apply(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if not user or user.role != "admin":
            QMessageBox.warning(
                self,
                texts.get("orders.discount_invalid_title"),
                texts.get("orders.discount_invalid_credentials"),
            )
            return
        self.value = float(self.value_spin.value())
        if self.discount_type == "percent" and self.value > 100:
            self.value = 100.0
        self.reason = self.rea.text().strip()
        self.accept()

    def _on_type_change(self):
        if self.percent_radio.isChecked():
            self.discount_type = "percent"
            self.value_spin.setDecimals(2)
            self.value_spin.setSingleStep(1.0)
            self.value_spin.setRange(0, 100)
            self.value_spin.setSuffix(f" {texts.get('orders.discount_percent_suffix')}")
        else:
            self.discount_type = "amount"
            self.value_spin.setDecimals(0)
            self.value_spin.setSingleStep(1.0)
            self.value_spin.setRange(0, 10_000_000)
            self.value_spin.setSuffix(f" {texts.get('orders.discount_amount_suffix')}")
