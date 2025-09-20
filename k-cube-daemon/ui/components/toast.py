# k-cube-daemon/ui/components/toast.py
# (替换完整内容)
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPainter, QColor
from ui.theme import Color, Font
import qtawesome as qta


class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QHBoxLayout(self)
        self.icon_label = QLabel(self)
        self.text_label = QLabel(self)

        # --- 核心修改：使用主题颜色 ---
        self.text_label.setStyleSheet(
            f"color: {Color.TEXT_PRIMARY.name()}; {Font.BODY} font-weight: 500;")

        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.text_label)

        # --- 核心修改：添加阴影效果 ---
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setDuration(300)

    def paintEvent(self, event):
        """自定义绘制事件，用于绘制带圆角的背景和边框。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 使用主题颜色
        painter.setBrush(Color.CONTENT_BACKGROUND)
        pen = painter.pen()
        pen.setWidth(1)
        pen.setColor(self.border_color)
        painter.setPen(pen)

        rect = self.rect()
        painter.drawRoundedRect(
            rect.x(), rect.y(), rect.width()-1, rect.height()-1, 8, 8)

    def show_toast(self, message: str, status: str = "success"):
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
        self.update()  # 触发 paintEvent

        self.adjustSize()
        self.setContentsMargins(15, 12, 18, 12)
        self.layout.setSpacing(10)
        self.adjustSize()

        parent_rect = self.parent().geometry()
        parent_pos = self.parent().mapToGlobal(self.parent().rect().topLeft())

        start_y = parent_pos.y()
        end_y = parent_pos.y() + 20

        start_pos = QRect(parent_pos.x() + (parent_rect.width() - self.width()) // 2,
                          start_y - self.height(),
                          self.width(), self.height())
        end_pos = QRect(start_pos.x(), end_y, self.width(), self.height())

        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.start()

        self.show()
        QTimer.singleShot(2500, self.close_toast)

    def close_toast(self):
        start_pos = self.geometry()
        end_pos = QRect(start_pos.x(), start_pos.y(
        ) - start_pos.height() - 20, start_pos.width(), start_pos.height())

        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.finished.connect(self.close)
        self.animation.start()
