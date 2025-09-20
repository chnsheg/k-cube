# k-cube-daemon/ui/components/vault_list_item.py
# (替换完整内容)
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QPainter
from pathlib import Path
from ui.theme import Color, Font
import qtawesome as qta
from .toast import Toast


class VaultListItem(QWidget):
    sync_requested = pyqtSignal()

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_selected = False  # 新增选中状态

        # --- 核心修改：让 Widget 自己可绘制 ---
        self.setAutoFillBackground(True)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 0, 10, 0)
        main_layout.setSpacing(15)

        # --- 状态灯 ---
        self.status_light = QLabel()
        self.status_light.setFixedSize(12, 12)

        # --- 文字区域 ---
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        fm = QFontMetrics(self.font())
        self.setToolTip(path)
        elided_path = fm.elidedText(path, Qt.TextElideMode.ElideMiddle, 300)

        self.name_label = QLabel(Path(path).name)
        self.name_label.setStyleSheet(Font.SUBTITLE)

        self.path_label = QLabel(elided_path)
        self.path_label.setStyleSheet(Font.CAPTION)

        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.path_label)

        # --- 同步按钮 ---
        self.sync_button = QPushButton(qta.icon(
            'fa5s.sync-alt', color=Color.TEXT_SECONDARY, color_active=Color.PRIMARY), "")
        self.sync_button.setFixedSize(32, 32)
        self.sync_button.setStyleSheet(
            "QPushButton { border: none; background-color: transparent; border-radius: 8px; } QPushButton:hover { background-color: #e5e5e5; }")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.clicked.connect(self.sync_requested)
        self.anim = None

        # --- 布局 ---
        main_layout.addWidget(self.status_light)
        main_layout.addWidget(text_widget, 1)  # 拉伸因子为1
        main_layout.addWidget(self.sync_button)

        # --- 核心修复：确保所有内容在更大的行高内垂直居中 ---
        main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.set_status("idle")

    def paintEvent(self, event):
        """自定义绘制事件，用于绘制卡片的背景、边框和选中状态。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 根据是否选中，决定背景和边框颜色
        if self.is_selected:
            bg_color = Color.SECONDARY
            border_color = Color.PRIMARY
        else:
            bg_color = Color.CONTENT_BACKGROUND
            border_color = Color.BORDER

        painter.setPen(border_color)
        painter.setBrush(bg_color)

        rect = self.rect()
        painter.drawRoundedRect(
            rect.x(), rect.y(), rect.width() - 1, rect.height() - 1, 8, 8)

    def set_selected(self, selected: bool):
        """外部调用的方法，用于更新选中状态并重绘。"""
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()  # 触发 paintEvent

    def set_status(self, status: str, message: str = ""):
        # ... (此方法保持不变) ...
        color_map = {
            "idle": Color.TEXT_SECONDARY.name(),
            "syncing": Color.PRIMARY.name(),
            "success": Color.GREEN.name(),
            "error": Color.RED.name()
        }
        color = color_map.get(status, Color.TEXT_SECONDARY.name())

        is_syncing = (status == "syncing")

        if is_syncing:
            if not self.anim:
                self.anim = qta.Spin(self.sync_button)
            self.sync_button.setIcon(
                qta.icon('fa5s.sync-alt', color=Color.PRIMARY, animation=self.anim))
        else:
            self.sync_button.setIcon(qta.icon(
                'fa5s.sync-alt', color=Color.TEXT_SECONDARY, color_active=Color.PRIMARY))

        self.sync_button.setEnabled(not is_syncing)

        self.status_light.setPixmap(
            qta.icon('fa5s.circle', color=color).pixmap(12, 12))

        if status in ["success", "error"] and message:
            parent_window = self.window()
            if parent_window and parent_window.isVisible():
                toast = Toast(parent_window)
                toast.show_toast(message, status=status)
