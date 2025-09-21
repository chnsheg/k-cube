from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPalette, QFont, QLinearGradient, QPen

from ui.theme import Color, Font as ThemeFont
import qtawesome as qta


class Toast(QWidget):
    def __init__(self):
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(18, 14, 20, 14)  # 调整内边距
        self.layout.setSpacing(12)

        self.icon_label = QLabel(self)
        self.text_label = QLabel(self)

        # 直接设置字体和颜色
        font = QFont()
        font.fromString(ThemeFont.BODY.split(';')[0])
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.Medium)
        self.text_label.setFont(font)

        palette = self.text_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, Color.TEXT_PRIMARY)
        self.text_label.setPalette(palette)

        self.layout.addWidget(self.icon_label)
        self.layout.addWidget(self.text_label)

        # 我们将手动绘制阴影，所以移除 QGraphicsDropShadowEffect

        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setDuration(300)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.close_toast)

        self.status_color = Color.PRIMARY

    def paintEvent(self, event):
        """
        终极绘制方案：使用双层绘制实现辉光和毛玻璃效果。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # 1. 绘制外层辉光/阴影
        shadow_margin = 10
        shadow_rect = QRect(
            rect.x() + shadow_margin, rect.y() + shadow_margin,
            rect.width() - 2 * shadow_margin, rect.height() - 2 * shadow_margin
        )

        # 创建一个从状态色到完全透明的路径渐变来模拟辉光
        gradient = QLinearGradient(
            0, 0, shadow_rect.width(), shadow_rect.height())
        glow_color = QColor(self.status_color)
        glow_color.setAlphaF(0.2)  # 辉光的不透明度
        gradient.setColorAt(0, glow_color)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(shadow_rect, 12, 12)

        # 2. 绘制内层内容背景 (半透明毛玻璃效果)
        content_margin = shadow_margin + 2
        content_rect = QRect(
            rect.x() + content_margin, rect.y() + content_margin,
            rect.width() - 2 * content_margin, rect.height() - 2 * content_margin
        )

        bg_color = QColor(Color.CONTENT_BACKGROUND)
        bg_color.setAlphaF(0.9)  # 90% 不透明的白色

        painter.setBrush(bg_color)
        painter.setPen(QPen(Color.BORDER, 1))
        painter.drawRoundedRect(content_rect, 10, 10)

    def show_toast(self, message: str, status: str = "success"):
        self.animation.stop()
        self.hide_timer.stop()

        self.text_label.setText(message)

        is_syncing_process = status in [
            "upload", "download", "bidirectional", "syncing"]

        if status == "success":
            self.status_color = Color.GREEN
            icon = qta.icon('fa5s.check-circle', color=Color.GREEN)
        elif status == "error":
            self.status_color = Color.RED
            icon = qta.icon('fa5s.times-circle', color=Color.RED)
        else:  # info and syncing
            self.status_color = Color.PRIMARY
            icon_name = {
                "upload": "fa5s.arrow-up", "download": "fa5s.arrow-down",
                "bidirectional": "fa5s.exchange-alt", "syncing": "fa5s.sync-alt"
            }.get(status, "fa5s.info-circle")
            anim = qta.Spin(self.icon_label) if is_syncing_process else None
            icon = qta.icon(icon_name, color=Color.PRIMARY, animation=anim)

        self.icon_label.setPixmap(icon.pixmap(20, 20))

        self.adjustSize()
        # 由于绘制区域变大，我们需要重新计算整体尺寸
        final_width = self.layout.sizeHint().width() + 40
        final_height = self.layout.sizeHint().height() + 30
        self.setFixedSize(final_width, final_height)

        # update() 触发 paintEvent
        self.update()

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        pos_x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        pos_y = screen_geometry.y() + 30
        start_pos = QPoint(pos_x, screen_geometry.y() - self.height())
        end_pos = QPoint(pos_x, pos_y)

        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)

        self.move(start_pos)
        self.show()

        self.animation.start()

        if not is_syncing_process:
            self.hide_timer.start(2500)

    def close_toast(self):
        self.animation.stop()
        start_pos = self.pos()
        end_pos = QPoint(start_pos.x(), -self.height() - 20)
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.finished.connect(self.close)
        self.animation.start()
