# k-cube-daemon/ui/components/vault_list_item.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFontMetrics, QPainter
from pathlib import Path
from ui.theme import Color, Font
import qtawesome as qta
from .toast import Toast


class VaultListItem(QWidget):
    sync_requested = pyqtSignal()
    delete_from_cloud_requested = pyqtSignal()

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.is_selected = False

        # 让 Widget 自己可绘制背景和边框
        self.setAutoFillBackground(True)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 0, 10, 0)
        main_layout.setSpacing(15)

        self.more_button = QPushButton(
            qta.icon('fa5s.ellipsis-h', color=Color.TEXT_SECONDARY), "")
        self.more_button.setFixedSize(32, 32)
        # ... (设置样式)
        self.more_button.clicked.connect(self.show_menu)

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
        # 根据父窗口宽度动态计算截断宽度会更理想，这里用一个较大的固定值
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
        main_layout.addWidget(self.more_button)  # 添加到布局

        # 确保所有内容在更大的行高内垂直居中
        main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.set_status("idle")

    def show_menu(self):
        menu = QMenu(self)
        # remove_local_action = menu.addAction("从列表移除")
        delete_cloud_action = menu.addAction("从云端永久删除...")

        action = menu.exec(self.mapToGlobal(
            QPoint(self.more_button.x(), self.more_button.y() + self.more_button.height())))

        if action == delete_cloud_action:
            self.delete_from_cloud_requested.emit()

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
        """更新列表项的状态指示灯和同步按钮。"""
        is_syncing_process = status in [
            "syncing", "upload", "download", "bidirectional"]

        color_map = {
            "idle": Color.TEXT_SECONDARY.name(),
            "success": Color.GREEN.name(),
            "error": Color.RED.name()
        }
        light_color = Color.PRIMARY.name() if is_syncing_process else color_map.get(
            status, Color.TEXT_SECONDARY.name())

        self.status_light.setPixmap(
            qta.icon('fa5s.circle', color=light_color).pixmap(12, 12))
        self.sync_button.setEnabled(not is_syncing_process)

        # 这个组件不再负责显示 Toast，将其移到主应用层面
        # if status in ["success", "error"] and message:
        #     parent_window = self.window()
        #     if parent_window and parent_window.isVisible():
        #         toast = Toast(parent_window)
        #         toast.show_toast(message, status=status)
