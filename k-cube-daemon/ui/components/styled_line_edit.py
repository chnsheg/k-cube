# k-cube-daemon/ui/components/styled_line_edit.py
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import QVariantAnimation
from PyQt6.QtGui import QColor
from ui.theme import Color, Font


class StyledLineEdit(QLineEdit):
    def __init__(self, placeholder_text="", is_password=False, parent=None):
        super().__init__(parent)

        self.setPlaceholderText(placeholder_text)
        if is_password:
            self.setEchoMode(QLineEdit.EchoMode.Password)

        self._border_color = Color.BORDER
        self._focus_color = Color.PRIMARY

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(200)
        self.animation.valueChanged.connect(self._on_border_color_changed)

        self._update_stylesheet()

    def _update_stylesheet(self):
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Color.CONTENT_BACKGROUND.name()};
                border: 1px solid {self._border_color.name()};
                border-radius: 8px;
                padding: 10px 12px;
                {Font.BODY}
            }}
        """)

    def _on_border_color_changed(self, color):
        self._border_color = color
        self._update_stylesheet()

    def focusInEvent(self, event):
        self.animation.setStartValue(self._border_color)
        self.animation.setEndValue(self._focus_color)
        self.animation.start()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.animation.setStartValue(self._border_color)
        self.animation.setEndValue(Color.BORDER)
        self.animation.start()
        super().focusOutEvent(event)
