# k-cube-daemon/ui/components/title_bar.py
from ui.theme import STYLESHEET
from k_cube.client import APIClient, APIError
from config_manager import config
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QMessageBox
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QSize
import qtawesome as qta

from ui.theme import Color, Font


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background-color: transparent;")
        # --- 核心修复：移除背景和圆角，使其透明 ---
        # self.setAutoFillBackground(True) # 移除
        # self.setStyleSheet(...) # 移除

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        self.icon_label = QLabel(self)
        icon = qta.icon('fa5s.cube', color=Color.TEXT_SECONDARY.name())
        self.icon_label.setPixmap(icon.pixmap(QSize(16, 16)))

        self.title_label = QLabel(self)
        self.title_label.setStyleSheet(
            f"color: {Color.TEXT_SECONDARY.name()}; {Font.BODY} font-weight: 500;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()

        btn_size = 30
        for name, slot, hover_color in [("fa5s.minus", self.parent.showMinimized, "#e5e5e5"),
                                        ("fa5s.clone",
                                         self._toggle_maximize, "#e5e5e5"),
                                        ("fa5s.times", self.parent.close, "#ff5f57")]:
            btn = QPushButton(qta.icon(name, color=Color.TEXT_SECONDARY.name(
            ), color_active=Color.TEXT_PRIMARY.name()), "", self)
            btn.clicked.connect(slot)
            btn.setFixedSize(btn_size, btn_size)
            btn.setStyleSheet(f"""
                QPushButton {{ border: none; background-color: transparent; border-radius: 5px; }}
                QPushButton:hover {{ background-color: {hover_color}; }}
            """)
            layout.addWidget(btn)

        self.setFixedHeight(40)
        self.start_pos = None

    def _toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    # ... (mouse events are unchanged) ...
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            delta = event.globalPosition().toPoint() - self.start_pos
            self.parent.move(self.parent.pos() + delta)
            self.start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.start_pos = None

    def setTitle(self, title):
        self.title_label.setText(title)
