# k-cube-daemon/tray_icon.py

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPainter, QColor, QPixmap, QPolygon
from PyQt6.QtCore import Qt, QTimer, QPoint


class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status = "idle"
        self._animation_angle = 0

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)

        self.revert_timer = QTimer(self)
        self.revert_timer.setSingleShot(True)
        self.revert_timer.timeout.connect(lambda: self.set_status("idle"))

        self._create_menu()
        self.set_status("idle", "等待初始化...")  # 初始状态

    def _create_menu(self):
        menu = QMenu()
        self.action_open = menu.addAction("打开 K-Cube")
        self.action_quit = menu.addAction("退出")
        self.setContextMenu(menu)

    def _update_animation(self):
        self._animation_angle = (self._animation_angle + 10) % 360
        self._draw_icon()

    def set_status(self, status: str, message: str = ""):
        self.status = status
        self.setToolTip(
            f"K-Cube: {message}" if message else f"K-Cube: {status.capitalize()}")

        self.animation_timer.stop()
        if status == "syncing":
            self.animation_timer.start(50)

        if status == "success":
            self.revert_timer.start(2000)

        self._draw_icon()

    def _draw_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_width = 4
        pen = painter.pen()
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        if self.status == "idle":
            pen.setColor(QColor("#a0a0a0"))
            painter.setPen(pen)
            painter.drawRect(18, 18, 28, 28)
        elif self.status == "syncing":
            pen.setColor(QColor("#3498db"))
            painter.setPen(pen)
            painter.translate(32, 32)
            painter.rotate(self._animation_angle)
            painter.translate(-32, -32)
            painter.drawArc(18, 18, 28, 28, 0 * 16, 270 * 16)
        elif self.status == "success":
            pen.setColor(QColor("#2ecc71"))
            painter.setPen(pen)
            # --- 关键修复 ---
            # 创建一个 QPolygon 对象来包含所有的点
            points = QPolygon([
                QPoint(18, 32),
                QPoint(28, 42),
                QPoint(46, 24)
            ])
            painter.drawPolyline(points)
        elif self.status == "error":
            pen.setColor(QColor("#e74c3c"))
            painter.setPen(pen)
            painter.drawLine(24, 24, 40, 40)
            painter.drawLine(24, 40, 40, 24)

        painter.end()
        self.setIcon(QIcon(pixmap))
