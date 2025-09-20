# k-cube-daemon/ui/components/toast.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsDropShadowEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtProperty
from PyQt6.QtGui import QPainter, QColor

from ui.theme import Color, Font
import qtawesome as qta


class Toast(QWidget):
    def __init__(self):
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QHBoxLayout(self)
        self.icon_label = QLabel(self)
        self.text_label = QLabel(self)

        self.text_label.setStyleSheet(
            f"color: {Color.TEXT_PRIMARY.name()}; {Font.BODY} font-weight: 500;")

        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.text_label)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        # 动画目标直接使用 QWidget 的原生 "windowOpacity" 属性
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.close_toast)

        self.border_color = Color.CONTENT_BACKGROUND

    # --- 核心修复：删除 get_opacity, set_opacity, 和 windowOpacity = pyqtProperty(...) ---

    def paintEvent(self, event):
        """自定义绘制事件，用于绘制带圆角的背景和边框。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(Color.CONTENT_BACKGROUND)
        pen = painter.pen()
        pen.setWidth(1)
        pen.setColor(self.border_color)
        painter.setPen(pen)

        rect = self.rect()
        painter.drawRoundedRect(
            rect.x(), rect.y(), rect.width() - 1, rect.height() - 1, 8, 8)

    def show_toast(self, message: str, status: str = "success"):
        self.animation.stop()
        self.hide_timer.stop()

        self.text_label.setText(message)

        if status == "success":
            self.border_color = Color.GREEN
            icon = qta.icon('fa5s.check-circle', color=Color.GREEN)
        elif status == "error":
            self.border_color = Color.RED
            icon = qta.icon('fa5s.times-circle', color=Color.RED)
        else:  # info
            self.border_color = Color.PRIMARY
            icon = qta.icon('fa5s.info-circle', color=Color.PRIMARY)

        self.icon_label.setPixmap(icon.pixmap(18, 18))
        self.update()

        self.adjustSize()
        self.setContentsMargins(15, 12, 18, 12)
        self.layout.setSpacing(10)
        self.adjustSize()

        screen_geometry = QApplication.primaryScreen().availableGeometry()

        pos_x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        pos_y = screen_geometry.y() + 30
        self.move(pos_x, pos_y)

        # 淡入动画
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)

        self.show()
        self.animation.start()

        self.hide_timer.start(2500)

    def close_toast(self):
        self.animation.stop()
        self.animation.setStartValue(self.windowOpacity())
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.close)
        self.animation.start()
